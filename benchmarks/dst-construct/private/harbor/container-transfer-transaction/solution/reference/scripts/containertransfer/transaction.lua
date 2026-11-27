-- Pure Lua transfer transaction. It knows nothing about the engine: every
-- world effect goes through the adapter, and every destructive step is
-- preceded by a persisted intent so a reload can finish or undo it.

local Transaction = {}
Transaction.__index = Transaction

local PREPARED, SOURCE_REMOVED, DESTINATION_ADDED = "prepared", "source_removed", "destination_added"
local COMMITTED, ROLLED_BACK, REJECTED = "committed", "rolled_back", "rejected"
local COMPENSATING = "compensating"

local FINAL = { [COMMITTED] = true, [ROLLED_BACK] = true, [REJECTED] = true }

local function is_identifier(value)
    return type(value) == "string" and value ~= "" and #value <= 96 and string.find(value, "%c") == nil
end

local function is_positive_integer(value)
    return type(value) == "number" and value == value and value >= 1
        and value ~= math.huge and math.floor(value) == value
end

local function copy_item(item)
    return {
        slot = item.slot,
        prefab = item.prefab,
        count = item.count,
        perish_percent = item.perish_percent,
        finite_uses_percent = item.finite_uses_percent,
    }
end

local function copy_items(items)
    local out = {}
    if type(items) == "table" then
        for index = 1, #items do
            if type(items[index]) == "table" then
                out[#out + 1] = copy_item(items[index])
            end
        end
    end
    return out
end

local function by_slot(items)
    local sorted = copy_items(items)
    table.sort(sorted, function(left, right)
        return (left.slot or 0) < (right.slot or 0)
    end)
    return sorted
end

local function copy_request(request)
    return {
        request_id = request.request_id,
        source_id = request.source_id,
        destination_id = request.destination_id,
        prefab = request.prefab,
        count = request.count,
    }
end

local function validate(request)
    if type(request) ~= "table" then
        return "invalid_request"
    end
    if not is_identifier(request.request_id) then
        return "invalid_request_id"
    end
    if not is_identifier(request.source_id) or not is_identifier(request.destination_id) then
        return "invalid_container"
    end
    if request.source_id == request.destination_id then
        return "same_container"
    end
    if not is_identifier(request.prefab) then
        return "invalid_prefab"
    end
    if not is_positive_integer(request.count) then
        return "invalid_count"
    end
    return nil
end

local function public_result(record)
    return {
        ok = record.phase == COMMITTED,
        status = record.phase,
        request_id = record.request.request_id,
        reason = record.reason,
        recoverable = not FINAL[record.phase],
        moved = record.phase == COMMITTED and copy_items(record.moved) or nil,
    }
end

function Transaction.new(adapter, persisted)
    local self = setmetatable({}, Transaction)
    self.adapter = adapter
    self.records = {}
    self.order = {}
    if type(persisted) == "table" and type(persisted.records) == "table" then
        for index = 1, #persisted.records do
            local saved = persisted.records[index]
            if type(saved) == "table" and type(saved.request) == "table"
                and is_identifier(saved.request.request_id)
                and self.records[saved.request.request_id] == nil then
                self.records[saved.request.request_id] = {
                    request = copy_request(saved.request),
                    phase = saved.phase,
                    reason = saved.reason,
                    source_snapshot = copy_items(saved.source_snapshot),
                    destination_snapshot = copy_items(saved.destination_snapshot),
                    selected = copy_items(saved.selected),
                    moved = copy_items(saved.moved),
                    pending_restore = type(saved.pending_restore) == "table" and {
                        destination = saved.pending_restore.destination and true or false,
                        source = saved.pending_restore.source and true or false,
                    } or nil,
                }
                self.order[#self.order + 1] = saved.request.request_id
            end
        end
    end
    return self
end

function Transaction.load(adapter, data)
    return Transaction.new(adapter, data)
end

function Transaction:_remember(record)
    local request_id = record.request.request_id
    if self.records[request_id] == nil then
        self.order[#self.order + 1] = request_id
    end
    self.records[request_id] = record
end

-- Undo in reverse order: the destination first, then the source. A restore
-- that fails leaves an explicit recoverable phase instead of a false success.
function Transaction:_compensate(record, reason)
    record.reason = record.reason or reason
    record.pending_restore = record.pending_restore or { destination = true, source = true }
    record.phase = COMPENSATING
    if record.pending_restore.destination then
        local restored = self.adapter:restore(record.request.destination_id, copy_items(record.destination_snapshot))
        if not restored then
            return public_result(record)
        end
        record.pending_restore.destination = false
    end
    if record.pending_restore.source then
        local restored = self.adapter:restore(record.request.source_id, copy_items(record.source_snapshot))
        if not restored then
            return public_result(record)
        end
        record.pending_restore.source = false
    end
    record.pending_restore = nil
    record.phase = ROLLED_BACK
    return public_result(record)
end

function Transaction:transfer(request)
    local problem = validate(request)
    if problem ~= nil then
        return { ok = false, status = REJECTED, reason = problem, recoverable = false }
    end
    -- A known request is answered from state; a committed one never touches
    -- the adapter again.
    local known = self.records[request.request_id]
    if known ~= nil then
        return public_result(known)
    end

    local record = { request = copy_request(request), phase = REJECTED }
    local source_snapshot = by_slot(self.adapter:snapshot(request.source_id))
    local destination_snapshot = by_slot(self.adapter:snapshot(request.destination_id))

    local available, selected, remaining = 0, {}, request.count
    for index = 1, #source_snapshot do
        local item = source_snapshot[index]
        if item.prefab == request.prefab and type(item.count) == "number" and item.count > 0 then
            available = available + item.count
            if remaining > 0 then
                local take = math.min(item.count, remaining)
                local chosen = copy_item(item)
                chosen.count = take
                selected[#selected + 1] = chosen
                remaining = remaining - take
            end
        end
    end
    if available < request.count then
        record.reason = "insufficient_source"
        self:_remember(record)
        return public_result(record)
    end
    local capacity = self.adapter:capacity(request.destination_id, request.prefab)
    if type(capacity) ~= "number" or capacity < request.count then
        record.reason = "insufficient_capacity"
        self:_remember(record)
        return public_result(record)
    end

    -- The intent, with both snapshots, exists before the first destructive call.
    record.phase = PREPARED
    record.source_snapshot = source_snapshot
    record.destination_snapshot = destination_snapshot
    record.selected = selected
    self:_remember(record)

    local removed = self.adapter:remove(request.source_id, request.prefab, request.count)
    if type(removed) ~= "table" then
        record.pending_restore = { destination = false, source = true }
        return self:_compensate(record, "remove_failed")
    end
    record.moved = copy_items(removed)
    record.phase = SOURCE_REMOVED

    local added = self.adapter:add(request.destination_id, removed)
    if not added then
        return self:_compensate(record, "add_failed")
    end
    record.phase = DESTINATION_ADDED
    record.phase = COMMITTED
    return public_result(record)
end

-- Finish or undo every interrupted request. Running it again changes nothing.
function Transaction:recover()
    local results = {}
    for index = 1, #self.order do
        local record = self.records[self.order[index]]
        if record.phase == DESTINATION_ADDED then
            record.phase = COMMITTED
        elseif record.phase == PREPARED or record.phase == SOURCE_REMOVED then
            self:_compensate(record, "recovered_after_interruption")
        elseif record.phase == COMPENSATING then
            self:_compensate(record, record.reason)
        end
        results[#results + 1] = public_result(record)
    end
    return results
end

function Transaction:status(request_id)
    local record = self.records[request_id]
    if record == nil then
        return nil
    end
    return public_result(record)
end

function Transaction:save()
    local records = {}
    for index = 1, #self.order do
        local record = self.records[self.order[index]]
        records[#records + 1] = {
            request = copy_request(record.request),
            phase = record.phase,
            reason = record.reason,
            source_snapshot = copy_items(record.source_snapshot),
            destination_snapshot = copy_items(record.destination_snapshot),
            selected = copy_items(record.selected),
            moved = copy_items(record.moved),
            pending_restore = record.pending_restore ~= nil and {
                destination = record.pending_restore.destination,
                source = record.pending_restore.source,
            } or nil,
        }
    end
    return { version = 1, records = records }
end

return Transaction
