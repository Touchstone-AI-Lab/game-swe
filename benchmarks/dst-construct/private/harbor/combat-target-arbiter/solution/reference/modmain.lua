local TAUNT_RANGE_SQ = 12 * 12
local TAUNT_DURATION = 6
local SESSION_PREFIX = "session:"

local function service()
    local world = GLOBAL.TheWorld
    if world == nil or not world.ismastersim or world.components == nil then
        return nil
    end
    return world.components.combattargetarbiter
end

-- Creatures get a session-scoped id: their GUID is only meaningful inside
-- this process. Players are tracked by the component under their user id.
AddComponentPostInit("combat", function(_component, inst)
    if GLOBAL.TheWorld == nil or not GLOBAL.TheWorld.ismastersim or inst:HasTag("player") then
        return
    end
    inst:DoTaskInTime(0, function()
        local arbiter = service()
        if arbiter ~= nil and inst:IsValid() and inst.components.health ~= nil then
            arbiter:Track(inst, SESSION_PREFIX .. tostring(inst.GUID))
        end
    end)
end)

-- A client names only the creature it wants to taunt. The taunting entity is
-- the RPC's own player, the duration is fixed here, and reach is measured
-- from server positions.
AddModRPCHandler("rhenium_arbiter", "taunt", function(player, source_id, token)
    local arbiter = service()
    if arbiter == nil or player == nil or type(player.userid) ~= "string" or player.userid == "" then
        return
    end
    if type(source_id) ~= "string" or type(token) ~= "string" or token == "" or #token > 32 then
        return
    end
    local record = arbiter.by_id[source_id]
    local source = record ~= nil and record.entity or nil
    if source == nil or not source:IsValid() or source == player then
        return
    end
    if player.components.health == nil or player.components.health:IsDead() then
        return
    end
    if player:GetDistanceSqToInst(source) > TAUNT_RANGE_SQ then
        return
    end
    arbiter:Taunt(player.userid .. ":" .. token, source, player, TAUNT_DURATION)
end)

AddPrefabPostInit("world", function(inst)
    if not inst.ismastersim then
        return inst
    end
    if inst.components.combattargetarbiter == nil then
        inst:AddComponent("combattargetarbiter")
    end
    return inst
end)
