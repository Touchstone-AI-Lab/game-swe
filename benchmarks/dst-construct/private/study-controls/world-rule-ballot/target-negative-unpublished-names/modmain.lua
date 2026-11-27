local TheNet = GLOBAL.TheNet
local net_string = GLOBAL.net_string

local STATE_EVENT = "ruleballotdirty"

AddReplicableComponent("ruleballot")

local function on_state_dirty(world)
    local view = world.replica ~= nil and world.replica.ruleballot or nil
    if view ~= nil then
        view:Refresh()
    end
end

AddPrefabPostInit("world", function(inst)
    -- The network variable exists on both sides and is created before the
    -- master-simulation guard so that server and clients agree on its order.
    inst._ballot_state = net_string(inst.GUID, "ruleballot.state", STATE_EVENT)

    if not inst.ismastersim then
        inst:ListenForEvent(STATE_EVENT, on_state_dirty)
        return inst
    end

    inst:AddComponent("ruleballot")
    return inst
end)

local function is_wire_revision(value)
    return type(value) == "number" and value >= 0 and value < 2 ^ 31 and value % 1 == 0
end

-- The only thing a client can say is "I choose this option". Who is speaking
-- comes from the connection (player.userid is read by the component), and no
-- handler exposes Open, Close or Cancel.
AddModRPCHandler("rhenium_ballot", "cast", function(player, proposal_id, choice_id, revision)
    if player == nil or type(player.userid) ~= "string" then
        return
    end
    if type(proposal_id) ~= "string" or type(choice_id) ~= "string" or not is_wire_revision(revision) then
        return
    end
    local world = GLOBAL.TheWorld
    if world == nil or not world.ismastersim or world.components.ruleballot == nil then
        return
    end
    world.components.ruleballot:Cast(player, proposal_id, choice_id, revision)
end)

-- Dedicated servers have no vote UI; an operator starts a configured proposal
-- from the server console only. Remote console input never reaches this path
-- with client-chosen contents because only the name of a fixed entry is used.
GLOBAL.rawset(GLOBAL, "c_ruleballot", function(name)
    local world = GLOBAL.TheWorld
    if TheNet == nil or not TheNet:GetIsServer() or world == nil or world.components.ruleballot == nil then
        return nil
    end
    return world.components.ruleballot:OpenConfigured(name)
end)
