-- Pure fuel ration allocator. No game globals are touched here: every time
-- value arrives through a `now` argument and every quantity is an integer
-- number of fuel units.

local Allocator = {}
Allocator.__index = Allocator

local MAX_ID_LENGTH = 64

local function is_time(value)
    return type(value) == "number" and value == value
        and value ~= math.huge and value ~= -math.huge and value >= 0
end

local function is_id(value)
    return type(value) == "string" and #value >= 1 and #value <= MAX_ID_LENGTH
end

local function is_integer(value, minimum)
    return type(value) == "number" and value == value
        and value ~= math.huge and value ~= -math.huge
        and value == math.floor(value) and value >= minimum
end

local function fail(code, extra)
    local result = { ok = false, code = code }
    if extra ~= nil then
        for key, value in pairs(extra) do
            result[key] = value
        end
    end
    return result
end

local function sorted_keys(map)
    local keys = {}
    for key in pairs(map) do
        keys[#keys + 1] = key
    end
    table.sort(keys)
    return keys
end

local function option(options, name, fallback)
    local value = type(options) == "table" and options[name] or nil
    if is_integer(value, 0) then
        return math.floor(value)
    end
    return fallback
end

function Allocator.new(options)
    local self = setmetatable({}, Allocator)
    self.depot_capacity = option(options, "depot_capacity", 1000)
    self.max_units_per_round = option(options, "max_units_per_round", 8)
    self.reserve_floor = option(options, "reserve_floor", 0)
    self.clock = 0
    self.available = 0
    self.reserved = 0
    self.deposited_total = 0
    self.delivered_total = 0
    self.requests = {}   -- player_id -> request_id -> recorded result
    self.contributions = {} -- player_id -> accepted units
    self.consumers = {}  -- consumer_id -> record
    self.round = nil     -- the single open round
    self.closed = {}     -- round_id -> summary
    return self
end

-- Steps 1 and 2 of the published validation order.
function Allocator:_check_time(now, compare)
    if not is_time(now) then
        return "invalid_time"
    end
    if compare and now < self.clock then
        return "time_regressed"
    end
    return nil
end

function Allocator:_advance(now)
    if now > self.clock then
        self.clock = now
    end
end

local function copy_request(record, duplicate)
    local result = { ok = record.ok, accepted = record.accepted, duplicate = duplicate }
    if record.ok then
        result.status = record.status
    else
        result.code = record.code
    end
    return result
end

function Allocator:lookup(request_id, player_id)
    if not is_id(request_id) or not is_id(player_id) then
        return nil
    end
    local record = self.requests[player_id] and self.requests[player_id][request_id] or nil
    if record == nil then
        return nil
    end
    return copy_request(record, true)
end

function Allocator:deposit(request_id, player_id, units, now)
    local problem = self:_check_time(now, true)
    if problem ~= nil then
        return fail(problem)
    end
    if not is_id(request_id) or not is_id(player_id) then
        return fail("invalid_id")
    end
    if not is_integer(units, 1) then
        return fail("invalid_units")
    end
    self:_advance(now)
    units = math.floor(units)

    local history = self.requests[player_id]
    if history == nil then
        history = {}
        self.requests[player_id] = history
    end
    if history[request_id] ~= nil then
        return copy_request(history[request_id], true)
    end

    local free = self.depot_capacity - self.available - self.reserved
    local record
    if free <= 0 then
        record = { ok = false, code = "depot_full", accepted = 0 }
    elseif units <= free then
        record = { ok = true, status = "accepted", accepted = units }
    else
        record = { ok = true, status = "partial", accepted = free }
    end
    history[request_id] = record
    if record.accepted > 0 then
        self.available = self.available + record.accepted
        self.deposited_total = self.deposited_total + record.accepted
        self.contributions[player_id] = (self.contributions[player_id] or 0) + record.accepted
    end
    return copy_request(record, false)
end

function Allocator:register(consumer_id, priority, capacity, now)
    local problem = self:_check_time(now, true)
    if problem ~= nil then
        return fail(problem)
    end
    if not is_id(consumer_id) then
        return fail("invalid_id")
    end
    if not is_integer(priority, 0) then
        return fail("invalid_priority")
    end
    if not is_integer(capacity, 1) then
        return fail("invalid_units")
    end
    self:_advance(now)
    if self.consumers[consumer_id] ~= nil then
        return fail("duplicate_consumer")
    end
    capacity = math.floor(capacity)
    self.consumers[consumer_id] = {
        priority = math.floor(priority),
        capacity = capacity,
        level = capacity,
        reported_at = now,
        received = 0,
    }
    return { ok = true, status = "registered" }
end

-- Settles one pending share. `delivered` units leave the system, the rest of
-- the reservation returns to the available depot.
function Allocator:_settle(share, status, delivered)
    share.status = status
    share.delivered = delivered
    share.returned = share.units - delivered
    self.reserved = self.reserved - share.units
    self.available = self.available + share.returned
    self.delivered_total = self.delivered_total + delivered
    self.round.delivered = self.round.delivered + delivered
end

function Allocator:unregister(consumer_id, now)
    local problem = self:_check_time(now, true)
    if problem ~= nil then
        return fail(problem)
    end
    if not is_id(consumer_id) then
        return fail("invalid_id")
    end
    self:_advance(now)
    if self.consumers[consumer_id] == nil then
        return fail("unknown_consumer")
    end
    local returned = 0
    local share = self.round ~= nil and self.round.shares[consumer_id] or nil
    if share ~= nil and share.status == "pending" then
        returned = share.units
        self:_settle(share, "aborted", 0)
    end
    self.consumers[consumer_id] = nil
    return { ok = true, status = "unregistered", returned = returned }
end

-- `now` is the measurement time here: it is neither compared with nor written
-- to the global clock, only to the consumer's own last report time.
function Allocator:report(consumer_id, level, now)
    local problem = self:_check_time(now, false)
    if problem ~= nil then
        return fail(problem)
    end
    if not is_id(consumer_id) then
        return fail("invalid_id")
    end
    if not is_integer(level, 0) then
        return fail("invalid_units")
    end
    local consumer = self.consumers[consumer_id]
    if consumer == nil then
        return fail("unknown_consumer")
    end
    if now < consumer.reported_at then
        return { ok = true, status = "stale", level = consumer.level, demand = consumer.capacity - consumer.level }
    end
    consumer.level = math.min(math.floor(level), consumer.capacity)
    consumer.reported_at = now
    return { ok = true, status = "reported", level = consumer.level, demand = consumer.capacity - consumer.level }
end

local function plan_result(round, duplicate)
    local shares = {}
    for index, consumer_id in ipairs(round.order) do
        local share = round.shares[consumer_id]
        shares[index] = { consumer_id = consumer_id, priority = share.priority, units = share.units }
    end
    return {
        ok = true,
        status = "planned",
        round_id = round.id,
        shares = shares,
        total = round.total,
        duplicate = duplicate,
    }
end

-- One unit at a time to the unsatisfied consumer holding the fewest units;
-- `ids` is already sorted, so the first minimum is the smallest id.
local function water_fill(ids, wants, budget)
    local grants = {}
    for _, id in ipairs(ids) do
        grants[id] = 0
    end
    while budget > 0 do
        local chosen
        for _, id in ipairs(ids) do
            if grants[id] < wants[id] and (chosen == nil or grants[id] < grants[chosen]) then
                chosen = id
            end
        end
        if chosen == nil then
            break
        end
        grants[chosen] = grants[chosen] + 1
        budget = budget - 1
    end
    return grants, budget
end

function Allocator:plan(round_id, now)
    local problem = self:_check_time(now, true)
    if problem ~= nil then
        return fail(problem)
    end
    if not is_id(round_id) then
        return fail("invalid_id")
    end
    self:_advance(now)
    if self.round ~= nil then
        if self.round.id == round_id then
            return plan_result(self.round, true)
        end
        return fail("round_open")
    end
    if self.closed[round_id] ~= nil then
        return fail("round_closed")
    end

    local classes, wants = {}, {}
    for _, consumer_id in ipairs(sorted_keys(self.consumers)) do
        local consumer = self.consumers[consumer_id]
        local want = math.min(consumer.capacity - consumer.level, self.max_units_per_round)
        if want > 0 then
            wants[consumer_id] = want
            local members = classes[consumer.priority]
            if members == nil then
                members = {}
                classes[consumer.priority] = members
            end
            members[#members + 1] = consumer_id
        end
    end

    local round = { id = round_id, total = 0, delivered = 0, order = {}, shares = {} }
    local budget = math.max(0, self.available - self.reserve_floor)
    for _, priority in ipairs(sorted_keys(classes)) do
        local members = classes[priority]
        local grants
        grants, budget = water_fill(members, wants, budget)
        for _, consumer_id in ipairs(members) do
            if grants[consumer_id] > 0 then
                round.order[#round.order + 1] = consumer_id
                round.shares[consumer_id] = {
                    priority = priority,
                    units = grants[consumer_id],
                    status = "pending",
                    delivered = 0,
                    returned = 0,
                }
                round.total = round.total + grants[consumer_id]
            end
        end
    end
    self.available = self.available - round.total
    self.reserved = self.reserved + round.total
    self.round = round
    return plan_result(round, false)
end

local function share_result(share, duplicate)
    return {
        ok = true,
        status = share.status,
        units = share.units,
        delivered = share.delivered,
        returned = share.returned,
        duplicate = duplicate,
    }
end

-- Shared by commit and abort: `delivered == nil` means abort.
function Allocator:_finish(round_id, consumer_id, delivered, now)
    local problem = self:_check_time(now, true)
    if problem ~= nil then
        return fail(problem)
    end
    if not is_id(round_id) or not is_id(consumer_id) then
        return fail("invalid_id")
    end
    if delivered ~= nil and not is_integer(delivered, 0) then
        return fail("invalid_units")
    end
    self:_advance(now)
    if self.round == nil or self.round.id ~= round_id then
        return fail(self.closed[round_id] ~= nil and "round_closed" or "unknown_round")
    end
    local share = self.round.shares[consumer_id]
    if share == nil then
        return fail("unknown_share")
    end
    if share.status ~= "pending" then
        return share_result(share, true)
    end
    if delivered == nil then
        self:_settle(share, "aborted", 0)
        return share_result(share, false)
    end
    delivered = math.floor(delivered)
    if delivered > share.units then
        return fail("over_delivery")
    end
    self:_settle(share, "committed", delivered)
    local consumer = self.consumers[consumer_id]
    if consumer ~= nil then
        consumer.level = math.min(consumer.capacity, consumer.level + delivered)
        consumer.received = consumer.received + delivered
    end
    return share_result(share, false)
end

function Allocator:commit(round_id, consumer_id, delivered_units, now)
    if delivered_units == nil then
        -- nil is not a quantity; keep abort the only way to return everything.
        local problem = self:_check_time(now, true)
        if problem ~= nil then
            return fail(problem)
        end
        if not is_id(round_id) or not is_id(consumer_id) then
            return fail("invalid_id")
        end
        return fail("invalid_units")
    end
    return self:_finish(round_id, consumer_id, delivered_units, now)
end

function Allocator:abort(round_id, consumer_id, now)
    return self:_finish(round_id, consumer_id, nil, now)
end

local function close_result(round_id, summary, duplicate)
    return {
        ok = true,
        status = "closed",
        round_id = round_id,
        total = summary.total,
        delivered = summary.delivered,
        returned = summary.returned,
        duplicate = duplicate,
    }
end

function Allocator:close(round_id, now)
    local problem = self:_check_time(now, true)
    if problem ~= nil then
        return fail(problem)
    end
    if not is_id(round_id) then
        return fail("invalid_id")
    end
    self:_advance(now)
    if self.closed[round_id] ~= nil then
        return close_result(round_id, self.closed[round_id], true)
    end
    local round = self.round
    if round == nil or round.id ~= round_id then
        return fail("unknown_round")
    end
    for _, consumer_id in ipairs(round.order) do
        local share = round.shares[consumer_id]
        if share.status == "pending" then
            self:_settle(share, "aborted", 0)
        end
    end
    local summary = { total = round.total, delivered = round.delivered, returned = round.total - round.delivered }
    self.closed[round_id] = summary
    self.round = nil
    return close_result(round_id, summary, false)
end

local function round_rows(round)
    local rows = {}
    for index, consumer_id in ipairs(round.order) do
        local share = round.shares[consumer_id]
        rows[index] = {
            consumer_id = consumer_id,
            priority = share.priority,
            units = share.units,
            status = share.status,
            delivered = share.delivered,
            returned = share.returned,
        }
    end
    return rows
end

function Allocator:snapshot(now)
    local consumers = {}
    for index, consumer_id in ipairs(sorted_keys(self.consumers)) do
        local consumer = self.consumers[consumer_id]
        consumers[index] = {
            consumer_id = consumer_id,
            priority = consumer.priority,
            capacity = consumer.capacity,
            level = consumer.level,
            demand = consumer.capacity - consumer.level,
            received = consumer.received,
        }
    end
    local contributors = {}
    for index, player_id in ipairs(sorted_keys(self.contributions)) do
        contributors[index] = { player_id = player_id, units = self.contributions[player_id] }
    end
    local round
    if self.round ~= nil then
        round = { round_id = self.round.id, total = self.round.total, shares = round_rows(self.round) }
    end
    return {
        clock = self.clock,
        available = self.available,
        reserved = self.reserved,
        free = self.depot_capacity - self.available - self.reserved,
        deposited_total = self.deposited_total,
        delivered_total = self.delivered_total,
        consumers = consumers,
        contributors = contributors,
        round = round,
    }
end

function Allocator:save(now)
    local data = self:snapshot(now)
    -- The snapshot omits what must stay private or is only needed to resume.
    for _, row in ipairs(data.consumers) do
        row.reported_at = self.consumers[row.consumer_id].reported_at
    end
    if data.round ~= nil then
        data.round.delivered = self.round.delivered
    else
        data.round = false
    end
    data.requests = {}
    for _, player_id in ipairs(sorted_keys(self.requests)) do
        for _, request_id in ipairs(sorted_keys(self.requests[player_id])) do
            local record = self.requests[player_id][request_id]
            data.requests[#data.requests + 1] = {
                player_id = player_id,
                request_id = request_id,
                ok = record.ok,
                status = record.status or "",
                code = record.code or "",
                accepted = record.accepted,
            }
        end
    end
    data.closed = {}
    for _, round_id in ipairs(sorted_keys(self.closed)) do
        local summary = self.closed[round_id]
        data.closed[#data.closed + 1] = {
            round_id = round_id,
            total = summary.total,
            delivered = summary.delivered,
            returned = summary.returned,
        }
    end
    data.version = 1
    return data
end

function Allocator.load(data, options)
    local self = Allocator.new(options)
    if type(data) ~= "table" or data.version ~= 1 then
        return self
    end
    self.clock = is_time(data.clock) and data.clock or 0
    self.available = data.available or 0
    self.reserved = data.reserved or 0
    self.deposited_total = data.deposited_total or 0
    self.delivered_total = data.delivered_total or 0
    for _, row in ipairs(data.consumers or {}) do
        self.consumers[row.consumer_id] = {
            priority = row.priority,
            capacity = row.capacity,
            level = row.level,
            reported_at = row.reported_at or 0,
            received = row.received or 0,
        }
    end
    for _, row in ipairs(data.contributors or {}) do
        self.contributions[row.player_id] = row.units
    end
    for _, row in ipairs(data.requests or {}) do
        local history = self.requests[row.player_id]
        if history == nil then
            history = {}
            self.requests[row.player_id] = history
        end
        local record = { ok = row.ok == true, accepted = row.accepted or 0 }
        if record.ok then
            record.status = row.status
        else
            record.code = row.code
        end
        history[row.request_id] = record
    end
    for _, row in ipairs(data.closed or {}) do
        self.closed[row.round_id] = { total = row.total, delivered = row.delivered, returned = row.returned }
    end
    if type(data.round) == "table" then
        local round = {
            id = data.round.round_id,
            total = data.round.total or 0,
            delivered = data.round.delivered or 0,
            order = {},
            shares = {},
        }
        for index, row in ipairs(data.round.shares or {}) do
            round.order[index] = row.consumer_id
            round.shares[row.consumer_id] = {
                priority = row.priority,
                units = row.units,
                status = row.status,
                delivered = row.delivered,
                returned = row.returned,
            }
        end
        self.round = round
    end
    return self
end

return Allocator
