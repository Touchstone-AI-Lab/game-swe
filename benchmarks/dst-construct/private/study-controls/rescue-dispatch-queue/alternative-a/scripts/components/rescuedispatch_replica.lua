-- Read-only view of the rescue queue. It holds the net variable and the last
-- decoded state; it has no scheduling logic and no way to change the queue.

local Wire = require("rescuedispatch/wire")

local function on_master()
    return TheWorld ~= nil and TheWorld.ismastersim == true
end

local RescueDispatchReplica = Class(function(self, inst)
    self.inst = inst
    if inst._rescue_state == nil then
        inst._rescue_state = net_string(inst.GUID, "rescuedispatch.state", "rescuedispatchdirty")
    end
    self.channel = inst._rescue_state
    self.view = Wire.decode(self.channel:value())

    if not on_master() then
        self.on_dirty = function()
            self.view = Wire.decode(self.channel:value())
            inst:PushEvent("rescuedispatch_viewchanged", self.view)
        end
        inst:ListenForEvent("rescuedispatchdirty", self.on_dirty)
    end
end)

-- Server side only: called by components/rescuedispatch.
function RescueDispatchReplica:Publish(text)
    if not on_master() or type(text) ~= "string" then
        return false
    end
    if self.channel:value() ~= text then
        self.channel:set(text)
    end
    self.view = Wire.decode(text)
    return true
end

function RescueDispatchReplica:GetQueue()
    return self.view.queue
end

function RescueDispatchReplica:GetLeases()
    return self.view.leases
end

function RescueDispatchReplica:GetLeaseForHelper(userid)
    for _, lease in ipairs(self.view.leases) do
        if lease.helper_id == userid then
            return lease
        end
    end
    return nil
end

function RescueDispatchReplica:OnRemoveFromEntity()
    if self.on_dirty ~= nil then
        self.inst:RemoveEventCallback("rescuedispatchdirty", self.on_dirty)
        self.on_dirty = nil
    end
end

return RescueDispatchReplica
