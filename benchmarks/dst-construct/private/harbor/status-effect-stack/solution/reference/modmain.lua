local function service()
    local world = GLOBAL.TheWorld
    if world == nil or not world.ismastersim or world.components == nil then
        return nil
    end
    return world.components.statuseffects
end

local function track_player(player)
    local effects = service()
    if effects ~= nil and player ~= nil and type(player.userid) == "string" and player.userid ~= "" then
        effects:Track(player, player.userid)
    end
end

-- A client may only ask to cleanse itself. The handler forwards the real
-- player entity; the component reads `player.userid` and checks the tag
-- against its whitelist. No entity, id, count or time comes from the client.
AddModRPCHandler("rhenium_statuseffects", "cleanse", function(player, tag)
    local effects = service()
    if effects == nil or player == nil or type(tag) ~= "string" then
        return
    end
    effects:Cleanse(player, tag)
end)

AddPrefabPostInit("world", function(inst)
    if not inst.ismastersim then
        return inst
    end
    if inst.components.statuseffects == nil then
        inst:AddComponent("statuseffects")
    end
    inst:ListenForEvent("ms_playerjoined", function(_world, player)
        track_player(player)
        -- A revived player is alive again and needs a fresh registration.
        player:ListenForEvent("ms_respawnedfromghost", track_player)
    end)
    return inst
end)
