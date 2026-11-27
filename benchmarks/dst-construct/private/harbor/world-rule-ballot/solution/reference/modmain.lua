local TheNet = GLOBAL.TheNet

AddReplicableComponent("ruleballot")

-- Clients may only express their own choice. Identity always comes from the
-- connected player entity; the electorate, deadline, quorum and rule to apply
-- are decided on the server and are not reachable from this handler.
AddModRPCHandler("rhenium_ballot", "cast", function(player, proposal_id, choice_id, revision)
    local voter_id = player ~= nil and player.userid or nil
    if type(voter_id) ~= "string" or voter_id == "" then
        return
    end
    if type(proposal_id) ~= "string" or type(choice_id) ~= "string" or type(revision) ~= "number" then
        return
    end
    local world = GLOBAL.TheWorld
    local service = world ~= nil and world.components ~= nil and world.components.ruleballot or nil
    if service ~= nil then
        service:Cast(player, proposal_id, choice_id, revision)
    end
end)

AddPrefabPostInit("world", function(inst)
    -- Authority lives on the master simulation only (TheWorld.ismastersim).
    if not inst.ismastersim then
        return inst
    end
    if inst.components.ruleballot == nil then
        inst:AddComponent("ruleballot")
    end
    return inst
end)
