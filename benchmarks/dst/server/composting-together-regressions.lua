-- Hidden dedicated-server suite: Composting Together.
-- The operator runs the mod with its default settings except Attract Fireflies,
-- which is set to "always". A server-spawned Wilson stands in for the player.
-- Composting time is advanced with the game's own long-update path, the same
-- one the server uses when it catches up on time that passed.

local function land_origin()
    local portal = TheSim:FindFirstEntityWithTag("multiplayer_portal")
    if portal ~= nil then
        local x, y, z = portal.Transform:GetWorldPosition()
        return Vector3(x, 0, z)
    end
    return Vector3(0, 0, 0)
end

local ORIGIN = land_origin()
local DAY = TUNING.TOTAL_DAY_TIME
local spawned = {}

local function spawn(prefab, dx, dz)
    local inst = SpawnPrefab(prefab)
    assert(inst ~= nil, "could not spawn " .. prefab)
    inst.Transform:SetPosition(ORIGIN.x + (dx or 0), 0, ORIGIN.z + (dz or 0))
    spawned[#spawned + 1] = inst
    return inst
end

local function cleanup()
    for _, inst in ipairs(spawned) do
        if inst:IsValid() then
            inst:Remove()
        end
    end
    spawned = {}
end

local function make_player(dx, dz)
    local player = spawn("wilson", dx, dz)
    player.components.health:SetInvincible(true)
    return player
end

-- Fills a pile with `count` items of `prefab`, each at `freshness` when perishable.
local function fill(pile, prefab, count, freshness)
    for _ = 1, count do
        local item = SpawnPrefab(prefab)
        if freshness ~= nil and item.components.perishable ~= nil then
            item.components.perishable:SetPercent(freshness)
        end
        assert(pile.components.container:GiveItem(item), "the pile refused " .. prefab)
    end
end

local function compost(player, pile)
    return BufferedAction(player, pile, ACTIONS.COMPOST):Do()
end

local function harvest(player, pile)
    return pcall(function()
        return BufferedAction(player, pile, ACTIONS.HARVEST):Do()
    end)
end

local function poop_in(player)
    local total = 0
    for _, item in ipairs(player.components.inventory:FindItems(function(item) return item.prefab == "poop" end)) do
        total = total + item.components.stackable:StackSize()
    end
    return total
end

local function offers_harvest(pile, player)
    local actions = {}
    pile:CollectActions("SCENE", player, actions, false)
    for _, action in ipairs(actions) do
        if action == ACTIONS.HARVEST then
            return true
        end
    end
    return false
end

local function status(pile, player)
    return pile.components.inspectable:GetStatus(player)
end

local function remove_fireflies(pile)
    for _, child in pairs(pile.children or {}) do
        if type(child) == "table" and child.prefab == "fireflies" and child:IsValid() then
            child:Remove()
        end
    end
end

return function(ctx)
    ctx:case("sentinel: the compost pile is available on the server", function()
        local pile = spawn("compostpile")
        local ok = pile.components.composter ~= nil and pile.components.container ~= nil
        cleanup()
        assert(ok, "the compost pile has no composter")
        assert(ACTIONS.COMPOST ~= nil, "the compost action is not registered")
    end)

    ctx:case("the compost pile recipe costs the configured rocks, logs and manure", function()
        local recipe = AllRecipes.compostpile
        assert(recipe ~= nil, "there is no compost pile recipe")
        local amounts = {}
        for _, ingredient in ipairs(recipe.ingredients) do
            amounts[ingredient.type] = ingredient.amount
        end
        assert(amounts.rocks == 6, "rocks cost " .. tostring(amounts.rocks))
        assert(amounts.log == 3, "logs cost " .. tostring(amounts.log))
        assert(amounts.poop == 4, "manure costs " .. tostring(amounts.poop))
    end)

    ctx:case("a pile needs at least three items before it composts", function()
        local player = make_player()
        local pile = spawn("compostpile", 4, 0)
        fill(pile, "twigs", 2)
        local early = pile.components.composter:CanCompost()
        fill(pile, "twigs", 1)
        local ready = pile.components.composter:CanCompost()
        cleanup()
        assert(not early, "two items were enough to compost")
        assert(ready, "three items were not enough to compost")
    end)

    ctx:case("a small batch takes three days to become compost", function()
        local player = make_player()
        local pile = spawn("compostpile", 4, 0)
        fill(pile, "twigs", 3)
        assert(compost(player, pile), "composting did not start")
        pile:LongUpdate(DAY * 2.5)
        local early = offers_harvest(pile, player)
        pile:LongUpdate(DAY * 0.6)
        local late = offers_harvest(pile, player)
        cleanup()
        assert(not early, "the small batch was ready after two and a half days")
        assert(late, "the small batch was not ready after three days")
    end)

    ctx:case("a finished pile reports that it is done when inspected", function()
        local player = make_player()
        local pile = spawn("compostpile", 4, 0)
        fill(pile, "twigs", 3)
        compost(player, pile)
        pile:LongUpdate(DAY * 4)
        local shown = status(pile, player)
        cleanup()
        assert(shown == "DONE", "a finished pile is inspected as " .. tostring(shown))
    end)

    ctx:case("harvesting a finished small batch hands over two manure", function()
        local player = make_player()
        local pile = spawn("compostpile", 4, 0)
        fill(pile, "twigs", 3)
        compost(player, pile)
        pile:LongUpdate(DAY * 4)
        harvest(player, pile)
        local poop = poop_in(player)
        remove_fireflies(pile)
        cleanup()
        assert(poop == 2, "harvest gave " .. poop .. " manure")
    end)

    ctx:case("harvesting with fireflies attracted completes and the pile can be refilled", function()
        local player = make_player()
        local pile = spawn("compostpile", 4, 0)
        fill(pile, "twigs", 3)
        compost(player, pile)
        pile:LongUpdate(DAY * 4)
        local ok, err = harvest(player, pile)
        local reopenable = pile.components.container.canbeopened
        local still_done = offers_harvest(pile, player)
        remove_fireflies(pile)
        cleanup()
        assert(ok, "harvesting raised: " .. tostring(err))
        assert(reopenable, "the harvested pile cannot be opened again")
        assert(not still_done, "the harvested pile still offers a harvest")
    end)

    ctx:case("a rich batch that makes the soil fertile starts composting", function()
        local player = make_player()
        local pile = spawn("compostpile", 4, 0)
        fill(pile, "carrot", 5, 0.2)
        local ok, err = pcall(compost, player, pile)
        local shown = status(pile, player)
        cleanup()
        assert(ok, "starting the rich batch raised: " .. tostring(err))
        assert(shown == "COMPOSTING_FERTILE", "the rich batch is inspected as " .. tostring(shown))
    end)

    ctx:case("the rotten-food bonus of one batch is not paid again on the next", function()
        local player = make_player()
        local pile = spawn("compostpile", 4, 0)
        fill(pile, "carrot", 3, 0.2)
        compost(player, pile)
        pile:LongUpdate(DAY * 4)
        harvest(player, pile)
        local first = poop_in(player)
        remove_fireflies(pile)
        fill(pile, "twigs", 3)
        compost(player, pile)
        pile:LongUpdate(DAY * 4)
        harvest(player, pile)
        local second = poop_in(player) - first
        remove_fireflies(pile)
        cleanup()
        assert(first == 6, "the rotten batch gave " .. first .. " manure")
        assert(second == 2, "the following plain batch gave " .. second .. " manure")
    end)

    ctx:case("a composting pile that is saved and reloaded finishes on time", function()
        local player = make_player()
        local pile = spawn("compostpile", 4, 0)
        fill(pile, "twigs", 3)
        compost(player, pile)
        local remaining = pile.components.composter:GetTimeToCompost()
        pile:LongUpdate(remaining / 3)
        local record = pile:GetPersistData()
        local reloaded = spawn("compostpile", 8, 0)
        reloaded:SetPersistData(record)
        local left = remaining - remaining / 3
        reloaded:LongUpdate(left - 5)
        local early = offers_harvest(reloaded, player)
        reloaded:LongUpdate(10)
        local late = offers_harvest(reloaded, player)
        cleanup()
        assert(not early, "the reloaded pile finished early")
        assert(late, "the reloaded pile did not finish")
    end)

    ctx:case("a finished pile still offers its harvest after a save and reload", function()
        local player = make_player()
        local pile = spawn("compostpile", 4, 0)
        fill(pile, "twigs", 3)
        compost(player, pile)
        pile:LongUpdate(DAY * 4)
        local record = pile:GetPersistData()
        local reloaded = spawn("compostpile", 8, 0)
        reloaded:SetPersistData(record)
        local offered = offers_harvest(reloaded, player)
        cleanup()
        assert(offered, "the reloaded finished pile offers no harvest")
    end)

    ctx:case("setup: an empty pile is saved and reloaded", function()
        local pile = spawn("compostpile", -6, 6)
        local reloaded = spawn("compostpile", -10, 6)
        reloaded:SetPersistData(pile:GetPersistData())
        ctx.empty_reloaded = reloaded
    end)

    ctx:after(2, function()
        ctx:case("an empty pile stays empty and usable after a save and reload", function()
            local player = make_player(-8, 8)
            local pile = ctx.empty_reloaded
            local offered = offers_harvest(pile, player)
            local openable = pile.components.container.canbeopened
            cleanup()
            assert(not offered, "the empty pile offers a harvest after reloading")
            assert(openable, "the empty pile cannot be opened after reloading")
        end)
    end)
end
