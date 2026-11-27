-- Status effect manager built as a closure over one flat instance journal.
-- Instances are never settled early: every instance keeps the history of its
-- stack count as segments, and `tick` integrates those segments on demand.
-- An instance stays in the journal until a tick has consumed its whole life.

local M = {}

local INF = math.huge

local function valid_time(t)
    return type(t) == "number" and t == t and t >= 0 and t ~= INF
end

local function ident(v)
    return type(v) == "string" and #v > 0
end

local function whole_positive(v)
    return type(v) == "number" and v == v and v ~= INF and v >= 1 and v % 1 == 0
end

local function clone(t)
    local out = {}
    for k, v in pairs(t) do
        if type(v) == "table" then
            out[k] = clone(v)
        else
            out[k] = v
        end
    end
    return out
end

local function refuse(code)
    return { ok = false, code = code }
end

-- state: { clock, last_tick, counter, known = {id=true}, journal = {...}, log = { {id, result} }, seen = {id=index} }
local function construct(options, state)
    local defs = (type(options) == "table" and type(options.effects) == "table") and options.effects or {}
    local cap = 3
    if type(options) == "table" and type(options.extend_cap) == "number" and options.extend_cap >= 1
        and options.extend_cap ~= INF then
        cap = options.extend_cap
    end

    local api = {}

    -- The moment an instance stopped existing: a forced end or its expiry.
    local function end_of(item)
        return item.ended_at or item.expires_at
    end

    local function alive(item, now)
        return item.ended_at == nil and now < item.expires_at
    end

    local function gate(now)
        if not valid_time(now) then
            return "invalid_time"
        end
        if now < state.clock then
            return "stale_time"
        end
        state.clock = now
        return nil
    end

    local function living(target_id, now, effect_id)
        local out = {}
        for _, item in ipairs(state.journal) do
            if item.target_id == target_id and alive(item, now)
                and (effect_id == nil or item.effect_id == effect_id) then
                out[#out + 1] = item
            end
        end
        table.sort(out, function(x, y) return x.seq < y.seq end)
        return out
    end

    -- Integral of the stack count of `item` over (from, to], clipped to its life.
    local function stack_seconds(item, from, to)
        local stop = math.min(to, end_of(item))
        local total = 0
        for index, segment in ipairs(item.segments) do
            local next_segment = item.segments[index + 1]
            local lo = math.max(segment.from, from)
            local hi = math.min(next_segment ~= nil and next_segment.from or INF, stop)
            if hi > lo then
                total = total + segment.stacks * (hi - lo)
            end
        end
        return total
    end

    function api:add_target(target_id, now)
        local code = gate(now)
        if code then return refuse(code) end
        if not ident(target_id) then return refuse("invalid_argument") end
        state.known[target_id] = true
        return { ok = true, code = "tracked", target_id = target_id }
    end

    function api:remove_target(target_id, now)
        local code = gate(now)
        if code then return refuse(code) end
        if not ident(target_id) then return refuse("invalid_argument") end
        if not state.known[target_id] then return refuse("unknown_target") end
        local cleared, rest = 0, {}
        for _, item in ipairs(state.journal) do
            if item.target_id == target_id then
                if alive(item, now) then cleared = cleared + 1 end
            else
                rest[#rest + 1] = item
            end
        end
        state.journal = rest
        state.known[target_id] = nil
        return { ok = true, code = "removed", target_id = target_id, count = cleared }
    end

    local function spawn(target_id, effect_id, source_id, def, now)
        state.counter = state.counter + 1
        local item = {
            target_id = target_id,
            effect_id = effect_id,
            seq = state.counter,
            applied_at = now,
            expires_at = now + def.duration,
            source_id = source_id,
            segments = { { from = now, stacks = 1 } },
        }
        state.journal[#state.journal + 1] = item
        return item
    end

    local function current_stacks(item)
        return item.segments[#item.segments].stacks
    end

    local function add_stack(item, def, now)
        local wanted = math.min(current_stacks(item) + 1, def.max_stacks)
        if wanted ~= current_stacks(item) then
            item.segments[#item.segments + 1] = { from = now, stacks = wanted }
        end
        return wanted
    end

    local function perform(target_id, effect_id, source_id, now)
        if not (ident(target_id) and ident(effect_id) and (source_id == nil or ident(source_id))) then
            return refuse("invalid_argument")
        end
        local def = defs[effect_id]
        if def == nil then return refuse("unknown_effect") end
        if not state.known[target_id] then return refuse("unknown_target") end

        local present = living(target_id, now, effect_id)
        local item, code, stacks
        if def.policy == "independent" then
            code = (#present == 0 and "applied") or (#present < def.max_stacks and "stacked") or "replaced"
            local remaining = #present
            if code == "replaced" then
                present[1].ended_at = now
                remaining = remaining - 1
            end
            item = spawn(target_id, effect_id, source_id, def, now)
            stacks = remaining + 1
        elseif #present == 0 then
            code, item, stacks = "applied", spawn(target_id, effect_id, source_id, def, now), 1
        else
            item = present[1]
            stacks = add_stack(item, def, now)
            item.source_id = source_id
            if def.policy == "extend" then
                code = "extended"
                local left = (item.expires_at - now) + def.duration
                local limit = cap * def.duration
                item.expires_at = now + (left < limit and left or limit)
            else
                code = "refreshed"
                item.expires_at = now + def.duration
            end
        end
        return {
            ok = true, code = code, target_id = target_id, effect_id = effect_id,
            seq = item.seq, stacks = stacks, expires_at = item.expires_at,
        }
    end

    function api:apply(request_id, target_id, effect_id, source_id, now)
        local code = gate(now)
        if code then return refuse(code) end
        if not ident(request_id) then return refuse("invalid_argument") end
        local index = state.seen[request_id]
        if index == nil then
            state.log[#state.log + 1] = { id = request_id, result = perform(target_id, effect_id, source_id, now) }
            index = #state.log
            state.seen[request_id] = index
        end
        return clone(state.log[index].result)
    end

    local function dispel_before(x, y)
        local px, py = defs[x.effect_id].priority, defs[y.effect_id].priority
        if px ~= py then return px > py end
        if x.applied_at ~= y.applied_at then return x.applied_at < y.applied_at end
        if x.effect_id ~= y.effect_id then return x.effect_id < y.effect_id end
        return x.seq < y.seq
    end

    function api:dispel(target_id, tag, max_count, now)
        local code = gate(now)
        if code then return refuse(code) end
        if not ident(target_id) or not ident(tag) or not (max_count == nil or whole_positive(max_count)) then
            return refuse("invalid_argument")
        end
        if not state.known[target_id] then return refuse("unknown_target") end
        local pool = {}
        for _, item in ipairs(living(target_id, now)) do
            for _, candidate in ipairs(defs[item.effect_id].tags or {}) do
                if candidate == tag then
                    pool[#pool + 1] = item
                    break
                end
            end
        end
        -- Repeatedly pick the best remaining candidate until the budget is spent.
        local removed = {}
        while #pool > 0 and (max_count == nil or #removed < max_count) do
            local best = 1
            for index = 2, #pool do
                if dispel_before(pool[index], pool[best]) then best = index end
            end
            local item = table.remove(pool, best)
            item.ended_at = now
            removed[#removed + 1] = { effect_id = item.effect_id, seq = item.seq, stacks = current_stacks(item) }
        end
        return { ok = true, code = "dispelled", target_id = target_id, count = #removed, removed = removed }
    end

    function api:tick(now)
        local code = gate(now)
        if code then return nil, code end
        local sums, keys, keep = {}, {}, {}
        for _, item in ipairs(state.journal) do
            local rate = defs[item.effect_id] and defs[item.effect_id].tick_health
            if type(rate) == "number" then
                local seconds = stack_seconds(item, state.last_tick, now)
                if seconds ~= 0 then
                    local bucket = sums[item.target_id]
                    if bucket == nil then
                        bucket = {}
                        sums[item.target_id] = bucket
                    end
                    if bucket[item.effect_id] == nil then
                        keys[#keys + 1] = { item.target_id, item.effect_id }
                        bucket[item.effect_id] = 0
                    end
                    bucket[item.effect_id] = bucket[item.effect_id] + rate * seconds
                end
            end
            if end_of(item) > now then
                -- Only the segment that is current at `now` matters from here on.
                local last = item.segments[#item.segments]
                item.segments = { { from = last.from, stacks = last.stacks } }
                keep[#keep + 1] = item
            end
        end
        state.journal = keep
        state.last_tick = now
        table.sort(keys, function(x, y)
            if x[1] ~= y[1] then return x[1] < y[1] end
            return x[2] < y[2]
        end)
        local out = {}
        for _, key in ipairs(keys) do
            local amount = sums[key[1]][key[2]]
            if amount ~= 0 then
                out[#out + 1] = { target_id = key[1], effect_id = key[2], amount = amount }
            end
        end
        return out
    end

    function api:modifiers(target_id, now)
        local code = gate(now)
        if code then return refuse(code) end
        if not ident(target_id) then return refuse("invalid_argument") end
        if not state.known[target_id] then return refuse("unknown_target") end
        local present = living(target_id, now)
        local result = { ok = true, code = "ok", target_id = target_id,
            speed_mult = 1, damage_mult = 1, tick_health = 0, count = #present }
        for _, item in ipairs(present) do
            local def, n = defs[item.effect_id], current_stacks(item)
            if def.speed_mult ~= nil then result.speed_mult = result.speed_mult * def.speed_mult ^ n end
            if def.damage_mult ~= nil then result.damage_mult = result.damage_mult * def.damage_mult ^ n end
            if def.tick_health ~= nil then result.tick_health = result.tick_health + def.tick_health * n end
        end
        return result
    end

    function api:snapshot(now)
        local code = gate(now)
        if code then return nil, code end
        local out = {}
        for _, item in ipairs(state.journal) do
            if alive(item, now) then
                out[#out + 1] = {
                    target_id = item.target_id, effect_id = item.effect_id, seq = item.seq,
                    stacks = current_stacks(item), applied_at = item.applied_at,
                    expires_at = item.expires_at, remaining = item.expires_at - now,
                    source_id = item.source_id,
                }
            end
        end
        table.sort(out, function(x, y)
            if x.target_id ~= y.target_id then return x.target_id < y.target_id end
            if x.effect_id ~= y.effect_id then return x.effect_id < y.effect_id end
            return x.seq < y.seq
        end)
        return out
    end

    function api:save(now)
        local code = gate(now)
        if code then return nil, code end
        local names = {}
        for id in pairs(state.known) do names[#names + 1] = id end
        table.sort(names)
        return {
            format = "statuseffects-journal-1",
            saved_at = now,
            last_tick = state.last_tick,
            counter = state.counter,
            known = names,
            journal = clone(state.journal),
            log = clone(state.log),
        }
    end

    return api
end

local function empty_state(clock)
    return { clock = clock, last_tick = 0, counter = 0, known = {}, journal = {}, log = {}, seen = {} }
end

function M.new(options)
    return construct(options, empty_state(0))
end

local function restore_item(raw, delta, defs)
    if type(raw) ~= "table" or defs[raw.effect_id] == nil or type(raw.segments) ~= "table"
        or #raw.segments == 0 or type(raw.expires_at) ~= "number" or type(raw.applied_at) ~= "number"
        or type(raw.seq) ~= "number" or not ident(raw.target_id) then
        return nil
    end
    local item = {
        target_id = raw.target_id, effect_id = raw.effect_id, seq = raw.seq,
        applied_at = raw.applied_at + delta, expires_at = raw.expires_at + delta,
        ended_at = type(raw.ended_at) == "number" and raw.ended_at + delta or nil,
        source_id = ident(raw.source_id) and raw.source_id or nil,
        segments = {},
    }
    for _, segment in ipairs(raw.segments) do
        if type(segment) ~= "table" or type(segment.from) ~= "number" or not whole_positive(segment.stacks) then
            return nil
        end
        item.segments[#item.segments + 1] = { from = segment.from + delta, stacks = segment.stacks }
    end
    return item
end

function M.load(data, options, now)
    local clock = valid_time(now) and now or 0
    local state = empty_state(clock)
    local defs = (type(options) == "table" and type(options.effects) == "table") and options.effects or {}
    if type(data) == "table" and data.format == "statuseffects-journal-1" and valid_time(data.saved_at) then
        local delta = clock - data.saved_at
        -- The previous tick moves with everything else; it may become negative.
        state.last_tick = (type(data.last_tick) == "number" and data.last_tick or 0) + delta
        state.counter = whole_positive(data.counter) and data.counter or 0
        for _, id in ipairs(type(data.known) == "table" and data.known or {}) do
            if ident(id) then state.known[id] = true end
        end
        for _, raw in ipairs(type(data.journal) == "table" and data.journal or {}) do
            local item = restore_item(raw, delta, defs)
            if item ~= nil and state.known[item.target_id] then
                state.journal[#state.journal + 1] = item
                if item.seq > state.counter then state.counter = item.seq end
            end
        end
        for _, entry in ipairs(type(data.log) == "table" and data.log or {}) do
            if type(entry) == "table" and ident(entry.id) and type(entry.result) == "table"
                and state.seen[entry.id] == nil then
                state.log[#state.log + 1] = { id = entry.id, result = clone(entry.result) }
                state.seen[entry.id] = #state.log
            end
        end
    end
    return construct(options, state)
end

return M
