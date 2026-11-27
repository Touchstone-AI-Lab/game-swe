local function depot()
    local world = GLOBAL.TheWorld
    if world == nil or not world.ismastersim then
        return nil
    end
    return world.components.fuelration
end

local function on_deposit_rpc(player, request_id, item_prefab, count)
    -- Everything but these three values is decided by the server.
    local service = depot()
    if service == nil or player == nil then
        return
    end
    if GLOBAL.type(request_id) == "string" and GLOBAL.type(item_prefab) == "string"
        and GLOBAL.type(count) == "number" then
        service:Deposit(player, request_id, item_prefab, count)
    end
end

AddModRPCHandler("rhenium_fuel", "deposit", on_deposit_rpc)

AddPrefabPostInit("world", function(world)
    if world.ismastersim then
        world:AddComponent("fuelration")
    end
end)
