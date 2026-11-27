local COMPONENT = "waystonenetwork"

local function gold_count(player)
    local _, found = player.components.inventory:Has("goldnugget", 1)
    return found
end

local function give_gold(player, amount)
    local gold = assert(SpawnPrefab("goldnugget"), "goldnugget prefab is unavailable")
    gold.components.stackable:SetStackSize(amount)
    assert(player.components.inventory:GiveItem(gold), "gold was not accepted by the real inventory")
end

local function at(entity, x, z)
    local ex, _, ez = entity.Transform:GetWorldPosition()
    return math.abs(ex - x) < 0.01 and math.abs(ez - z) < 0.01
end

local function expect_ok(result, label)
    assert(type(result) == "table" and result.ok == true,
        label .. " should succeed, got code " .. tostring(type(result) == "table" and result.code or result))
    return result
end

local function expect_code(result, code, label)
    assert(type(result) == "table" and result.ok == false, label .. " should be rejected")
    assert(result.code == code, label .. " expected code " .. code .. ", got " .. tostring(result.code))
    return result
end

-- Runs body(make) and removes every entity it created, even when it fails.
local function scoped(body)
    local made = {}
    local make = {}
    function make.anchor(x, z)
        local entity = CreateEntity()
        entity.entity:AddTransform()
        entity.Transform:SetPosition(x, 0, z)
        made[#made + 1] = entity
        return entity
    end
    function make.person(userid, x, z, gold, physics)
        local entity = CreateEntity()
        entity.entity:AddTransform()
        if physics then MakeCharacterPhysics(entity, 75, .5) end
        entity.Transform:SetPosition(x, 0, z)
        entity:AddComponent("inventory")
        entity.userid = userid
        made[#made + 1] = entity
        if gold ~= nil and gold > 0 then give_gold(entity, gold) end
        return entity
    end
    local ok, message = pcall(body, make)
    for index = #made, 1, -1 do
        if made[index]:IsValid() then made[index]:Remove() end
    end
    if not ok then error(message, 0) end
end

local function is_plain(value, depth)
    local kind = type(value)
    if kind == "string" or kind == "number" or kind == "boolean" then return true end
    if kind ~= "table" or depth > 12 then return false end
    for key, item in pairs(value) do
        if type(key) ~= "string" and type(key) ~= "number" then return false end
        if not is_plain(item, depth + 1) then return false end
    end
    return true
end

return function(ctx)
    ctx:case("world waystone component is master attached", function()
        assert(TheWorld ~= nil and TheWorld.ismastersim, "suite requires master simulation")
        local service = assert(TheWorld.components[COMPONENT], "world is missing waystonenetwork")
        for _, method in ipairs({ "Register", "Link", "Route", "Travel", "OnSave", "OnLoad", "OnRemoveFromEntity" }) do
            assert(type(service[method]) == "function", "component must expose " .. method)
        end
        scoped(function(make)
            local owner = make.person("KU_wrn_owner1", 100, 100)
            local nameless = make.person(nil, 100, 100)
            local stone = make.anchor(100, 100)
            expect_code(service:Register({}, "s1-a", owner), "invalid_entity", "registering a non-entity")
            expect_code(service:Register(stone, "s1-a", nameless), "invalid_player", "owner without userid")
            expect_code(service:Travel(nameless, "s1-r1", "s1-a", "s1-b"), "invalid_player", "traveler without userid")
            expect_code(service:Route("s1-a", "s1-b"), "unknown_node", "rejected registrations create no node")
            local spots = { { 100, 100 }, { 100, 161 }, { 160, 100 }, { 130, 130 } }
            for index, spot in ipairs(spots) do
                expect_ok(service:Register(make.anchor(spot[1], spot[2]), "s1-n" .. index, owner), "register s1-n" .. index)
            end
            expect_code(service:Register(make.anchor(120, 120), "s1-n5", owner), "owner_limit", "fifth waystone of one owner")
            expect_code(service:Link("s1-n1", "s1-n2"), "link_too_long", "real anchors 61 units apart")
            assert(expect_ok(service:Link("s1-n1", "s1-n3"), "real anchors 60 units apart").cost == 60, "60 units cost 60")
        end)
    end)

    ctx:case("real travel charges gold and moves the player", function()
        local service = assert(TheWorld.components[COMPONENT], "world is missing waystonenetwork")
        scoped(function(make)
            local owner = make.person("KU_wrn_owner2", 200, 200)
            local a, b, c = make.anchor(200, 200), make.anchor(203, 204), make.anchor(206, 208)
            local first = expect_ok(service:Register(a, "s2-a", owner), "register a")
            assert(first.rebound == false and first.node_id == "s2-a", "a new node reports rebound = false and node_id")
            expect_ok(service:Register(b, "s2-b", owner), "register b")
            expect_ok(service:Register(c, "s2-c", owner), "register c")
            expect_code(service:Register(a, "s2-a2", owner), "already_registered", "entity registered twice")
            expect_code(service:Register(make.anchor(209, 212), "s2-a", owner), "duplicate_node", "bound node id reused")
            local linked = expect_ok(service:Link("s2-a", "s2-b"), "link a-b")
            assert(linked.created == true and linked.cost == 5, "link cost must come from the real transforms (3-4-5)")
            assert(expect_ok(service:Link("s2-b", "s2-c"), "link b-c").cost == 5, "b-c costs 5")
            local route = expect_ok(service:Route("s2-a", "s2-c"), "route a-c")
            assert(route.cost == 10 and table.concat(route.path, ",") == "s2-a,s2-b,s2-c", "route a-b-c costs 10")

            local rich = make.person("KU_wrn_p1", 204, 200, 5, true)
            local trip = expect_ok(service:Travel(rich, "s2-r1", "s2-a", "s2-c"), "travel at exactly the travel radius")
            assert(trip.duplicate == false and trip.price == 3, "10 * 0.25 = 2.5 rounds up to a price of 3")
            assert(type(trip.ticket) == "table" and trip.ticket.status == "committed"
                and trip.ticket.traveler_id == "KU_wrn_p1", "ticket is committed for player.userid")
            assert(at(rich, 206, 208), "player was not moved to the destination anchor")
            assert(gold_count(rich) == 2, "exactly 3 gold must leave the real inventory, left " .. tostring(gold_count(rich)))

            local replay = expect_ok(service:Travel(rich, "s2-r1", "s2-a", "s2-c"), "retry of a committed request")
            assert(replay.duplicate == true, "a retry must be reported as duplicate")
            assert(gold_count(rich) == 2 and at(rich, 206, 208), "a retry must not charge or move again")
            expect_code(service:Travel(rich, "s2-r2", "s2-c", "s2-a"), "cooldown", "second trip during cooldown")
            assert(gold_count(rich) == 2 and at(rich, 206, 208), "a cooldown rejection must change nothing")

            local poor = make.person("KU_wrn_p2", 200, 200, 2, false)
            local broke = expect_code(service:Travel(poor, "s2-r3", "s2-a", "s2-c"), "insufficient_funds", "underfunded trip")
            assert(broke.price == 3, "insufficient_funds carries the price")
            assert(gold_count(poor) == 2 and at(poor, 200, 200), "an underfunded rejection must change nothing")
            give_gold(poor, 1)
            local closed = expect_code(service:Travel(poor, "s2-r3", "s2-a", "s2-c"), "ticket_closed", "reused failed request id")
            assert(closed.status == "aborted", "the failed trip's ticket must have been aborted")
            expect_ok(service:Travel(poor, "s2-r4", "s2-a", "s2-c"), "a failed trip leaves no live ticket or cooldown")
            assert(gold_count(poor) == 0 and at(poor, 206, 208), "transform-only traveler was charged and moved")

            local distant = make.person("KU_wrn_p3", 204.5, 200, 5, false)
            expect_code(service:Travel(distant, "s2-r5", "s2-a", "s2-c"), "too_far", "traveler outside the travel radius")
            assert(gold_count(distant) == 5 and at(distant, 204.5, 200), "a too_far rejection must change nothing")
        end)
    end)

    ctx:case("removed anchor invalidates routes and rolls back travel", function()
        local service = assert(TheWorld.components[COMPONENT], "world is missing waystonenetwork")
        scoped(function(make)
            local owner = make.person("KU_wrn_owner3", 300, 300)
            local a, b, c, e = make.anchor(300, 300), make.anchor(303, 304), make.anchor(306, 308), make.anchor(300, 305)
            expect_ok(service:Register(a, "s3-a", owner), "register a")
            expect_ok(service:Register(b, "s3-b", owner), "register b")
            expect_ok(service:Register(c, "s3-c", owner), "register c")
            expect_ok(service:Register(e, "s3-e", owner), "register e")
            expect_ok(service:Link("s3-a", "s3-b"), "link a-b")
            expect_ok(service:Link("s3-b", "s3-c"), "link b-c")
            expect_ok(service:Link("s3-a", "s3-e"), "link a-e")
            expect_ok(service:Route("s3-a", "s3-e"), "route a-e")
            e:Remove()
            expect_code(service:Route("s3-a", "s3-e"), "unknown_node", "route to a removed anchor")
            local again = expect_ok(service:Register(make.anchor(300, 305), "s3-e", owner), "node id is free after removal")
            assert(again.rebound == false, "a removed node is created anew")
            expect_code(service:Route("s3-a", "s3-e"), "no_route", "links of a removed anchor are gone")

            -- The intermediate anchor disappears while the fare is being taken:
            -- the commit must fail and every real effect must be undone.
            local traveler = make.person("KU_wrn_p4", 301, 300, 3, false)
            local fired = false
            local function vanish()
                if not fired then
                    fired = true
                    b:Remove()
                end
            end
            traveler:ListenForEvent("itemlose", vanish)
            local result = service:Travel(traveler, "s3-r1", "s3-a", "s3-c")
            traveler:RemoveEventCallback("itemlose", vanish)
            assert(fired, "the fare must be removed from the real inventory before the commit")
            expect_code(result, "route_changed", "travel whose route vanished before commit")
            assert(gold_count(traveler) == 3, "the fare must be refunded, inventory holds " .. tostring(gold_count(traveler)))
            assert(at(traveler, 301, 300), "the traveler must be moved back")
            expect_code(service:Route("s3-a", "s3-c"), "no_route", "route through the removed anchor")

            assert(expect_ok(service:Link("s3-a", "s3-c"), "direct link").cost == 10, "direct a-c costs 10")
            expect_ok(service:Travel(traveler, "s3-r2", "s3-a", "s3-c"), "a rolled back trip starts no cooldown")
            assert(gold_count(traveler) == 0 and at(traveler, 306, 308), "the second trip was charged and moved")
        end)
    end)

    ctx:case("state persists and listeners are released", function()
        local service = assert(TheWorld.components[COMPONENT], "world is missing waystonenetwork")
        scoped(function(make)
            local owner = make.person("KU_wrn_owner4", 400, 400)
            local stranger = make.person("KU_wrn_owner5", 400, 400)
            local a, c = make.anchor(400, 400), make.anchor(403, 404)
            expect_ok(service:Register(a, "s4-a", owner), "register a")
            expect_ok(service:Register(c, "s4-c", owner), "register c")
            expect_ok(service:Link("s4-a", "s4-c"), "link a-c")
            local early = make.person("KU_wrn_p5", 400, 400, 4, false)
            assert(expect_ok(service:Travel(early, "s4-r1", "s4-a", "s4-c"), "trip before save").price == 2, "5 * 0.25 rounds up to 2")

            local data = service:OnSave()
            assert(type(data) == "table" and is_plain(data, 0), "OnSave must return plain serializable data")
            service:OnLoad(data)
            assert(expect_ok(service:Route("s4-a", "s4-c"), "route after load").cost == 5, "nodes and links survive load")
            local replay = expect_ok(service:Travel(early, "s4-r1", "s4-a", "s4-c"), "retry after load")
            assert(replay.duplicate == true and gold_count(early) == 2, "request history survives load")

            local late = make.person("KU_wrn_p6", 400, 400, 4, false)
            expect_code(service:Travel(late, "s4-r2", "s4-a", "s4-c"), "unbound_node", "travel before anchors register again")
            assert(gold_count(late) == 4 and at(late, 400, 400), "an unbound_node rejection must change nothing")
            expect_code(service:Register(a, "s4-a", stranger), "owner_mismatch", "rebinding with another owner")
            assert(expect_ok(service:Register(a, "s4-a", owner), "rebind a").rebound == true, "a persisted node is rebound")
            assert(expect_ok(service:Register(c, "s4-c", owner), "rebind c").rebound == true, "a persisted node is rebound")
            expect_ok(service:Travel(late, "s4-r3", "s4-a", "s4-c"), "travel after rebinding")
            assert(gold_count(late) == 2 and at(late, 403, 404), "rebound anchors move and charge the player")
            expect_code(service:Travel(early, "s4-r4", "s4-c", "s4-a"), "cooldown", "cooldown survives load")

            assert(a.event_listeners ~= nil and a.event_listeners.onremove ~= nil, "registered anchors are watched for onremove")
            local ok, message = pcall(function()
                TheWorld:RemoveComponent(COMPONENT)
                assert(a.event_listeners == nil or a.event_listeners.onremove == nil,
                    "OnRemoveFromEntity must remove every onremove callback")
                assert(c.event_listeners == nil or c.event_listeners.onremove == nil,
                    "OnRemoveFromEntity must remove every onremove callback")
            end)
            if TheWorld.components[COMPONENT] == nil then TheWorld:AddComponent(COMPONENT) end
            assert(ok, message)
            assert(TheWorld.components[COMPONENT] ~= nil, "component can be attached again")
        end)
    end)
end
