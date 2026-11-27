-- Master-simulation world component. The pure stack decides which effects are
-- live; this component pushes the aggregate onto base-game components and
-- owns every listener and task it creates.

local Stack = require("statuseffects/stack")

local EFFECTS = {
    chill = { duration = 8, max_stacks = 3, policy = "refresh", tags = { "debuff", "cold" }, priority = 2, speed_mult = 0.5 },
    venom = { duration = 6, max_stacks = 2, policy = "independent", tags = { "debuff", "poison" }, priority = 3, tick_health = -2 },
    frenzy = { duration = 10, max_stacks = 2, policy = "extend", tags = { "buff" }, priority = 1, speed_mult = 1.25, damage_mult = 1.5 },
    regen = { duration = 4, max_stacks = 1, policy = "refresh", tags = { "buff", "heal" }, priority = 1, tick_health = 1 },
}
local OPTIONS = { effects = EFFECTS, extend_cap = 3 }
local CLEANSE_TAGS = { cold = true, poison = true }
local MODIFIER_KEY = "rhenium_statuseffects"
local TICK_PERIOD = 0.5

local function is_id(value)
    return type(value) == "string" and value ~= ""
end

local function is_entity(value)
    return type(value) == "table" and type(value.components) == "table" and value.IsValid ~= nil and value:IsValid()
end

local function is_alive(entity)
    local health = entity.components.health
    return health ~= nil and not health:IsDead()
end

local StatusEffects = Class(function(self, inst)
    self.inst = inst
    self.stack = Stack.new(OPTIONS)
    self.clock = 0
    self.by_id = {}
    self.by_entity = {}
    self.tick_task = inst:DoPeriodicTask(TICK_PERIOD, function()
        self:Tick()
    end, TICK_PERIOD)
end)

-- An explicit `now` lets a caller drive time. Without one the simulation
-- clock is used, but never a value behind a time the stack already accepted.
function StatusEffects:_Now(now)
    if now == nil then
        return math.max(GetTime(), self.clock)
    end
    return now
end

function StatusEffects:_Accept(now)
    if type(now) == "number" and now > self.clock then
        self.clock = now
    end
end

function StatusEffects:_ClearModifiers(entity)
    if entity.components == nil then
        return
    end
    local locomotor = entity.components.locomotor
    if locomotor ~= nil then
        locomotor:RemoveExternalSpeedMultiplier(self.inst, MODIFIER_KEY)
    end
    local combat = entity.components.combat
    if combat ~= nil and combat.externaldamagemultipliers ~= nil then
        combat.externaldamagemultipliers:RemoveModifier(self.inst, MODIFIER_KEY)
    end
end

function StatusEffects:_Release(record, now)
    local entity = record.entity
    self.by_entity[entity] = nil
    self.by_id[record.stable_id] = nil
    entity:RemoveEventCallback("death", record.on_death)
    entity:RemoveEventCallback("onremove", record.on_remove)
    self:_ClearModifiers(entity)
    now = self:_Now(now)
    self.stack:remove_target(record.stable_id, now)
    self:_Accept(now)
end

function StatusEffects:Track(entity, stable_id)
    if not TheWorld.ismastersim or not is_entity(entity) or not is_id(stable_id) or not is_alive(entity) then
        return false
    end
    local existing = self.by_entity[entity]
    if existing ~= nil then
        return existing.stable_id == stable_id
    end
    if self.by_id[stable_id] ~= nil then
        return false
    end
    local now = self:_Now()
    if not self.stack:add_target(stable_id, now).ok then
        return false
    end
    self:_Accept(now)

    -- The record keeps the exact function objects so they can be removed.
    local record = { entity = entity, stable_id = stable_id }
    record.on_death = function()
        if self.by_entity[entity] == record then
            self:_Release(record)
        end
    end
    record.on_remove = record.on_death
    entity:ListenForEvent("death", record.on_death)
    entity:ListenForEvent("onremove", record.on_remove)
    self.by_entity[entity] = record
    self.by_id[stable_id] = record
    self:Reconcile(entity, now)
    return true
end

function StatusEffects:Apply(request_id, entity, effect_id, source_entity, now)
    if not TheWorld.ismastersim then
        return { ok = false, code = "not_authoritative" }
    end
    local record = entity ~= nil and self.by_entity[entity] or nil
    if record == nil then
        return { ok = false, code = "unknown_target" }
    end
    local source_id = nil
    if source_entity ~= nil then
        local source = self.by_entity[source_entity]
        if source == nil then
            return { ok = false, code = "unknown_source" }
        end
        source_id = source.stable_id
    end
    now = self:_Now(now)
    local result = self.stack:apply(request_id, record.stable_id, effect_id, source_id, now)
    if result.code ~= "invalid_time" and result.code ~= "stale_time" then
        self:_Accept(now)
        self:Reconcile(entity, now)
    end
    return result
end

function StatusEffects:Dispel(entity, tag, max_count, now)
    if not TheWorld.ismastersim then
        return { ok = false, code = "not_authoritative" }
    end
    local record = entity ~= nil and self.by_entity[entity] or nil
    if record == nil then
        return { ok = false, code = "unknown_target" }
    end
    now = self:_Now(now)
    local result = self.stack:dispel(record.stable_id, tag, max_count, now)
    if result.code ~= "invalid_time" and result.code ~= "stale_time" then
        self:_Accept(now)
        self:Reconcile(entity, now)
    end
    return result
end

-- Player-driven entry. The target is always the calling player: identity is
-- read from `player.userid`, the tag must be whitelisted and one instance is
-- removed per call.
function StatusEffects:Cleanse(player, tag, now)
    if not TheWorld.ismastersim then
        return { ok = false, code = "not_authoritative" }
    end
    if type(tag) ~= "string" or not CLEANSE_TAGS[tag] then
        return { ok = false, code = "forbidden_tag" }
    end
    local userid = type(player) == "table" and player.userid or nil
    local record = is_id(userid) and self.by_id[userid] or nil
    if record == nil or record.entity ~= player then
        return { ok = false, code = "unknown_target" }
    end
    return self:Dispel(player, tag, 1, now)
end

-- Pushes the live aggregate onto the base-game components. A neutral
-- aggregate removes the modifier instead of storing a multiplier of 1.
function StatusEffects:Reconcile(entity, now)
    if not TheWorld.ismastersim then
        return nil
    end
    local record = entity ~= nil and self.by_entity[entity] or nil
    if record == nil or not entity:IsValid() then
        return nil
    end
    now = self:_Now(now)
    local aggregate = self.stack:modifiers(record.stable_id, now)
    if not aggregate.ok then
        return nil
    end
    self:_Accept(now)
    local locomotor = entity.components.locomotor
    if locomotor ~= nil then
        if aggregate.speed_mult ~= 1 then
            locomotor:SetExternalSpeedMultiplier(self.inst, MODIFIER_KEY, aggregate.speed_mult)
        else
            locomotor:RemoveExternalSpeedMultiplier(self.inst, MODIFIER_KEY)
        end
    end
    local combat = entity.components.combat
    if combat ~= nil and combat.externaldamagemultipliers ~= nil then
        if aggregate.damage_mult ~= 1 then
            combat.externaldamagemultipliers:SetModifier(self.inst, aggregate.damage_mult, MODIFIER_KEY)
        else
            combat.externaldamagemultipliers:RemoveModifier(self.inst, MODIFIER_KEY)
        end
    end
    return aggregate
end

function StatusEffects:_SortedIds()
    local ids = {}
    for stable_id in pairs(self.by_id) do
        ids[#ids + 1] = stable_id
    end
    table.sort(ids)
    return ids
end

-- Applies the health accrued since the previous tick. Dead or removed
-- entities are never touched, so healing can not revive anything.
function StatusEffects:Tick(now)
    if not TheWorld.ismastersim then
        return false
    end
    now = self:_Now(now)
    local deltas = self.stack:tick(now)
    if deltas == nil then
        return false
    end
    self:_Accept(now)
    for index = 1, #deltas do
        local delta = deltas[index]
        local record = self.by_id[delta.target_id]
        if record ~= nil and record.entity:IsValid() and is_alive(record.entity) then
            record.entity.components.health:DoDelta(delta.amount, true, delta.effect_id)
        end
    end
    for _, stable_id in ipairs(self:_SortedIds()) do
        local record = self.by_id[stable_id]
        if record ~= nil then
            self:Reconcile(record.entity, now)
        end
    end
    return true
end

function StatusEffects:OnSave()
    local now = self:_Now()
    local data = self.stack:save(now)
    self:_Accept(now)
    return { version = 1, stack = data }
end

-- GetTime() restarts with the process, so the stack is rebased onto the
-- current simulation time. Entities tracked in this process stay tracked.
function StatusEffects:OnLoad(data)
    local now = GetTime()
    local saved = type(data) == "table" and data.version == 1 and data.stack or nil
    self.stack = Stack.load(saved, OPTIONS, now)
    self.clock = now
    for _, stable_id in ipairs(self:_SortedIds()) do
        self.stack:add_target(stable_id, now)
        self:Reconcile(self.by_id[stable_id].entity, now)
    end
end

function StatusEffects:OnRemoveFromEntity()
    if self.tick_task ~= nil then
        self.tick_task:Cancel()
        self.tick_task = nil
    end
    for _, stable_id in ipairs(self:_SortedIds()) do
        self:_Release(self.by_id[stable_id])
    end
end

function StatusEffects:GetDebugString()
    return string.format("tracked=%d clock=%.2f", #self:_SortedIds(), self.clock)
end

return StatusEffects
