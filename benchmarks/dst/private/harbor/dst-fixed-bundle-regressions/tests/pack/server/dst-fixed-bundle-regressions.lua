-- Hidden dedicated-server suite: DST Fixed, gifts and bundles.
-- Runs on the master simulation with Inventory Unwrap enabled and Show Bundle on
-- (its default). A server-spawned Wilson stands in for the player who unwraps.

-- Every case runs synchronously in one simulation frame near the spawn portal,
-- so nothing moves between an action and its assertions.
local function land_origin()
    local portal = TheSim:FindFirstEntityWithTag("multiplayer_portal")
    if portal ~= nil then
        local x, y, z = portal.Transform:GetWorldPosition()
        return Vector3(x, 0, z)
    end
    return Vector3(0, 0, 0)
end

local ORIGIN = land_origin()

local spawned = {}

-- Offsets are relative to the land origin.
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

local function make_player()
    local player = spawn("wilson")
    player.components.health:SetInvincible(true)
    return player
end

-- A bundle of `prefab` wrapped from real entities, as a player's bundling wrap does.
local function wrap(bundle_prefab, items)
    local bundle = spawn(bundle_prefab)
    local entities = {}
    for _, item in ipairs(items) do
        entities[#entities + 1] = type(item) == "string" and SpawnPrefab(item) or item
    end
    bundle.components.unwrappable:WrapItems(entities)
    for _, item in ipairs(entities) do
        item:Remove()
    end
    return bundle
end

local function count_in(inventory_or_container, prefab)
    local total = 0
    local items = inventory_or_container:FindItems(function(item)
        return item.prefab == prefab
    end)
    for _, item in ipairs(items) do
        total = total + (item.components.stackable ~= nil and item.components.stackable:StackSize() or 1)
    end
    return total
end

local function nearby(prefab, dx, dz, radius)
    local found = {}
    for _, ent in ipairs(TheSim:FindEntities(ORIGIN.x + dx, 0, ORIGIN.z + dz, radius, nil, { "INLIMBO" })) do
        if ent.prefab == prefab and ent:IsValid() then
            found[#found + 1] = ent
        end
    end
    return found
end

-- Asks the server for a bundle preview the way a hovering client does and
-- returns the preview entries the server sends back.
local function request_preview(modname, player, target)
    local rpc = MOD_RPC[modname] and MOD_RPC[modname].ShowBundle
    assert(rpc ~= nil, "the Show Bundle request is not registered")
    local handler = MOD_RPC_HANDLERS[modname][rpc.id]
    local sent = nil
    local original = SendModRPCToClient
    SendModRPCToClient = function(id_table, userid, entity, data)
        sent = { entity = entity, data = data }
    end
    local ok, err = pcall(handler, player, target)
    SendModRPCToClient = original
    assert(ok, err)
    assert(sent ~= nil, "the server sent no preview")
    assert(sent.entity == target, "the preview was sent for another entity")
    local loaded, entries = RunInSandboxSafe("return {" .. sent.data .. "}")
    assert(loaded and type(entries) == "table", "the preview payload does not parse")
    return entries
end

local function preview_prefabs(entries)
    local names = {}
    for index = 1, 8 do
        local entry = entries[index]
        if entry ~= nil then
            names[#names + 1] = tostring(entry.prefab)
        end
    end
    return table.concat(names, ",")
end

return function(ctx)
    local modname = ctx.modname

    ctx:case("sentinel: DST Fixed is loaded with Show Bundle and Inventory Unwrap", function()
        assert(SB ~= nil and type(SB.MakeItemData) == "function", "Show Bundle is not loaded")
        assert(MOD_RPC[modname] ~= nil and MOD_RPC[modname].ShowBundle ~= nil, "Show Bundle RPC missing")
    end)

    ctx:case("ordinary items from a held bundle go into the player's inventory", function()
        local player = make_player()
        local bundle = wrap("bundle", { "meat", "twigs", "cutgrass" })
        player.components.inventory:GiveItem(bundle)
        bundle.components.unwrappable:Unwrap(player)
        local inv = player.components.inventory
        assert(count_in(inv, "meat") == 1, "meat is not in the inventory")
        assert(count_in(inv, "twigs") == 1, "twigs are not in the inventory")
        assert(count_in(inv, "cutgrass") == 1, "grass is not in the inventory")
        assert(count_in(inv, "waxpaper") == 1, "the wax paper is not returned to the inventory")
        assert(not bundle:IsValid(), "the bundle was not consumed")
        cleanup()
    end)

    ctx:case("a live butterfly from a held bundle goes into the player's inventory", function()
        local player = make_player()
        local bundle = wrap("bundle", { "butterfly", "twigs" })
        player.components.inventory:GiveItem(bundle)
        local before = #nearby("butterfly", 0, 0, 12)
        bundle.components.unwrappable:Unwrap(player)
        assert(count_in(player.components.inventory, "butterfly") == 1, "the butterfly is not in the inventory")
        assert(#nearby("butterfly", 0, 0, 12) == before, "a butterfly was left in the world")
        cleanup()
    end)

    ctx:case("moongleam from a held bundle goes into the player's inventory", function()
        local player = make_player()
        local bundle = wrap("bundle", { "moonstorm_spark", "twigs" })
        player.components.inventory:GiveItem(bundle)
        bundle.components.unwrappable:Unwrap(player)
        assert(count_in(player.components.inventory, "moonstorm_spark") == 1, "the moongleam is not in the inventory")
        cleanup()
    end)

    ctx:case("a bundle opened inside a chest fills the chest", function()
        local player = make_player()
        local chest = spawn("treasurechest", 2, 0)
        local bundle = wrap("bundle", { "rocks", "flint" })
        chest.components.container:GiveItem(bundle)
        bundle.components.unwrappable:Unwrap(player)
        assert(count_in(chest.components.container, "rocks") == 1, "rocks did not stay in the chest")
        assert(count_in(chest.components.container, "flint") == 1, "flint did not stay in the chest")
        assert(count_in(player.components.inventory, "rocks") == 0, "rocks were moved to the player")
        cleanup()
    end)

    ctx:case("a bundle opened on the ground drops its items and announces the unwrap", function()
        local player = make_player()
        local bundle = wrap("bundle", { "log", "goldnugget" })
        bundle.Transform:SetPosition(ORIGIN.x + 8, 0, ORIGIN.z + 8)
        local heard = nil
        bundle:ListenForEvent("unwrapped", function(inst, data)
            heard = data
        end)
        local logs, nuggets = nearby("log", 8, 8, 4), nearby("goldnugget", 8, 8, 4)
        local known = {}
        for _, ent in ipairs(logs) do known[ent] = true end
        for _, ent in ipairs(nuggets) do known[ent] = true end
        bundle.components.unwrappable:Unwrap(player)
        local new_logs, new_nuggets = nearby("log", 8, 8, 4), nearby("goldnugget", 8, 8, 4)
        for _, list in ipairs({ new_logs, new_nuggets, nearby("waxpaper", 8, 8, 4) }) do
            for _, ent in ipairs(list) do
                if not known[ent] then
                    ent:Remove()
                end
            end
        end
        assert(#new_logs == #logs + 1, "the log was not dropped at the bundle")
        assert(#new_nuggets == #nuggets + 1, "the nugget was not dropped at the bundle")
        assert(heard ~= nil and heard.doer == player, "the ground unwrap was not announced")
        cleanup()
    end)

    ctx:case("a surprise gift opened from the inventory releases its creature", function()
        local player = make_player()
        player.Transform:SetPosition(ORIGIN.x - 6, 0, ORIGIN.z - 6)
        local gift = spawn("gift", -6, -6)
        local before = #nearby("hound", -6, -6, 12)
        local items = {
            SpawnPrefab("giftsurprise"):SetCreatureSurprise("hound"),
            SpawnPrefab("giftsurprise"),
            SpawnPrefab("giftsurprise"),
            SpawnPrefab("giftsurprise"),
        }
        gift.components.unwrappable:WrapItems(items)
        for _, item in ipairs(items) do
            item:Remove()
        end
        player.components.inventory:GiveItem(gift)
        gift.components.unwrappable:Unwrap(player)
        local hounds = nearby("hound", -6, -6, 12)
        local leftover = count_in(player.components.inventory, "giftsurprise")
        for _, hound in ipairs(hounds) do
            hound:Remove()
        end
        for _, ent in ipairs(nearby("giftsurprise", -6, -6, 12)) do
            ent:Remove()
        end
        cleanup()
        assert(leftover == 0, "the surprise ended up in the inventory")
        assert(#hounds == before + 1, "expected one new hound from the surprise gift, found " .. (#hounds - before))
    end)

    ctx:case("opening a held bundle announces the unwrap with the opener", function()
        local player = make_player()
        local bundle = wrap("bundle", { "meat" })
        local heard = nil
        bundle:ListenForEvent("unwrapped", function(inst, data)
            heard = data
        end)
        player.components.inventory:GiveItem(bundle)
        bundle.components.unwrappable:Unwrap(player)
        cleanup()
        assert(heard ~= nil, "the bundle did not announce the unwrap")
        assert(heard.doer == player, "the announcement does not name the opener")
    end)

    ctx:case("every item of a held bundle is told it was unwrapped, by whom and from what", function()
        local player = make_player()
        local bundle = wrap("bundle", { "meat", "twigs" })
        local heard = {}
        local listener = function(inst, data)
            heard[#heard + 1] = { prefab = inst.prefab, bundle = data and data.bundle, doer = data and data.doer }
        end
        local original = SpawnPrefab
        SpawnPrefab = function(...)
            local inst = original(...)
            if inst ~= nil then
                inst:ListenForEvent("unwrappeditem", listener)
            end
            return inst
        end
        player.components.inventory:GiveItem(bundle)
        local ok, err = pcall(bundle.components.unwrappable.Unwrap, bundle.components.unwrappable, player)
        SpawnPrefab = original
        cleanup()
        assert(ok, err)
        assert(#heard == 2, "expected two unwrapped-item notices, got " .. #heard)
        for _, notice in ipairs(heard) do
            assert(notice.bundle == bundle, "a notice does not name the bundle")
            assert(notice.doer == player, "a notice does not name the opener")
        end
    end)

    ctx:case("the preview of a bundle wrapped from items lists every item", function()
        local player = make_player()
        local bundle = wrap("bundle", { "meat", "twigs", "flint" })
        local entries = request_preview(modname, player, bundle)
        cleanup()
        assert(preview_prefabs(entries) == "meat,twigs,flint", "preview lists " .. preview_prefabs(entries))
    end)

    ctx:case("the preview of a bundle the game wraps from prefab names lists every item", function()
        local player = make_player()
        local bundle = spawn("bundle")
        bundle.components.unwrappable:WrapItems({ "meat", "rocks", "log" })
        local entries = request_preview(modname, player, bundle)
        cleanup()
        assert(preview_prefabs(entries) == "meat,rocks,log", "preview lists " .. preview_prefabs(entries))
        for index = 1, 3 do
            assert(type(entries[index].image) == "string", "preview entry " .. index .. " has no image")
        end
    end)

    ctx:case("a saved bundle with a blank preview shows its items after loading", function()
        local player = make_player()
        local records = { SpawnPrefab("meat"), SpawnPrefab("cutstone") }
        local items = {}
        for index, item in ipairs(records) do
            items[index] = item:GetSaveRecord()
            item:Remove()
        end
        items.showbundle_itemdata = { {}, {} }
        local bundle = spawn("bundle")
        bundle:SetPersistData({ unwrappable = { items = items } })
        local entries = request_preview(modname, player, bundle)
        cleanup()
        assert(preview_prefabs(entries) == "meat,cutstone", "preview lists " .. preview_prefabs(entries))
    end)

    ctx:case("the preview shows Rot on the spoiled background it has in the inventory", function()
        local player = make_player()
        local bundle = wrap("bundle", { "spoiled_food", "twigs" })
        local entries = request_preview(modname, player, bundle)
        cleanup()
        assert(preview_prefabs(entries) == "spoiled_food,twigs", "preview lists " .. preview_prefabs(entries))
        assert(entries[1].show_spoiled == true, "the Rot entry does not ask for the spoiled background")
    end)

    ctx:case("the preview keeps fresh food's spoilage and leaves other items on a plain slot", function()
        local player = make_player()
        local bundle = wrap("bundle", { "berries", "twigs" })
        local entries = request_preview(modname, player, bundle)
        cleanup()
        assert(preview_prefabs(entries) == "berries,twigs", "preview lists " .. preview_prefabs(entries))
        assert(entries[1].spoil == true and type(entries[1].perish) == "number", "the berries entry lost its spoilage")
        assert(not entries[2].show_spoiled and not entries[2].spoil, "the twigs entry asks for a spoiled background")
    end)
end
