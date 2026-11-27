-- Server wiring for the trade escrow. RPC payloads carry only strings and
-- numbers: a trade id, a target userid, prefab/count pairs and a revision. The
-- acting player always comes from the server, never from the payload.

local function service()
    local world = GLOBAL.TheWorld
    if world == nil or not world.ismastersim or world.components == nil then
        return nil
    end
    return world.components.tradeescrow
end

local function find_player(userid)
    if GLOBAL.type(userid) ~= "string" or userid == "" then
        return nil
    end
    for _, candidate in GLOBAL.ipairs(GLOBAL.AllPlayers) do
        if candidate.userid == userid then
            return candidate
        end
    end
    return nil
end

-- Turns the alternating prefab/count varargs into an offer map. Anything that
-- is not a (string, number) pair, an odd argument count or a repeated prefab
-- drops the whole request.
local function parse_pairs(...)
    local total = GLOBAL.select("#", ...)
    if total % 2 ~= 0 then
        return nil
    end
    local items = {}
    for index = 1, total, 2 do
        local prefab = GLOBAL.select(index, ...)
        local count = GLOBAL.select(index + 1, ...)
        if GLOBAL.type(prefab) ~= "string" or GLOBAL.type(count) ~= "number" or items[prefab] ~= nil then
            return nil
        end
        items[prefab] = count
    end
    return items
end

AddModRPCHandler("rhenium_trade", "open", function(player, target_userid)
    local escrow = service()
    local target = find_player(target_userid)
    if escrow ~= nil and player ~= nil and target ~= nil then
        escrow:Open(player, target)
    end
end)

AddModRPCHandler("rhenium_trade", "offer", function(player, trade_id, ...)
    local escrow = service()
    local items = parse_pairs(...)
    if escrow ~= nil and player ~= nil and GLOBAL.type(trade_id) == "string" and items ~= nil then
        escrow:Offer(player, trade_id, items)
    end
end)

AddModRPCHandler("rhenium_trade", "confirm", function(player, trade_id, seen_revision)
    local escrow = service()
    if escrow ~= nil and player ~= nil and GLOBAL.type(trade_id) == "string"
        and GLOBAL.type(seen_revision) == "number" then
        escrow:Confirm(player, trade_id, seen_revision)
    end
end)

AddModRPCHandler("rhenium_trade", "cancel", function(player, trade_id)
    local escrow = service()
    if escrow ~= nil and player ~= nil and GLOBAL.type(trade_id) == "string" then
        escrow:Cancel(player, trade_id)
    end
end)

AddPrefabPostInit("world", function(inst)
    -- Authority lives on the master simulation only.
    if not inst.ismastersim then
        return
    end
    if inst.components.tradeescrow == nil then
        inst:AddComponent("tradeescrow")
    end
end)
