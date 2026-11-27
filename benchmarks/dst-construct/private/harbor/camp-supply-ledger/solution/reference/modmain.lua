-- The RPC payload carries only a request identifier and a bundle name. The
-- player comes from the server; prefabs, counts, the day and quotas never do.
AddModRPCHandler("rhenium_supply", "claim", function(player, request_id, bundle_id)
    if player == nil or type(request_id) ~= "string" or type(bundle_id) ~= "string" then
        return
    end
    local world = GLOBAL.TheWorld
    local service = world ~= nil and world.components ~= nil and world.components.campsupplyledger or nil
    if service ~= nil then
        service:Claim(player, request_id, bundle_id)
    end
end)

AddPrefabPostInit("world", function(inst)
    -- Authority lives on the master simulation only (TheWorld.ismastersim).
    if not inst.ismastersim then
        return
    end
    if inst.components.campsupplyledger == nil then
        inst:AddComponent("campsupplyledger")
    end
end)
