local TheWorldOf = function()
    return GLOBAL.TheWorld
end

local function attach(world)
    if world.ismastersim and world.components.waystonenetwork == nil then
        world:AddComponent("waystonenetwork")
    end
end

AddPrefabPostInit("world", attach)

local function only_strings(...)
    for index = 1, select("#", ...) do
        local value = select(index, ...)
        if type(value) ~= "string" or value == "" or value:len() > 64 then
            return false
        end
    end
    return true
end

-- The RPC carries three identifiers and nothing else. Who travels is decided by
-- the engine-supplied player entity (player.userid is read inside Travel).
local function on_travel_rpc(player, request_id, from_id, to_id, ...)
    if select("#", ...) > 0 or player == nil or player.userid == nil then
        return
    end
    if not only_strings(request_id, from_id, to_id) then
        return
    end
    local world = TheWorldOf()
    if world == nil or not world.ismastersim then
        return
    end
    local component = world.components.waystonenetwork
    if component ~= nil then
        component:Travel(player, request_id, from_id, to_id)
    end
end

AddModRPCHandler("rhenium_waystone", "travel", on_travel_rpc)
