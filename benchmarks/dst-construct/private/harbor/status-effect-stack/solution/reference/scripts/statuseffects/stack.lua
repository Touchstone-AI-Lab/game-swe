-- Pure status-effect stack manager. No DST globals: every timestamp arrives
-- through a `now` argument, so the module is deterministic and testable.

local Stack = {}
Stack.__index = Stack

local DEFAULT_EXTEND_CAP = 3

local function is_time(value)
    return type(value) == "number" and value == value and value >= 0 and value < math.huge
end

local function is_finite(value)
    return type(value) == "number" and value == value and value > -math.huge and value < math.huge
end

local function is_id(value)
    return type(value) == "string" and value ~= ""
end

local function is_positive_integer(value)
    return is_finite(value) and value >= 1 and math.floor(value) == value
end

local function fail(code)
    return { ok = false, code = code }
end

local function shallow_copy(source)
    local target = {}
    for key, value in pairs(source) do
        target[key] = value
    end
    return target
end

local function sorted_keys(map)
    local keys = {}
    for key in pairs(map) do
        keys[#keys + 1] = key
    end
    table.sort(keys)
    return keys
end

local function has_tag(definition, tag)
    local tags = definition.tags
    if type(tags) ~= "table" then
        return false
    end
    for index = 1, #tags do
        if tags[index] == tag then
            return true
        end
    end
    return false
end

-- Each stack multiplies once, so `stacks` stacks contribute mult ^ stacks.
local function stacked_multiplier(mult, stacks)
    local value = 1
    for _ = 1, stacks do
        value = value * mult
    end
    return value
end

local function build(options, clock)
    options = type(options) == "table" and options or {}
    local self = setmetatable({}, Stack)
    self.effects = type(options.effects) == "table" and options.effects or {}
    self.extend_cap = is_finite(options.extend_cap) and options.extend_cap >= 1
        and options.extend_cap or DEFAULT_EXTEND_CAP
    self.clock = clock
    self.next_seq = 1
    self.targets = {}
    self.history = {}
    self.history_order = {}
    return self
end

function Stack.new(options)
    return build(options, 0)
end

-- Accrue health-over-time up to `now`, clipped to every instance's expiry,
-- then drop the instances that are expired at `now`. Accrual lands in a
-- per-target, per-effect accumulator that only `tick` hands out, which makes
-- the reported totals independent of how often anything is called.
function Stack:_settle(now)
    for _, target in pairs(self.targets) do
        local kept = {}
        for index = 1, #target.instances do
            local instance = target.instances[index]
            local definition = self.effects[instance.effect_id]
            local upto = math.min(now, instance.expires_at)
            if upto > instance.cursor then
                if definition ~= nil and is_finite(definition.tick_health) then
                    local amount = definition.tick_health * instance.stacks * (upto - instance.cursor)
                    target.pending[instance.effect_id] = (target.pending[instance.effect_id] or 0) + amount
                end
                instance.cursor = upto
            end
            if now < instance.expires_at then
                kept[#kept + 1] = instance
            end
        end
        target.instances = kept
    end
end

-- Shared entry gate: validates time, advances the clock and settles.
function Stack:_enter(now)
    if not is_time(now) then
        return "invalid_time"
    end
    if now < self.clock then
        return "stale_time"
    end
    self.clock = now
    self:_settle(now)
    return nil
end

function Stack:add_target(target_id, now)
    local code = self:_enter(now)
    if code ~= nil then
        return fail(code)
    end
    if not is_id(target_id) then
        return fail("invalid_argument")
    end
    if self.targets[target_id] == nil then
        self.targets[target_id] = { instances = {}, pending = {} }
    end
    return { ok = true, code = "tracked", target_id = target_id }
end

local function live_of_effect(target, effect_id)
    local found = {}
    for index = 1, #target.instances do
        if target.instances[index].effect_id == effect_id then
            found[#found + 1] = target.instances[index]
        end
    end
    return found
end

function Stack:_new_instance(target, effect_id, source_id, definition, now)
    local instance = {
        effect_id = effect_id,
        seq = self.next_seq,
        stacks = 1,
        applied_at = now,
        expires_at = now + definition.duration,
        cursor = now,
        source_id = source_id,
    }
    self.next_seq = self.next_seq + 1
    target.instances[#target.instances + 1] = instance
    return instance
end

function Stack:_apply(target_id, effect_id, source_id, now)
    if not is_id(target_id) or not is_id(effect_id) or (source_id ~= nil and not is_id(source_id)) then
        return fail("invalid_argument")
    end
    local definition = self.effects[effect_id]
    if type(definition) ~= "table" then
        return fail("unknown_effect")
    end
    local target = self.targets[target_id]
    if target == nil then
        return fail("unknown_target")
    end

    local live = live_of_effect(target, effect_id)
    local instance, code, stacks
    if definition.policy == "independent" then
        if #live == 0 then
            code = "applied"
        elseif #live < definition.max_stacks then
            code = "stacked"
        else
            -- Instances are kept in sequence order, so live[1] is the oldest.
            code = "replaced"
            local oldest = live[1]
            for index = #target.instances, 1, -1 do
                if target.instances[index] == oldest then
                    table.remove(target.instances, index)
                end
            end
            table.remove(live, 1)
        end
        instance = self:_new_instance(target, effect_id, source_id, definition, now)
        stacks = #live + 1
    elseif #live == 0 then
        code = "applied"
        instance = self:_new_instance(target, effect_id, source_id, definition, now)
        stacks = 1
    else
        instance = live[1]
        instance.stacks = math.min(instance.stacks + 1, definition.max_stacks)
        instance.source_id = source_id
        if definition.policy == "extend" then
            code = "extended"
            local remaining = instance.expires_at - now + definition.duration
            instance.expires_at = now + math.min(remaining, self.extend_cap * definition.duration)
        else
            code = "refreshed"
            instance.expires_at = now + definition.duration
        end
        stacks = instance.stacks
    end
    return {
        ok = true,
        code = code,
        target_id = target_id,
        effect_id = effect_id,
        seq = instance.seq,
        stacks = stacks,
        expires_at = instance.expires_at,
    }
end

function Stack:apply(request_id, target_id, effect_id, source_id, now)
    local code = self:_enter(now)
    if code ~= nil then
        return fail(code)
    end
    if not is_id(request_id) then
        return fail("invalid_argument")
    end
    local recorded = self.history[request_id]
    if recorded ~= nil then
        return shallow_copy(recorded)
    end
    local result = self:_apply(target_id, effect_id, source_id, now)
    self.history[request_id] = result
    self.history_order[#self.history_order + 1] = request_id
    return shallow_copy(result)
end

function Stack:dispel(target_id, tag, max_count, now)
    local code = self:_enter(now)
    if code ~= nil then
        return fail(code)
    end
    if not is_id(target_id) or not is_id(tag) or (max_count ~= nil and not is_positive_integer(max_count)) then
        return fail("invalid_argument")
    end
    local target = self.targets[target_id]
    if target == nil then
        return fail("unknown_target")
    end

    local matching = {}
    for index = 1, #target.instances do
        local instance = target.instances[index]
        if has_tag(self.effects[instance.effect_id], tag) then
            matching[#matching + 1] = instance
        end
    end
    local effects = self.effects
    table.sort(matching, function(left, right)
        local left_priority = effects[left.effect_id].priority
        local right_priority = effects[right.effect_id].priority
        if left_priority ~= right_priority then
            return left_priority > right_priority
        end
        if left.applied_at ~= right.applied_at then
            return left.applied_at < right.applied_at
        end
        if left.effect_id ~= right.effect_id then
            return left.effect_id < right.effect_id
        end
        return left.seq < right.seq
    end)

    local doomed, removed = {}, {}
    for index = 1, #matching do
        if max_count ~= nil and index > max_count then
            break
        end
        local instance = matching[index]
        doomed[instance] = true
        removed[#removed + 1] = { effect_id = instance.effect_id, seq = instance.seq, stacks = instance.stacks }
    end
    local kept = {}
    for index = 1, #target.instances do
        if not doomed[target.instances[index]] then
            kept[#kept + 1] = target.instances[index]
        end
    end
    target.instances = kept
    return { ok = true, code = "dispelled", target_id = target_id, count = #removed, removed = removed }
end

function Stack:remove_target(target_id, now)
    local code = self:_enter(now)
    if code ~= nil then
        return fail(code)
    end
    if not is_id(target_id) then
        return fail("invalid_argument")
    end
    local target = self.targets[target_id]
    if target == nil then
        return fail("unknown_target")
    end
    -- The accumulator goes with the target: a dead target owes nothing.
    self.targets[target_id] = nil
    return { ok = true, code = "removed", target_id = target_id, count = #target.instances }
end

function Stack:tick(now)
    local code = self:_enter(now)
    if code ~= nil then
        return nil, code
    end
    local deltas = {}
    local target_ids = sorted_keys(self.targets)
    for _, target_id in ipairs(target_ids) do
        local target = self.targets[target_id]
        local effect_ids = sorted_keys(target.pending)
        for _, effect_id in ipairs(effect_ids) do
            local amount = target.pending[effect_id]
            if amount ~= 0 then
                deltas[#deltas + 1] = { target_id = target_id, effect_id = effect_id, amount = amount }
            end
        end
        target.pending = {}
    end
    return deltas
end

function Stack:modifiers(target_id, now)
    local code = self:_enter(now)
    if code ~= nil then
        return fail(code)
    end
    if not is_id(target_id) then
        return fail("invalid_argument")
    end
    local target = self.targets[target_id]
    if target == nil then
        return fail("unknown_target")
    end
    local speed, damage, health = 1, 1, 0
    for index = 1, #target.instances do
        local instance = target.instances[index]
        local definition = self.effects[instance.effect_id]
        if is_finite(definition.speed_mult) then
            speed = speed * stacked_multiplier(definition.speed_mult, instance.stacks)
        end
        if is_finite(definition.damage_mult) then
            damage = damage * stacked_multiplier(definition.damage_mult, instance.stacks)
        end
        if is_finite(definition.tick_health) then
            health = health + definition.tick_health * instance.stacks
        end
    end
    return {
        ok = true,
        code = "ok",
        target_id = target_id,
        speed_mult = speed,
        damage_mult = damage,
        tick_health = health,
        count = #target.instances,
    }
end

function Stack:snapshot(now)
    local code = self:_enter(now)
    if code ~= nil then
        return nil, code
    end
    local rows = {}
    for target_id, target in pairs(self.targets) do
        for index = 1, #target.instances do
            local instance = target.instances[index]
            rows[#rows + 1] = {
                target_id = target_id,
                effect_id = instance.effect_id,
                seq = instance.seq,
                stacks = instance.stacks,
                applied_at = instance.applied_at,
                expires_at = instance.expires_at,
                remaining = instance.expires_at - now,
                source_id = instance.source_id,
            }
        end
    end
    table.sort(rows, function(left, right)
        if left.target_id ~= right.target_id then
            return left.target_id < right.target_id
        end
        if left.effect_id ~= right.effect_id then
            return left.effect_id < right.effect_id
        end
        return left.seq < right.seq
    end)
    return rows
end

-- The saved table holds only strings, numbers, booleans and nested tables.
function Stack:save(now)
    local code = self:_enter(now)
    if code ~= nil then
        return nil, code
    end
    local data = { version = 1, clock = now, next_seq = self.next_seq, targets = {}, history = {} }
    for _, target_id in ipairs(sorted_keys(self.targets)) do
        local target = self.targets[target_id]
        local saved = { id = target_id, instances = {}, pending = {} }
        for index = 1, #target.instances do
            saved.instances[index] = shallow_copy(target.instances[index])
        end
        for _, effect_id in ipairs(sorted_keys(target.pending)) do
            saved.pending[#saved.pending + 1] = { effect_id = effect_id, amount = target.pending[effect_id] }
        end
        data.targets[#data.targets + 1] = saved
    end
    for index = 1, #self.history_order do
        local request_id = self.history_order[index]
        data.history[index] = { request_id = request_id, result = shallow_copy(self.history[request_id]) }
    end
    return data
end

local function load_instance(self, raw, shift)
    if type(raw) ~= "table" or not is_id(raw.effect_id) or type(self.effects[raw.effect_id]) ~= "table" then
        return nil
    end
    if not is_positive_integer(raw.seq) or not is_positive_integer(raw.stacks)
        or not is_finite(raw.applied_at) or not is_finite(raw.expires_at) or not is_finite(raw.cursor) then
        return nil
    end
    return {
        effect_id = raw.effect_id,
        seq = raw.seq,
        stacks = raw.stacks,
        applied_at = raw.applied_at + shift,
        expires_at = raw.expires_at + shift,
        cursor = raw.cursor + shift,
        source_id = is_id(raw.source_id) and raw.source_id or nil,
    }
end

-- Every saved timestamp is rebased by (now - saved clock): remaining
-- durations, instance ages and the accrual cursor survive a process whose
-- clock restarted. Recorded request results are returned verbatim.
function Stack.load(data, options, now)
    local clock = is_time(now) and now or 0
    local self = build(options, clock)
    if type(data) ~= "table" or data.version ~= 1 or not is_time(data.clock) then
        return self
    end
    local shift = clock - data.clock
    if type(data.targets) == "table" then
        for _, saved in ipairs(data.targets) do
            if type(saved) == "table" and is_id(saved.id) and self.targets[saved.id] == nil then
                local target = { instances = {}, pending = {} }
                if type(saved.instances) == "table" then
                    for _, raw in ipairs(saved.instances) do
                        local instance = load_instance(self, raw, shift)
                        if instance ~= nil then
                            target.instances[#target.instances + 1] = instance
                            if instance.seq >= self.next_seq then
                                self.next_seq = instance.seq + 1
                            end
                        end
                    end
                end
                table.sort(target.instances, function(left, right)
                    return left.seq < right.seq
                end)
                if type(saved.pending) == "table" then
                    for _, entry in ipairs(saved.pending) do
                        if type(entry) == "table" and is_id(entry.effect_id) and is_finite(entry.amount)
                            and type(self.effects[entry.effect_id]) == "table" then
                            target.pending[entry.effect_id] = (target.pending[entry.effect_id] or 0) + entry.amount
                        end
                    end
                end
                self.targets[saved.id] = target
            end
        end
    end
    if is_positive_integer(data.next_seq) and data.next_seq > self.next_seq then
        self.next_seq = data.next_seq
    end
    if type(data.history) == "table" then
        for _, entry in ipairs(data.history) do
            if type(entry) == "table" and is_id(entry.request_id) and type(entry.result) == "table"
                and self.history[entry.request_id] == nil then
                self.history[entry.request_id] = shallow_copy(entry.result)
                self.history_order[#self.history_order + 1] = entry.request_id
            end
        end
    end
    return self
end

return Stack
