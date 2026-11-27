-- Hidden dedicated-server suite: DsMMO.
-- The mod runs with its default settings. A server-spawned Wilson stands in for
-- the player. Skill rolls are made to succeed by answering the mod's
-- math.random() calls with 0 for the duration of one action, and the player's
-- DsMMO levels are raised through the component's own set_level, which is what
-- the mod's dsmmo_set admin command calls.

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

local function make_player(dx, dz, levels)
    local player = spawn("wilson", dx, dz)
    player.components.health:SetInvincible(true)
    assert(player.components.DsMMO ~= nil, "the player has no DsMMO component")
    for action, level in pairs(levels or {}) do
        assert(player.components.DsMMO:set_level(action, level, true), "unknown DsMMO action " .. action)
    end
    return player
end

-- Runs `fn` while every skill roll succeeds.
local function lucky(fn)
    local random = math.random
    math.random = function(low, high)
        if low ~= nil then
            return low
        end
        return 0
    end
    local ok, err = pcall(fn)
    math.random = random
    return ok, err
end

local function performed(player, action, target, invobject)
    return lucky(function()
        player:PushEvent("performaction", { action = BufferedAction(player, target, action, invobject) })
    end)
end

local function attacked(player, data)
    return lucky(function()
        player:PushEvent("attacked", data)
    end)
end

local function new_near(prefab, dx, dz, radius, known)
    local found = {}
    for _, ent in ipairs(TheSim:FindEntities(ORIGIN.x + dx, 0, ORIGIN.z + dz, radius, nil, { "INLIMBO" })) do
        if ent.prefab == prefab and ent:IsValid() and not known[ent] then
            found[#found + 1] = ent
        end
    end
    return found
end

local function snapshot(prefab, dx, dz, radius)
    local known = {}
    for _, ent in ipairs(new_near(prefab, dx, dz, radius, {})) do
        known[ent] = true
    end
    return known
end

-- The experience the player's save record carries for one DsMMO action.
local function saved_exp(player, action)
    local record = player:GetPersistData()
    local data = record ~= nil and record.DsMMO or nil
    assert(data ~= nil and data.dsmmo_exp ~= nil, "the player's save record has no DsMMO experience")
    return data.dsmmo_exp[action]
end

local function remove_all(entities)
    for _, ent in ipairs(entities) do
        if ent:IsValid() then
            ent:Remove()
        end
    end
end

return function(ctx)
    ctx:case("sentinel: DsMMO gives a spawned player its skill component", function()
        local player = make_player()
        local ok = type(saved_exp(player, "CHOP")) == "number"
        cleanup()
        assert(ok, "the player's DsMMO experience is not saved")
    end)

    ctx:case("an attack on the player earns attack experience", function()
        local player = make_player()
        local spider = spawn("spider", 3, 0)
        local before = saved_exp(player, "ATTACK")
        local ok, err = attacked(player, { attacker = spider, damage = 10 })
        local after = saved_exp(player, "ATTACK")
        cleanup()
        assert(ok, "the attack raised: " .. tostring(err))
        assert(after == before + 1, "attack experience went from " .. before .. " to " .. after)
    end)

    ctx:case("Beetaliation sends a bee after a creature that attacks the player", function()
        local player = make_player(0, 0, { ATTACK = 10 })
        local spider = spawn("spider", 3, 0)
        local known = snapshot("bee", 0, 0, 6)
        local ok, err = attacked(player, { attacker = spider, damage = 10 })
        local bees = new_near("bee", 0, 0, 6, known)
        local target = bees[1] and bees[1].components.combat.target
        remove_all(bees)
        cleanup()
        assert(ok, "the attack raised: " .. tostring(err))
        assert(#bees == 1, "expected one retaliating bee, found " .. #bees)
        assert(target == spider, "the bee does not go after the attacker")
    end)

    ctx:case("damage without an attacker, like the darkness, is handled", function()
        local player = make_player(-8, 0, { ATTACK = 10 })
        local known = snapshot("bee", -8, 0, 6)
        local ok, err = attacked(player, { damage = 10 })
        local bees = new_near("bee", -8, 0, 6, known)
        remove_all(bees)
        cleanup()
        assert(ok, "being hurt without an attacker raised: " .. tostring(err))
        assert(#bees == 0, "a bee was spawned for damage without an attacker")
    end)

    ctx:case("a player who hurts themselves is not chased by their own bee", function()
        local player = make_player(8, 0, { ATTACK = 10 })
        local known = snapshot("bee", 8, 0, 6)
        local ok, err = attacked(player, { attacker = player, damage = 10 })
        local bees = new_near("bee", 8, 0, 6, known)
        remove_all(bees)
        cleanup()
        assert(ok, "self-inflicted damage raised: " .. tostring(err))
        assert(#bees == 0, "a bee was spawned against the player themselves")
    end)

    ctx:case("Explosive touch hits a creature that can fight", function()
        local player = make_player(0, 8, { ATTACK = 10 })
        local spider = spawn("spider", 2, 8)
        local before = spider.components.health.currenthealth
        local ok, err = performed(player, ACTIONS.ATTACK, spider)
        local after = spider.components.health.currenthealth
        cleanup()
        assert(ok, "the attack raised: " .. tostring(err))
        assert(after < before, "the explosive touch did no damage")
    end)

    ctx:case("Explosive touch on something that cannot fight back is handled", function()
        local player = make_player(0, -8, { ATTACK = 10 })
        local rock = spawn("rocks", 2, -8)
        local ok, err = performed(player, ACTIONS.ATTACK, rock)
        cleanup()
        assert(ok, "attacking an object without combat raised: " .. tostring(err))
    end)

    ctx:case("Ghosty fireflies turn a haunted evil flower into fireflies", function()
        local player = make_player(12, 12, { PICK = 10 })
        local flower = spawn("flower_evil", 14, 12)
        local known = snapshot("fireflies", 14, 12, 4)
        local ok, err = performed(player, ACTIONS.HAUNT, flower)
        local fireflies = new_near("fireflies", 14, 12, 4, known)
        local removed = not flower:IsValid()
        remove_all(fireflies)
        cleanup()
        assert(ok, "haunting raised: " .. tostring(err))
        assert(removed, "the evil flower is still there")
        assert(#fireflies == 1, "expected one firefly swarm, found " .. #fireflies)
    end)

    ctx:case("a haunt that has no target is handled", function()
        local player = make_player(-12, 12, { PICK = 10 })
        local ok, err = performed(player, ACTIONS.HAUNT, nil)
        cleanup()
        assert(ok, "a haunt without a target raised: " .. tostring(err))
    end)

    ctx:case("digging earns dig experience", function()
        local player = make_player(-12, -12)
        local grass = spawn("grass", -10, -12)
        local shovel = SpawnPrefab("shovel")
        player.components.inventory:GiveItem(shovel)
        local before = saved_exp(player, "DIG")
        local ok, err = performed(player, ACTIONS.DIG, grass, shovel)
        local after = saved_exp(player, "DIG")
        cleanup()
        assert(ok, "digging raised: " .. tostring(err))
        assert(after == before + 1, "dig experience went from " .. before .. " to " .. after)
    end)

    ctx:case("digging without a tool, as a werebeaver does, is handled", function()
        local player = make_player(12, -12, { DIG = 10 })
        local grass = spawn("grass", 14, -12)
        local ok, err = performed(player, ACTIONS.DIG, grass, nil)
        cleanup()
        assert(ok, "digging without a tool raised: " .. tostring(err))
    end)

    ctx:case("a save made under the current Exp-gain setting loads as it was saved", function()
        local player = make_player(16, -16, { DIG = 6, CHOP = 3 })
        local record = player:GetPersistData()
        local loaded = make_player(18, -16)
        local ok, err = pcall(function()
            loaded:SetPersistData(deepcopy(record))
        end)
        local after = loaded:GetPersistData().DsMMO
        cleanup()
        assert(ok, "loading the save raised: " .. tostring(err))
        for _, action in ipairs({ "DIG", "CHOP" }) do
            assert(after.dsmmo_exp[action] == record.DsMMO.dsmmo_exp[action], action .. " experience changed on load")
            assert(after.dsmmo_level[action] == record.DsMMO.dsmmo_level[action], action .. " level changed on load")
        end
    end)

    ctx:case("a save made under another Exp-gain setting gets its levels recalculated", function()
        local player = make_player(20, -16, { DIG = 6 })
        local record = player:GetPersistData()
        local current = record.DsMMO
        -- The same experience, saved while the server ran another Exp-gain setting, which
        -- had given it a different level.
        local stale = deepcopy(record)
        stale.DsMMO.dsmmo_level_up_rate = (current.dsmmo_level_up_rate or 1.5) + 1
        stale.DsMMO.dsmmo_level.DIG = 1
        stale.DsMMO.dsmmo_max_exp.DIG = current.dsmmo_exp.DIG + 1
        local loaded = make_player(22, -16)
        local ok, err = pcall(function()
            loaded:SetPersistData(stale)
        end)
        local after = loaded:GetPersistData().DsMMO
        cleanup()
        assert(ok, "loading the save raised: " .. tostring(err))
        assert(after.dsmmo_exp.DIG == current.dsmmo_exp.DIG, "DIG experience changed on load")
        assert(
            after.dsmmo_level.DIG == current.dsmmo_level.DIG,
            "the loaded DIG level is " .. tostring(after.dsmmo_level.DIG) .. ", but that experience is level "
                .. tostring(current.dsmmo_level.DIG) .. " under the current setting"
        )
        assert(after.dsmmo_max_exp.DIG == current.dsmmo_max_exp.DIG, "the experience needed for the next DIG level was not recalculated")
    end)

    ctx:case("an incomplete #dsmmo eat command is handled", function()
        local player = make_player(-16, 16, { EAT = 5, DIG = 10 })
        local known = snapshot("minisign", -16, 16, 6)
        local ok, err = pcall(function()
            player.components.DsMMO:run_command("#dsmmo", "eat")
        end)
        local ok_one, err_one = pcall(function()
            player.components.DsMMO:run_command("#dsmmo", "eat", "dig")
        end)
        remove_all(new_near("minisign", -16, 16, 6, known))
        cleanup()
        assert(ok, "#dsmmo eat without arguments raised: " .. tostring(err))
        assert(ok_one, "#dsmmo eat without a stat raised: " .. tostring(err_one))
    end)

    ctx:case("the full #dsmmo eat command still exchanges experience for sanity", function()
        local player = make_player(-20, 16, { EAT = 5, DIG = 10 })
        player.components.sanity:SetPercent(0.5)
        local before = saved_exp(player, "DIG")
        local ok, err = pcall(function()
            player.components.DsMMO:run_command("#dsmmo", "eat", "dig", "sanity")
        end)
        local percent = player.components.sanity:GetPercent()
        local after = saved_exp(player, "DIG")
        cleanup()
        assert(ok, "#dsmmo eat dig sanity raised: " .. tostring(err))
        assert(percent == 1, "sanity is at " .. percent .. " after the command")
        assert(after < before, "DIG experience went from " .. before .. " to " .. after)
    end)
end
