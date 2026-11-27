local CHOICES = { need = true, greed = true, pass = true }

-- Clients may only state their own choice. Identity always comes from the
-- connected player entity; the item, the eligible set, the seed and the
-- deadline are decided on the server and cannot be reached from this handler.
AddModRPCHandler("rhenium_lootroll", "choose", function(player, roll_id, choice, revision)
    local userid = type(player) == "table" and player.userid or nil
    if type(userid) ~= "string" or userid == "" then
        return
    end
    if type(roll_id) ~= "string" or type(revision) ~= "number" or not CHOICES[choice] then
        return
    end
    local world = GLOBAL.TheWorld
    local service = world ~= nil and world.ismastersim and world.components.lootrollarbiter or nil
    if service ~= nil then
        service:Choose(player, roll_id, choice, revision)
    end
end)

local function decode_state(encoded)
    local rolls = {}
    for roll_id, item, chosen, total in string.gmatch(encoded or "", "([^|;]+)|([^|;]+)|(%d+)|(%d+)") do
        rolls[#rolls + 1] = {
            roll_id = roll_id, item = item,
            chosen = GLOBAL.tonumber(chosen), total = GLOBAL.tonumber(total),
        }
    end
    return rolls
end

AddPrefabPostInit("world", function(inst)
    -- Net variables must exist on both sides, so this precedes the guard.
    inst._lootroll_state = GLOBAL.net_string(inst.GUID, "lootrollarbiter.state", "lootrolldirty")

    if not inst.ismastersim then
        inst:ListenForEvent("lootrolldirty", function()
            inst.lootroll_public = decode_state(inst._lootroll_state:value())
            inst:PushEvent("lootrollchanged", inst.lootroll_public)
        end)
        return inst
    end

    if inst.components.lootrollarbiter == nil then
        inst:AddComponent("lootrollarbiter")
    end
    return inst
end)
