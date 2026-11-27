local TheWorldService = function()
    local world = GLOBAL.TheWorld
    if world == nil or not world.ismastersim then
        return nil
    end
    return world.components ~= nil and world.components.combattargetarbiter or nil
end

-- The arbiter lives on the master simulation only.
AddPrefabPostInit("world", function(inst)
    if not inst.ismastersim then
        return
    end
    inst:AddComponent("combattargetarbiter")
end)

-- Anything that can fight and can be hurt is followed from the moment it
-- exists. The component is attached one frame later because prefab
-- constructors add `health` and `combat` in no fixed order.
AddComponentPostInit("combat", function(_, inst)
    inst:DoTaskInTime(0, function()
        local service = TheWorldService()
        if service ~= nil and inst:IsValid() then
            service:TrackAutomatically(inst)
        end
    end)
end)

-- The client only says "I taunt" plus a retry token. Who taunts is the RPC's
-- own player, and which creatures are affected is decided from server-side
-- positions; no entity, damage, sequence number or duration is accepted.
AddModRPCHandler("rhenium_arbiter", "taunt", function(player, token)
    local service = TheWorldService()
    if service == nil or player == nil or type(token) ~= "string" then
        return
    end
    service:TauntNearby(player, token)
end)
