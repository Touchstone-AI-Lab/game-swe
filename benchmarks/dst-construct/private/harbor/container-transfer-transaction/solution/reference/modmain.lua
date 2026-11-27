local GLOBAL = GLOBAL
local TheWorld = nil

local MAX_RPC_COUNT = 400
local INTERACT_RANGE_SQ = 6 * 6
local TRACKED_TAG = "rhenium_transfer_tracked"

local function world_service()
    TheWorld = GLOBAL.TheWorld
    if TheWorld == nil or not TheWorld.ismastersim then
        return nil
    end
    return TheWorld.components.containertransfer
end

local function in_range(player, entity)
    return player ~= nil and entity ~= nil and entity:IsValid()
        and player:GetDistanceSqToInst(entity) <= INTERACT_RANGE_SQ
end

-- The server resolves both containers from stable ids and re-checks reach;
-- nothing else the client says is trusted.
local function authorised_transfer(player, request)
    local service = world_service()
    if service == nil or player == nil then
        return { ok = false, status = "rejected", reason = "not_authoritative", recoverable = false }
    end
    local source = service.tracked[request.source_id]
    local destination = service.tracked[request.destination_id]
    if source == nil or destination == nil then
        return { ok = false, status = "rejected", reason = "unknown_container", recoverable = false }
    end
    if not in_range(player, source.entity) or not in_range(player, destination.entity) then
        return { ok = false, status = "rejected", reason = "out_of_range", recoverable = false }
    end
    return service:Transfer(request)
end

local function action_fn(act)
    local service = world_service()
    if service == nil or act.doer == nil or act.target == nil then
        return false
    end
    local destination_id = service:StableIdOf(act.target)
    local inventory = act.doer.components.inventory
    if destination_id == nil or inventory == nil then
        return false
    end
    -- The source is a tracked container the doer currently has open.
    for opened in pairs(inventory.opencontainers or {}) do
        local source_id = service:StableIdOf(opened)
        if source_id ~= nil and source_id ~= destination_id then
            local container = opened.components.container
            for slot = 1, container:GetNumSlots() do
                local item = container:GetItemInSlot(slot)
                if item ~= nil then
                    local count = item.components.stackable ~= nil and item.components.stackable:StackSize() or 1
                    local result = authorised_transfer(act.doer, {
                        request_id = string.format("action:%s:%d:%d", act.doer.userid or "local", item.GUID, GLOBAL.GetTick()),
                        source_id = source_id,
                        destination_id = destination_id,
                        prefab = item.prefab,
                        count = count,
                    })
                    return result.ok == true
                end
            end
        end
    end
    return false
end

local ACTION = AddAction("RHENIUM_TRANSFER", "Transfer", action_fn)
ACTION.distance = 2
ACTION.mount_valid = false

AddComponentAction("SCENE", "container", function(inst, doer, actions, right)
    if right and inst:HasTag(TRACKED_TAG) and doer ~= nil and doer:HasTag("player") then
        actions[#actions + 1] = ACTION
    end
end)

AddStategraphActionHandler("wilson", GLOBAL.ActionHandler(ACTION, "doshortaction"))
AddStategraphActionHandler("wilson_client", GLOBAL.ActionHandler(ACTION, "doshortaction"))

AddModRPCHandler("rhenium_transfer", "request", function(player, request_id, source_id, destination_id, prefab, count)
    if type(request_id) ~= "string" or type(source_id) ~= "string" or type(destination_id) ~= "string"
        or type(prefab) ~= "string" or type(count) ~= "number" or count > MAX_RPC_COUNT then
        return
    end
    authorised_transfer(player, {
        -- Request ids are namespaced per user so one client cannot replay or
        -- shadow another client's request.
        request_id = (player ~= nil and player.userid or "unknown") .. ":" .. request_id,
        source_id = source_id,
        destination_id = destination_id,
        prefab = prefab,
        count = count,
    })
end)

AddPrefabPostInit("world", function(inst)
    if not inst.ismastersim then
        return
    end
    inst:AddComponent("containertransfer")
end)
