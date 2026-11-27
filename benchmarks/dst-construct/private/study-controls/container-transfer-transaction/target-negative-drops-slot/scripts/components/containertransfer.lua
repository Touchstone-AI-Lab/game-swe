-- World component (master simulation only). It keeps the registry of tracked
-- containers, owns the transaction object and is the single entry point used
-- by the action, the RPC handler and the save system.

local Transaction = require("containertransfer/transaction")
local MakeChestAdapter = require("containertransfer/chest_adapter")

local TAG = "transfer_endpoint"

local function usable_id(value)
    return type(value) == "string" and value ~= "" and #value <= 128 and not string.find(value, "[%c]")
end

local function refusal(reason)
    return { ok = false, status = "refused", reason = reason, recoverable = false }
end

local ContainerTransfer = Class(function(self, inst)
    self.inst = inst
    self.by_id = {}        -- stable id -> registration
    self.by_entity = {}    -- entity -> stable id
    self.scratch = {}      -- short-lived entities created by the adapter
    self.busy = false
    self.pending_recover = nil
    self.adapter = MakeChestAdapter(function(stable_id)
        return self:ContainerFor(stable_id)
    end, self.scratch)
    self.transaction = Transaction.new(self.adapter, nil)
end)

function ContainerTransfer:ContainerFor(stable_id)
    local registration = self.by_id[stable_id]
    if registration == nil then
        return nil
    end
    local entity = registration.entity
    if not entity:IsValid() or entity.components.container == nil then
        return nil
    end
    return entity.components.container
end

function ContainerTransfer:IdOf(entity)
    return entity ~= nil and self.by_entity[entity] or nil
end

function ContainerTransfer:EntityFor(stable_id)
    local registration = self.by_id[stable_id]
    return registration ~= nil and registration.entity or nil
end

-- Number of item changes on a tracked container that did not come from one of
-- our own transactions. Exposed so callers can tell a quiet container from
-- one that players are actively using.
function ContainerTransfer:ForeignChanges(stable_id)
    local registration = self.by_id[stable_id]
    return registration ~= nil and registration.foreign_changes or 0
end

function ContainerTransfer:Track(entity, stable_id)
    if not TheWorld.ismastersim then
        return false
    end
    if not usable_id(stable_id) or type(entity) ~= "table" or entity.components == nil
        or entity.components.container == nil then
        return false
    end
    if self.by_entity[entity] == stable_id then
        return true
    end
    if self.by_entity[entity] ~= nil then
        self:Forget(self.by_entity[entity])
    end
    if self.by_id[stable_id] ~= nil then
        self:Forget(stable_id)
    end

    local registration = { entity = entity, foreign_changes = 0 }
    local function note_change()
        if not self.busy then
            registration.foreign_changes = registration.foreign_changes + 1
        end
    end
    registration.handlers = {
        itemget = function(_, data)
            if data ~= nil and data.item ~= nil then
                note_change()
            end
        end,
        itemlose = function(_, data)
            if data ~= nil and data.slot ~= nil then
                note_change()
            end
        end,
        onremove = function()
            self:Forget(stable_id)
        end,
    }
    for event, handler in pairs(registration.handlers) do
        entity:ListenForEvent(event, handler)
    end
    entity:AddTag(TAG)
    self.by_id[stable_id] = registration
    self.by_entity[entity] = stable_id
    return true
end

function ContainerTransfer:Forget(stable_id)
    local registration = self.by_id[stable_id]
    if registration == nil then
        return false
    end
    local entity = registration.entity
    for event, handler in pairs(registration.handlers) do
        entity:RemoveEventCallback(event, handler)
    end
    registration.handlers = {}
    if entity:IsValid() then
        entity:RemoveTag(TAG)
    end
    self.by_id[stable_id] = nil
    self.by_entity[entity] = nil
    return true
end

function ContainerTransfer:ClearScratch()
    for index = #self.scratch, 1, -1 do
        local entity = self.scratch[index]
        self.scratch[index] = nil
        if entity ~= nil and entity:IsValid() then
            entity:Remove()
        end
    end
end

function ContainerTransfer:Guarded(method, ...)
    self.busy = true
    local ok, result = pcall(method, self.transaction, ...)
    self.busy = false
    self:ClearScratch()
    return ok, result
end

function ContainerTransfer:Transfer(request)
    if not TheWorld.ismastersim then
        return refusal("not_master")
    end
    if type(request) == "table" and usable_id(request.request_id)
        and self.transaction:status(request.request_id) == nil
        and usable_id(request.source_id) and usable_id(request.destination_id)
        and request.source_id ~= request.destination_id
        and (self:ContainerFor(request.source_id) == nil or self:ContainerFor(request.destination_id) == nil) then
        -- Nothing is journalled for a container this server does not track.
        return refusal("unknown_container")
    end
    local ok, result = self:Guarded(self.transaction.transfer, request)
    if not ok then
        -- The journal already holds the intent; Recover settles it later.
        return { ok = false, status = "interrupted", reason = "adapter_error", recoverable = true }
    end
    return result
end

function ContainerTransfer:Recover()
    if not TheWorld.ismastersim then
        return {}
    end
    local ok, report = self:Guarded(self.transaction.recover)
    return ok and report or {}
end

function ContainerTransfer:Status(request_id)
    return self.transaction:status(request_id)
end

function ContainerTransfer:OnSave()
    return { transfers = self.transaction:save() }
end

function ContainerTransfer:OnLoad(data)
    local saved = type(data) == "table" and type(data.transfers) == "table" and data.transfers or nil
    self.transaction = Transaction.load(self.adapter, saved)
    -- Recover right away for containers that are already tracked, and once
    -- more after the load frame, when saved containers have registered again.
    self:Recover()
    if self.pending_recover ~= nil then
        self.pending_recover:Cancel()
    end
    self.pending_recover = self.inst:DoTaskInTime(0, function()
        self.pending_recover = nil
        self:Recover()
    end)
end

function ContainerTransfer:OnRemoveFromEntity()
    if self.pending_recover ~= nil then
        self.pending_recover:Cancel()
        self.pending_recover = nil
    end
    local ids = {}
    for stable_id in pairs(self.by_id) do
        ids[#ids + 1] = stable_id
    end
    for index = 1, #ids do
        self:Forget(ids[index])
    end
    self:ClearScratch()
end

ContainerTransfer.OnRemoveEntity = ContainerTransfer.OnRemoveFromEntity

function ContainerTransfer:GetDebugString()
    local tracked = 0
    for _ in pairs(self.by_id) do
        tracked = tracked + 1
    end
    return string.format("tracked=%d busy=%s", tracked, tostring(self.busy))
end

return ContainerTransfer
