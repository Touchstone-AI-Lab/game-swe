-- Master-simulation world component. It owns the mapping from stable ids to
-- container entities and adapts base-game containers to the pure transaction.

local Transaction = require("containertransfer/transaction")

local TRACKED_TAG = "rhenium_transfer_tracked"

local function is_identifier(value)
    return type(value) == "string" and value ~= "" and #value <= 96 and string.find(value, "%c") == nil
end

local function stack_size(item)
    if item.components.stackable ~= nil then
        return item.components.stackable:StackSize()
    end
    return 1
end

local function max_stack(item)
    if item.components.stackable ~= nil then
        return item.components.stackable.maxsize or 1
    end
    return 1
end

local function describe(item, slot)
    return {
        slot = slot,
        prefab = item.prefab,
        count = stack_size(item),
        perish_percent = item.components.perishable ~= nil and item.components.perishable:GetPercent() or nil,
        finite_uses_percent = item.components.finiteuses ~= nil and item.components.finiteuses:GetPercent() or nil,
    }
end

local function same_item(current, wanted)
    if current == nil or wanted == nil then
        return current == nil and wanted == nil
    end
    return current.prefab == wanted.prefab and stack_size(current) == wanted.count
end

local function spawn_described(wanted)
    local item = SpawnPrefab(wanted.prefab)
    if item == nil then
        return nil
    end
    if item.components.stackable ~= nil and type(wanted.count) == "number" then
        item.components.stackable:SetStackSize(wanted.count)
    end
    if item.components.perishable ~= nil and type(wanted.perish_percent) == "number" then
        item.components.perishable:SetPercent(wanted.perish_percent)
    end
    if item.components.finiteuses ~= nil and type(wanted.finite_uses_percent) == "number" then
        item.components.finiteuses:SetPercent(wanted.finite_uses_percent)
    end
    return item
end

local ContainerTransfer = Class(function(self, inst)
    self.inst = inst
    self.tracked = {}
    self.held = {}
    self.external_changes = 0
    self.in_flight = false
    self.recover_task = nil
    self.transaction = Transaction.new(self:_MakeAdapter(), nil)
end)

function ContainerTransfer:_Container(stable_id)
    local entry = self.tracked[stable_id]
    if entry == nil or not entry.entity:IsValid() then
        return nil
    end
    return entry.entity.components.container
end

function ContainerTransfer:_DropHeld()
    for index = 1, #self.held do
        local item = self.held[index]
        if item:IsValid() and item.components.inventoryitem ~= nil
            and item.components.inventoryitem.owner == nil then
            item:Remove()
        end
    end
    self.held = {}
end

function ContainerTransfer:_MakeAdapter()
    local service = self
    local adapter = {}

    function adapter:snapshot(stable_id)
        local container = service:_Container(stable_id)
        local items = {}
        if container ~= nil then
            for slot = 1, container:GetNumSlots() do
                local item = container:GetItemInSlot(slot)
                if item ~= nil then
                    items[#items + 1] = describe(item, slot)
                end
            end
        end
        return items
    end

    function adapter:capacity(stable_id, prefab)
        local container = service:_Container(stable_id)
        if container == nil then
            return 0
        end
        local probe_max, free_slots, room = nil, 0, 0
        for slot = 1, container:GetNumSlots() do
            local item = container:GetItemInSlot(slot)
            if item == nil then
                free_slots = free_slots + 1
            elseif item.prefab == prefab and container.acceptsstacks ~= false then
                probe_max = probe_max or max_stack(item)
                room = room + math.max(0, max_stack(item) - stack_size(item))
            end
        end
        if probe_max == nil then
            local source_max = service.pending_max_stack
            probe_max = type(source_max) == "number" and source_max or 1
        end
        return room + free_slots * probe_max
    end

    function adapter:remove(stable_id, prefab, count)
        local container = service:_Container(stable_id)
        if container == nil then
            return nil
        end
        local removed, remaining = {}, count
        for slot = 1, container:GetNumSlots() do
            if remaining <= 0 then
                break
            end
            local item = container:GetItemInSlot(slot)
            if item ~= nil and item.prefab == prefab then
                local size = stack_size(item)
                local taken
                if size <= remaining then
                    taken = container:RemoveItemBySlot(slot)
                else
                    taken = item.components.stackable:Get(remaining)
                end
                if taken == nil then
                    return nil
                end
                service.held[#service.held + 1] = taken
                removed[#removed + 1] = describe(taken, slot)
                remaining = remaining - stack_size(taken)
            end
        end
        if remaining > 0 then
            return nil
        end
        return removed
    end

    function adapter:add(stable_id, _items)
        local container = service:_Container(stable_id)
        if container == nil then
            return false
        end
        local held = service.held
        for index = 1, #held do
            local item = held[index]
            if not item:IsValid() or not container:GiveItem(item, nil, nil, false) then
                return false
            end
        end
        service.held = {}
        return true
    end

    -- Converge only the slots that differ from the snapshot, so untouched
    -- items keep their identity and metadata.
    function adapter:restore(stable_id, snapshot)
        local container = service:_Container(stable_id)
        if container == nil then
            return false
        end
        service:_DropHeld()
        local wanted = {}
        for index = 1, #snapshot do
            wanted[snapshot[index].slot] = snapshot[index]
        end
        for slot = 1, container:GetNumSlots() do
            local current = container:GetItemInSlot(slot)
            if not same_item(current, wanted[slot]) then
                if current ~= nil then
                    local removed = container:RemoveItemBySlot(slot)
                    if removed ~= nil then
                        removed:Remove()
                    end
                end
                if wanted[slot] ~= nil then
                    local item = spawn_described(wanted[slot])
                    if item == nil or not container:GiveItem(item, slot, nil, false) then
                        if item ~= nil then
                            item:Remove()
                        end
                        return false
                    end
                end
            end
        end
        return true
    end

    return adapter
end

function ContainerTransfer:Track(entity, stable_id)
    if not TheWorld.ismastersim then
        return false
    end
    if type(entity) ~= "table" or entity.components == nil or entity.components.container == nil
        or not is_identifier(stable_id) then
        return false
    end
    local existing = self.tracked[stable_id]
    if existing ~= nil then
        if existing.entity == entity then
            return true
        end
        self:Untrack(stable_id)
    end
    local service = self
    local entry = { entity = entity }
    entry.on_item_get = function(_inst, _data)
        if not service.in_flight then
            service.external_changes = service.external_changes + 1
        end
    end
    entry.on_item_lose = function(_inst, _data)
        if not service.in_flight then
            service.external_changes = service.external_changes + 1
        end
    end
    entry.on_remove = function()
        service:Untrack(stable_id)
    end
    entity:ListenForEvent("itemget", entry.on_item_get)
    entity:ListenForEvent("itemlose", entry.on_item_lose)
    entity:ListenForEvent("onremove", entry.on_remove)
    entity:AddTag(TRACKED_TAG)
    entity.rhenium_transfer_id = stable_id
    self.tracked[stable_id] = entry
    return true
end

function ContainerTransfer:Untrack(stable_id)
    local entry = self.tracked[stable_id]
    if entry == nil then
        return false
    end
    self.tracked[stable_id] = nil
    local entity = entry.entity
    entity:RemoveEventCallback("itemget", entry.on_item_get)
    entity:RemoveEventCallback("itemlose", entry.on_item_lose)
    entity:RemoveEventCallback("onremove", entry.on_remove)
    if entity:IsValid() then
        entity:RemoveTag(TRACKED_TAG)
    end
    entity.rhenium_transfer_id = nil
    return true
end

function ContainerTransfer:StableIdOf(entity)
    if type(entity) ~= "table" then
        return nil
    end
    local stable_id = entity.rhenium_transfer_id
    if stable_id ~= nil and self.tracked[stable_id] ~= nil and self.tracked[stable_id].entity == entity then
        return stable_id
    end
    return nil
end

function ContainerTransfer:_SourceMaxStack(request)
    if type(request) ~= "table" or not is_identifier(request.source_id) then
        return nil
    end
    local container = self:_Container(request.source_id)
    if container == nil then
        return nil
    end
    for slot = 1, container:GetNumSlots() do
        local item = container:GetItemInSlot(slot)
        if item ~= nil and item.prefab == request.prefab then
            return max_stack(item)
        end
    end
    return nil
end

function ContainerTransfer:Transfer(request)
    if not TheWorld.ismastersim then
        return { ok = false, status = "rejected", reason = "not_authoritative", recoverable = false }
    end
    if type(request) == "table" and is_identifier(request.source_id) and is_identifier(request.destination_id)
        and request.source_id ~= request.destination_id
        and self.transaction:status(request.request_id) == nil
        and (self:_Container(request.source_id) == nil or self:_Container(request.destination_id) == nil) then
        return { ok = false, status = "rejected", reason = "unknown_container", recoverable = false }
    end
    self.pending_max_stack = self:_SourceMaxStack(request)
    self.in_flight = true
    local ok, result = pcall(self.transaction.transfer, self.transaction, request)
    self.in_flight = false
    self.pending_max_stack = nil
    if not ok then
        -- The intent is already recorded; a later Recover converges the world.
        self:_DropHeld()
        return { ok = false, status = "interrupted", reason = "internal_error", recoverable = true }
    end
    return result
end

function ContainerTransfer:Recover()
    if not TheWorld.ismastersim then
        return {}
    end
    self.in_flight = true
    local ok, results = pcall(self.transaction.recover, self.transaction)
    self.in_flight = false
    if not ok then
        return {}
    end
    return results
end

function ContainerTransfer:Status(request_id)
    return self.transaction:status(request_id)
end

function ContainerTransfer:OnSave()
    return { version = 1, transaction = self.transaction:save() }
end

function ContainerTransfer:OnLoad(data)
    local persisted = type(data) == "table" and data.transaction or nil
    self.transaction = Transaction.load(self:_MakeAdapter(), persisted)
    if self.recover_task ~= nil then
        self.recover_task:Cancel()
    end
    -- Containers re-register during world load; recover once they had a chance.
    self.recover_task = self.inst:DoTaskInTime(0, function()
        self.recover_task = nil
        self:Recover()
    end)
end

function ContainerTransfer:OnRemoveFromEntity()
    if self.recover_task ~= nil then
        self.recover_task:Cancel()
        self.recover_task = nil
    end
    local ids = {}
    for stable_id in pairs(self.tracked) do
        ids[#ids + 1] = stable_id
    end
    for index = 1, #ids do
        self:Untrack(ids[index])
    end
    self:_DropHeld()
end

function ContainerTransfer:GetDebugString()
    local tracked = 0
    for _ in pairs(self.tracked) do
        tracked = tracked + 1
    end
    return string.format("tracked=%d external_changes=%d", tracked, self.external_changes)
end

return ContainerTransfer
