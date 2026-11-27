-- Master-simulation world component. It observes real player state, feeds the
-- pure dispatcher, advances lease expiry and publishes the read-only view.

local Dispatch = require("rescuedispatch/dispatch")

local OPTIONS = { lease_ttl = 20, aging_interval = 30, max_severity = 5, recovery_threshold = 0.75 }
local TICK_PERIOD = 1
local MAX_PUBLISHED = 12

local function severity_for(health_percent)
    if health_percent <= 0.10 then
        return 5
    elseif health_percent <= 0.25 then
        return 4
    elseif health_percent <= 0.40 then
        return 3
    elseif health_percent <= 0.55 then
        return 2
    end
    return 1
end

local function player_id(player)
    if type(player) ~= "table" or type(player.userid) ~= "string" or player.userid == "" then
        return nil
    end
    return player.userid
end

local RescueDispatch
RescueDispatch = Class(function(self, inst)
    self.inst = inst
    self.dispatch = Dispatch.new(OPTIONS)
    self.time_offset = 0
    self.revision = 0
    self.hooks = {}
    self.positions = {}

    self.on_player_joined = function(_world, player)
        self:UpdatePlayer(player)
    end
    self.on_player_left = function(_world, player)
        self:_Depart(player)
    end
    inst:ListenForEvent("ms_playerjoined", self.on_player_joined, TheWorld)
    inst:ListenForEvent("ms_playerleft", self.on_player_left, TheWorld)

    self.tick_task = inst:DoPeriodicTask(TICK_PERIOD, function()
        self:Tick()
    end, TICK_PERIOD)

    -- Bound to this instance so a save hook works with or without a receiver.
    self.OnSave = function()
        return RescueDispatch.OnSave(self)
    end
    self.OnLoad = function(first, second)
        local data = second
        if data == nil and first ~= self then
            data = first
        end
        return RescueDispatch.OnLoad(self, data)
    end
end)

function RescueDispatch:_Now()
    return math.max(self.dispatch.clock, GetTime() + self.time_offset)
end

function RescueDispatch:_Hook(player)
    if self.hooks[player] ~= nil then
        return
    end
    local hook = {}
    hook.refresh = function()
        self:UpdatePlayer(player)
    end
    hook.depart = function()
        self:_Depart(player)
    end
    player:ListenForEvent("healthdelta", hook.refresh)
    player:ListenForEvent("death", hook.refresh)
    player:ListenForEvent("respawnfromghost", hook.refresh)
    player:ListenForEvent("onremove", hook.depart)
    self.hooks[player] = hook
end

function RescueDispatch:_Unhook(player)
    local hook = self.hooks[player]
    if hook == nil then
        return
    end
    self.hooks[player] = nil
    player:RemoveEventCallback("healthdelta", hook.refresh)
    player:RemoveEventCallback("death", hook.refresh)
    player:RemoveEventCallback("respawnfromghost", hook.refresh)
    player:RemoveEventCallback("onremove", hook.depart)
end

function RescueDispatch:_Observe(player, connected)
    local id = player_id(player)
    if id == nil then
        return nil
    end
    local health = player.components ~= nil and player.components.health or nil
    local percent, alive = 1, true
    if health ~= nil then
        percent = health:GetPercent()
        alive = not health:IsDead()
    end
    if player:HasTag("playerghost") then
        alive = false
    end
    if type(percent) ~= "number" or percent ~= percent then
        return nil
    end
    percent = math.min(1, math.max(0, percent))
    if connected and player.Transform ~= nil then
        local x, _, z = player.Transform:GetWorldPosition()
        self.positions[id] = { x = x, z = z }
    else
        self.positions[id] = nil
    end
    self.revision = self.revision + 1
    return {
        id = id,
        revision = self.revision,
        connected = connected,
        alive = alive,
        health_percent = percent,
    }
end

function RescueDispatch:UpdatePlayer(player)
    if not TheWorld.ismastersim then
        return false
    end
    local record = self:_Observe(player, true)
    if record == nil then
        return false
    end
    self:_Hook(player)
    local result = self.dispatch:update_player(record, self:_Now())
    self:_Publish()
    return result
end

function RescueDispatch:_Depart(player)
    self:_Unhook(player)
    local record = self:_Observe(player, false)
    if record ~= nil then
        self.dispatch:update_player(record, self:_Now())
        self:_Publish()
    end
end

-- Severity is always derived from the server-observed health; a client hint
-- is never consulted.
function RescueDispatch:Request(request_id, target)
    if not TheWorld.ismastersim or type(request_id) ~= "string" then
        return false
    end
    local id = player_id(target)
    if id == nil or self:UpdatePlayer(target) == false then
        return false
    end
    local observed = self.dispatch.players[id]
    local result = self.dispatch:request(request_id, id, severity_for(observed.health_percent), self:_Now())
    self:_Publish()
    return result
end

function RescueDispatch:Volunteer(request_id, helper)
    if not TheWorld.ismastersim or type(request_id) ~= "string" then
        return false
    end
    local id = player_id(helper)
    if id == nil or self:UpdatePlayer(helper) == false then
        return false
    end
    local result = self.dispatch:volunteer(request_id, id, self:_Now())
    self:_Publish()
    return result
end

function RescueDispatch:Heartbeat(lease_id, helper)
    local id = player_id(helper)
    if not TheWorld.ismastersim or id == nil then
        return false
    end
    local result = self.dispatch:heartbeat(lease_id, id, self:_Now())
    self:_Publish()
    return result
end

function RescueDispatch:Complete(lease_id, helper)
    local id = player_id(helper)
    if not TheWorld.ismastersim or id == nil then
        return false
    end
    local result = self.dispatch:complete(lease_id, id, self:_Now())
    self:_Publish()
    return result
end

function RescueDispatch:Cancel(target)
    local id = player_id(target)
    if not TheWorld.ismastersim or id == nil then
        return false
    end
    local result = self.dispatch:cancel(id, self:_Now())
    self:_Publish()
    return result
end

function RescueDispatch:Tick(now)
    if not TheWorld.ismastersim then
        return false
    end
    local result = self.dispatch:tick(type(now) == "number" and now or self:_Now())
    if result.ok and #result.expired > 0 then
        self:_Publish()
    end
    return result
end

function RescueDispatch:_Publish()
    local replica = self.inst.replica ~= nil and self.inst.replica.rescuedispatch or nil
    if replica == nil or replica.SetState == nil then
        return
    end
    local snapshot = self.dispatch:snapshot(self:_Now())
    local queue, leases = {}, {}
    for index = 1, math.min(#snapshot.queue, MAX_PUBLISHED) do
        local entry = snapshot.queue[index]
        local position = self.positions[entry.target_id] or {}
        queue[#queue + 1] = string.format("%s,%d,%d,%d", entry.target_id, entry.effective_severity,
            math.floor((position.x or 0) + 0.5), math.floor((position.z or 0) + 0.5))
    end
    for index = 1, math.min(#snapshot.leases, MAX_PUBLISHED) do
        local lease = snapshot.leases[index]
        leases[#leases + 1] = string.format("%s,%s,%s,%d", lease.lease_id, lease.target_id,
            lease.helper_id, math.floor(lease.expires_at))
    end
    replica:SetState(table.concat(queue, ";") .. "|" .. table.concat(leases, ";"))
end

function RescueDispatch:_Save()
    return { version = 1, revision = self.revision, dispatch = self.dispatch:save(self:_Now()) }
end

-- GetTime() restarts with the process, so the saved dispatcher clock is kept
-- ahead of it: lease boundaries survive a restart and time never runs backward.
function RescueDispatch:_Load(data)
    if type(data) ~= "table" or data.version ~= 1 then
        return
    end
    self.dispatch = Dispatch.load(data.dispatch, OPTIONS)
    self.time_offset = math.max(0, self.dispatch.clock - GetTime())
    if type(data.revision) == "number" and data.revision > self.revision then
        self.revision = data.revision
    end
    self:_Publish()
end

function RescueDispatch:OnSave()
    return self:_Save()
end

function RescueDispatch:OnLoad(data)
    return self:_Load(data)
end

function RescueDispatch:OnRemoveFromEntity()
    if self.tick_task ~= nil then
        self.tick_task:Cancel()
        self.tick_task = nil
    end
    self.inst:RemoveEventCallback("ms_playerjoined", self.on_player_joined, TheWorld)
    self.inst:RemoveEventCallback("ms_playerleft", self.on_player_left, TheWorld)
    local hooked = {}
    for player in pairs(self.hooks) do
        hooked[#hooked + 1] = player
    end
    for index = 1, #hooked do
        self:_Unhook(hooked[index])
    end
end

function RescueDispatch:GetDebugString()
    local snapshot = self.dispatch:snapshot(self:_Now())
    return string.format("queue=%d leases=%d", #snapshot.queue, #snapshot.leases)
end

return RescueDispatch
