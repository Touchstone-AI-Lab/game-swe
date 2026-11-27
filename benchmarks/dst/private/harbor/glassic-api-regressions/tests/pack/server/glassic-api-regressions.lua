-- Hidden dedicated-server suite: Glassic API.
-- The library mod runs with its default settings. Every case calls the public
-- GlassicAPI functions the way a dependent mod does.

local FILTER = "TOOLS"
-- A client id as the network layer passes it; offline, it owns only default skins.
local USERID = "KU_rhenium01"

local function listed(filter)
    local names = {}
    for _, name in ipairs(CRAFTING_FILTERS[filter].recipes) do
        names[#names + 1] = name
    end
    return names
end

local function stored(filter)
    local count = 0
    for _ in pairs(CRAFTING_FILTERS[filter].recipes) do
        count = count + 1
    end
    return count
end

local function index_of(list, value)
    for index, item in ipairs(list) do
        if item == value then
            return index
        end
    end
end

local function occurrences(list, value)
    local count = 0
    for _, item in ipairs(list) do
        if item == value then
            count = count + 1
        end
    end
    return count
end

-- Restores the filter's recipe list after a case so later cases see the original.
local function with_filter(filter, fn)
    local recipes = CRAFTING_FILTERS[filter].recipes
    local saved = {}
    for key, value in pairs(recipes) do
        saved[key] = value
    end
    local ok, err = pcall(fn, listed(filter))
    for key in pairs(recipes) do
        recipes[key] = nil
    end
    for key, value in pairs(saved) do
        recipes[key] = value
    end
    assert(ok, err)
end

local function assert_same_set(before, after)
    assert(#after == #before, "the filter lists " .. #after .. " recipes instead of " .. #before)
    for _, name in ipairs(before) do
        assert(occurrences(after, name) == 1, name .. " is listed " .. occurrences(after, name) .. " times")
    end
end

local function has_character(name)
    for _, character in ipairs(DST_CHARACTERLIST) do
        if character == name then
            return true
        end
    end
    return false
end

local function inventory_has(skin)
    for _, item in ipairs(TheInventory:GetFullInventory()) do
        if item.item_type == skin then
            return true
        end
    end
    return false
end

-- The skins the default skin selection popup offers for an item, for a popup
-- opened for the given character.
local function popup_skins(character, item)
    local DefaultSkinSelectionPopup = require("screens/redux/defaultskinselection")
    local popup = setmetatable({ character = character }, { __index = DefaultSkinSelectionPopup })
    local names = {}
    for _, data in ipairs(popup:GetSkinsList(item)) do
        names[#names + 1] = data.item
    end
    return names
end

return function(ctx)
    ctx:case("sentinel: Glassic API is loaded", function()
        assert(GlassicAPI ~= nil, "GlassicAPI is missing")
        assert(type(GlassicAPI.RecipeSortAfter) == "function", "RecipeSortAfter is missing")
        assert(type(GlassicAPI.SkinHandler) == "table", "SkinHandler is missing")
        assert(#listed(FILTER) >= 6, "the " .. FILTER .. " filter is unexpectedly short")
    end)

    ctx:case("sorting the last recipe of a filter after the first keeps the filter intact", function()
        with_filter(FILTER, function(before)
            local moved, anchor = before[#before], before[1]
            GlassicAPI.RecipeSortAfter(moved, anchor, FILTER)
            local after = listed(FILTER)
            assert_same_set(before, after)
            assert(index_of(after, moved) == 2, moved .. " is at " .. tostring(index_of(after, moved)))
        end)
    end)

    ctx:case("sorting a recipe after a later one keeps every recipe of the filter listed", function()
        with_filter(FILTER, function(before)
            local moved, anchor = before[2], before[#before - 1]
            GlassicAPI.RecipeSortAfter(moved, anchor, FILTER)
            local after = listed(FILTER)
            assert(stored(FILTER) == #after, "the filter has holes: " .. stored(FILTER) .. " stored, " .. #after .. " listed")
            assert_same_set(before, after)
            assert(index_of(after, moved) == index_of(after, anchor) + 1, moved .. " is not right after " .. anchor)
        end)
    end)

    ctx:case("sorting a recipe before an earlier one keeps every recipe of the filter listed", function()
        with_filter(FILTER, function(before)
            local moved, anchor = before[#before - 1], before[2]
            GlassicAPI.RecipeSortBefore(moved, anchor, FILTER)
            local after = listed(FILTER)
            assert(stored(FILTER) == #after, "the filter has holes: " .. stored(FILTER) .. " stored, " .. #after .. " listed")
            assert_same_set(before, after)
            assert(index_of(after, moved) == index_of(after, anchor) - 1, moved .. " is not right before " .. anchor)
        end)
    end)

    ctx:case("sorting a recipe to the end of a filter keeps every recipe listed", function()
        with_filter(FILTER, function(before)
            local moved = before[3]
            GlassicAPI.RecipeSortAfter(moved, nil, FILTER)
            local after = listed(FILTER)
            assert(stored(FILTER) == #after, "the filter has holes: " .. stored(FILTER) .. " stored, " .. #after .. " listed")
            assert_same_set(before, after)
            assert(after[#after] == moved, moved .. " is not last")
        end)
    end)

    ctx:case("a spawn request for a vanilla character is accepted", function()
        assert(has_character("wendy"), "wendy is not a vanilla character here")
        local prefab = ValidateSpawnPrefabRequest(USERID, "wendy", "wendy_none", "", "", "", "")
        assert(prefab == "wendy", "a request for wendy spawned " .. tostring(prefab))
    end)

    ctx:case("a vanilla character that receives mod skins stays selectable", function()
        GlassicAPI.SkinHandler.AddModSkins({ wilson = { "wilson_rhenium_probe" } })
        local first = ValidateSpawnPrefabRequest(USERID, "wilson", "wilson_none", "", "", "", "")
        local listed_after_first = has_character("wilson")
        local second = ValidateSpawnPrefabRequest(USERID, "wilson", "wilson_none", "", "", "", "")
        assert(first == "wilson", "the first request spawned " .. tostring(first))
        assert(listed_after_first, "wilson left the character list after a spawn request")
        assert(second == "wilson", "the second request spawned " .. tostring(second))
    end)

    -- A mod character is registered the way the mod loader registers one, by name
    -- in MODCHARACTERLIST, and removed again afterwards.
    ctx:case("a mod character that receives mod skins is only borrowed into the base character list", function()
        local name = "rheniumprobe"
        table.insert(MODCHARACTERLIST, name)
        local ok, err = pcall(function()
            GlassicAPI.SkinHandler.AddModSkins({ [name] = { name .. "_rhenium" } })
            local spawned = ValidateSpawnPrefabRequest(USERID, name, name .. "_none", "", "", "", "")
            assert(spawned == name, "a request for the mod character spawned " .. tostring(spawned))
            assert(not has_character(name), "the mod character was left in DST_CHARACTERLIST")
        end)
        for index = #MODCHARACTERLIST, 1, -1 do
            if MODCHARACTERLIST[index] == name then
                table.remove(MODCHARACTERLIST, index)
            end
        end
        assert(ok, err)
    end)

    ctx:case("an item without a skin reports an empty skin build", function()
        local axe = SpawnPrefab("axe")
        local ok, build = pcall(function()
            return axe.AnimState:GetSkinBuild()
        end)
        axe:Remove()
        assert(ok, "reading the skin build raised: " .. tostring(build))
        assert(build == "", "an unskinned axe reports the skin build " .. tostring(build))
    end)

    ctx:case("an item with a mod skin reports the mod skin's build", function()
        local axe = SpawnPrefab("axe")
        -- The library's SpawnPrefab names the entity's mod skin this way.
        axe.skinname = "axe_rhenium_probe"
        local ok, build = pcall(function()
            return axe.AnimState:GetSkinBuild()
        end)
        axe:Remove()
        assert(ok, "reading the skin build raised: " .. tostring(build))
        assert(build == "axe_rhenium_probe", "a mod-skinned axe reports the skin build " .. tostring(build))
    end)

    ctx:case("an item's skin build can be read while the item is removed", function()
        local axe = SpawnPrefab("axe")
        local ok, build
        axe:ListenForEvent("onremove", function(inst)
            ok, build = pcall(function()
                return inst.AnimState:GetSkinBuild()
            end)
        end)
        axe:Remove()
        assert(ok ~= nil, "the onremove listener did not run")
        assert(ok, "reading the skin build on removal raised: " .. tostring(build))
        assert(build == "", "an unskinned axe reports the skin build " .. tostring(build) .. " on removal")
    end)

    ctx:case("a mod skin that anyone may use is listed in the inventory", function()
        GlassicAPI.SkinHandler.AddModSkins({ axe = { "axe_rhenium_open" } })
        assert(inventory_has("axe_rhenium_open"), "the open mod skin is not in the inventory")
    end)

    ctx:case("a mod skin that its test refuses is left out of the inventory", function()
        GlassicAPI.SkinHandler.AddModSkins({
            axe = { { name = "axe_rhenium_locked", test_fn = function() return false end } },
        })
        assert(not GlassicAPI.SkinHandler.ValidateModSkin("axe_rhenium_locked"), "the locked skin passes its own test")
        assert(not inventory_has("axe_rhenium_locked"), "the locked mod skin is in the inventory")
    end)

    ctx:case("a character-exclusive skin is offered to its character", function()
        GlassicAPI.SkinHandler.AddModSkins({
            axe = { { name = "axe_rhenium_wendy", exclusive_char = "wendy" }, "axe_rhenium_shared" },
        })
        local skins = popup_skins("wendy", "axe")
        assert(index_of(skins, "axe_rhenium_wendy"), "Wendy is not offered her exclusive axe skin")
        assert(index_of(skins, "axe_rhenium_shared"), "Wendy is not offered the shared axe skin")
    end)

    ctx:case("a character-exclusive skin is not offered to another character", function()
        GlassicAPI.SkinHandler.AddModSkins({
            axe = { { name = "axe_rhenium_wendy", exclusive_char = "wendy" }, "axe_rhenium_shared" },
        })
        local skins = popup_skins("wilson", "axe")
        assert(index_of(skins, "axe_rhenium_shared"), "Wilson is not offered the shared axe skin")
        assert(not index_of(skins, "axe_rhenium_wendy"), "Wilson is offered Wendy's exclusive axe skin")
    end)
end
