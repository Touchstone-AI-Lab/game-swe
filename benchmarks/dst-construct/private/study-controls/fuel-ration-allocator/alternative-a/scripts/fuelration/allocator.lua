-- Fuel ration allocator built as a closure: all state lives in upvalues and the
-- returned object only carries methods. Collections are kept as sorted arrays,
-- and a class is filled with the closed form of integer water-filling.

local Allocator = {}

local INF = math.huge

local function finite(value)
    return type(value) == "number" and value == value and value ~= INF and value ~= -INF
end

local function whole(value, least)
    return finite(value) and value % 1 == 0 and value >= least
end

local function ident(value)
    return type(value) == "string" and value ~= "" and string.len(value) <= 64
end

local function no(code)
    return { ok = false, code = code }
end

-- Binary search over an array sorted by `field`; returns index, found.
local function locate(list, field, key)
    local low, high = 1, #list
    while low <= high do
        local middle = math.floor((low + high) / 2)
        local probe = list[middle][field]
        if probe == key then
            return middle, true
        elseif probe < key then
            low = middle + 1
        else
            high = middle - 1
        end
    end
    return low, false
end

local function clone(value)
    if type(value) ~= "table" then
        return value
    end
    local out = {}
    for key, item in pairs(value) do
        out[key] = clone(item)
    end
    return out
end

-- Closed form of the one-unit-at-a-time rule for one priority class.
-- `members` is sorted by consumer id; returns grants aligned with it and the
-- units that were used.
local function fill_class(members, budget)
    local grants, need = {}, 0
    for index, member in ipairs(members) do
        grants[index] = 0
        need = need + member.want
    end
    if need <= budget then
        for index, member in ipairs(members) do
            grants[index] = member.want
        end
        return grants, need
    end
    -- Largest water level whose cost still fits into the budget.
    local level, cost = 0, 0
    while true do
        local next_cost = 0
        for _, member in ipairs(members) do
            next_cost = next_cost + math.min(member.want, level + 1)
        end
        if next_cost > budget then
            break
        end
        level, cost = level + 1, next_cost
    end
    local spare = budget - cost
    for index, member in ipairs(members) do
        local grant = math.min(member.want, level)
        if spare > 0 and member.want > level then
            grant = grant + 1
            spare = spare - 1
        end
        grants[index] = grant
    end
    return grants, budget
end

local function build(options, seed)
    local capacity_limit = options.depot_capacity
    local per_round = options.max_units_per_round
    local floor_units = options.reserve_floor

    local state = seed or {
        clock = 0,
        available = 0,
        reserved = 0,
        deposited = 0,
        delivered = 0,
        consumers = {},   -- sorted by id: { id, priority, capacity, level, seen, received }
        players = {},     -- sorted by id: { id, units }
        ledger = {},      -- sorted by key: { key, ok, word, accepted }
        finished = {},    -- sorted by id: { id, total, delivered }
        open = false,     -- or { id, total, delivered, shares = { { id, priority, units, state, delivered } } }
    }

    local function ledger_key(player_id, request_id)
        return string.len(player_id) .. ":" .. player_id .. request_id
    end

    -- Runs the published validation pipeline. `ids` and `numbers` are lists in
    -- signature order; numbers are { value, least, code }.
    local function admit(now, ids, numbers, measured)
        if not finite(now) or now < 0 then
            return "invalid_time"
        end
        if not measured and now < state.clock then
            return "time_regressed"
        end
        for index = 1, ids.n do
            if not ident(ids[index]) then
                return "invalid_id"
            end
        end
        for _, spec in ipairs(numbers) do
            if not whole(spec[1], spec[2]) then
                return spec[3]
            end
        end
        if not measured and now > state.clock then
            state.clock = now
        end
        return nil
    end

    local function replay_deposit(entry, duplicate)
        local result = { ok = entry.ok, accepted = entry.accepted, duplicate = duplicate }
        if entry.ok then
            result.status = entry.word
        else
            result.code = entry.word
        end
        return result
    end

    local function share_of(consumer_id)
        if state.open then
            for _, share in ipairs(state.open.shares) do
                if share.id == consumer_id then
                    return share
                end
            end
        end
        return nil
    end

    local function release(share, outcome, delivered)
        share.state = outcome
        share.delivered = delivered
        state.reserved = state.reserved - share.units
        state.available = state.available + (share.units - delivered)
        state.delivered = state.delivered + delivered
        state.open.delivered = state.open.delivered + delivered
    end

    local function settlement(share, duplicate)
        return {
            ok = true,
            status = share.state,
            units = share.units,
            delivered = share.delivered,
            returned = share.units - share.delivered,
            duplicate = duplicate,
        }
    end

    local function plan_view(duplicate)
        local shares = {}
        for index, share in ipairs(state.open.shares) do
            shares[index] = { consumer_id = share.id, priority = share.priority, units = share.units }
        end
        return {
            ok = true,
            status = "planned",
            round_id = state.open.id,
            shares = shares,
            total = state.open.total,
            duplicate = duplicate,
        }
    end

    local function closing(entry, duplicate)
        return {
            ok = true,
            status = "closed",
            round_id = entry.id,
            total = entry.total,
            delivered = entry.delivered,
            returned = entry.total - entry.delivered,
            duplicate = duplicate,
        }
    end

    local object = {}

    function object.deposit(_, request_id, player_id, units, now)
        local problem = admit(now, { n = 2, request_id, player_id }, { { units, 1, "invalid_units" } })
        if problem then
            return no(problem)
        end
        local key = ledger_key(player_id, request_id)
        local at, found = locate(state.ledger, "key", key)
        if found then
            return replay_deposit(state.ledger[at], true)
        end
        local free = capacity_limit - state.available - state.reserved
        local entry = { key = key, ok = true, word = "accepted", accepted = units }
        if free <= 0 then
            entry.ok, entry.word, entry.accepted = false, "depot_full", 0
        elseif units > free then
            entry.word, entry.accepted = "partial", free
        end
        table.insert(state.ledger, at, entry)
        if entry.accepted > 0 then
            state.available = state.available + entry.accepted
            state.deposited = state.deposited + entry.accepted
            local slot, known = locate(state.players, "id", player_id)
            if known then
                state.players[slot].units = state.players[slot].units + entry.accepted
            else
                table.insert(state.players, slot, { id = player_id, units = entry.accepted })
            end
        end
        return replay_deposit(entry, false)
    end

    function object.lookup(_, request_id, player_id)
        if not ident(request_id) or not ident(player_id) then
            return nil
        end
        local at, found = locate(state.ledger, "key", ledger_key(player_id, request_id))
        if not found then
            return nil
        end
        return replay_deposit(state.ledger[at], true)
    end

    function object.register(_, consumer_id, priority, capacity, now)
        local problem = admit(now, { n = 1, consumer_id },
            { { priority, 0, "invalid_priority" }, { capacity, 1, "invalid_units" } })
        if problem then
            return no(problem)
        end
        local at, found = locate(state.consumers, "id", consumer_id)
        if found then
            return no("duplicate_consumer")
        end
        table.insert(state.consumers, at, {
            id = consumer_id, priority = priority, capacity = capacity,
            level = capacity, seen = now, received = 0,
        })
        return { ok = true, status = "registered" }
    end

    function object.unregister(_, consumer_id, now)
        local problem = admit(now, { n = 1, consumer_id }, {})
        if problem then
            return no(problem)
        end
        local at, found = locate(state.consumers, "id", consumer_id)
        if not found then
            return no("unknown_consumer")
        end
        local returned = 0
        local share = share_of(consumer_id)
        if share ~= nil and share.state == "pending" then
            returned = share.units
            release(share, "aborted", 0)
        end
        table.remove(state.consumers, at)
        return { ok = true, status = "unregistered", returned = returned }
    end

    function object.report(_, consumer_id, level, now)
        local problem = admit(now, { n = 1, consumer_id }, { { level, 0, "invalid_units" } }, true)
        if problem then
            return no(problem)
        end
        local at, found = locate(state.consumers, "id", consumer_id)
        if not found then
            return no("unknown_consumer")
        end
        local consumer = state.consumers[at]
        local status = "stale"
        if now >= consumer.seen then
            status = "reported"
            consumer.seen = now
            consumer.level = level > consumer.capacity and consumer.capacity or level
        end
        return { ok = true, status = status, level = consumer.level, demand = consumer.capacity - consumer.level }
    end

    function object.plan(_, round_id, now)
        local problem = admit(now, { n = 1, round_id }, {})
        if problem then
            return no(problem)
        end
        if state.open then
            if state.open.id == round_id then
                return plan_view(true)
            end
            return no("round_open")
        end
        local _, was_closed = locate(state.finished, "id", round_id)
        if was_closed then
            return no("round_closed")
        end

        -- Bucket the hungry consumers; the consumer array is already id-sorted.
        local priorities, buckets = {}, {}
        for _, consumer in ipairs(state.consumers) do
            local want = math.min(consumer.capacity - consumer.level, per_round)
            if want > 0 then
                if buckets[consumer.priority] == nil then
                    buckets[consumer.priority] = {}
                    priorities[#priorities + 1] = consumer.priority
                end
                local bucket = buckets[consumer.priority]
                bucket[#bucket + 1] = { id = consumer.id, want = want }
            end
        end
        table.sort(priorities)

        local budget = state.available - floor_units
        if budget < 0 then
            budget = 0
        end
        local round = { id = round_id, total = 0, delivered = 0, shares = {} }
        for _, priority in ipairs(priorities) do
            if budget <= 0 then
                break
            end
            local members = buckets[priority]
            local grants, used = fill_class(members, budget)
            budget = budget - used
            for index, member in ipairs(members) do
                if grants[index] > 0 then
                    round.shares[#round.shares + 1] = {
                        id = member.id, priority = priority, units = grants[index],
                        state = "pending", delivered = 0,
                    }
                end
            end
            round.total = round.total + used
        end
        state.available = state.available - round.total
        state.reserved = state.reserved + round.total
        state.open = round
        return plan_view(false)
    end

    local function settle(round_id, consumer_id, now, numbers, amount)
        local problem = admit(now, { n = 2, round_id, consumer_id }, numbers)
        if problem then
            return no(problem)
        end
        if not state.open or state.open.id ~= round_id then
            local _, was_closed = locate(state.finished, "id", round_id)
            return no(was_closed and "round_closed" or "unknown_round")
        end
        local share = share_of(consumer_id)
        if share == nil then
            return no("unknown_share")
        end
        if share.state ~= "pending" then
            return settlement(share, true)
        end
        if amount == nil then
            release(share, "aborted", 0)
            return settlement(share, false)
        end
        if amount > share.units then
            return no("over_delivery")
        end
        release(share, "committed", amount)
        local at, found = locate(state.consumers, "id", consumer_id)
        if found then
            local consumer = state.consumers[at]
            consumer.received = consumer.received + amount
            consumer.level = math.min(consumer.capacity, consumer.level + amount)
        end
        return settlement(share, false)
    end

    function object.commit(_, round_id, consumer_id, delivered_units, now)
        local amount = whole(delivered_units, 0) and delivered_units or -1
        return settle(round_id, consumer_id, now, { { delivered_units, 0, "invalid_units" } }, amount)
    end

    function object.abort(_, round_id, consumer_id, now)
        return settle(round_id, consumer_id, now, {}, nil)
    end

    function object.close(_, round_id, now)
        local problem = admit(now, { n = 1, round_id }, {})
        if problem then
            return no(problem)
        end
        local at, was_closed = locate(state.finished, "id", round_id)
        if was_closed then
            return closing(state.finished[at], true)
        end
        if not state.open or state.open.id ~= round_id then
            return no("unknown_round")
        end
        for _, share in ipairs(state.open.shares) do
            if share.state == "pending" then
                release(share, "aborted", 0)
            end
        end
        local entry = { id = round_id, total = state.open.total, delivered = state.open.delivered }
        table.insert(state.finished, at, entry)
        state.open = false
        return closing(entry, false)
    end

    function object.snapshot(_, _now)
        local view = {
            clock = state.clock,
            available = state.available,
            reserved = state.reserved,
            free = capacity_limit - state.available - state.reserved,
            deposited_total = state.deposited,
            delivered_total = state.delivered,
            consumers = {},
            contributors = {},
        }
        for index, consumer in ipairs(state.consumers) do
            view.consumers[index] = {
                consumer_id = consumer.id,
                priority = consumer.priority,
                capacity = consumer.capacity,
                level = consumer.level,
                demand = consumer.capacity - consumer.level,
                received = consumer.received,
            }
        end
        for index, player in ipairs(state.players) do
            view.contributors[index] = { player_id = player.id, units = player.units }
        end
        if state.open then
            local rows = {}
            for index, share in ipairs(state.open.shares) do
                rows[index] = {
                    consumer_id = share.id,
                    priority = share.priority,
                    units = share.units,
                    status = share.state,
                    delivered = share.delivered,
                    returned = share.state == "pending" and 0 or share.units - share.delivered,
                }
            end
            view.round = { round_id = state.open.id, total = state.open.total, shares = rows }
        end
        return view
    end

    function object.save(_, _now)
        return { format = "fuelration-closure-1", state = clone(state) }
    end

    return object
end

local function well_formed(data)
    if type(data) ~= "table" or data.format ~= "fuelration-closure-1" or type(data.state) ~= "table" then
        return false
    end
    local state = data.state
    for _, name in ipairs({ "consumers", "players", "ledger", "finished" }) do
        if type(state[name]) ~= "table" then
            return false
        end
    end
    return finite(state.clock) and whole(state.available, 0) and whole(state.reserved, 0)
        and whole(state.deposited, 0) and whole(state.delivered, 0)
        and (state.open == false or type(state.open) == "table")
end

function Allocator.new(options)
    return build(options, nil)
end

function Allocator.load(data, options)
    if not well_formed(data) then
        return build(options, nil)
    end
    return build(options, clone(data.state))
end

return Allocator
