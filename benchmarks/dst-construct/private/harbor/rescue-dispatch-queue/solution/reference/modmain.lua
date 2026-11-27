AddReplicableComponent("rescuedispatch")

local function service()
    local world = GLOBAL.TheWorld
    if world == nil or not world.ismastersim or world.components == nil then
        return nil
    end
    return world.components.rescuedispatch
end

local function is_token(value)
    return type(value) == "string" and value ~= "" and #value <= 64
end

-- Identity always comes from the connected player entity (player.userid).
-- Clients send only request or lease identifiers: never a severity, a
-- position, a helper id or another player's id.
AddModRPCHandler("rhenium_rescue", "request", function(player, request_id)
    local dispatch = service()
    if dispatch ~= nil and player ~= nil and is_token(request_id) then
        dispatch:Request(player.userid .. ":" .. request_id, player)
    end
end)

AddModRPCHandler("rhenium_rescue", "volunteer", function(player, request_id)
    local dispatch = service()
    if dispatch ~= nil and player ~= nil and is_token(request_id) then
        dispatch:Volunteer(request_id, player)
    end
end)

AddModRPCHandler("rhenium_rescue", "heartbeat", function(player, lease_id)
    local dispatch = service()
    if dispatch ~= nil and player ~= nil and is_token(lease_id) then
        dispatch:Heartbeat(lease_id, player)
    end
end)

AddModRPCHandler("rhenium_rescue", "complete", function(player, lease_id)
    local dispatch = service()
    if dispatch ~= nil and player ~= nil and is_token(lease_id) then
        dispatch:Complete(lease_id, player)
    end
end)

AddModRPCHandler("rhenium_rescue", "cancel", function(player)
    local dispatch = service()
    if dispatch ~= nil and player ~= nil then
        dispatch:Cancel(player)
    end
end)

AddPrefabPostInit("world", function(inst)
    if not inst.ismastersim then
        return inst
    end
    if inst.components.rescuedispatch == nil then
        inst:AddComponent("rescuedispatch")
    end
    return inst
end)
