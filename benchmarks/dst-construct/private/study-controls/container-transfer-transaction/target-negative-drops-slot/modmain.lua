local function current_world()
    return GLOBAL.TheWorld
end

local REACH = 4
local MAX_COUNT = 1000

local function service()
    local world = current_world()
    if world == nil or not world.ismastersim then
        return nil
    end
    return world.components.containertransfer
end

-- Server-side gate shared by the action and the RPC: both ids must name
-- tracked containers and the player must stand next to both of them.
local function transfer_for(player, fields)
    local transfers = service()
    if transfers == nil or player == nil or type(player.userid) ~= "string" then
        return nil
    end
    local source = transfers:EntityFor(fields.source_id)
    local destination = transfers:EntityFor(fields.destination_id)
    if source == nil or destination == nil or source == destination then
        return nil
    end
    if not player:IsNear(source, REACH) or not player:IsNear(destination, REACH) then
        return nil
    end
    return transfers:Transfer({
        request_id = player.userid .. "/" .. fields.request_id,
        source_id = fields.source_id,
        destination_id = fields.destination_id,
        prefab = fields.prefab,
        count = fields.count,
    })
end

-- Two-step interaction: the first use on a tracked container marks it as the
-- source; the next use on another tracked container moves the first stack of
-- the marked source into it.
local function first_stack(entity)
    local container = entity.components.container
    for slot = 1, container:GetNumSlots() do
        local item = container:GetItemInSlot(slot)
        if item ~= nil then
            local stackable = item.components.stackable
            return item.prefab, stackable ~= nil and stackable:StackSize() or 1
        end
    end
    return nil
end

local function run_action(act)
    local transfers = service()
    local doer, target = act.doer, act.target
    if transfers == nil or doer == nil or target == nil then
        return false
    end
    local target_id = transfers:IdOf(target)
    if target_id == nil then
        return false
    end
    local marked = doer.transfer_marked_source
    local marked_entity = marked ~= nil and transfers:EntityFor(marked) or nil
    if marked_entity == nil or marked == target_id then
        doer.transfer_marked_source = target_id
        return true
    end
    doer.transfer_marked_source = nil
    local prefab, count = first_stack(marked_entity)
    if prefab == nil then
        return false, "EMPTY"
    end
    doer.transfer_sequence = (doer.transfer_sequence or 0) + 1
    local outcome = transfer_for(doer, {
        request_id = "act-" .. tostring(doer.transfer_sequence) .. "-" .. tostring(GLOBAL.GetTick()),
        source_id = marked,
        destination_id = target_id,
        prefab = prefab,
        count = count,
    })
    return outcome ~= nil and outcome.ok == true
end

local TRANSFER = AddAction("RHENIUM_TRANSFER", "Transfer", run_action)
TRANSFER.priority = 1
TRANSFER.distance = 2

AddComponentAction("SCENE", "container", function(inst, doer, actions, right)
    if right and inst:HasTag("transfer_endpoint") then
        actions[#actions + 1] = TRANSFER
    end
end)

AddStategraphActionHandler("wilson", GLOBAL.ActionHandler(TRANSFER, "doshortaction"))
AddStategraphActionHandler("wilson_client", GLOBAL.ActionHandler(TRANSFER, "doshortaction"))

-- The client names containers by stable id only. Entities, slots, snapshots
-- and capacities are always resolved on the server.
AddModRPCHandler("rhenium_transfer", "request", function(player, request_id, source_id, destination_id, prefab, count)
    local function text(value)
        return type(value) == "string" and value ~= "" and #value <= 64
    end
    if not (text(request_id) and text(source_id) and text(destination_id) and text(prefab)) then
        return
    end
    if type(count) ~= "number" or count < 1 or count > MAX_COUNT or count % 1 ~= 0 then
        return
    end
    transfer_for(player, {
        request_id = request_id, source_id = source_id, destination_id = destination_id,
        prefab = prefab, count = count,
    })
end)

AddPrefabPostInit("world", function(inst)
    if not inst.ismastersim then
        return
    end
    if inst.components.containertransfer == nil then
        inst:AddComponent("containertransfer")
    end
end)
