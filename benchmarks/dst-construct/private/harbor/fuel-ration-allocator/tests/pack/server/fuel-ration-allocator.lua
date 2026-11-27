-- Published server configuration: unit_size 15, depot_capacity 60,
-- max_units_per_round 6, reserve_floor 2, log = 3 units, twigs = 1, cutgrass = 1.
local UNIT = 15

local pristine

local function service()
    local component = assert(TheWorld.components.fuelration, "world is missing fuelration")
    if pristine == nil then
        pristine = assert(component:OnSave(), "OnSave must return the component state")
    end
    return component
end

-- Runs a case body and removes every entity it created, even when it fails.
local function scenario(body)
    local created = {}
    local function keep(entity)
        created[#created + 1] = entity
        return entity
    end
    local ok, message = pcall(body, keep)
    for index = #created, 1, -1 do
        if created[index]:IsValid() then created[index]:Remove() end
    end
    if not ok then error(message, 0) end
end

local function make_player(keep, userid, items)
    local player = keep(CreateEntity())
    player.entity:AddTransform()
    player:AddComponent("inventory")
    player.userid = userid
    for prefab, count in pairs(items or {}) do
        local item = assert(SpawnPrefab(prefab), "could not spawn " .. prefab)
        if count > 1 then item.components.stackable:SetStackSize(count) end
        assert(player.components.inventory:GiveItem(item), "test inventory rejected " .. prefab)
    end
    return player
end

local function count_items(player, prefab)
    local _, found = player.components.inventory:Has(prefab, 1)
    return found
end

local function make_fire(keep, prefab, x, fuel)
    local fire = keep(assert(SpawnPrefab(prefab), "could not spawn " .. prefab))
    fire.Transform:SetPosition(x, 0, 0)
    assert(fire.components.fueled ~= nil, prefab .. " has no fueled component on the server")
    fire.components.fueled:InitializeFuelLevel(fuel)
    assert(fire.components.fueled.currentfuel == fuel, "could not set the fuel level")
    return fire
end

local function onremove_listeners(entity)
    local total = 0
    local listeners = entity.event_listeners ~= nil and entity.event_listeners.onremove or nil
    for _, functions in pairs(listeners or {}) do
        for _ in pairs(functions) do total = total + 1 end
    end
    return total
end

local function pending_tasks(entity)
    local total = 0
    for _ in pairs(entity.pendingtasks or {}) do total = total + 1 end
    return total
end

local function expect_depot(component, available, label)
    local snapshot = component:Snapshot()
    assert(type(snapshot) == "table", label .. ": Snapshot must return a table")
    assert(snapshot.available == available and snapshot.reserved == 0,
        label .. ": expected " .. available .. " available units, got " .. tostring(snapshot.available)
        .. " (reserved " .. tostring(snapshot.reserved) .. ")")
    assert(snapshot.available >= 0 and snapshot.free == 60 - snapshot.available, label .. ": depot bounds")
    return snapshot
end

local function expect_code(result, code, label)
    assert(type(result) == "table" and result.ok == false and result.code == code,
        label .. ": expected code " .. code .. ", got " .. tostring(type(result) == "table" and (result.code or result.status)))
end

local function expect_fuel(fire, fuel, label)
    local current = fire.components.fueled.currentfuel
    assert(math.abs(current - fuel) < 0.001, label .. ": expected fuel " .. fuel .. ", got " .. tostring(current))
end

return function(ctx)
    ctx:case("fuelration is attached with server authority", function()
        assert(TheWorld ~= nil and TheWorld.ismastersim, "suite requires master simulation")
        local component = service()
        for _, method in ipairs({ "Track", "Untrack", "Deposit", "RunRound", "Snapshot", "OnSave", "OnLoad", "OnRemoveFromEntity" }) do
            assert(type(component[method]) == "function", "component must expose " .. method)
        end
        component:OnLoad(pristine)
        expect_depot(component, 0, "initial depot")
        scenario(function(keep)
            local bare = keep(CreateEntity())
            bare.entity:AddTransform()
            expect_code(component:Track(bare, "attach-bare", 1), "not_fueled", "entity without fueled")
            local nobody = make_player(keep, nil, { log = 2 })
            expect_code(component:Deposit(nobody, "attach-1", "log", 1), "invalid_player", "player without userid")
            assert(count_items(nobody, "log") == 2, "a rejected deposit removed items")
            local pockets = keep(CreateEntity())
            pockets.userid = "attach-no-inventory"
            expect_code(component:Deposit(pockets, "attach-2", "log", 1), "no_inventory", "player without inventory")
            expect_depot(component, 0, "after rejected calls")
            assert(#component:Snapshot().consumers == 0, "rejected Track registered a consumer")
        end)
    end)

    ctx:case("deposit removes real items and credits the depot once", function()
        local component = service()
        component:OnLoad(pristine)
        scenario(function(keep)
            local player = make_player(keep, "KU_deposit_a", { log = 10, twigs = 2, charcoal = 3 })
            local first = component:Deposit(player, "dep-1", "log", 4)
            assert(type(first) == "table" and first.ok == true and first.status == "accepted"
                and first.accepted == 12, "four logs are worth twelve units")
            assert(count_items(player, "log") == 6, "exactly four logs must leave the inventory")
            expect_depot(component, 12, "after first deposit")
            local retry = component:Deposit(player, "dep-1", "log", 4)
            assert(retry.ok == true and retry.accepted == 12 and retry.duplicate == true, "retry must replay the result")
            assert(count_items(player, "log") == 6, "a retry removed items again")
            expect_depot(component, 12, "after retry")

            expect_code(component:Deposit(player, "dep-2", "log", 7), "insufficient_items", "more logs than held")
            expect_code(component:Deposit(player, "dep-3", "charcoal", 1), "not_fuel", "prefab outside the whitelist")
            expect_code(component:Deposit(player, "dep-4", "log", 2.5), "invalid_units", "fractional count")
            expect_code(component:Deposit(player, "dep-5", "log", 0), "invalid_units", "zero count")
            expect_code(component:Deposit(player, "", "log", 1), "invalid_id", "empty request id")
            assert(count_items(player, "log") == 6 and count_items(player, "charcoal") == 3,
                "a rejected deposit must not remove anything")
            expect_depot(component, 12, "after rejected deposits")

            local twigs = component:Deposit(player, "dep-6", "twigs", 2)
            assert(twigs.ok == true and twigs.accepted == 2, "two twigs are worth two units")
            assert(count_items(player, "twigs") == 0, "both twigs must leave the inventory")
            local spent = component:Deposit(player, "dep-6", "twigs", 2)
            assert(spent.ok == true and spent.duplicate == true and spent.accepted == 2,
                "a retry is replayed even when the items are gone")
            expect_depot(component, 14, "after twigs")

            -- The registered RPC handler is the client entry point: server player first, then
            -- request id, prefab and count. Forged payloads are ignored without raising.
            local namespace = MOD_RPC_HANDLERS["rhenium_fuel"]
            local entry = MOD_RPC["rhenium_fuel"] ~= nil and MOD_RPC["rhenium_fuel"]["deposit"] or nil
            assert(namespace ~= nil and entry ~= nil and type(namespace[entry.id]) == "function",
                "AddModRPCHandler(\"rhenium_fuel\", \"deposit\", fn) is not registered")
            local handler = namespace[entry.id]
            handler(player, "rpc-1", "log", 2)
            assert(count_items(player, "log") == 4, "the RPC must deposit two real logs")
            expect_depot(component, 20, "after the RPC deposit")
            handler(player, "rpc-1", "log", 2)
            handler(player, "rpc-2", "log", "3")
            handler(player, 17, "log", 1)
            handler(player, "rpc-3", "charcoal", 1)
            handler(player, "rpc-4", { "log" }, 1)
            assert(count_items(player, "log") == 4 and count_items(player, "charcoal") == 3,
                "retried or forged RPC payloads must not remove items")
            expect_depot(component, 20, "after forged RPC payloads")

            local hauler = make_player(keep, "KU_deposit_b", { log = 20 })
            expect_code(component:Deposit(hauler, "big-1", "log", 14), "depot_full", "42 units into 40 free")
            assert(count_items(hauler, "log") == 20, "a deposit that does not fit removes nothing")
            local fits = component:Deposit(hauler, "big-1", "log", 13)
            assert(fits.ok == true and fits.accepted == 39 and fits.duplicate ~= true,
                "a component level rejection is not recorded")
            assert(count_items(hauler, "log") == 7, "thirteen logs must leave the inventory")
            local snapshot = expect_depot(component, 59, "after hauler")
            assert(snapshot.deposited_total == 59, "deposited total")
            local rows = snapshot.contributors
            assert(#rows == 2 and rows[1].player_id == "KU_deposit_a" and rows[1].units == 20
                and rows[2].player_id == "KU_deposit_b" and rows[2].units == 39, "contributions come from player.userid")
        end)
    end)

    ctx:case("round fuels real fires by priority and fairness", function()
        local component = service()
        component:OnLoad(pristine)
        scenario(function(keep)
            local pit = make_fire(keep, "firepit", 20, 290)
            local fire_a = make_fire(keep, "campfire", 40, 50)
            local fire_b = make_fire(keep, "campfire", 60, 250)
            local tracked = component:Track(pit, "pit-p", 0)
            assert(type(tracked) == "table" and tracked.ok == true and tracked.status == "registered"
                and tracked.capacity == 24 and tracked.level == 20, "firepit is 24 units with 290 fuel as level 20")
            local a = component:Track(fire_a, "fire-a", 1)
            assert(a.ok == true and a.capacity == 18 and a.level == 4, "campfire is 18 units with 50 fuel as level 4")
            local b = component:Track(fire_b, "fire-b", 1)
            assert(b.ok == true and b.capacity == 18 and b.level == 17, "250 fuel rounds up to level 17")
            expect_code(component:Track(fire_b, "fire-b", 1), "already_tracked", "entity tracked twice")
            local fire_c = make_fire(keep, "campfire", 80, 90)
            local base_c = onremove_listeners(fire_c)
            expect_code(component:Track(fire_c, "fire-b", 1), "duplicate_consumer", "consumer id used twice")
            expect_code(component:Track(fire_c, "fire-c", -1), "invalid_priority", "negative priority")
            assert(onremove_listeners(fire_c) == base_c, "a rejected Track must not leave a listener")

            local player = make_player(keep, "KU_round", { log = 3, twigs = 2 })
            assert(component:Deposit(player, "round-logs", "log", 3).ok == true)
            assert(component:Deposit(player, "round-twigs", "twigs", 2).ok == true)
            expect_depot(component, 11, "before the round")

            -- budget 11 - 2 = 9: pit-p (class 0) takes its demand 4; class 1 shares 5 units:
            -- fire-a 1, fire-b 1 (demand met), fire-a 2, 3, 4.
            local result = component:RunRound("server-round-1")
            assert(type(result) == "table" and result.ok == true and result.status == "closed", "round must close")
            assert(result.total == 9 and result.delivered == 9 and result.returned == 0, "round totals")
            local expected = { { "pit-p", 4 }, { "fire-a", 4 }, { "fire-b", 1 } }
            assert(type(result.shares) == "table" and #result.shares == 3, "three shares expected")
            for index, row in ipairs(expected) do
                local share = result.shares[index]
                assert(share.consumer_id == row[1] and share.units == row[2] and share.delivered == row[2]
                    and share.status == "committed", "share " .. index .. " should be " .. row[1] .. "=" .. row[2])
            end
            expect_fuel(pit, 290 + 4 * UNIT, "firepit")
            expect_fuel(fire_a, 50 + 4 * UNIT, "campfire a")
            expect_fuel(fire_b, 250 + 1 * UNIT, "campfire b")
            expect_fuel(fire_c, 90, "untracked campfire")
            local snapshot = expect_depot(component, 2, "after the round")
            assert(snapshot.delivered_total == 9 and snapshot.round == nil, "round accounting")

            expect_code(component:RunRound("server-round-1"), "round_closed", "closed round id")
            local idle = component:RunRound("server-round-2")
            assert(idle.ok == true and idle.total == 0 and #idle.shares == 0, "the reserve floor is never planned")
            expect_fuel(pit, 350, "firepit after idle rounds")
            expect_fuel(fire_a, 110, "campfire a after idle rounds")
            expect_fuel(fire_b, 265, "campfire b after idle rounds")
            expect_depot(component, 2, "after idle rounds")

            -- The real component may accept less than planned: fire-d is tracked with the stock
            -- campfire limit and then its real maxfuel is lowered to 120, so DoDelta stops there.
            -- Only what was measured may be committed; the rest returns to the depot.
            local fire_d = make_fire(keep, "campfire", 100, 60)
            assert(component:Track(fire_d, "fire-d", 1).ok == true)
            fire_d.components.fueled.maxfuel = 120
            local donor = make_player(keep, "KU_round_b", { log = 4 })
            assert(component:Deposit(donor, "round-more", "log", 4).ok == true)
            expect_depot(component, 14, "before the clipped round")
            local clipped = component:RunRound("server-round-3")
            assert(clipped.ok == true and clipped.status == "closed" and clipped.delivered == 10,
                "fire-a takes 6 units and fire-d only the 4 units its fueled component accepted")
            for _, share in ipairs(clipped.shares) do
                if share.consumer_id == "fire-d" then
                    assert(share.delivered == 4 and share.status == "committed", "fire-d must commit the measured 4 units")
                end
            end
            expect_fuel(fire_a, 110 + 6 * UNIT, "campfire a after the clipped round")
            expect_fuel(fire_d, 120, "campfire d is clipped at its real maxfuel")
            local after = expect_depot(component, 4, "undelivered units return to the depot")
            assert(after.delivered_total == 19, "only accepted fuel counts as delivered")
        end)
    end)

    ctx:case("removed fires are released and state survives reload", function()
        local component = service()
        component:OnLoad(pristine)
        local real_time = GetTime
        local ok, message = pcall(scenario, function(keep)
            local fire_a = make_fire(keep, "campfire", 100, 60)
            local fire_b = make_fire(keep, "campfire", 120, 60)
            local base_a, base_b = onremove_listeners(fire_a), onremove_listeners(fire_b)
            assert(component:Track(fire_a, "keep-a", 1).ok == true)
            assert(component:Track(fire_b, "gone-b", 1).ok == true)
            assert(onremove_listeners(fire_a) > base_a, "Track must listen for onremove on the entity")
            local player = make_player(keep, "KU_reload", { log = 9, twigs = 2 })
            assert(component:Deposit(player, "reload-1", "log", 2).ok == true)
            assert(component:Deposit(player, "reload-2", "twigs", 2).ok == true)

            -- The removed fire is unregistered, so the whole budget of 6 goes to keep-a.
            fire_b:Remove()
            local snapshot = expect_depot(component, 8, "after removing a fire")
            assert(#snapshot.consumers == 1 and snapshot.consumers[1].consumer_id == "keep-a",
                "onremove must unregister the consumer")
            local result = component:RunRound("reload-round-1")
            assert(result.ok == true and #result.shares == 1 and result.shares[1].consumer_id == "keep-a"
                and result.shares[1].delivered == 6, "the removed fire must not hold a share")
            expect_fuel(fire_a, 60 + 6 * UNIT, "campfire keep-a")
            expect_depot(component, 2, "after the round")

            -- Untrack pairs the listener and returns the consumer.
            local fire_u = make_fire(keep, "campfire", 140, 60)
            local base_u = onremove_listeners(fire_u)
            assert(component:Track(fire_u, "untrack-u", 1).ok == true)
            local untracked = component:Untrack("untrack-u")
            assert(type(untracked) == "table" and untracked.ok == true and untracked.status == "unregistered")
            assert(onremove_listeners(fire_u) == base_u, "Untrack must remove its onremove listener")
            expect_code(component:Untrack("untrack-u"), "unknown_consumer", "second Untrack")

            local saved = component:OnSave()
            assert(type(saved) == "table", "OnSave must return a table")
            local fire_c = make_fire(keep, "campfire", 160, 60)
            assert(component:Track(fire_c, "late-c", 1).ok == true)
            assert(component:Deposit(player, "reload-3", "log", 4).ok == true)
            expect_depot(component, 14, "before reload")

            -- A new server session restarts GetTime() at zero while the saved clock does not.
            GetTime = function() return 0 end
            component:OnLoad(saved)
            local restored = expect_depot(component, 2, "restored depot")
            assert(restored.deposited_total == 8 and restored.delivered_total == 6, "restored totals")
            assert(#restored.contributors == 1 and restored.contributors[1].player_id == "KU_reload"
                and restored.contributors[1].units == 8, "restored contributions")
            assert(#restored.consumers == 2 and restored.consumers[1].consumer_id == "keep-a"
                and restored.consumers[2].consumer_id == "late-c", "OnLoad must reconcile tracked entities")
            local again = component:Deposit(player, "reload-1", "log", 2)
            assert(again.ok == true and again.duplicate == true, "request history must survive reload")
            local credited = component:Deposit(player, "reload-3", "log", 3)
            assert(type(credited) == "table" and credited.ok == true and credited.accepted == 9
                and credited.duplicate ~= true, "time must not run backwards after reload")
            assert(count_items(player, "log") == 0, "three more logs must leave the inventory")
            expect_code(component:RunRound("reload-round-1"), "round_closed", "closed ids must survive reload")
            GetTime = real_time

            -- budget 11 - 2 = 9 between keep-a (level 10) and late-c (level 4): 5 and 4.
            local second = component:RunRound("reload-round-2")
            assert(second.ok == true and second.total == 9 and second.delivered == 9, "round after reload")
            expect_fuel(fire_a, 150 + 5 * UNIT, "campfire keep-a after reload")
            expect_fuel(fire_c, 60 + 4 * UNIT, "campfire late-c after reload")
            expect_depot(component, 2, "after the round following reload")

            -- Removing the component cancels its task and drops every listener.
            local tasks = pending_tasks(TheWorld)
            TheWorld:RemoveComponent("fuelration")
            assert(onremove_listeners(fire_a) == base_a, "OnRemoveFromEntity must remove onremove listeners")
            assert(pending_tasks(TheWorld) < tasks, "OnRemoveFromEntity must cancel the periodic task")
            fire_a:Remove()
        end)
        GetTime = real_time
        if TheWorld.components.fuelration == nil then
            TheWorld:AddComponent("fuelration")
        end
        if not ok then error(message, 0) end
    end)
end
