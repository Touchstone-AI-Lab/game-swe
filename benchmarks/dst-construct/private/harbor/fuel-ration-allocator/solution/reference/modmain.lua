-- The RPC payload carries a request id, a prefab name and a count. The player
-- comes from the server; units, depot state and consumers never come from a client.
AddModRPCHandler("rhenium_fuel", "deposit", function(player, request_id, item_prefab, count)
    if player == nil or type(request_id) ~= "string" or type(item_prefab) ~= "string"
        or type(count) ~= "number" then
        return
    end
    local world = GLOBAL.TheWorld
    local service = world ~= nil and world.ismastersim and world.components.fuelration or nil
    if service ~= nil then
        service:Deposit(player, request_id, item_prefab, count)
    end
end)

AddPrefabPostInit("world", function(inst)
    -- Authority lives on the master simulation only.
    if not inst.ismastersim then
        return
    end
    if inst.components.fuelration == nil then
        inst:AddComponent("fuelration")
    end
end)
