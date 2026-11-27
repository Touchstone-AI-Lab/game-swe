-- Wiring only: replica registration, the world netvar, the world component and
-- the RPC surface. All decisions are taken by components/rescuedispatch on the
-- master simulation.

local NAMESPACE = "rhenium_rescue"
local ID_LIMIT = 48

AddReplicableComponent("rescuedispatch")

AddPrefabPostInit("world", function(inst)
    -- The net variable exists on both sides, so it is created before the
    -- client-side early return.
    if inst._rescue_state == nil then
        inst._rescue_state = GLOBAL.net_string(inst.GUID, "rescuedispatch.state", "rescuedispatchdirty")
    end
    if not inst.ismastersim then
        return
    end
    inst:AddComponent("rescuedispatch")
end)

local function authority()
    local world = GLOBAL.TheWorld
    if world ~= nil and world.ismastersim and world.components ~= nil then
        return world.components.rescuedispatch
    end
    return nil
end

local function clean_id(value)
    return GLOBAL.type(value) == "string" and #value > 0 and #value <= ID_LIMIT
        and GLOBAL.string.find(value, "[%c]") == nil
end

local function sender_id(player)
    if GLOBAL.type(player) == "table" and GLOBAL.type(player.userid) == "string" and player.userid ~= "" then
        return player.userid
    end
    return nil
end

-- Every handler receives the real player entity from the RPC framework. The
-- payload is one opaque identifier; helper identity, target identity, health,
-- severity and position are all taken from the server side.
local function route(name, needs_id, deliver)
    AddModRPCHandler(NAMESPACE, name, function(player, identifier)
        local service = authority()
        local userid = sender_id(player)
        if service == nil or userid == nil then
            return
        end
        if needs_id and not clean_id(identifier) then
            return
        end
        deliver(service, player, userid, identifier)
    end)
end

route("request", true, function(service, player, userid, request_id)
    -- Request ids are scoped to their sender so two players cannot collide.
    service:Request(userid .. "/" .. request_id, player)
end)

route("volunteer", true, function(service, player, _, request_id)
    service:Volunteer(request_id, player)
end)

route("heartbeat", true, function(service, player, _, lease_id)
    service:Heartbeat(lease_id, player)
end)

route("complete", true, function(service, player, _, lease_id)
    service:Complete(lease_id, player)
end)

route("cancel", false, function(service, player)
    service:Cancel(player)
end)
