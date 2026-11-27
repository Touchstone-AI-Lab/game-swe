-- Camp supply ledger core (plain Lua, no engine globals).
--
-- Design: the ledger keeps one append-only journal of reservations. Quota use
-- is never stored as a counter; it is derived on demand by summing the journal
-- entries of one (player, day, prefab) that are still pending or committed.
-- Because nothing is cached, rollback, day rollover and reload cannot drift.
-- The object returned by Ledger.new is a table of closures over private state;
-- callers may use either `ledger:claim(...)` or `ledger.claim(ledger, ...)`.

local Ledger = {}

local ID_LIMIT = 96
local PENDING, COMMITTED, ROLLED_BACK, REJECTED = "pending", "committed", "rolled_back", "rejected"

---------------------------------------------------------------------------
-- validation helpers
---------------------------------------------------------------------------

local function valid_id(value)
    if type(value) ~= "string" then
        return false
    end
    local length = #value
    if length == 0 or length > ID_LIMIT then
        return false
    end
    for position = 1, length do
        local byte = string.byte(value, position)
        if byte < 32 or byte == 127 then
            return false
        end
    end
    return true
end

local function whole_number(value, minimum)
    return type(value) == "number"
        and value == value
        and value >= minimum
        and value < 2 ^ 53
        and value % 1 == 0
end

local function ascending(list, key_of)
    table.sort(list, function(a, b)
        return key_of(a) < key_of(b)
    end)
    return list
end

local function clone_lines(lines)
    local copy = {}
    for index, line in ipairs(lines) do
        copy[index] = { prefab = line.prefab, count = line.count }
    end
    return copy
end

---------------------------------------------------------------------------
-- configuration
---------------------------------------------------------------------------

-- A bundle may be written as a list of { prefab = , count = } lines or as a
-- prefab -> count map. Either way it becomes a prefab-sorted list of lines with
-- one line per prefab. A bundle with any illegal line is not claimable at all.
local function compile_bundle(spec)
    if type(spec) ~= "table" then
        return nil
    end
    local counts = {}
    local legal = true
    local function take(prefab, count)
        if valid_id(prefab) and whole_number(count, 1) then
            counts[prefab] = (counts[prefab] or 0) + count
        else
            legal = false
        end
    end
    for key, value in pairs(spec) do
        if type(key) == "number" then
            if type(value) == "table" then
                take(value.prefab, value.count)
            else
                legal = false
            end
        else
            take(key, value)
        end
    end
    if not legal then
        return nil
    end
    local lines = {}
    for prefab, count in pairs(counts) do
        lines[#lines + 1] = { prefab = prefab, count = count }
    end
    if #lines == 0 then
        return nil
    end
    return ascending(lines, function(line)
        return line.prefab
    end)
end

local function compile_options(options)
    local catalog, limits = {}, {}
    if type(options) == "table" then
        if type(options.bundles) == "table" then
            for bundle_id, spec in pairs(options.bundles) do
                if valid_id(bundle_id) then
                    catalog[bundle_id] = compile_bundle(spec)
                end
            end
        end
        if type(options.daily_limits) == "table" then
            for prefab, limit in pairs(options.daily_limits) do
                if valid_id(prefab) and whole_number(limit, 0) then
                    limits[prefab] = limit
                end
            end
        end
    end
    return catalog, limits
end

---------------------------------------------------------------------------
-- construction
---------------------------------------------------------------------------

local function build(options, restored)
    local catalog, limits = compile_options(options)

    -- private state
    local today = nil          -- current day or nil before the first begin_day
    local roster = {}          -- player_id -> boolean
    local journal = {}         -- array of reservation entries in token order
    local by_token = {}        -- token -> journal entry
    local outcomes = {}        -- player_id -> request_id -> outcome
    local sequence = 0         -- last issued token number

    -- An outcome is either { entry = <journal entry> } or { reason = <string> }.

    local function spent(player_id, day, prefab)
        local total = 0
        for _, entry in ipairs(journal) do
            if entry.player_id == player_id and entry.day == day and entry.status ~= ROLLED_BACK then
                for _, line in ipairs(entry.items) do
                    if line.prefab == prefab then
                        total = total + line.count
                    end
                end
            end
        end
        return total
    end

    local function describe(outcome)
        if outcome.entry == nil then
            return { ok = false, status = REJECTED, reason = outcome.reason }
        end
        local entry = outcome.entry
        return {
            ok = entry.status ~= ROLLED_BACK,
            status = entry.status,
            token = entry.token,
            day = entry.day,
            bundle_id = entry.bundle_id,
            items = clone_lines(entry.items),
        }
    end

    local function remember(player_id, request_id, outcome)
        local mine = outcomes[player_id]
        if mine == nil then
            mine = {}
            outcomes[player_id] = mine
        end
        mine[request_id] = outcome
        return describe(outcome)
    end

    local function refuse(reason)
        return { ok = false, status = REJECTED, reason = reason }
    end

    local api = {}

    function api.begin_day(_, day)
        if not whole_number(day, 0) then
            return false
        end
        if today ~= nil and day <= today then
            return false
        end
        today = day
        return true
    end

    function api.set_player(_, player_id, active)
        if not valid_id(player_id) then
            return false
        end
        roster[player_id] = active == true
        return true
    end

    function api.claim(_, player_id, request_id, bundle_id, day)
        if not (valid_id(player_id) and valid_id(request_id)) then
            return refuse("bad_identifier")
        end
        -- Idempotency comes first: a known request never touches quota again.
        local mine = outcomes[player_id]
        if mine ~= nil and mine[request_id] ~= nil then
            local first = describe(mine[request_id])
            first.replayed = true
            return first
        end
        -- A request for any day other than the current one is not recorded, so a
        -- stale day leaves the ledger byte-for-byte unchanged.
        if today == nil or not whole_number(day, 0) or day ~= today then
            return refuse("wrong_day")
        end
        if not valid_id(bundle_id) or catalog[bundle_id] == nil then
            return remember(player_id, request_id, { reason = "unknown_bundle" })
        end
        if roster[player_id] ~= true then
            return remember(player_id, request_id, { reason = "inactive_player" })
        end
        local lines = catalog[bundle_id]
        for _, line in ipairs(lines) do
            local limit = limits[line.prefab]
            if limit == nil or spent(player_id, today, line.prefab) + line.count > limit then
                return remember(player_id, request_id, { reason = "quota_exhausted" })
            end
        end
        sequence = sequence + 1
        local entry = {
            token = "csl:" .. string.format("%010d", sequence),
            player_id = player_id,
            request_id = request_id,
            bundle_id = bundle_id,
            day = today,
            status = PENDING,
            items = clone_lines(lines),
        }
        journal[#journal + 1] = entry
        by_token[entry.token] = entry
        return remember(player_id, request_id, { entry = entry })
    end

    local function settle(token, wanted)
        local entry = type(token) == "string" and by_token[token] or nil
        if entry == nil then
            return { ok = false, status = "unknown_token", reason = "unknown_token" }
        end
        local changed = false
        if entry.status == PENDING then
            entry.status = wanted
            changed = true
        end
        return entry, changed
    end

    function api.commit(_, token)
        local entry = settle(token, COMMITTED)
        if entry.token == nil then
            return entry
        end
        return { ok = entry.status == COMMITTED, status = entry.status, token = entry.token }
    end

    function api.rollback(_, token)
        local entry, changed = settle(token, ROLLED_BACK)
        if entry.token == nil then
            return entry
        end
        -- Only the transition itself reports success; a repeat or a committed
        -- token reports the final status and releases nothing.
        return { ok = changed == true, status = entry.status, token = entry.token }
    end

    function api.current_day()
        return today
    end

    function api.snapshot()
        local players = {}
        for player_id, active in pairs(roster) do
            local quotas = {}
            for prefab, limit in pairs(limits) do
                local used = today ~= nil and spent(player_id, today, prefab) or 0
                quotas[#quotas + 1] = { prefab = prefab, limit = limit, used = used, available = limit - used }
            end
            ascending(quotas, function(row)
                return row.prefab
            end)
            players[#players + 1] = { player_id = player_id, active = active, quotas = quotas }
        end
        ascending(players, function(row)
            return row.player_id
        end)
        local tokens = {}
        for _, entry in ipairs(journal) do
            tokens[#tokens + 1] = {
                token = entry.token,
                player_id = entry.player_id,
                request_id = entry.request_id,
                bundle_id = entry.bundle_id,
                day = entry.day,
                status = entry.status,
                items = clone_lines(entry.items),
            }
        end
        ascending(tokens, function(row)
            return row.token
        end)
        return { day = today, players = players, tokens = tokens }
    end

    function api.save()
        local view = api.snapshot()
        local roster_rows = {}
        for _, row in ipairs(view.players) do
            roster_rows[#roster_rows + 1] = { id = row.player_id, active = row.active }
        end
        local refusals = {}
        for player_id, mine in pairs(outcomes) do
            for request_id, outcome in pairs(mine) do
                if outcome.entry == nil then
                    refusals[#refusals + 1] = { player_id = player_id, request_id = request_id, reason = outcome.reason }
                end
            end
        end
        ascending(refusals, function(row)
            return row.player_id .. "\n" .. row.request_id
        end)
        return {
            format = "campsupply.journal.1",
            day = today,
            sequence = sequence,
            roster = roster_rows,
            journal = view.tokens,
            refusals = refusals,
        }
    end

    -- restore (used by Ledger.load); malformed rows are skipped, never trusted
    if type(restored) == "table" then
        if whole_number(restored.day, 0) then
            today = restored.day
        end
        for _, row in ipairs(type(restored.roster) == "table" and restored.roster or {}) do
            if type(row) == "table" and valid_id(row.id) then
                roster[row.id] = row.active == true
            end
        end
        local highest = 0
        for _, row in ipairs(type(restored.journal) == "table" and restored.journal or {}) do
            local usable = type(row) == "table"
                and valid_id(row.token) and by_token[row.token] == nil
                and valid_id(row.player_id) and valid_id(row.request_id)
                and whole_number(row.day, 0) and type(row.items) == "table"
                and (row.status == PENDING or row.status == COMMITTED or row.status == ROLLED_BACK)
            if usable then
                local items = {}
                for _, line in ipairs(row.items) do
                    if type(line) == "table" and valid_id(line.prefab) and whole_number(line.count, 1) then
                        items[#items + 1] = { prefab = line.prefab, count = line.count }
                    end
                end
                local entry = {
                    token = row.token, player_id = row.player_id, request_id = row.request_id,
                    bundle_id = row.bundle_id, day = row.day, status = row.status, items = items,
                }
                journal[#journal + 1] = entry
                by_token[entry.token] = entry
                outcomes[entry.player_id] = outcomes[entry.player_id] or {}
                outcomes[entry.player_id][entry.request_id] = { entry = entry }
                local number = tonumber(string.match(entry.token, "^csl:(%d+)$"))
                if number ~= nil and number > highest then
                    highest = number
                end
            end
        end
        for _, row in ipairs(type(restored.refusals) == "table" and restored.refusals or {}) do
            if type(row) == "table" and valid_id(row.player_id) and valid_id(row.request_id) then
                outcomes[row.player_id] = outcomes[row.player_id] or {}
                if outcomes[row.player_id][row.request_id] == nil then
                    outcomes[row.player_id][row.request_id] = { reason = tostring(row.reason) }
                end
            end
        end
        -- The token counter never moves backwards, even if the saved number is
        -- missing or smaller than a token that is already in the journal.
        sequence = highest
        if whole_number(restored.sequence, 0) and restored.sequence > sequence then
            sequence = restored.sequence
        end
    end

    return api
end

function Ledger.new(options)
    return build(options, nil)
end

function Ledger.load(data, options)
    return build(options, data)
end

return Ledger
