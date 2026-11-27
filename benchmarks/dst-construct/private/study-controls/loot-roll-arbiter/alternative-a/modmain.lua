-- Loot Roll Arbiter: mod entry point.
--
-- The world gets a choice-free net_string on every simulation, the arbiter
-- component on the master simulation only, and clients may submit nothing
-- but their own choice through a single mod RPC.

local type = GLOBAL.type

local RPC_NAMESPACE = "rhenium_lootroll"

AddPrefabPostInit("world", function(inst)
    -- Network variables must exist on both server and clients, so this is
    -- created before the non-master early return.
    inst._lootroll_state = GLOBAL.net_string(inst.GUID, "lootrollarbiter.state", "lootrolldirty")

    local is_master = inst.ismastersim
    if is_master == nil and GLOBAL.TheWorld ~= nil then
        is_master = GLOBAL.TheWorld.ismastersim
    end
    if not is_master then
        return
    end

    inst:AddComponent("lootrollarbiter")
end)

-- The handler accepts a roll id, a choice and a revision only. The sender's
-- identity is taken from the player entity supplied by the engine; items,
-- seeds, player ids and deadlines can never be supplied by a client.
AddModRPCHandler(RPC_NAMESPACE, "choose", function(player, roll_id, choice, revision)
    local userid = player ~= nil and player.userid or nil
    if type(userid) ~= "string" or userid == "" then
        return { ok = false, code = "not_eligible" }
    end
    if type(roll_id) ~= "string" then
        return { ok = false, code = "unknown_roll" }
    end
    if type(choice) ~= "string" then
        return { ok = false, code = "invalid_choice" }
    end
    if type(revision) ~= "number" then
        return { ok = false, code = "invalid_revision" }
    end
    local world = GLOBAL.TheWorld
    local component = world ~= nil and world.components.lootrollarbiter or nil
    if component == nil then
        return { ok = false, code = "unknown_roll" }
    end
    return component:Choose(player, roll_id, choice, revision)
end)
