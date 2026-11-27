-- Master-simulation world component. Threat is derived only from real
-- `attacked` events on tracked entities; the pure arbiter ranks it and this
-- component applies the choice through the base-game combat component.

local Arbiter = require("combatarbiter/arbiter")

local OPTIONS = { decay_per_second = 2 }
local RECONCILE_PERIOD = 0.5
local SESSION_PREFIX = "session:"

local function is_identifier(value)
    return type(value) == "string" and value ~= "" and #value <= 96 and string.find(value, "%c") == nil
end

local function is_alive(entity)
    if entity == nil or not entity:IsValid() then
        return false
    end
    local health = entity.components.health
    return health ~= nil and not health:IsDead()
end

local CombatTargetArbiter = Class(function(self, inst)
    self.inst = inst
    self.arbiter = Arbiter.new(OPTIONS)
    self.time_offset = 0
    self.revision = 0
    self.by_id = {}
    self.by_entity = {}
    self.applied = {}

    self.on_player_joined = function(_world, player)
        if player ~= nil and type(player.userid) == "string" and player.userid ~= "" then
            self:Track(player, "player:" .. player.userid)
        end
    end
    inst:ListenForEvent("ms_playerjoined", self.on_player_joined, TheWorld)

    self.reconcile_task = inst:DoPeriodicTask(RECONCILE_PERIOD, function()
        self:ReconcileAll()
    end, RECONCILE_PERIOD)
end)

function CombatTargetArbiter:_Now()
    return math.max(self.arbiter.clock, GetTime() + self.time_offset)
end

function CombatTargetArbiter:_Observe(stable_id, alive)
    self.revision = self.revision + 1
    return self.arbiter:observe({ id = stable_id, alive = alive, revision = self.revision }, self:_Now())
end

function CombatTargetArbiter:Track(entity, stable_id)
    if not TheWorld.ismastersim then
        return false
    end
    if type(entity) ~= "table" or entity.components == nil or entity.components.health == nil
        or not is_identifier(stable_id) then
        return false
    end
    if self.by_entity[entity] ~= nil then
        if self.by_entity[entity].stable_id == stable_id then
            return true
        end
        self:Untrack(entity)
    end
    if self.by_id[stable_id] ~= nil then
        self:Untrack(self.by_id[stable_id].entity)
    end

    -- Each tracked entity keeps its own callbacks so the very same function
    -- objects can be unregistered later.
    local record = { entity = entity, stable_id = stable_id }
    record.on_attacked = function(_inst, data)
        local attacker = data ~= nil and data.attacker or nil
        local damage = data ~= nil and data.damage or nil
        if attacker ~= nil and type(damage) == "number" then
            self:ObserveDamage(entity, attacker, damage)
        end
    end
    record.on_death = function()
        self:_Observe(stable_id, false)
        self:_DropApplied(entity)
    end
    record.on_remove = function()
        self:Untrack(entity)
    end
    entity:ListenForEvent("attacked", record.on_attacked)
    entity:ListenForEvent("death", record.on_death)
    entity:ListenForEvent("onremove", record.on_remove)
    self.by_id[stable_id] = record
    self.by_entity[entity] = record
    return self:_Observe(stable_id, is_alive(entity)) ~= false
end

function CombatTargetArbiter:Untrack(entity)
    local record = self.by_entity[entity]
    if record == nil then
        return false
    end
    self.by_entity[entity] = nil
    self.by_id[record.stable_id] = nil
    self.applied[entity] = nil
    entity:RemoveEventCallback("attacked", record.on_attacked)
    entity:RemoveEventCallback("death", record.on_death)
    entity:RemoveEventCallback("onremove", record.on_remove)
    self.arbiter:remove(record.stable_id, self:_Now())
    return true
end

-- `source` is the entity that was hurt and is choosing whom to fight;
-- `target` is its attacker. A caller that has no sequence of its own gets the
-- next number of that source/target stream.
function CombatTargetArbiter:ObserveDamage(source, target, amount, seq)
    if not TheWorld.ismastersim then
        return false
    end
    local source_record, target_record = self.by_entity[source], self.by_entity[target]
    if source_record == nil or target_record == nil or source == target then
        return false
    end
    if type(amount) ~= "number" or amount ~= amount or amount <= 0 or amount == math.huge then
        return false
    end
    if seq == nil then
        seq = self.arbiter:last_seq(source_record.stable_id, target_record.stable_id) + 1
    end
    return self.arbiter:add_threat(source_record.stable_id, target_record.stable_id, amount, seq, self:_Now())
end

function CombatTargetArbiter:Taunt(request_id, source, target, duration)
    if not TheWorld.ismastersim then
        return { ok = false, reason = "not_authoritative" }
    end
    local source_record, target_record = self.by_entity[source], self.by_entity[target]
    if source_record == nil or target_record == nil then
        return { ok = false, reason = "untracked_entity" }
    end
    return self.arbiter:taunt(request_id, source_record.stable_id, target_record.stable_id, duration, self:_Now())
end

function CombatTargetArbiter:_DropApplied(dead_target)
    for source, target in pairs(self.applied) do
        if target == dead_target then
            self.applied[source] = nil
            local combat = source:IsValid() and source.components.combat or nil
            if combat ~= nil and combat.target == dead_target then
                combat:SetTarget(nil)
            end
        end
    end
end

-- Returns the entity that is the combat target after reconciliation, or nil.
function CombatTargetArbiter:Reconcile(source)
    if not TheWorld.ismastersim then
        return nil
    end
    local record = self.by_entity[source]
    local combat = record ~= nil and source:IsValid() and source.components.combat or nil
    if combat == nil then
        return nil
    end
    local choice = self.arbiter:choose(record.stable_id, self:_Now())
    local wanted = choice ~= nil and self.by_id[choice.target_id] or nil
    local target = wanted ~= nil and wanted.entity or nil

    if target ~= nil and is_alive(target) and not target:HasTag("INLIMBO") then
        if combat.target ~= target then
            combat:SetTarget(target)
        end
        -- SetTarget still runs the base-game validity and aggro checks, so the
        -- call alone proves nothing; only the resulting field does.
        if combat.target == target then
            self.applied[source] = target
            return target
        end
    end

    -- Nothing valid to fight: release only a target this component applied.
    local previous = self.applied[source]
    self.applied[source] = nil
    if previous ~= nil and combat.target == previous then
        combat:SetTarget(nil)
    end
    return nil
end

function CombatTargetArbiter:ReconcileAll()
    self.arbiter:tick(self:_Now())
    local ids = {}
    for stable_id, record in pairs(self.by_id) do
        if record.entity.components.combat ~= nil then
            ids[#ids + 1] = stable_id
        end
    end
    table.sort(ids)
    for index = 1, #ids do
        local record = self.by_id[ids[index]]
        if record ~= nil then
            self:Reconcile(record.entity)
        end
    end
end

function CombatTargetArbiter:OnSave()
    return { version = 1, revision = self.revision, arbiter = self.arbiter:save(self:_Now()) }
end

-- GetTime() restarts with the process; the offset keeps the arbiter clock
-- monotonic so taunt boundaries and decay survive a restart. Session-scoped
-- ids name entities of the previous process and are retired.
function CombatTargetArbiter:OnLoad(data)
    if type(data) ~= "table" or data.version ~= 1 then
        return
    end
    local saved_clock = type(data.arbiter) == "table" and type(data.arbiter.clock) == "number"
        and data.arbiter.clock or 0
    self.time_offset = math.max(0, saved_clock - GetTime())
    self.arbiter = Arbiter.load(data.arbiter, OPTIONS, saved_clock)
    if type(data.revision) == "number" and data.revision > self.revision then
        self.revision = data.revision
    end
    local now = self:_Now()
    local stale = {}
    for stable_id in pairs(self.arbiter.entities) do
        if string.sub(stable_id, 1, #SESSION_PREFIX) == SESSION_PREFIX and self.by_id[stable_id] == nil then
            stale[#stale + 1] = stable_id
        end
    end
    table.sort(stale)
    for index = 1, #stale do
        self.arbiter:remove(stale[index], now)
    end
    -- Entities tracked in this process stay authoritative for their ids.
    for stable_id, record in pairs(self.by_id) do
        self:_Observe(stable_id, is_alive(record.entity))
    end
end

function CombatTargetArbiter:OnRemoveFromEntity()
    if self.reconcile_task ~= nil then
        self.reconcile_task:Cancel()
        self.reconcile_task = nil
    end
    self.inst:RemoveEventCallback("ms_playerjoined", self.on_player_joined, TheWorld)
    local tracked = {}
    for entity in pairs(self.by_entity) do
        tracked[#tracked + 1] = entity
    end
    for index = 1, #tracked do
        self:Untrack(tracked[index])
    end
end

function CombatTargetArbiter:GetDebugString()
    local tracked = 0
    for _ in pairs(self.by_id) do
        tracked = tracked + 1
    end
    return string.format("tracked=%d rows=%d", tracked, #self.arbiter:snapshot(self:_Now()))
end

return CombatTargetArbiter
