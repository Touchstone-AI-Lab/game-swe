-- Master-simulation world component for the rescue queue.
--
-- It turns live player entities into dispatcher records (health, life state
-- and position are always read from the entity), drives lease expiry with one
-- periodic task, and publishes the public view through the replica.

local Dispatch = require("rescuedispatch/dispatch")
local Wire = require("rescuedispatch/wire")

local SETTINGS = {
    lease_ttl = 20,
    aging_interval = 45,
    severity_cap = 5,
    recovery_percent = 0.8,
}
local SWEEP_PERIOD = 1
local PLAYER_EVENTS = { "healthdelta", "death", "respawnfromghost" }

local function userid_of(entity)
    if type(entity) == "table" and type(entity.userid) == "string" and entity.userid ~= "" then
        return entity.userid
    end
    return nil
end

-- Severity comes from the observed health only: 1 (scratched) .. cap (dying).
local function severity_from(percent)
    local level = math.ceil((1 - percent) * SETTINGS.severity_cap)
    return math.max(1, math.min(SETTINGS.severity_cap, level))
end

local RescueDispatch
RescueDispatch = Class(function(self, inst)
    self.inst = inst
    self.core = Dispatch.new(SETTINGS)
    self.clock_base = 0
    self.revisions = {}
    self.watched = {}
    self.places = {}
    self.last_seen = {}

    -- One function object per kind of event, shared by every player. The
    -- engine passes the event source first, so the player is an argument.
    self.on_vitals = function(player)
        self:UpdatePlayer(player)
    end
    self.on_player_removed = function(player)
        self:ForgetPlayer(player)
    end
    self.on_joined = function(_, player)
        self:UpdatePlayer(player)
    end
    self.on_left = function(_, player)
        self:ForgetPlayer(player)
    end

    self.world = TheWorld or inst
    inst:ListenForEvent("ms_playerjoined", self.on_joined, self.world)
    inst:ListenForEvent("ms_playerleft", self.on_left, self.world)

    self.sweep_task = inst:DoPeriodicTask(SWEEP_PERIOD, function()
        self:Tick()
    end, SWEEP_PERIOD)

    for _, player in ipairs(AllPlayers or {}) do
        self:UpdatePlayer(player)
    end

    -- Persistence hooks are also reachable as plain fields (component.OnSave()),
    -- so each instance carries wrappers that supply the receiver when the
    -- caller left it out.
    self.OnSave = function()
        return RescueDispatch.OnSave(self)
    end
    self.OnLoad = function(first, second)
        if first == self then
            return RescueDispatch.OnLoad(self, second)
        end
        return RescueDispatch.OnLoad(self, first)
    end
end)

function RescueDispatch:IsAuthority()
    return TheWorld ~= nil and TheWorld.ismastersim == true
end

-- The dispatcher clock must never run backwards, also not across a restart
-- where GetTime() starts again from zero.
function RescueDispatch:Now()
    return math.max(self.core:clock(), self.clock_base + GetTime())
end

function RescueDispatch:NextRevision(userid)
    local known = self.core:player(userid)
    local floor = math.max(self.revisions[userid] or 0, known ~= nil and known.revision or 0)
    self.revisions[userid] = floor + 1
    return floor + 1
end

function RescueDispatch:Watch(player)
    if self.watched[player] then
        return
    end
    self.watched[player] = true
    for _, event in ipairs(PLAYER_EVENTS) do
        player:ListenForEvent(event, self.on_vitals)
    end
    player:ListenForEvent("onremove", self.on_player_removed)
end

function RescueDispatch:Unwatch(player)
    if not self.watched[player] then
        return
    end
    self.watched[player] = nil
    for _, event in ipairs(PLAYER_EVENTS) do
        player:RemoveEventCallback(event, self.on_vitals)
    end
    player:RemoveEventCallback("onremove", self.on_player_removed)
end

-- Reads the authoritative state of a live player entity.
function RescueDispatch:Observe(player)
    local userid = userid_of(player)
    if userid == nil then
        return nil
    end
    local percent, alive = 1, true
    local health = player.components ~= nil and player.components.health or nil
    if health ~= nil then
        percent = health:GetPercent()
        alive = not health:IsDead()
    end
    if player.HasTag ~= nil and player:HasTag("playerghost") then
        alive = false
    end
    if type(percent) ~= "number" or percent ~= percent then
        return nil
    end
    percent = math.max(0, math.min(1, percent))
    if player.Transform ~= nil then
        local x, _, z = player.Transform:GetWorldPosition()
        self.places[userid] = { x = x, z = z }
    end
    local seen = { alive = alive, health_percent = percent }
    self.last_seen[userid] = seen
    return {
        id = userid,
        revision = self:NextRevision(userid),
        connected = true,
        alive = alive,
        health_percent = percent,
    }
end

function RescueDispatch:UpdatePlayer(player)
    if not self:IsAuthority() then
        return false
    end
    local record = self:Observe(player)
    if record == nil then
        return false
    end
    self:Watch(player)
    local result = self.core:update_player(record, self:Now())
    self:Publish()
    return result
end

-- A player that left or was removed is reported as disconnected with the last
-- state the server saw; the entity is not read again.
function RescueDispatch:ForgetPlayer(player)
    if type(player) ~= "table" then
        return false
    end
    self:Unwatch(player)
    local userid = userid_of(player)
    if userid == nil or self.core:player(userid) == nil then
        return false
    end
    local seen = self.last_seen[userid] or { alive = true, health_percent = 1 }
    self.last_seen[userid] = nil
    self.places[userid] = nil
    local result = self.core:update_player({
        id = userid,
        revision = self:NextRevision(userid),
        connected = false,
        alive = seen.alive,
        health_percent = seen.health_percent,
    }, self:Now())
    self:Publish()
    return result
end

function RescueDispatch:Request(request_id, target)
    if not self:IsAuthority() or type(request_id) ~= "string" then
        return false
    end
    local observed = self:UpdatePlayer(target)
    if observed == false or not observed.ok then
        return false
    end
    local seen = self.last_seen[userid_of(target)]
    local result = self.core:request(request_id, userid_of(target), severity_from(seen.health_percent), self:Now())
    self:Publish()
    return result
end

function RescueDispatch:Volunteer(request_id, helper)
    if not self:IsAuthority() or type(request_id) ~= "string" then
        return false
    end
    local observed = self:UpdatePlayer(helper)
    if observed == false or not observed.ok then
        return false
    end
    local result = self.core:volunteer(request_id, userid_of(helper), self:Now())
    self:Publish()
    return result
end

function RescueDispatch:Heartbeat(lease_id, helper)
    local userid = userid_of(helper)
    if not self:IsAuthority() or userid == nil then
        return false
    end
    local result = self.core:heartbeat(lease_id, userid, self:Now())
    self:Publish()
    return result
end

function RescueDispatch:Complete(lease_id, helper)
    local userid = userid_of(helper)
    if not self:IsAuthority() or userid == nil then
        return false
    end
    local result = self.core:complete(lease_id, userid, self:Now())
    self:Publish()
    return result
end

function RescueDispatch:Cancel(target)
    local userid = userid_of(target)
    if not self:IsAuthority() or userid == nil then
        return false
    end
    local result = self.core:cancel(userid, self:Now())
    self:Publish()
    return result
end

function RescueDispatch:Tick(now)
    if not self:IsAuthority() then
        return false
    end
    local at = self:Now()
    if type(now) == "number" and now > at then
        at = now
    end
    local result = self.core:tick(at)
    if result.ok and #result.expired > 0 then
        self:Publish()
    end
    return result
end

function RescueDispatch:Publish()
    local replica = self.inst.replica ~= nil and self.inst.replica.rescuedispatch or nil
    if replica == nil then
        return
    end
    replica:Publish(Wire.encode(self.core:snapshot(self:Now()), self.places))
end

function RescueDispatch:OnSave()
    local revisions = {}
    for userid, revision in pairs(self.revisions) do
        revisions[userid] = revision
    end
    return { schema = 1, revisions = revisions, core = self.core:save(self:Now()) }
end

function RescueDispatch:OnLoad(data)
    if type(data) ~= "table" or data.schema ~= 1 or type(data.core) ~= "table" then
        return
    end
    self.core = Dispatch.load(data.core, SETTINGS)
    self.clock_base = math.max(0, self.core:clock() - GetTime())
    if type(data.revisions) == "table" then
        for userid, revision in pairs(data.revisions) do
            if type(userid) == "string" and type(revision) == "number"
                and revision > (self.revisions[userid] or 0) then
                self.revisions[userid] = revision
            end
        end
    end
    self:Publish()
end

function RescueDispatch:OnRemoveFromEntity()
    if self.sweep_task ~= nil then
        self.sweep_task:Cancel()
        self.sweep_task = nil
    end
    self.inst:RemoveEventCallback("ms_playerjoined", self.on_joined, self.world)
    self.inst:RemoveEventCallback("ms_playerleft", self.on_left, self.world)
    local players = {}
    for player in pairs(self.watched) do
        players[#players + 1] = player
    end
    for _, player in ipairs(players) do
        self:Unwatch(player)
    end
end

function RescueDispatch:GetDebugString()
    local view = self.core:snapshot(self:Now())
    return string.format("waiting=%d leased=%d", #view.queue, #view.leases)
end

return RescueDispatch
