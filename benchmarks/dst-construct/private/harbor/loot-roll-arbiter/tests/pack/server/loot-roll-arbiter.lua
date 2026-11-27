local ITEM = "goldnugget"

local function make_player(userid)
    local player = CreateEntity()
    player.entity:AddTransform()
    player:AddComponent("inventory")
    player.userid = userid
    return player
end

local function held(player)
    local inventory = player.components.inventory
    if inventory == nil then
        return 0
    end
    local _, count = inventory:Has(ITEM, 1)
    return count or 0
end

-- Total stack size of every live ITEM entity, wherever it is.
local function world_total()
    local total = 0
    for _, entity in pairs(Ents) do
        if entity.prefab == ITEM and entity:IsValid() then
            local stackable = entity.components.stackable
            total = total + (stackable ~= nil and stackable:StackSize() or 1)
        end
    end
    return total
end

-- Unfinished DoTaskInTime/DoPeriodicTask tasks the engine tracks for an entity.
local function pending_tasks(entity)
    local count = 0
    for _ in pairs(entity.pendingtasks or {}) do
        count = count + 1
    end
    return count
end

local function world_tasks()
    return pending_tasks(TheWorld)
end

-- Callbacks registered on the entity itself for one event.
local function listener_count(entity, event)
    local count = 0
    local listeners = entity.event_listeners ~= nil and entity.event_listeners[event] or nil
    for _, callbacks in pairs(listeners or {}) do
        for _ in pairs(callbacks) do
            count = count + 1
        end
    end
    return count
end

-- A private host entity carries its own component instance, so lifecycle events can be
-- pushed and the component removed without disturbing the live world.
local function with_host(body)
    local host = CreateEntity()
    host.entity:AddTransform()
    local ok, message = pcall(function()
        host:AddComponent("lootrollarbiter")
        body(host, assert(host.components.lootrollarbiter, "component could not be added to a plain entity"))
    end)
    host:Remove()
    if not ok then
        error(message, 0)
    end
end

local function published()
    local netvar = TheWorld._lootroll_state
    assert(netvar ~= nil and type(netvar.value) == "function", "world is missing the _lootroll_state net_string")
    local value = netvar:value()
    assert(type(value) == "string", "_lootroll_state must hold a string")
    return value
end

local function plain(value, depth)
    depth = depth or 0
    assert(depth < 32, "saved data is too deep or cyclic")
    local kind = type(value)
    if kind == "table" then
        for key, inner in pairs(value) do
            assert(type(key) == "string" or type(key) == "number", "saved keys must be strings or numbers")
            plain(inner, depth + 1)
        end
    else
        assert(kind == "string" or kind == "number" or kind == "boolean", "saved data contains a " .. kind)
    end
end

-- Runs body and removes the entities afterwards even when an assertion fails.
local function with_players(userids, body)
    local players = {}
    for index, userid in ipairs(userids) do
        players[index] = make_player(userid)
    end
    local ok, message = pcall(body, players)
    for _, player in ipairs(players) do
        for index = #AllPlayers, 1, -1 do
            if AllPlayers[index] == player then
                table.remove(AllPlayers, index)
            end
        end
        player:Remove()
    end
    if not ok then
        error(message, 0)
    end
end

local function open_roll(service, players, seed)
    local opened = service:Open(ITEM, players, seed)
    assert(type(opened) == "table" and opened.ok == true, "Open failed: " .. tostring(type(opened) == "table" and opened.code or opened))
    assert(type(opened.roll_id) == "string" and opened.roll_id ~= "", "Open must return a roll_id string")
    return opened.roll_id
end

local function choose(service, player, roll_id, choice, revision)
    local result = service:Choose(player, roll_id, choice, revision)
    assert(type(result) == "table", "Choose must return a table")
    return result
end

return function(ctx)
    ctx:case("loot roll component is attached on the master simulation", function()
        assert(TheWorld ~= nil and TheWorld.ismastersim, "suite requires master simulation")
        local service = TheWorld.components.lootrollarbiter
        assert(service ~= nil, "world is missing lootrollarbiter")
        for _, method in ipairs({ "Open", "Choose", "Resolve", "OnSave", "OnLoad", "OnRemoveFromEntity" }) do
            assert(type(service[method]) == "function", "component must expose " .. method)
        end
        published()
        local rpc = MOD_RPC["rhenium_lootroll"] ~= nil and MOD_RPC["rhenium_lootroll"]["choose"] or nil
        assert(rpc ~= nil and type(MOD_RPC_HANDLERS["rhenium_lootroll"][rpc.id]) == "function", "rhenium_lootroll/choose RPC handler is not registered")
        with_players({ "rh_attach_a" }, function(players)
            local before = world_total()
            local refused = service:Open("log", players, 1)
            assert(type(refused) == "table" and refused.ok == false and refused.code == "item_not_allowed", "items outside the whitelist must be refused")
            refused = service:Open(ITEM, {}, 1)
            assert(type(refused) == "table" and refused.ok == false and refused.code == "invalid_eligible", "an empty player list must be refused")
            assert(world_total() == before, "a refused Open must not create items")
            -- Without a seed the server picks one itself.
            local tasks = world_tasks()
            local unseeded = open_roll(service, players)
            assert(world_tasks() == tasks + 1, "an open roll must keep exactly one deadline task on the world")
            local passed = choose(service, players[1], unseeded, "pass", 1)
            assert(passed.ok == true and passed.complete == true, "a lone pass completes the roll")
            local settled = service:Resolve(unseeded)
            assert(type(settled) == "table" and settled.status == "unclaimed" and settled.winner == nil, "a roll everybody passed is unclaimed")
            assert(world_tasks() == tasks, "the deadline task must be cancelled when the roll settles")
            assert(world_total() == before, "an unclaimed roll must not create items")
        end)
    end)

    ctx:case("predicted winner receives one real item exactly once", function()
        local service = assert(TheWorld.components.lootrollarbiter)
        with_players({ "rh_roll_a", "rh_roll_b", "rh_roll_c" }, function(players)
            local a, b, c = players[1], players[2], players[3]
            -- The predicted winner already owns a nugget, so delivery merges into a stack.
            assert(c.components.inventory:GiveItem(SpawnPrefab(ITEM)), "fixture could not hold a nugget")
            local before, tasks = world_total(), world_tasks()
            local roll_id = open_roll(service, { c, a, b, a }, 0)
            local spare = open_roll(service, { a }, 0)
            assert(spare ~= roll_id, "roll ids must be unique")
            assert(world_tasks() == tasks + 2, "every open roll must keep exactly one deadline task on the world")
            assert(choose(service, a, roll_id, "need", 1).ok == true, "first choice refused")
            assert(choose(service, a, roll_id, "greed", 2).ok == true, "a higher revision must replace the choice")
            local stale = choose(service, a, roll_id, "need", 2)
            assert(stale.ok == false and stale.code == "stale_revision", "a repeated revision must be refused")
            local outsider = make_player("rh_roll_outsider")
            local refused = choose(service, outsider, roll_id, "need", 1)
            outsider:Remove()
            assert(refused.ok == false and refused.code == "not_eligible", "identity must come from player.userid")
            -- The third player chooses through the registered RPC handler, like a real client.
            local handler = MOD_RPC_HANDLERS["rhenium_lootroll"][MOD_RPC["rhenium_lootroll"]["choose"].id]
            handler(c, roll_id, "need", 1)
            local state = published()
            local first, second = roll_id .. "|" .. ITEM .. "|2|3", spare .. "|" .. ITEM .. "|0|1"
            if spare < roll_id then
                first, second = second, first
            end
            assert(string.find(state, first .. ";" .. second, 1, true),
                "net state must list open rolls as roll_id|item|chosen|total joined by ';' in ascending roll id order, got: " .. state)
            assert(not string.find(state, "need", 1, true) and not string.find(state, "greed", 1, true)
                and not string.find(state, "rh_roll_", 1, true), "net state must not reveal choices or player ids")
            assert(choose(service, a, spare, "pass", 1).complete == true, "a lone pass completes the spare roll")
            assert(not string.find(published(), spare .. "|", 1, true), "a settled roll must leave the net state")
            assert(world_tasks() == tasks + 1, "the deadline task must be cancelled when its roll settles")
            local early = service:Resolve(roll_id)
            assert(type(early) == "table" and early.ok == false and early.code == "not_ready", "an incomplete roll cannot be resolved before its deadline")
            assert(world_total() == before and held(c) == 1, "no item may exist before resolution")
            -- The last choice completes the roll and must settle it immediately.
            assert(choose(service, b, roll_id, "need", 1).ok == true, "last choice refused")
            -- need tier {b, c} with seed 0 draws b=72, c=95: c wins although a (greed) is eligible.
            assert(held(c) == 2, "the predicted winner must hold the item in the real inventory")
            assert(held(a) == 0 and held(b) == 0, "only the winner may receive the item")
            assert(world_total() == before + 1, "exactly one item must be created")
            local result = service:Resolve(roll_id)
            assert(type(result) == "table" and result.ok == true and result.status == "delivered" and result.winner == "rh_roll_c"
                and result.tier == "need", "Resolve must report the delivered winner")
            assert(#result.rolls == 2 and result.rolls[1].player_id == "rh_roll_b" and result.rolls[1].roll == 72
                and result.rolls[2].player_id == "rh_roll_c" and result.rolls[2].roll == 95, "draws differ from the published generator")
            local again = service:Resolve(roll_id)
            assert(again.status == "delivered" and again.winner == "rh_roll_c", "a second Resolve must return the same result")
            assert(held(c) == 2 and world_total() == before + 1, "a second Resolve must not duplicate the item")
            assert(world_tasks() == tasks, "no deadline task may survive settlement")
            assert(not string.find(published(), roll_id .. "|", 1, true), "a settled roll must leave the net state")
        end)
    end)

    ctx:case("failed delivery moves the item to the next-best roll", function()
        local service = assert(TheWorld.components.lootrollarbiter)
        with_players({ "rh_fail_a", "rh_fail_b", "rh_fail_c" }, function(players)
            local a, b, c = players[1], players[2], players[3]
            local before = world_total()
            local roll_id = open_roll(service, players, 0)
            assert(choose(service, a, roll_id, "need", 1).ok == true and choose(service, b, roll_id, "need", 1).ok == true)
            -- Seed 0 draws a=72, b=95, c=87. b has no inventory and c cannot hold anything,
            -- so the single item must end up with a and nothing may be left on the ground.
            b:RemoveComponent("inventory")
            c.components.inventory.maxslots = 0
            assert(choose(service, c, roll_id, "need", 1).ok == true)
            local result = service:Resolve(roll_id)
            assert(type(result) == "table" and result.status == "delivered" and result.winner == "rh_fail_a", "third-best player must win after two failures")
            assert(#result.failed == 2 and result.failed[1] == "rh_fail_b" and result.failed[2] == "rh_fail_c", "failed deliveries must be recorded in order")
            assert(held(a) == 1 and held(c) == 0, "the item must be in the final winner's real inventory")
            assert(world_total() == before + 1, "failed attempts must not leave extra items in the world")

            -- Nobody can receive the item: the roll ends unclaimed and no item survives.
            local lonely = open_roll(service, { b }, 5)
            assert(choose(service, b, lonely, "greed", 1).ok == true)
            local unclaimed = service:Resolve(lonely)
            assert(unclaimed.status == "unclaimed" and unclaimed.winner == nil, "no deliverable player means unclaimed")
            assert(world_total() == before + 1, "an unclaimed roll must not leave an item behind")
        end)

        -- A player who leaves stays in the frozen set, but the cached entity is forgotten:
        -- the departed winner cannot be found in AllPlayers, so the runner-up gets the item.
        with_players({ "rh_left_a", "rh_left_b" }, function(players)
            with_host(function(host, private)
                local a, b = players[1], players[2]
                local before = world_total()
                local roll_id = open_roll(private, players, 0)
                host:PushEvent("ms_playerleft", b)
                assert(choose(private, b, roll_id, "need", 1).ok == true, "ms_playerleft must not shrink the frozen eligible set")
                assert(choose(private, a, roll_id, "need", 1).complete == true, "both frozen players have chosen")
                -- Seed 0 draws a=72, b=95: b wins the roll but can no longer be delivered to.
                local result = private:Resolve(roll_id)
                assert(type(result) == "table" and result.status == "delivered" and result.winner == "rh_left_a", "runner-up must receive the departed winner's item")
                assert(#result.choices == 2 and #result.rolls == 2 and result.rolls[2].player_id == "rh_left_b" and result.rolls[2].roll == 95
                    and result.failed[1] == "rh_left_b", "the departed player must still have taken part in the roll")
                assert(held(a) == 1 and held(b) == 0 and world_total() == before + 1, "exactly one item must reach the runner-up")
            end)
        end)
    end)

    ctx:case("open rolls survive save and load and removal cleans up", function()
        local service = assert(TheWorld.components.lootrollarbiter)
        with_players({ "rh_save_a", "rh_save_b" }, function(players)
            local a, b = players[1], players[2]
            -- After a reload the component finds players by userid in AllPlayers.
            table.insert(AllPlayers, a); table.insert(AllPlayers, b)
            local before, tasks = world_total(), world_tasks()
            local roll_id = open_roll(service, players, 9)
            assert(choose(service, a, roll_id, "greed", 4).ok == true)
            local data = service:OnSave()
            assert(type(data) == "table", "OnSave must return a table")
            plain(data)
            service:OnLoad(data)
            assert(string.find(published(), roll_id .. "|" .. ITEM .. "|1|2", 1, true), "OnLoad must republish open rolls")
            assert(world_tasks() == tasks + 1, "OnLoad must cancel the old deadline task and schedule exactly one per open roll")
            local stale = choose(service, a, roll_id, "need", 4)
            assert(stale.ok == false and stale.code == "stale_revision", "revisions must survive OnLoad")
            local spare = open_roll(service, { a }, 1)
            assert(spare ~= roll_id, "roll ids must stay unique after OnLoad")
            assert(choose(service, a, spare, "pass", 1).ok == true)
            assert(world_total() == before, "loading must not create items")
            -- greed tier {a, b} with seed 9 draws a=11, b=41.
            assert(choose(service, b, roll_id, "greed", 1).ok == true)
            local result = service:Resolve(roll_id)
            assert(result.status == "delivered" and result.winner == "rh_save_b" and result.tier == "greed", "restored roll must settle for the predicted winner")
            assert(held(b) == 1 and held(a) == 0 and world_total() == before + 1, "restored roll must deliver exactly one real item")
            assert(world_tasks() == tasks, "no deadline task may survive settlement")

            -- Removing the component cancels its deadline tasks and its ms_playerleft listener.
            with_host(function(host, private)
                assert(listener_count(host, "ms_playerleft") >= 1, "component must listen to ms_playerleft on its own entity")
                open_roll(private, { a }, 3); open_roll(private, { b }, 4)
                assert(pending_tasks(host) == 2, "every open roll must keep exactly one deadline task on the component's entity")
                host:RemoveComponent("lootrollarbiter")
                assert(pending_tasks(host) == 0, "OnRemoveFromEntity must cancel every deadline task")
                assert(listener_count(host, "ms_playerleft") == 0, "OnRemoveFromEntity must remove the ms_playerleft callback")
            end)
        end)
    end)
end
