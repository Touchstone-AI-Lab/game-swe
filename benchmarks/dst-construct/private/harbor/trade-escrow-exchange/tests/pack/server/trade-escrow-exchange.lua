local function make_player(userid, x)
    local player = CreateEntity()
    player.entity:AddTransform()
    player.Transform:SetPosition(x, 0, 0)
    player:AddComponent("inventory")
    player.userid = userid
    return player
end

local function give(player, prefab, count)
    local item = assert(SpawnPrefab(prefab), "could not spawn " .. prefab)
    if count > 1 then
        item.components.stackable:SetStackSize(count)
    end
    assert(player.components.inventory:GiveItem(item), "fixture item was not accepted")
    return item
end

local function held(player, prefab)
    local _, found = player.components.inventory:Has(prefab, 0)
    return found
end

local function discard(player)
    if player == nil or not player:IsValid() then
        return
    end
    local inventory = player.components.inventory
    if inventory ~= nil then
        for _, item in ipairs(inventory:FindItems(function() return true end)) do
            local removed = inventory:RemoveItem(item, true)
            if removed ~= nil and removed:IsValid() then
                removed:Remove()
            end
        end
    end
    player:Remove()
end

-- Runs the body and always removes the fixture players, even on failure.
local function with_players(prefix, body)
    local a = make_player(prefix .. "_a", 4)
    local b = make_player(prefix .. "_b", 8)
    local ok, message = pcall(body, a, b)
    discard(a)
    discard(b)
    if not ok then
        error(message, 0)
    end
end

local function service()
    return assert(TheWorld.components.tradeescrow, "world is missing tradeescrow")
end

local function check(result, ok, code, label)
    assert(type(result) == "table", label .. ": result must be a table")
    assert(result.ok == ok and result.code == code, label .. ": expected ok=" .. tostring(ok) .. " code=" .. code
        .. ", got ok=" .. tostring(result.ok) .. " code=" .. tostring(result.code))
    return result
end

local function trade_view(trade_id)
    local component = service()
    local snapshot = component.escrow:snapshot(component:Now())
    for _, view in ipairs(snapshot.trades) do
        if view.trade_id == trade_id then
            return view
        end
    end
    error("snapshot is missing trade " .. tostring(trade_id), 0)
end

local function party_view(trade_id, userid)
    for _, party in ipairs(trade_view(trade_id).parties) do
        if party.id == userid then
            return party
        end
    end
    error("trade is missing party " .. userid, 0)
end

local function open_trade(a, b)
    local opened = check(service():Open(a, b), true, "opened", "Open")
    assert(type(opened.trade_id) == "string" and opened.trade_id ~= "", "Open must return a trade_id")
    return opened.trade_id
end

local function count_keys(map)
    local total = 0
    for _ in pairs(map or {}) do
        total = total + 1
    end
    return total
end

-- Number of callbacks registered on the world for one world event.
local function listener_count(event)
    local total = 0
    for _, callbacks in pairs(TheWorld.event_listeners ~= nil and TheWorld.event_listeners[event] or {}) do
        total = total + count_keys(callbacks)
    end
    return total
end

local function is_plain(value, depth)
    local kind = type(value)
    if kind == "string" or kind == "number" or kind == "boolean" then
        return true
    end
    if kind ~= "table" or depth > 24 then
        return false
    end
    for key, field in pairs(value) do
        if (type(key) ~= "string" and type(key) ~= "number") or not is_plain(field, depth + 1) then
            return false
        end
    end
    return true
end

return function(ctx)
    ctx:case("trade escrow component is attached on the master simulation", function()
        assert(TheWorld ~= nil and TheWorld.ismastersim, "suite requires the master simulation")
        local component = service()
        for _, name in ipairs({ "Open", "Offer", "Confirm", "Cancel", "OnPlayerLeft", "Recover", "Now",
            "OnSave", "OnLoad", "OnRemoveFromEntity" }) do
            assert(type(component[name]) == "function", "component must expose " .. name)
        end
        assert(type(component.escrow) == "table" and type(component.escrow.snapshot) == "function",
            "component.escrow must be the core instance")
        assert(type(component:Now()) == "number", "Now must return a number")
        with_players("KU_rhenium_attach", function(a, b)
            local nameless = CreateEntity()
            nameless:AddComponent("inventory")
            local bare = CreateEntity()
            bare.userid = "KU_rhenium_attach_bare"
            local first = component:Open(a, nameless)
            local second = component:Open(bare, b)
            nameless:Remove()
            bare:Remove()
            check(first, false, "invalid_player", "Open without userid")
            check(second, false, "invalid_player", "Open without inventory")
        end)

        -- Removing the component must release its world listener and periodic task.
        local listeners, tasks = listener_count("ms_playerleft"), count_keys(TheWorld.pendingtasks)
        local removed, message = pcall(function() TheWorld:RemoveComponent("tradeescrow") end)
        local listeners_after, tasks_after = listener_count("ms_playerleft"), count_keys(TheWorld.pendingtasks)
        if TheWorld.components.tradeescrow == nil then
            TheWorld:AddComponent("tradeescrow")
        end
        assert(removed, "OnRemoveFromEntity raised: " .. tostring(message))
        assert(listeners_after < listeners, "OnRemoveFromEntity must remove the ms_playerleft listener")
        assert(tasks_after < tasks, "OnRemoveFromEntity must cancel the periodic expiry task")
        assert(service() ~= component and listener_count("ms_playerleft") > listeners_after,
            "the component must be attachable again after removal")
    end)

    ctx:case("confirmed trade swaps real inventory stacks exactly", function()
        with_players("KU_rhenium_swap", function(a, b)
            local component = service()
            give(a, "twigs", 40)
            give(a, "twigs", 5)
            local grass = give(a, "cutgrass", 2)
            give(b, "flint", 3)
            local trade_id = open_trade(a, b)

            local view = trade_view(trade_id)
            assert(math.abs(view.expires_at - view.opened_at - 120) < 0.001, "the server ttl must be 120")
            check(component:Offer(a, trade_id, { twigs = 1, cutgrass = 1, flint = 1, log = 1, rocks = 1 }), false,
                "too_many_prefabs", "Offer above max_distinct")
            assert(check(component:Offer(a, trade_id, { twigs = 1, cutgrass = 1, log = 1, rocks = 1 }), true, "offered",
                "Offer at max_distinct").revision == 1, "the first accepted offer must be revision 1")
            assert(check(component:Offer(a, trade_id, { twigs = 42, cutgrass = 2 }), true, "offered", "Offer a").revision == 2,
                "the server must assign increasing revisions")
            check(component:Offer(b, trade_id, { goldnugget = 1 }), false, "prefab_not_allowed", "Offer outside the whitelist")
            check(component:Offer(b, trade_id, { flint = 1 }), true, "offered", "Offer b")
            assert(check(component:Offer(b, trade_id, { flint = 2 }), true, "offered", "Offer b again").revision == 2,
                "the server must assign increasing revisions")

            check(component:Confirm(a, trade_id, 1), false, "stale_confirmation", "Confirm of an outdated revision")
            local first = check(component:Confirm(a, trade_id), true, "confirmed", "first Confirm")
            assert(first.phase == "open" and held(a, "twigs") == 45 and held(b, "flint") == 3,
                "one confirmation must not move items")
            local settled = check(component:Confirm(b, trade_id, 2), true, "settled", "second Confirm")
            assert(settled.phase == "settled", "second Confirm must settle the trade")

            assert(held(a, "twigs") == 3 and held(b, "twigs") == 42, "twigs did not move exactly across stacks")
            assert(held(a, "cutgrass") == 0 and held(b, "cutgrass") == 2, "cutgrass did not move exactly")
            assert(held(a, "flint") == 2 and held(b, "flint") == 1, "flint did not move exactly")
            assert(grass:IsValid() and grass.components.inventoryitem:GetGrandOwner() == b,
                "a whole stack must move as the original entity")
            assert(trade_view(trade_id).phase == "settled", "core must record the settlement")

            check(component:Confirm(b, trade_id, 2), false, "trade_closed", "Confirm after settlement")
            assert(held(a, "twigs") == 3 and held(b, "twigs") == 42 and held(a, "flint") == 2,
                "a repeated Confirm moved items again")
            local next_id = open_trade(a, b)
            assert(next_id ~= trade_id, "trade ids must not repeat")
            check(component:Cancel(a, next_id), true, "canceled", "Cancel")
        end)
    end)

    ctx:case("failed settlement restores both inventories and reopens", function()
        with_players("KU_rhenium_fail", function(a, b)
            local component = service()
            give(a, "twigs", 5)
            give(b, "flint", 2)
            local trade_id = open_trade(a, b)
            check(component:Offer(a, trade_id, { twigs = 5 }), true, "offered", "Offer a")
            check(component:Offer(b, trade_id, { flint = 2 }), true, "offered", "Offer b")
            a.components.inventory:ConsumeByName("twigs", 2)
            check(component:Confirm(a, trade_id), true, "confirmed", "Confirm a")
            local short = check(component:Confirm(b, trade_id), false, "insufficient_items", "under-funded Confirm")
            assert(short.phase == "open", "an under-funded settlement must reopen the trade")
            assert(held(a, "twigs") == 3 and held(a, "flint") == 0 and held(b, "flint") == 2 and held(b, "twigs") == 0,
                "an under-funded settlement changed an inventory")
            assert(trade_view(trade_id).phase == "open" and party_view(trade_id, a.userid).confirmed == false
                and party_view(trade_id, b.userid).confirmed == false, "reopening must clear both confirmations")

            give(a, "twigs", 2)
            check(component:Confirm(a, trade_id), true, "confirmed", "Confirm a after refunding")
            check(component:Confirm(b, trade_id), true, "settled", "Confirm b after refunding")
            assert(held(a, "twigs") == 0 and held(a, "flint") == 2 and held(b, "twigs") == 5 and held(b, "flint") == 0,
                "the re-confirmed trade did not swap exactly")

            -- b's inventory is now filled completely, so two incoming prefabs cannot both fit.
            local slots = b.components.inventory:GetNumSlots()
            for _ = 1, slots - 1 do
                give(b, "axe", 1)
            end
            assert(b.components.inventory:IsFull(), "fixture inventory must be full")
            give(a, "cutgrass", 1)
            give(a, "rocks", 3)
            local full_id = open_trade(a, b)
            check(component:Offer(a, full_id, { cutgrass = 1, rocks = 3 }), true, "offered", "Offer into a full inventory")
            check(component:Confirm(a, full_id), true, "confirmed", "Confirm a")
            local undelivered = check(component:Confirm(b, full_id), false, "delivery_failed", "Confirm into a full inventory")
            assert(undelivered.phase == "open", "a failed delivery must reopen the trade")
            assert(held(a, "cutgrass") == 1 and held(a, "rocks") == 3 and held(a, "flint") == 2,
                "a failed delivery did not restore the giver")
            assert(held(b, "cutgrass") == 0 and held(b, "rocks") == 0 and held(b, "twigs") == 5
                and held(b, "axe") == slots - 1, "a failed delivery did not restore the receiver")
            check(component:Cancel(b, full_id), true, "canceled", "Cancel")
        end)
    end)

    ctx:case("departure, rpc input and crash recovery keep state consistent", function()
        with_players("KU_rhenium_life", function(a, b)
            local component = service()
            local first_id = open_trade(a, b)
            component:OnPlayerLeft(a)
            assert(trade_view(first_id).phase == "canceled", "a departing player's open trade must be canceled")
            local trade_id = open_trade(a, b)
            assert(trade_id ~= first_id, "trade ids must not repeat")

            local offer = GetModRPCHandler("rhenium_trade", "offer")
            local confirm = GetModRPCHandler("rhenium_trade", "confirm")
            assert(type(offer) == "function" and type(confirm) == "function"
                and type(GetModRPCHandler("rhenium_trade", "open")) == "function"
                and type(GetModRPCHandler("rhenium_trade", "cancel")) == "function", "all four RPC handlers are required")
            offer(a, trade_id, "twigs", 2)
            local mine = party_view(trade_id, a.userid)
            assert(mine.revision == 1 and #mine.items == 1 and mine.items[1].prefab == "twigs"
                and mine.items[1].count == 2, "a valid offer RPC must reach the core")
            offer(a, trade_id, b, 1)
            offer(a, trade_id, "twigs")
            offer(a, trade_id, "twigs", 1, "twigs", 2)
            offer(a, trade_id, "twigs", "3")
            offer(a, trade_id, { twigs = 3 })
            assert(party_view(trade_id, a.userid).revision == 1, "a malformed offer RPC must be dropped")
            confirm(a, trade_id, "0")
            assert(party_view(trade_id, a.userid).confirmed == false, "a malformed confirm RPC must be dropped")
            confirm(b, trade_id, 1)
            assert(party_view(trade_id, b.userid).confirmed == true, "a valid confirm RPC must reach the core")

            -- Simulate a crash between begin_settle and finish_settle.
            check(component.escrow:confirm(trade_id, a.userid, 0, component:Now()), true, "confirmed", "core confirm")
            check(component.escrow:begin_settle(trade_id, component:Now()), true, "settling", "core begin_settle")
            local recovered = component:Recover()
            assert(type(recovered) == "table" and recovered.ok == true and type(recovered.recovered) == "table"
                and #recovered.recovered == 1 and recovered.recovered[1] == trade_id, "Recover must report the reopened trade")
            assert(trade_view(trade_id).phase == "open" and party_view(trade_id, b.userid).confirmed == false,
                "Recover must reopen with confirmations cleared")

            check(component.escrow:confirm(trade_id, a.userid, 0, component:Now()), true, "confirmed", "core confirm")
            check(component.escrow:confirm(trade_id, b.userid, 1, component:Now()), true, "confirmed", "core confirm")
            check(component.escrow:begin_settle(trade_id, component:Now()), true, "settling", "core begin_settle")
            local before = component:Now()
            local data = component:OnSave()
            assert(type(data) == "table" and is_plain(data, 0), "OnSave must return plain serialisable data")
            component:OnLoad(data)
            assert(component:Now() >= before, "the component clock must continue after load")
            assert(trade_view(first_id).phase == "canceled", "closed trades must survive load")
            assert(trade_view(trade_id).phase == "open" and party_view(trade_id, a.userid).confirmed == false
                and party_view(trade_id, b.userid).confirmed == false, "OnLoad must recover a settling trade")
            mine = party_view(trade_id, a.userid)
            assert(mine.revision == 1 and #mine.items == 1 and mine.items[1].count == 2, "offers must survive load")
            assert(#component:Recover().recovered == 0, "nothing is left to recover after load")

            check(component:Cancel(a, trade_id), true, "canceled", "Cancel after load")
            local third_id = open_trade(a, b)
            assert(third_id ~= first_id and third_id ~= trade_id, "trade ids must not repeat after load")
            GetModRPCHandler("rhenium_trade", "cancel")(b, third_id)
            assert(trade_view(third_id).phase == "canceled", "a cancel RPC must reach the core")

            -- A counterparty whose entity is gone blocks settlement before it begins.
            local c = make_player("KU_rhenium_life_c", 12)
            local gone_id = open_trade(a, c)
            local early = component:Confirm(c, gone_id)
            c:Remove()
            check(early, true, "confirmed", "Confirm by the departing player")
            local blocked = check(component:Confirm(a, gone_id), false, "counterparty_unavailable", "Confirm without counterparty")
            assert(blocked.phase == "open" and trade_view(gone_id).phase == "open"
                and party_view(gone_id, a.userid).confirmed == true and party_view(gone_id, c.userid).confirmed == true,
                "an unavailable counterparty must leave the trade open with confirmations kept")
            check(component:Cancel(a, gone_id), true, "canceled", "Cancel")
        end)
    end)
end
