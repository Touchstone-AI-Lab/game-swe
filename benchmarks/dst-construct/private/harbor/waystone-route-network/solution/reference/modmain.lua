local function service()
    local world = GLOBAL.TheWorld
    if world == nil or not world.ismastersim or world.components == nil then
        return nil
    end
    return world.components.waystonenetwork
end

local function is_token(value)
    return type(value) == "string" and value ~= "" and #value <= 64
end

-- The traveler is always the connected player entity supplied by the engine
-- (player.userid inside Travel). Clients send only a request id and two node
-- ids: never a position, a price, a route or another player's identity.
AddModRPCHandler("rhenium_waystone", "travel", function(player, request_id, from_id, to_id)
    local network = service()
    if network ~= nil and player ~= nil and is_token(request_id) and is_token(from_id) and is_token(to_id) then
        network:Travel(player, request_id, from_id, to_id)
    end
end)

AddPrefabPostInit("world", function(inst)
    if not inst.ismastersim then
        return inst
    end
    if inst.components.waystonenetwork == nil then
        inst:AddComponent("waystonenetwork")
    end
    return inst
end)
