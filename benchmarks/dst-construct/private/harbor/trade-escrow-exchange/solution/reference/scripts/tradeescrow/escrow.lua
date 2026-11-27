-- Pure two-party item escrow state machine. No game globals are used here:
-- every notion of time arrives through the `now` argument, and persistence is
-- a plain table of strings, numbers and booleans.

local Escrow = {}
Escrow.__index = Escrow

local CLOSED = { settled = true, canceled = true, expired = true }
local SAVE_VERSION = 1

-- ---------------------------------------------------------------------------
-- Argument predicates
-- ---------------------------------------------------------------------------

local function is_id(value)
    return type(value) == "string" and value ~= ""
end

local function is_time(value)
    return type(value) == "number" and value == value
end

local function is_integer(value, minimum)
    return type(value) == "number"
        and value == value
        and value < math.huge
        and value >= minimum
        and value == math.floor(value)
end

local function sorted_keys(map)
    local keys = {}
    for key in pairs(map) do
        keys[#keys + 1] = key
    end
    table.sort(keys)
    return keys
end

local function copy_items(items)
    local copy = {}
    for prefab, count in pairs(items) do
        copy[prefab] = count
    end
    return copy
end

local function same_items(left, right)
    for prefab, count in pairs(left) do
        if right[prefab] ~= count then
            return false
        end
    end
    for prefab, count in pairs(right) do
        if left[prefab] ~= count then
            return false
        end
    end
    return true
end

-- ---------------------------------------------------------------------------
-- Construction
-- ---------------------------------------------------------------------------

local function normalise_options(options)
    options = type(options) == "table" and options or {}
    local allowed = {}
    if type(options.allowed_prefabs) == "table" then
        for prefab, enabled in pairs(options.allowed_prefabs) do
            if is_id(prefab) and enabled then
                allowed[prefab] = true
            end
        end
    end
    return {
        allowed = allowed,
        max_distinct = is_integer(options.max_distinct, 1) and options.max_distinct or 1,
        ttl = (is_time(options.ttl) and options.ttl > 0) and options.ttl or 1,
    }
end

function Escrow.new(options)
    local self = setmetatable({}, Escrow)
    self.options = normalise_options(options)
    self.trades = {}   -- trade_id -> record (closed records stay as tombstones)
    self.busy = {}     -- party_id -> trade_id of the in-progress trade
    return self
end

local function new_side()
    return { revision = 0, items = {}, confirmed = false }
end

-- ---------------------------------------------------------------------------
-- Results
-- ---------------------------------------------------------------------------

local function result(ok, code, trade, extra)
    local value = { ok = ok, code = code }
    if trade ~= nil then
        value.phase = trade.phase
    end
    if extra ~= nil then
        for key, field in pairs(extra) do
            value[key] = field
        end
    end
    return value
end

local function reject(code, trade)
    return result(false, code, trade)
end

-- ---------------------------------------------------------------------------
-- Internal transitions
-- ---------------------------------------------------------------------------

function Escrow:_close(trade, phase)
    trade.phase = phase
    for _, party in ipairs(trade.order) do
        if self.busy[party] == trade.id then
            self.busy[party] = nil
        end
    end
end

-- Expires every open trade whose deadline has been reached. Returns the ids
-- that expired during this very call, ascending.
function Escrow:_expire(now)
    local seen, expired = {}, {}
    for _, trade_id in pairs(self.busy) do
        if not seen[trade_id] then
            seen[trade_id] = true
            local trade = self.trades[trade_id]
            if trade ~= nil and trade.phase == "open" and now >= trade.expires_at then
                expired[#expired + 1] = trade_id
            end
        end
    end
    table.sort(expired)
    for _, trade_id in ipairs(expired) do
        self:_close(self.trades[trade_id], "expired")
    end
    return expired
end

local function counterparty(trade, party_id)
    if trade.order[1] == party_id then
        return trade.order[2]
    end
    return trade.order[1]
end

local function both_confirmed(trade)
    return trade.sides[trade.order[1]].confirmed and trade.sides[trade.order[2]].confirmed
end

local function build_plan(trade)
    local plan = {}
    local givers = { trade.order[1], trade.order[2] }
    table.sort(givers)
    for _, giver in ipairs(givers) do
        local items = trade.sides[giver].items
        for _, prefab in ipairs(sorted_keys(items)) do
            plan[#plan + 1] = {
                from = giver,
                to = counterparty(trade, giver),
                prefab = prefab,
                count = items[prefab],
            }
        end
    end
    return plan
end

-- Shared prologue of the party-driven calls: locate the trade and the party.
function Escrow:_locate(trade_id, party_id)
    local trade = self.trades[trade_id]
    if trade == nil then
        return nil, reject("unknown_trade")
    end
    if party_id ~= nil and trade.sides[party_id] == nil then
        return nil, reject("not_a_party", trade)
    end
    return trade
end

-- ---------------------------------------------------------------------------
-- Public API
-- ---------------------------------------------------------------------------

function Escrow:open(trade_id, a_id, b_id, now)
    if not (is_id(trade_id) and is_id(a_id) and is_id(b_id) and a_id ~= b_id and is_time(now)) then
        return reject("invalid_argument")
    end
    self:_expire(now)

    local existing = self.trades[trade_id]
    if existing ~= nil then
        if CLOSED[existing.phase] then
            return reject("trade_closed", existing)
        end
        if existing.sides[a_id] ~= nil and existing.sides[b_id] ~= nil then
            return result(true, "opened", existing, { trade_id = trade_id, expires_at = existing.expires_at })
        end
        return reject("trade_exists", existing)
    end
    if self.busy[a_id] ~= nil or self.busy[b_id] ~= nil then
        return reject("party_busy")
    end

    local trade = {
        id = trade_id,
        phase = "open",
        opened_at = now,
        expires_at = now + self.options.ttl,
        order = { a_id, b_id },
        sides = { [a_id] = new_side(), [b_id] = new_side() },
    }
    self.trades[trade_id] = trade
    self.busy[a_id] = trade_id
    self.busy[b_id] = trade_id
    return result(true, "opened", trade, { trade_id = trade_id, expires_at = trade.expires_at })
end

function Escrow:_validate_items(items)
    local distinct = 0
    for _ in pairs(items) do
        distinct = distinct + 1
    end
    if distinct > self.options.max_distinct then
        return "too_many_prefabs"
    end
    for prefab in pairs(items) do
        if not is_id(prefab) or not self.options.allowed[prefab] then
            return "prefab_not_allowed"
        end
    end
    for _, count in pairs(items) do
        if not is_integer(count, 1) then
            return "invalid_count"
        end
    end
    return nil
end

function Escrow:offer(trade_id, party_id, items, revision, now)
    if not (is_id(trade_id) and is_id(party_id) and type(items) == "table"
            and is_integer(revision, 1) and is_time(now)) then
        return reject("invalid_argument")
    end
    self:_expire(now)
    local trade, failure = self:_locate(trade_id, party_id)
    if trade == nil then
        return failure
    end
    if CLOSED[trade.phase] then
        return reject("trade_closed", trade)
    end
    if trade.phase ~= "open" then
        return reject("trade_locked", trade)
    end

    local side = trade.sides[party_id]
    if revision < side.revision then
        return reject("stale_revision", trade)
    end
    if revision == side.revision then
        if same_items(side.items, items) then
            return result(true, "offered", trade, { revision = side.revision })
        end
        return reject("revision_conflict", trade)
    end

    local problem = self:_validate_items(items)
    if problem ~= nil then
        return reject(problem, trade)
    end

    side.items = copy_items(items)
    side.revision = revision
    -- Any accepted change, by either party, voids BOTH confirmations.
    for _, party in ipairs(trade.order) do
        trade.sides[party].confirmed = false
    end
    return result(true, "offered", trade, { revision = revision })
end

function Escrow:confirm(trade_id, party_id, seen_revision, now)
    if not (is_id(trade_id) and is_id(party_id) and is_integer(seen_revision, 0) and is_time(now)) then
        return reject("invalid_argument")
    end
    self:_expire(now)
    local trade, failure = self:_locate(trade_id, party_id)
    if trade == nil then
        return failure
    end
    if CLOSED[trade.phase] then
        return reject("trade_closed", trade)
    end
    if trade.phase ~= "open" then
        return reject("trade_locked", trade)
    end

    local other = trade.sides[counterparty(trade, party_id)]
    if seen_revision ~= other.revision then
        return reject("stale_confirmation", trade)
    end
    trade.sides[party_id].confirmed = true
    return result(true, "confirmed", trade, { ready = both_confirmed(trade) })
end

function Escrow:cancel(trade_id, party_id, now)
    if not (is_id(trade_id) and is_id(party_id) and is_time(now)) then
        return reject("invalid_argument")
    end
    self:_expire(now)
    local trade, failure = self:_locate(trade_id, party_id)
    if trade == nil then
        return failure
    end
    if trade.phase == "canceled" then
        return result(true, "canceled", trade)
    end
    if CLOSED[trade.phase] then
        return reject("trade_closed", trade)
    end
    if trade.phase ~= "open" then
        return reject("trade_locked", trade)
    end
    self:_close(trade, "canceled")
    return result(true, "canceled", trade)
end

function Escrow:begin_settle(trade_id, now)
    if not (is_id(trade_id) and is_time(now)) then
        return reject("invalid_argument")
    end
    self:_expire(now)
    local trade, failure = self:_locate(trade_id, nil)
    if trade == nil then
        return failure
    end
    if CLOSED[trade.phase] then
        return reject("trade_closed", trade)
    end
    if trade.phase == "open" then
        if not both_confirmed(trade) then
            return reject("not_ready", trade)
        end
        trade.phase = "settling"
    end
    return result(true, "settling", trade, { plan = build_plan(trade) })
end

function Escrow:finish_settle(trade_id, ok, now)
    if not (is_id(trade_id) and type(ok) == "boolean" and is_time(now)) then
        return reject("invalid_argument")
    end
    self:_expire(now)
    local trade, failure = self:_locate(trade_id, nil)
    if trade == nil then
        return failure
    end
    if trade.phase == "settled" and ok then
        return result(true, "settled", trade)
    end
    if CLOSED[trade.phase] then
        return reject("trade_closed", trade)
    end
    if trade.phase ~= "settling" then
        return reject("not_settling", trade)
    end
    if ok then
        self:_close(trade, "settled")
        return result(true, "settled", trade)
    end
    trade.phase = "open"
    for _, party in ipairs(trade.order) do
        trade.sides[party].confirmed = false
    end
    return result(true, "reopened", trade)
end

function Escrow:tick(now)
    if not is_time(now) then
        return reject("invalid_argument")
    end
    return result(true, "ticked", nil, { expired = self:_expire(now) })
end

-- ---------------------------------------------------------------------------
-- Views and persistence
-- ---------------------------------------------------------------------------

local function party_view(trade, party_id)
    local side = trade.sides[party_id]
    local items = {}
    for _, prefab in ipairs(sorted_keys(side.items)) do
        items[#items + 1] = { prefab = prefab, count = side.items[prefab] }
    end
    return { id = party_id, revision = side.revision, confirmed = side.confirmed, items = items }
end

local function trade_view(trade)
    local parties = { trade.order[1], trade.order[2] }
    table.sort(parties)
    return {
        trade_id = trade.id,
        phase = trade.phase,
        opened_at = trade.opened_at,
        expires_at = trade.expires_at,
        parties = { party_view(trade, parties[1]), party_view(trade, parties[2]) },
    }
end

function Escrow:snapshot(now)
    if is_time(now) then
        self:_expire(now)
    end
    local trades = {}
    for _, trade_id in ipairs(sorted_keys(self.trades)) do
        trades[#trades + 1] = trade_view(self.trades[trade_id])
    end
    return { trades = trades }
end

function Escrow:save(now)
    local data = self:snapshot(now)
    data.version = SAVE_VERSION
    return data
end

local PHASES = { open = true, settling = true, settled = true, canceled = true, expired = true }

local function load_side(row)
    if type(row) ~= "table" or not is_id(row.id) or not is_integer(row.revision, 0) then
        return nil
    end
    local side = { revision = row.revision, items = {}, confirmed = row.confirmed == true }
    if type(row.items) == "table" then
        for _, entry in ipairs(row.items) do
            if type(entry) == "table" and is_id(entry.prefab) and is_integer(entry.count, 1) then
                side.items[entry.prefab] = entry.count
            end
        end
    end
    return side
end

function Escrow.load(data, options)
    local self = Escrow.new(options)
    if type(data) ~= "table" or type(data.trades) ~= "table" then
        return self
    end
    for _, row in ipairs(data.trades) do
        local parties = type(row) == "table" and row.parties or nil
        if type(parties) == "table" and is_id(row.trade_id) and PHASES[row.phase]
            and is_time(row.opened_at) and is_time(row.expires_at)
            and self.trades[row.trade_id] == nil then
            local first, second = load_side(parties[1]), load_side(parties[2])
            if first ~= nil and second ~= nil and parties[1].id ~= parties[2].id then
                local trade = {
                    id = row.trade_id,
                    phase = row.phase,
                    opened_at = row.opened_at,
                    expires_at = row.expires_at,
                    order = { parties[1].id, parties[2].id },
                    sides = { [parties[1].id] = first, [parties[2].id] = second },
                }
                self.trades[trade.id] = trade
                if not CLOSED[trade.phase] then
                    self.busy[parties[1].id] = trade.id
                    self.busy[parties[2].id] = trade.id
                end
            end
        end
    end
    return self
end

return Escrow
