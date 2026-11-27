-- World component for timed status effects (master simulation only).
-- Bindings live in one ordered array; each binding owns its two listeners.
-- The affected entity itself is the modifier source, so base-game cleanup of
-- a removed source and this component's cleanup agree with each other.

local Manager = require("statuseffects/stack")

local CONFIG = {
    extend_cap = 3,
    effects = {
        chill = { duration = 8, max_stacks = 3, policy = "refresh", tags = { "debuff", "cold" }, priority = 2, speed_mult = 0.5 },
        venom = { duration = 6, max_stacks = 2, policy = "independent", tags = { "debuff", "poison" }, priority = 3, tick_health = -2 },
        frenzy = { duration = 10, max_stacks = 2, policy = "extend", tags = { "buff" }, priority = 1, speed_mult = 1.25, damage_mult = 1.5 },
        regen = { duration = 4, max_stacks = 1, policy = "refresh", tags = { "buff", "heal" }, priority = 1, tick_health = 1 },
    },
}
local SELF_CLEANSE = { cold = true, poison = true }
local KEY = "statuseffects_aggregate"
local PERIOD = 1

local function usable_id(value)
    return type(value) == "string" and value ~= ""
end

local function can_be_tracked(entity)
    if type(entity) ~= "table" or type(entity.IsValid) ~= "function" or not entity:IsValid() then
        return false
    end
    local health = entity.components ~= nil and entity.components.health or nil
    return health ~= nil and not health:IsDead()
end

local function strip_modifiers(entity)
    local parts = entity.components
    if parts == nil then
        return
    end
    if parts.locomotor ~= nil then
        parts.locomotor:RemoveExternalSpeedMultiplier(entity, KEY)
    end
    if parts.combat ~= nil then
        parts.combat.externaldamagemultipliers:RemoveModifier(entity, KEY)
    end
end

local function write_modifiers(entity, aggregate)
    local parts = entity.components
    if parts.locomotor ~= nil then
        if aggregate.speed_mult == 1 then
            parts.locomotor:RemoveExternalSpeedMultiplier(entity, KEY)
        else
            parts.locomotor:SetExternalSpeedMultiplier(entity, KEY, aggregate.speed_mult)
        end
    end
    if parts.combat ~= nil then
        local list = parts.combat.externaldamagemultipliers
        if aggregate.damage_mult == 1 then
            list:RemoveModifier(entity, KEY)
        else
            list:SetModifier(entity, aggregate.damage_mult, KEY)
        end
    end
end

local StatusEffects = Class(function(self, inst)
    self.inst = inst
    self.manager = Manager.new(CONFIG)
    self.latest = 0
    self.bindings = {}

    self.on_player_joined = function(_, player)
        if player ~= nil and usable_id(player.userid) then
            self:Track(player, player.userid)
        end
    end
    inst:ListenForEvent("ms_playerjoined", self.on_player_joined)

    self.periodic = inst:DoPeriodicTask(PERIOD, function()
        self:Tick()
    end)
end)

-- Time handed to the manager: the explicit value, or the simulation time
-- clamped so that it never falls behind something the manager accepted.
function StatusEffects:When(now)
    if now ~= nil then
        return now
    end
    local sim = GetTime()
    return sim > self.latest and sim or self.latest
end

function StatusEffects:Accepted(now)
    if now > self.latest then
        self.latest = now
    end
end

function StatusEffects:Find(entity, stable_id)
    for index, binding in ipairs(self.bindings) do
        if (entity ~= nil and binding.entity == entity) or (stable_id ~= nil and binding.id == stable_id) then
            return binding, index
        end
    end
    return nil
end

function StatusEffects:Forget(binding)
    local _, index = self:Find(binding.entity)
    if index == nil or self.bindings[index] ~= binding then
        return
    end
    table.remove(self.bindings, index)
    binding.entity:RemoveEventCallback("death", binding.death)
    binding.entity:RemoveEventCallback("onremove", binding.removal)
    strip_modifiers(binding.entity)
    local now = self:When()
    if self.manager:remove_target(binding.id, now).ok then
        self:Accepted(now)
    end
end

function StatusEffects:Track(entity, stable_id)
    if not TheWorld.ismastersim or not usable_id(stable_id) or not can_be_tracked(entity) then
        return false
    end
    local mine = self:Find(entity)
    local theirs = self:Find(nil, stable_id)
    if mine ~= nil or theirs ~= nil then
        return mine ~= nil and mine == theirs
    end
    local now = self:When()
    if self.manager:add_target(stable_id, now).ok ~= true then
        return false
    end
    self:Accepted(now)
    local binding = { entity = entity, id = stable_id }
    binding.death = function() self:Forget(binding) end
    binding.removal = function() self:Forget(binding) end
    entity:ListenForEvent("death", binding.death)
    entity:ListenForEvent("onremove", binding.removal)
    self.bindings[#self.bindings + 1] = binding
    self:Reconcile(entity, now)
    return true
end

local function time_was_rejected(result)
    return result.code == "invalid_time" or result.code == "stale_time"
end

function StatusEffects:Apply(request_id, entity, effect_id, source_entity, now)
    if not TheWorld.ismastersim then
        return { ok = false, code = "not_authoritative" }
    end
    local target = self:Find(entity)
    if entity == nil or target == nil then
        return { ok = false, code = "unknown_target" }
    end
    local source_id = nil
    if source_entity ~= nil then
        local source = self:Find(source_entity)
        if source == nil then
            return { ok = false, code = "unknown_source" }
        end
        source_id = source.id
    end
    local at = self:When(now)
    local outcome = self.manager:apply(request_id, target.id, effect_id, source_id, at)
    if not time_was_rejected(outcome) then
        self:Accepted(at)
        self:Reconcile(entity, at)
    end
    return outcome
end

function StatusEffects:Dispel(entity, tag, max_count, now)
    if not TheWorld.ismastersim then
        return { ok = false, code = "not_authoritative" }
    end
    local target = self:Find(entity)
    if entity == nil or target == nil then
        return { ok = false, code = "unknown_target" }
    end
    local at = self:When(now)
    local outcome = self.manager:dispel(target.id, tag, max_count, at)
    if not time_was_rejected(outcome) then
        self:Accepted(at)
        self:Reconcile(entity, at)
    end
    return outcome
end

function StatusEffects:Cleanse(player, tag, now)
    if SELF_CLEANSE[tag] ~= true then
        return { ok = false, code = "forbidden_tag" }
    end
    local userid = type(player) == "table" and player.userid or nil
    local binding = usable_id(userid) and self:Find(nil, userid) or nil
    if binding == nil or binding.entity ~= player then
        return { ok = false, code = "unknown_target" }
    end
    return self:Dispel(player, tag, 1, now)
end

function StatusEffects:Reconcile(entity, now)
    local binding = entity ~= nil and self:Find(entity) or nil
    if binding == nil or not TheWorld.ismastersim then
        return nil
    end
    local at = self:When(now)
    local aggregate = self.manager:modifiers(binding.id, at)
    if aggregate.ok ~= true then
        return nil
    end
    self:Accepted(at)
    write_modifiers(entity, aggregate)
    return aggregate
end

function StatusEffects:Tick(now)
    local at = self:When(now)
    local changes = TheWorld.ismastersim and self.manager:tick(at) or nil
    if changes == nil then
        return false
    end
    self:Accepted(at)
    for _, change in ipairs(changes) do
        -- Looked up per change: an earlier DoDelta may have killed the entity
        -- and already dropped its binding through the death callback.
        local binding = self:Find(nil, change.target_id)
        if binding ~= nil and binding.entity:IsValid() then
            local health = binding.entity.components.health
            if health ~= nil and not health:IsDead() then
                health:DoDelta(change.amount, true, change.effect_id)
            end
        end
    end
    local snapshot = {}
    for index, binding in ipairs(self.bindings) do
        snapshot[index] = binding.entity
    end
    for _, entity in ipairs(snapshot) do
        self:Reconcile(entity, at)
    end
    return true
end

function StatusEffects:OnSave()
    local at = self:When()
    local saved = self.manager:save(at)
    self:Accepted(at)
    return { statuseffects = saved }
end

function StatusEffects:OnLoad(data)
    local sim = GetTime()
    self.manager = Manager.load(type(data) == "table" and data.statuseffects or nil, CONFIG, sim)
    self.latest = sim
    for _, binding in ipairs(self.bindings) do
        self.manager:add_target(binding.id, sim)
    end
    for _, binding in ipairs(self.bindings) do
        self:Reconcile(binding.entity, sim)
    end
end

function StatusEffects:OnRemoveFromEntity()
    if self.periodic ~= nil then
        self.periodic:Cancel()
        self.periodic = nil
    end
    self.inst:RemoveEventCallback("ms_playerjoined", self.on_player_joined)
    while #self.bindings > 0 do
        self:Forget(self.bindings[#self.bindings])
    end
end

return StatusEffects
