-- World component of the master simulation. It feeds the pure arbiter with
-- facts the server observed itself (attacked / death / onremove on followed
-- entities) and periodically applies the arbiter's answer through the
-- base-game combat component.

local Arbiter = require("combatarbiter/arbiter")
local Registry = require("combatarbiter/registry")

local SETTINGS = { decay_per_second = 1.5 }
local PERIOD = 0.75
local TAUNT_SECONDS = 5
local TAUNT_RADIUS = 10
local EPHEMERAL = "guid:"
local PLAYER = "user:"

local function good_id(value)
    return type(value) == "string" and value ~= "" and #value <= 128 and string.find(value, "%c") == nil
end

local function breathing(entity)
    if entity == nil or not entity:IsValid() then
        return false
    end
    local health = entity.components.health
    return health ~= nil and not health:IsDead()
end

local function attackable(entity)
    return breathing(entity) and not entity:HasTag("INLIMBO")
end

local CombatTargetArbiter = Class(function(self, inst)
    self.inst = inst
    self.core = Arbiter.new(SETTINGS)
    self.shift = 0
    self.last_now = 0
    self.revision = 0
    self.counters = {}
    self.given = {}

    self.registry = Registry.new({
        attacked = function(entity, _, data)
            self:_OnAttacked(entity, data)
        end,
        death = function(entity, id)
            self:_Report(id, false)
            self:_Withdraw(entity)
        end,
        removed = function(entity)
            self:Forget(entity)
        end,
    })

    self._on_joined = function(_, player)
        if player ~= nil and good_id(player.userid) then
            self:Track(player, PLAYER .. player.userid)
        end
    end
    inst:ListenForEvent("ms_playerjoined", self._on_joined, TheWorld)

    self._task = inst:DoPeriodicTask(PERIOD, function()
        self:ReconcileAll()
    end, PERIOD)
end)

-- Server time, shifted so that it continues where a loaded save stopped and
-- never runs backwards within this process.
function CombatTargetArbiter:_Clock()
    local now = GetTime() + self.shift
    if now < self.last_now then
        now = self.last_now
    end
    self.last_now = now
    return now
end

function CombatTargetArbiter:_Report(id, alive)
    self.revision = self.revision + 1
    return self.core:observe({ id = id, alive = alive, revision = self.revision }, self:_Clock())
end

function CombatTargetArbiter:Track(entity, stable_id)
    if not TheWorld.ismastersim or type(entity) ~= "table" or not good_id(stable_id) then
        return false
    end
    if entity.components == nil or entity.components.health == nil or not entity:IsValid() then
        return false
    end
    local current = self.registry.id_of(entity)
    if current == stable_id then
        return true
    end
    if current ~= nil then
        self:Forget(entity)
    end
    local holder = self.registry.entity_of(stable_id)
    if holder ~= nil then
        self:Forget(holder)
    end
    self.registry.bind(entity, stable_id)
    return self:_Report(stable_id, breathing(entity)) ~= false
end

function CombatTargetArbiter:TrackAutomatically(entity)
    if self.registry.id_of(entity) ~= nil or entity.components.health == nil then
        return false
    end
    if entity:HasTag("player") then
        if not good_id(entity.userid) then
            return false
        end
        return self:Track(entity, PLAYER .. entity.userid)
    end
    return self:Track(entity, EPHEMERAL .. tostring(entity.GUID))
end

function CombatTargetArbiter:Forget(entity)
    local id = self.registry.release(entity)
    if id == nil then
        return false
    end
    self:_Withdraw(entity)
    self.given[entity] = nil
    self.core:remove(id, self:_Clock())
    return true
end

function CombatTargetArbiter:Lookup(stable_id)
    return self.registry.entity_of(stable_id)
end

-- Clears a target this component handed out, wherever it is still in use.
function CombatTargetArbiter:_Withdraw(target)
    for source, handed in pairs(self.given) do
        if handed == target then
            self.given[source] = nil
            local combat = source:IsValid() and source.components.combat or nil
            if combat ~= nil and combat.target == target then
                combat:SetTarget(nil)
            end
        end
    end
end

function CombatTargetArbiter:_NextSeq(source_id, target_id)
    local key = source_id .. "\n" .. target_id
    return (self.counters[key] or 0) + 1
end

-- `source` was hurt by `target`. Without `seq` the server numbers the event
-- itself; a supplied `seq` goes through the same replay guard.
function CombatTargetArbiter:ObserveDamage(source, target, amount, seq)
    if not TheWorld.ismastersim or source == nil or target == nil or source == target then
        return false
    end
    local source_id, target_id = self.registry.id_of(source), self.registry.id_of(target)
    if source_id == nil or target_id == nil then
        return false
    end
    if type(amount) ~= "number" or amount ~= amount or amount <= 0 or amount == math.huge then
        return false
    end
    if seq == nil then
        seq = self:_NextSeq(source_id, target_id)
    end
    local accepted = self.core:add_threat(source_id, target_id, amount, seq, self:_Clock())
    if type(seq) == "number" then
        local key = source_id .. "\n" .. target_id
        if seq > (self.counters[key] or 0) and seq == math.floor(seq) and seq ~= math.huge then
            self.counters[key] = seq
        end
    end
    return accepted
end

function CombatTargetArbiter:_OnAttacked(victim, data)
    local attacker = data ~= nil and data.attacker or nil
    local damage = data ~= nil and data.damage or nil
    if attacker == nil or type(damage) ~= "number" or damage <= 0 then
        return
    end
    if self.registry.id_of(attacker) == nil and attacker.components ~= nil
        and attacker.components.health ~= nil and attacker.components.combat ~= nil then
        self:TrackAutomatically(attacker)
    end
    self:ObserveDamage(victim, attacker, damage)
end

function CombatTargetArbiter:Taunt(request_id, source, target, duration)
    if not TheWorld.ismastersim then
        return { ok = false, reason = "not_master" }
    end
    local source_id, target_id = self.registry.id_of(source), self.registry.id_of(target)
    if source_id == nil or target_id == nil then
        return { ok = false, reason = "not_tracked" }
    end
    return self.core:taunt(request_id, source_id, target_id, duration, self:_Clock())
end

-- RPC entry: every followed fighter close enough to the real player is taunted.
function CombatTargetArbiter:TauntNearby(player, token)
    if not good_id(token) or #token > 40 or not good_id(player.userid) or not breathing(player) then
        return 0
    end
    if self.registry.id_of(player) == nil and not self:Track(player, PLAYER .. player.userid) then
        return 0
    end
    local granted = 0
    local ids = self.registry.ids()
    for index = 1, #ids do
        local creature = self.registry.entity_of(ids[index])
        if creature ~= nil and creature ~= player and creature.components.combat ~= nil
            and breathing(creature) and player:GetDistanceSqToInst(creature) <= TAUNT_RADIUS * TAUNT_RADIUS then
            local request_id = player.userid .. "/" .. token .. "/" .. ids[index]
            if #request_id <= 128 and self:Taunt(request_id, creature, player, TAUNT_SECONDS).ok then
                granted = granted + 1
            end
        end
    end
    return granted
end

function CombatTargetArbiter:Reconcile(source)
    if not TheWorld.ismastersim or source == nil then
        return nil
    end
    local source_id = self.registry.id_of(source)
    local combat = source_id ~= nil and source:IsValid() and source.components.combat or nil
    if combat == nil then
        return nil
    end
    local pick = self.core:choose(source_id, self:_Clock())
    local target = pick ~= nil and self.registry.entity_of(pick.target_id) or nil
    if target ~= nil and attackable(target) then
        if combat.target ~= target then
            combat:SetTarget(target)
        end
        -- The base game may still refuse the target; only the field counts.
        if combat.target == target then
            self.given[source] = target
            return target
        end
    end
    local handed = self.given[source]
    self.given[source] = nil
    if handed ~= nil and combat.target == handed then
        combat:SetTarget(nil)
    end
    return nil
end

function CombatTargetArbiter:ReconcileAll()
    self.core:tick(self:_Clock())
    local ids = self.registry.ids()
    for index = 1, #ids do
        local entity = self.registry.entity_of(ids[index])
        if entity ~= nil and entity.components.combat ~= nil then
            self:Reconcile(entity)
        end
    end
end

function CombatTargetArbiter:OnSave()
    local counters = {}
    for key, value in pairs(self.counters) do
        counters[#counters + 1] = { stream = key, seq = value }
    end
    table.sort(counters, function(left, right)
        return left.stream < right.stream
    end)
    return { format = 1, revision = self.revision, counters = counters, core = self.core:save(self:_Clock()) }
end

function CombatTargetArbiter:OnLoad(data)
    if type(data) ~= "table" or data.format ~= 1 or type(data.core) ~= "table" then
        return
    end
    local resume = type(data.core.horizon) == "number" and data.core.horizon or 0
    local now = self:_Clock()
    if resume > now then
        self.shift = self.shift + (resume - now)
        now = self:_Clock()
    end
    self.core = Arbiter.load(data.core, SETTINGS, now)
    if type(data.revision) == "number" and data.revision > self.revision then
        self.revision = data.revision
    end
    if type(data.counters) == "table" then
        for index = 1, #data.counters do
            local row = data.counters[index]
            if type(row) == "table" and type(row.stream) == "string" and type(row.seq) == "number"
                and row.seq > (self.counters[row.stream] or 0) then
                self.counters[row.stream] = row.seq
            end
        end
    end
    -- Ids derived from a GUID belong to the process that wrote the save.
    local view = self.core:snapshot(now)
    for index = 1, #view.entities do
        local id = view.entities[index].id
        if string.sub(id, 1, #EPHEMERAL) == EPHEMERAL and self.registry.entity_of(id) == nil then
            self.core:remove(id, now)
        end
    end
    -- What is followed right now is reported again with a newer revision.
    local ids = self.registry.ids()
    for index = 1, #ids do
        self:_Report(ids[index], breathing(self.registry.entity_of(ids[index])))
    end
end

function CombatTargetArbiter:OnRemoveFromEntity()
    if self._task ~= nil then
        self._task:Cancel()
        self._task = nil
    end
    self.inst:RemoveEventCallback("ms_playerjoined", self._on_joined, TheWorld)
    local now = self:_Clock()
    local ids = self.registry.release_all()
    for index = 1, #ids do
        self.core:remove(ids[index], now)
    end
    self.given = {}
end

CombatTargetArbiter.OnRemoveEntity = CombatTargetArbiter.OnRemoveFromEntity

return CombatTargetArbiter
