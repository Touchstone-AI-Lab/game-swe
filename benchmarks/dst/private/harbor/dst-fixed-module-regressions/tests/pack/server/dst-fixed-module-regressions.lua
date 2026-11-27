-- Hidden dedicated-server suite: DST Fixed, six optional modules.
-- The server runs with Nameable Backtrek Watch, Combinable Equipment, Enhanced
-- Sand Stone, Block Pooping With a Bung, Glommer Statue Repairing and Gather
-- Moon Dial's Glass enabled.
-- A server-spawned Wilson stands in for the player.

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

local function in_world(prefab, dx, dz, radius)
    local found = {}
    for _, ent in ipairs(TheSim:FindEntities(ORIGIN.x + dx, 0, ORIGIN.z + dz, radius, nil, { "INLIMBO" })) do
        if ent.prefab == prefab and ent:IsValid() then
            found[#found + 1] = ent
        end
    end
    return found
end

-- Items dropped or flung onto an ocean tile sink, so every check that looks for
-- dropped items runs where all ground within `radius` is land. The preferred
-- offset is kept when it qualifies; otherwise the nearest qualifying offset on
-- rings around the spawn portal is used. The result depends only on the world.
local function land_offset(dx, dz, radius)
    local map = TheWorld.Map
    local function all_land(ox, oz)
        for x = -radius, radius, 2 do
            for z = -radius, radius, 2 do
                if x * x + z * z <= radius * radius
                    and not map:IsAboveGroundAtPoint(ORIGIN.x + ox + x, 0, ORIGIN.z + oz + z) then
                    return false
                end
            end
        end
        return true
    end
    if all_land(dx, dz) then
        return dx, dz
    end
    for ring = 4, 80, 4 do
        for step = -ring, ring, 4 do
            for _, candidate in ipairs({ { step, -ring }, { step, ring }, { -ring, step }, { ring, step } }) do
                if all_land(candidate[1], candidate[2]) then
                    return candidate[1], candidate[2]
                end
            end
        end
    end
    error("no land area of radius " .. radius .. " near the spawn portal")
end

local function stack_total(entities)
    local total = 0
    for _, ent in ipairs(entities) do
        total = total + (ent.components.stackable ~= nil and ent.components.stackable:StackSize() or 1)
    end
    return total
end

local function remove_all(entities)
    for _, ent in ipairs(entities) do
        if ent:IsValid() then
            ent:Remove()
        end
    end
end

local function count_loot(loot, prefab)
    local total = 0
    for _, name in ipairs(loot) do
        if name == prefab then
            total = total + 1
        end
    end
    return total
end

local function give_bung(creature, player)
    local bung = SpawnPrefab("trinket_8")
    player.components.inventory:GiveItem(bung)
    local accepted = creature.components.trader:AcceptGift(player, bung)
    if bung:IsValid() then
        bung:Remove()
    end
    return accepted
end

local function refuses_bung(creature, player)
    local bung = SpawnPrefab("trinket_8")
    local wants = creature.components.trader:WantsToAccept(bung, player)
    bung:Remove()
    return not wants
end

-- Names a watch the way a player does: the feather pencil starts the rename and
-- the player's client then submits the text.
local function rename(player, watch, text)
    local pencil = SpawnPrefab("featherpencil")
    player.components.inventory:GiveItem(pencil)
    assert(ACTIONS.RENAME_WATCH ~= nil, "watches cannot be renamed")
    local started = BufferedAction(player, watch, ACTIONS.RENAME_WATCH, pencil):Do()
    assert(started, "the rename did not start")
    assert(watch.components.writeable ~= nil, "the watch cannot be written on")
    watch.components.writeable:Write(player, text)
end

return function(ctx)
    ctx:case("sentinel: DST Fixed is loaded with the operator's modules", function()
        local watch = SpawnPrefab("pocketwatch_portal")
        local hat = SpawnPrefab("antlionhat")
        local ok = hat.components.sewingnew ~= nil and PrefabExists("townportal_invisible")
        watch:Remove()
        hat:Remove()
        assert(ok, "Combinable Equipment or Enhanced Sand Stone is not active")
    end)

    -- Nameable Backtrek Watch -------------------------------------------------
    ctx:case("a Backtrek Watch can be given a name that shows in its display name", function()
        local player = make_player()
        local watch = spawn("pocketwatch_recall", 1, 0)
        rename(player, watch, "Home Base")
        local shown = watch:GetDisplayName()
        cleanup()
        assert(string.find(shown, "Home Base", 1, true) ~= nil, "display name is " .. tostring(shown))
    end)

    ctx:case("a named Rift Watch keeps its name across a save and reload", function()
        local player = make_player()
        local watch = spawn("pocketwatch_portal", 1, 0)
        rename(player, watch, "Oasis")
        local record = watch:GetPersistData()
        local reloaded = spawn("pocketwatch_portal", 2, 0)
        reloaded:SetPersistData(record)
        local shown = reloaded:GetDisplayName()
        cleanup()
        assert(string.find(shown, "Oasis", 1, true) ~= nil, "reloaded display name is " .. tostring(shown))
    end)

    ctx:case("naming a watch uses up one Feather Pencil of a stack", function()
        local player = make_player()
        local watch = spawn("pocketwatch_recall", 1, 0)
        local pencils = SpawnPrefab("featherpencil")
        pencils.components.stackable:SetStackSize(5)
        player.components.inventory:GiveItem(pencils)
        assert(ACTIONS.RENAME_WATCH ~= nil, "watches cannot be renamed")
        local started = BufferedAction(player, watch, ACTIONS.RENAME_WATCH, pencils):Do()
        local _, left = player.components.inventory:Has("featherpencil", 1)
        cleanup()
        assert(started, "the rename did not start")
        assert(left == 4, "the player has " .. tostring(left) .. " of 5 Feather Pencils after starting one rename")
    end)

    -- Combinable Equipment ----------------------------------------------------
    ctx:case("combining two spears adds up their durability", function()
        local player = make_player()
        local target = spawn("spear", 1, 0)
        local source = spawn("spear", 1, 1)
        target.components.finiteuses:SetUses(40)
        source.components.finiteuses:SetUses(30)
        player.components.inventory:GiveItem(target)
        player.components.inventory:GiveItem(source)
        local ok = BufferedAction(player, target, ACTIONS.SEWINGNEW, source):Do()
        local uses = target.components.finiteuses:GetUses()
        local consumed = not source:IsValid()
        cleanup()
        assert(ok, "the combine action failed")
        assert(consumed, "the spear used as material was not consumed")
        assert(uses == 70, "combined uses are " .. tostring(uses))
    end)

    ctx:case("combining never raises durability above full", function()
        local player = make_player()
        local target = spawn("spear", 1, 0)
        local source = spawn("spear", 1, 1)
        local max = target.components.finiteuses.total
        target.components.finiteuses:SetUses(max - 5)
        source.components.finiteuses:SetUses(max - 5)
        player.components.inventory:GiveItem(target)
        player.components.inventory:GiveItem(source)
        BufferedAction(player, target, ACTIONS.SEWINGNEW, source):Do()
        local percent = target.components.finiteuses:GetPercent()
        cleanup()
        assert(percent == 1, "durability is " .. tostring(percent))
    end)

    ctx:case("combining Turf-Raiser Helms keeps the turf loaded in the consumed helm", function()
        local hx, hz = land_offset(10, 10, 6)
        local player = make_player(hx, hz)
        local target = spawn("antlionhat", hx, hz)
        local source = spawn("antlionhat", hx, hz)
        target.components.finiteuses:SetPercent(0.5)
        source.components.finiteuses:SetPercent(0.25)
        local turf = SpawnPrefab("turf_grass")
        turf.components.stackable:SetStackSize(7)
        assert(source.components.container:GiveItem(turf), "the helm refused the turf")
        player.components.inventory:GiveItem(target)
        player.components.inventory:GiveItem(source)
        local before_world = stack_total(in_world("turf_grass", hx, hz, 6))
        BufferedAction(player, target, ACTIONS.SEWINGNEW, source):Do()
        local dropped = in_world("turf_grass", hx, hz, 6)
        local total = stack_total(dropped) - before_world
        remove_all(dropped)
        cleanup()
        assert(total == 7, "turf left after combining: " .. tostring(total))
    end)

    -- Enhanced Sand Stone -----------------------------------------------------
    -- Uses a Desert Stone from the inventory and returns the temporary portal it opens.
    local function use_desert_stone(player)
        local stone = SpawnPrefab("townportaltalisman")
        player.components.inventory:GiveItem(stone)
        assert(ACTIONS.ENHANCEDSANDSTONE ~= nil, "Desert Stones cannot be used from the inventory")
        assert(BufferedAction(player, nil, ACTIONS.ENHANCEDSANDSTONE, stone):Do(), "the Desert Stone did nothing")
        local x, y, z = player.Transform:GetWorldPosition()
        for _, ent in ipairs(TheSim:FindEntities(x, y, z, 3, { "townportal" })) do
            if ent ~= player and ent.components.channelable ~= nil and ent.components.channelable:IsChanneling() then
                spawned[#spawned + 1] = ent
                return ent
            end
        end
        error("no channeling temporary Lazy Deserter was opened")
    end

    ctx:case("using a Desert Stone opens a temporary Lazy Deserter that other portals lead to", function()
        local player = make_player(-12, 0)
        local desert = spawn("townportal", -20, 0)
        local temporary = use_desert_stone(player)
        local target = desert.components.teleporter.targetTeleporter
        pcall(temporary.components.channelable.StopChanneling, temporary.components.channelable, true)
        cleanup()
        assert(target == temporary, "the other Lazy Deserter does not lead to the temporary one")
    end)

    ctx:case("the temporary Lazy Deserter stops channeling cleanly and unlinks other portals", function()
        local player = make_player(-12, 0)
        local desert = spawn("townportal", -20, 0)
        local temporary = use_desert_stone(player)
        local ok, err = pcall(temporary.components.channelable.StopChanneling, temporary.components.channelable, true)
        local still_linked = desert.components.teleporter:IsActive()
        cleanup()
        assert(ok, "stopping the channel raised: " .. tostring(err))
        assert(not still_linked, "the other Lazy Deserter still leads to the stopped portal")
    end)

    -- Block Pooping With a Bung ------------------------------------------------
    ctx:case("a beefalo takes one bung and refuses a second", function()
        local player = make_player(15, -10)
        local beefalo = spawn("beefalo", 15, -12)
        assert(not refuses_bung(beefalo, player), "an unblocked beefalo refuses a bung")
        assert(give_bung(beefalo, player), "the beefalo did not take the bung")
        assert(refuses_bung(beefalo, player), "a blocked beefalo accepts another bung")
        cleanup()
    end)

    ctx:case("a blocked beefalo stays blocked after a save and reload", function()
        local player = make_player(15, -10)
        local beefalo = spawn("beefalo", 15, -12)
        give_bung(beefalo, player)
        local record = beefalo:GetPersistData()
        local reloaded = spawn("beefalo", 18, -12)
        reloaded:SetPersistData(record)
        local blocked = refuses_bung(reloaded, player)
        cleanup()
        assert(blocked, "the reloaded beefalo is no longer blocked")
    end)

    ctx:case("a blocked koalefant drops its bung when it dies", function()
        local player = make_player(-15, 12)
        local koalefant = spawn("koalefant_summer", -15, 15)
        give_bung(koalefant, player)
        local loot = koalefant.components.lootdropper:GenerateLoot()
        cleanup()
        assert(count_loot(loot, "trinket_8") == 1, "a blocked koalefant drops " .. count_loot(loot, "trinket_8") .. " bungs")
    end)

    ctx:case("blocking one koalefant does not give other koalefants a bung", function()
        local player = make_player(-15, 12)
        local blocked = spawn("koalefant_summer", -15, 15)
        local other = spawn("koalefant_summer", -18, 15)
        give_bung(blocked, player)
        blocked.components.lootdropper:GenerateLoot()
        local loot = other.components.lootdropper:GenerateLoot()
        cleanup()
        assert(count_loot(loot, "trinket_8") == 0, "an unblocked koalefant drops " .. count_loot(loot, "trinket_8") .. " bungs")
    end)

    -- Glommer Statue Repairing -------------------------------------------------
    -- The statues are checked a moment after they are spawned, as a player meets
    -- them in a running world, and are kept out of the shared clean-up until then.
    local statues = {}
    local function place_statue(dx, dz)
        local statue = SpawnPrefab("statueglommer")
        statue.Transform:SetPosition(ORIGIN.x + dx, 0, ORIGIN.z + dz)
        statues[#statues + 1] = statue
        return statue
    end

    -- Repairs with Marble through the game's repair action; returns how many
    -- repairs went through.
    local function repair(player, statue, times)
        local marble = SpawnPrefab("marble")
        marble.components.stackable:SetStackSize(times)
        player.components.inventory:GiveItem(marble)
        local done = 0
        for _ = 1, times do
            local item = player.components.inventory:FindItem(function(ent)
                return ent.prefab == "marble"
            end)
            if item == nil or not BufferedAction(player, statue, ACTIONS.REPAIR, item):Do() then
                break
            end
            done = done + 1
        end
        return done
    end

    local fresh_statue, old_statue
    ctx:case("setup: a fresh Glommer statue and one loaded from a base-game save stand in the world", function()
        local sx, sz = land_offset(-30, 25, 6)
        fresh_statue = place_statue(sx, sz)
        old_statue = place_statue(sx - 4, sz)
        -- What the base game saves for a statue that was mined down to 2, before
        -- this module ever ran on the world.
        old_statue:SetPersistData({ workable = { maxwork = -1, workleft = 2 } })
        assert(fresh_statue.components.repairable ~= nil, "Glommer Statue Repairing is not active")
    end)

    ctx:after(1, function()
        ctx:case("a partly mined Glommer statue is repaired with Marble up to full and no further", function()
            local player = make_player(-30, 30)
            local workable = fresh_statue.components.workable
            workable:WorkedBy(player, 3)
            local mined_to = workable.workleft
            local repairs = repair(player, fresh_statue, 3)
            local workleft = workable.workleft
            cleanup()
            assert(mined_to == TUNING.ROCKS_MINE - 3, "mining left " .. tostring(mined_to) .. " work")
            assert(repairs == 2, tostring(repairs) .. " of 3 Marble went into the statue")
            assert(workleft == TUNING.ROCKS_MINE, "the repaired statue has " .. tostring(workleft) .. " work left")
        end)

        ctx:case("a Glommer statue saved before the option was switched on can be repaired with Marble", function()
            local player = make_player(-30, 30)
            local repairs = repair(player, old_statue, 1)
            local workleft = old_statue.components.workable.workleft
            cleanup()
            for _, statue in ipairs(statues) do
                statue:Remove()
            end
            assert(repairs == 1, "the statue refused the Marble")
            assert(workleft == 4, "the repaired statue has " .. tostring(workleft) .. " work left")
        end)
    end)

    -- Gather Moon Dial's Glass -----------------------------------------------
    -- A moon storm glasses the dials; when it ends while nobody is near them,
    -- the glass is produced at once.
    local function moon_storm(active)
        TheWorld:PushEvent("ms_stormchanged", { stormtype = STORM_TYPES.MOONSTORM, setting = active })
    end

    ctx:case("without a celestial portal a dial drops its glass beside itself", function()
        local dx, dz = land_offset(30, -30, 6)
        spawn("moondial", dx, dz)
        local before = stack_total(in_world("moonglass", dx, dz, 6))
        moon_storm(true)
        moon_storm(false)
        local shards = in_world("moonglass", dx, dz, 6)
        local total = stack_total(shards) - before
        remove_all(shards)
        cleanup()
        assert(total == 1, "the dial dropped " .. total .. " moon glass")
    end)

    -- The celestial portal flings the glass around itself, so it stands on land;
    -- the dials stand 20 units to its west.
    local px, pz = 25, 25
    ctx:case("setup: two moon dials are glassed and the storm ends next to a celestial portal", function()
        px, pz = land_offset(25, 25, 10)
        local celestial = spawn("multiplayer_portal_moonrock", px, pz)
        spawn("moondial", px - 20, pz)
        spawn("moondial", px - 20, pz + 5)
        moon_storm(true)
        moon_storm(false)
        assert(celestial:IsValid())
    end)

    ctx:after(2, function()
        ctx:case("the celestial portal receives exactly one moon glass per dial", function()
            local shards = in_world("moonglass", px, pz, 10)
            local at_dials = in_world("moonglass", px - 20, pz + 2, 3)
            local total = stack_total(shards)
            remove_all(shards)
            remove_all(at_dials)
            cleanup()
            assert(#at_dials == 0, "glass was dropped at the dials instead of the portal")
            assert(total == 2, "the portal received " .. total .. " moon glass for two dials")
        end)
    end)
end
