local type, ipairs, select = GLOBAL.type, GLOBAL.ipairs, GLOBAL.select

AddPrefabPostInit("world", function(world)
    if world.ismastersim and world.components.tradeescrow == nil then
        world:AddComponent("tradeescrow")
    end
end)

-- Every handler goes through this gate: the sender must be a server-provided
-- player and the component must exist on the master simulation.
local function with_component(player, run)
    local world = GLOBAL.TheWorld
    if player == nil or world == nil or not world.ismastersim then
        return
    end
    local component = world.components.tradeescrow
    if component ~= nil then
        run(component)
    end
end

local function decode_offer(...)
    local argc = select("#", ...)
    local packed = { ... }
    local offer = {}
    if argc % 2 == 1 then
        return nil
    end
    local cursor = 1
    while cursor < argc do
        local prefab, count = packed[cursor], packed[cursor + 1]
        local well_formed = type(prefab) == "string" and type(count) == "number"
        if not well_formed or offer[prefab] ~= nil then
            return nil
        end
        offer[prefab] = count
        cursor = cursor + 2
    end
    return offer
end

local HANDLERS = {
    open = function(player, target_userid)
        if type(target_userid) ~= "string" then
            return
        end
        with_component(player, function(component)
            for _, other in ipairs(GLOBAL.AllPlayers) do
                if other.userid == target_userid then
                    component:Open(player, other)
                    return
                end
            end
        end)
    end,
    offer = function(player, trade_id, ...)
        local offer = decode_offer(...)
        if type(trade_id) == "string" and offer ~= nil then
            with_component(player, function(component)
                component:Offer(player, trade_id, offer)
            end)
        end
    end,
    confirm = function(player, trade_id, seen_revision)
        if type(trade_id) == "string" and type(seen_revision) == "number" then
            with_component(player, function(component)
                component:Confirm(player, trade_id, seen_revision)
            end)
        end
    end,
    cancel = function(player, trade_id)
        if type(trade_id) == "string" then
            with_component(player, function(component)
                component:Cancel(player, trade_id)
            end)
        end
    end,
}

AddModRPCHandler("rhenium_trade", "open", HANDLERS.open)
AddModRPCHandler("rhenium_trade", "offer", HANDLERS.offer)
AddModRPCHandler("rhenium_trade", "confirm", HANDLERS.confirm)
AddModRPCHandler("rhenium_trade", "cancel", HANDLERS.cancel)
