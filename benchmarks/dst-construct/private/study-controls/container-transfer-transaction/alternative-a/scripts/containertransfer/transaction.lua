-- Container transfer transaction, engine independent.
--
-- Design: every accepted request becomes one journal entry. An entry carries
-- the frozen request, both container snapshots, the chosen source items, the
-- list of phases it went through and an "undo stack" naming the containers
-- that must be restored if the entry is abandoned. The stack is pushed right
-- before the matching destructive adapter call, so unwinding it from the top
-- always restores the destination before the source.
--
-- The object returned by Transaction.new is built from closures; the journal
-- is private and can only leave through save(), which deep-copies plain data.

local Transaction = {}

local PHASE_ORDER = { "prepared", "source_removed", "destination_added", "committed" }
local TERMINAL = { committed = true, aborted = true, refused = true }
local ID_LIMIT = 128

----------------------------------------------------------------------------
-- plain data helpers
----------------------------------------------------------------------------

local function plain_copy(value, depth)
    depth = depth or 0
    local kind = type(value)
    if kind == "table" then
        if depth > 8 then
            return nil
        end
        local out = {}
        for key, inner in pairs(value) do
            local key_kind = type(key)
            if key_kind == "string" or key_kind == "number" then
                out[key] = plain_copy(inner, depth + 1)
            end
        end
        return out
    end
    if kind == "string" or kind == "number" or kind == "boolean" then
        return value
    end
    return nil
end

local function valid_id(text)
    if type(text) ~= "string" then
        return false
    end
    local length = #text
    if length == 0 or length > ID_LIMIT then
        return false
    end
    return not string.find(text, "[%c]")
end

local function whole_positive(number)
    if type(number) ~= "number" or number ~= number then
        return false
    end
    if number < 1 or number == math.huge then
        return false
    end
    return number % 1 == 0
end

local REQUEST_FIELDS = { "request_id", "source_id", "destination_id", "prefab" }

-- Returns a frozen copy of the request, or nil plus the offending field.
local function freeze_request(request)
    if type(request) ~= "table" then
        return nil, "request"
    end
    local frozen = {}
    for index = 1, #REQUEST_FIELDS do
        local field = REQUEST_FIELDS[index]
        if not valid_id(request[field]) then
            return nil, field
        end
        frozen[field] = request[field]
    end
    if not whole_positive(request.count) then
        return nil, "count"
    end
    frozen.count = request.count
    if frozen.source_id == frozen.destination_id then
        return nil, "destination_id"
    end
    return frozen
end

-- Keeps only well-formed snapshot rows and orders them by slot.
local function normalise_snapshot(rows)
    local out = {}
    if type(rows) == "table" then
        for _, row in pairs(rows) do
            if type(row) == "table" and type(row.slot) == "number" and type(row.prefab) == "string"
                and type(row.count) == "number" and row.count > 0 then
                out[#out + 1] = {
                    slot = row.slot,
                    prefab = row.prefab,
                    count = row.count,
                    perish_percent = type(row.perish_percent) == "number" and row.perish_percent or nil,
                    finite_uses_percent = type(row.finite_uses_percent) == "number"
                        and row.finite_uses_percent or nil,
                }
            end
        end
    end
    table.sort(out, function(a, b)
        if a.slot ~= b.slot then
            return a.slot < b.slot
        end
        return a.prefab < b.prefab
    end)
    return out
end

-- Walks the ordered snapshot and takes items until the wanted amount is met.
-- Returns the picked rows and the amount that could not be satisfied.
local function pick_from(snapshot, prefab, wanted)
    local picked, missing = {}, wanted
    for index = 1, #snapshot do
        local row = snapshot[index]
        if missing > 0 and row.prefab == prefab then
            local part = row.count < missing and row.count or missing
            picked[#picked + 1] = {
                slot = row.slot,
                prefab = row.prefab,
                count = part,
                perish_percent = row.perish_percent,
                finite_uses_percent = row.finite_uses_percent,
            }
            missing = missing - part
        end
    end
    return picked, missing
end

----------------------------------------------------------------------------
-- journal entries
----------------------------------------------------------------------------

local function current_phase(entry)
    return entry.phases[#entry.phases]
end

local function describe(entry)
    local phase = current_phase(entry)
    local view = {
        ok = phase == "committed",
        status = phase,
        request_id = entry.request.request_id,
        reason = entry.reason,
        recoverable = not TERMINAL[phase],
    }
    if phase == "committed" then
        view.items = plain_copy(entry.selected)
    end
    return view
end

local function revive_entry(raw)
    if type(raw) ~= "table" or type(raw.phases) ~= "table" or #raw.phases == 0 then
        return nil
    end
    local request = freeze_request(raw.request)
    if request == nil then
        return nil
    end
    local entry = {
        request = request,
        phases = {},
        reason = type(raw.reason) == "string" and raw.reason or nil,
        source_snapshot = normalise_snapshot(raw.source_snapshot),
        destination_snapshot = normalise_snapshot(raw.destination_snapshot),
        selected = normalise_snapshot(raw.selected),
        undo = {},
    }
    for index = 1, #raw.phases do
        if type(raw.phases[index]) == "string" then
            entry.phases[#entry.phases + 1] = raw.phases[index]
        end
    end
    if #entry.phases == 0 then
        return nil
    end
    if type(raw.undo) == "table" then
        for index = 1, #raw.undo do
            if raw.undo[index] == "source" or raw.undo[index] == "destination" then
                entry.undo[#entry.undo + 1] = raw.undo[index]
            end
        end
    end
    return entry
end

----------------------------------------------------------------------------
-- construction
----------------------------------------------------------------------------

local function build(adapter, persisted)
    local journal = {}      -- ordered entries
    local index_of = {}     -- request_id -> position in journal

    local function append(entry)
        journal[#journal + 1] = entry
        index_of[entry.request.request_id] = #journal
    end

    if type(persisted) == "table" and type(persisted.journal) == "table" then
        for position = 1, #persisted.journal do
            local entry = revive_entry(persisted.journal[position])
            if entry ~= nil and index_of[entry.request.request_id] == nil then
                append(entry)
            end
        end
    end

    local function container_of(entry, role)
        if role == "destination" then
            return entry.request.destination_id, entry.destination_snapshot
        end
        return entry.request.source_id, entry.source_snapshot
    end

    -- Pops the undo stack. A failed restore stops the unwinding and leaves the
    -- entry in the recoverable "compensating" phase with the rest of the stack.
    local function unwind(entry, reason)
        if entry.reason == nil then
            entry.reason = reason
        end
        if current_phase(entry) ~= "compensating" then
            entry.phases[#entry.phases + 1] = "compensating"
        end
        while #entry.undo > 0 do
            local container_id, snapshot = container_of(entry, entry.undo[#entry.undo])
            local ok, restored = pcall(adapter.restore, adapter, container_id, plain_copy(snapshot))
            if not ok or not restored then
                return describe(entry)
            end
            entry.undo[#entry.undo] = nil
        end
        entry.phases[#entry.phases + 1] = "aborted"
        return describe(entry)
    end

    local function refuse(request, reason)
        local entry = {
            request = request, phases = { "refused" }, reason = reason,
            source_snapshot = {}, destination_snapshot = {}, selected = {}, undo = {},
        }
        append(entry)
        return describe(entry)
    end

    local self = {}

    function self.transfer(_, request)
        local frozen, bad_field = freeze_request(request)
        if frozen == nil then
            return {
                ok = false, status = "refused", reason = "invalid_" .. bad_field, recoverable = false,
            }
        end
        local seen = index_of[frozen.request_id]
        if seen ~= nil then
            return describe(journal[seen])
        end

        local source_snapshot = normalise_snapshot(adapter:snapshot(frozen.source_id))
        local destination_snapshot = normalise_snapshot(adapter:snapshot(frozen.destination_id))
        local selected, missing = pick_from(source_snapshot, frozen.prefab, frozen.count)
        if missing > 0 then
            return refuse(frozen, "source_short")
        end
        local room = adapter:capacity(frozen.destination_id, frozen.prefab)
        if type(room) ~= "number" or room < frozen.count then
            return refuse(frozen, "destination_full")
        end

        -- Write-ahead intent: recorded (and visible to save) before any
        -- destructive adapter call happens.
        local entry = {
            request = frozen,
            phases = { PHASE_ORDER[1] },
            source_snapshot = source_snapshot,
            destination_snapshot = destination_snapshot,
            selected = selected,
            undo = { "source" },
        }
        append(entry)

        local removed = adapter:remove(frozen.source_id, frozen.prefab, frozen.count)
        if not removed then
            return unwind(entry, "remove_failed")
        end
        entry.phases[#entry.phases + 1] = PHASE_ORDER[2]

        entry.undo[#entry.undo + 1] = "destination"
        local added = adapter:add(frozen.destination_id, plain_copy(entry.selected))
        if not added then
            return unwind(entry, "add_failed")
        end
        entry.phases[#entry.phases + 1] = PHASE_ORDER[3]

        entry.undo = {}
        entry.phases[#entry.phases + 1] = PHASE_ORDER[4]
        return describe(entry)
    end

    function self.recover(_)
        local report = {}
        for position = 1, #journal do
            local entry = journal[position]
            local phase = current_phase(entry)
            if phase == "destination_added" then
                -- Both sides already changed; only the final mark was missing.
                entry.undo = {}
                entry.phases[#entry.phases + 1] = "committed"
            elseif phase == "prepared" or phase == "source_removed" then
                if #entry.undo == 0 then
                    entry.undo = phase == "prepared" and { "source" } or { "source", "destination" }
                end
                unwind(entry, "interrupted")
            elseif phase == "compensating" then
                unwind(entry, entry.reason)
            end
            report[#report + 1] = describe(entry)
        end
        return report
    end

    function self.status(_, request_id)
        local seen = index_of[request_id]
        if seen == nil then
            return nil
        end
        return describe(journal[seen])
    end

    function self.save(_)
        local out = { schema = 2, journal = {} }
        for position = 1, #journal do
            local entry = journal[position]
            out.journal[position] = {
                request = plain_copy(entry.request),
                phases = plain_copy(entry.phases),
                reason = entry.reason,
                source_snapshot = plain_copy(entry.source_snapshot),
                destination_snapshot = plain_copy(entry.destination_snapshot),
                selected = plain_copy(entry.selected),
                undo = plain_copy(entry.undo),
            }
        end
        return out
    end

    return self
end

function Transaction.new(adapter, persisted)
    return build(adapter, persisted)
end

function Transaction.load(adapter, data)
    return build(adapter, data)
end

return Transaction
