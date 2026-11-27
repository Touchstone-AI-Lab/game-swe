local loaded, Network = pcall(load_submission, "scripts/waystones/network.lua")
if not loaded or type(Network) ~= "table" then Network = {} end
local cases = {}
local function expect(value, message) if not value then error(message or "expectation failed", 0) end end
local function run(name, body)
    local ok, message = pcall(body)
    cases[#cases + 1] = { name = name, passed = ok, message = ok and "ok" or tostring(message) }
end

local WIDE = { max_nodes_per_owner = 50, max_link_length = 100, cost_per_unit = 0.25, ticket_ttl = 10, cooldown = 30 }

local function fresh(options)
    expect(type(Network.new) == "function", "module must export Network.new")
    local net = Network.new(options)
    expect(type(net) == "table", "Network.new must return a network")
    return net
end
local function good(result, label)
    expect(type(result) == "table" and result.ok == true,
        label .. " should succeed, got code " .. tostring(type(result) == "table" and result.code or result))
    return result
end
local function bad(result, code, label)
    expect(type(result) == "table" and result.ok == false, label .. " should be rejected")
    expect(result.code == code, label .. " expected code " .. code .. ", got " .. tostring(result.code))
    return result
end
-- nodes: { id, x, z } rows, links: { a, b, expected_cost } rows, all at time `now`.
local function build(options, nodes, links, now)
    local net = fresh(options)
    for _, row in ipairs(nodes) do
        good(net:add_node(row[1], "owner", row[2], row[3], now), "add_node " .. row[1])
    end
    for _, row in ipairs(links) do
        local linked = good(net:link(row[1], row[2], now), "link " .. row[1] .. "-" .. row[2])
        expect(linked.created == true and linked.cost == row[3],
            "link " .. row[1] .. "-" .. row[2] .. " expected cost " .. row[3] .. ", got " .. tostring(linked.cost))
    end
    return net
end
local function expect_route(net, from_id, to_id, now, cost, path)
    local label = "route " .. from_id .. "->" .. to_id
    local found = good(net:route(from_id, to_id, now), label)
    expect(type(found.path) == "table", label .. " must return a path")
    expect(found.cost == cost, label .. " expected cost " .. cost .. ", got " .. tostring(found.cost))
    expect(table.concat(found.path, ",") == table.concat(path, ","),
        label .. " expected path " .. table.concat(path, ",") .. ", got " .. table.concat(found.path, ","))
    expect(found.hops == #path - 1, label .. " expected hops " .. (#path - 1) .. ", got " .. tostring(found.hops))
end
-- Numeric fields are compared as numbers, never through tostring, so an
-- implementation may hold 5 or 5.0 under Lua 5.4.
local function expect_links(view, rows, label)
    expect(type(view.links) == "table" and #view.links == #rows, label .. ": expected " .. #rows .. " links")
    for index, row in ipairs(rows) do
        local link = view.links[index]
        expect(type(link) == "table" and link.a == row[1] and link.b == row[2] and link.cost == row[3],
            label .. ": link " .. index .. " must be " .. row[1] .. "-" .. row[2] .. " cost " .. row[3])
    end
end
local function deep_copy(value)
    if type(value) ~= "table" then return value end
    local out = {}
    for key, item in pairs(value) do out[key] = deep_copy(item) end
    return out
end
local function deep_equal(a, b)
    if type(a) ~= "table" or type(b) ~= "table" then return a == b end
    for key, item in pairs(a) do if not deep_equal(item, b[key]) then return false end end
    for key in pairs(b) do if a[key] == nil then return false end end
    return true
end
local function is_plain(value, depth)
    local kind = type(value)
    if kind == "string" or kind == "number" or kind == "boolean" then return true end
    if kind ~= "table" or depth > 12 or getmetatable(value) ~= nil then return false end
    for key, item in pairs(value) do
        if type(key) ~= "string" and type(key) ~= "number" then return false end
        if not is_plain(item, depth + 1) then return false end
    end
    return true
end
local function scrub(value)
    for key, item in pairs(value) do
        if type(item) == "table" then scrub(item) end
        value[key] = nil
    end
end

run("nodes and links enforce ids caps rounding and length", function()
    local net = fresh({ max_nodes_per_owner = 2, max_link_length = 60 })
    local added = good(net:add_node("a", "o1", 0, 0, 1), "add a")
    expect(added.node_id == "a", "add_node must return node_id")
    bad(net:add_node("", "o9", 1, 1, 1), "invalid_id", "empty node id")
    bad(net:add_node("bad id", "o9", 1, 1, 1), "invalid_id", "node id with a space")
    bad(net:add_node(string.rep("n", 65), "o9", 1, 1, 1), "invalid_id", "65 character node id")
    bad(net:add_node("n1", 42, 1, 1, 1), "invalid_id", "numeric owner id")
    bad(net:add_node("n1", "o9", 0 / 0, 1, 1), "invalid_position", "NaN x")
    bad(net:add_node("n1", "o9", 1, math.huge, 1), "invalid_position", "infinite z")
    bad(net:add_node("n1", "o9", 1, "2", 1), "invalid_position", "string z")
    good(net:add_node(string.rep("n", 64), "o9", 9, 9, 1), "64 character node id")
    bad(net:add_node("a", "o2", 5, 5, 1), "duplicate_node", "duplicate node id")
    good(net:add_node("b", "o1", 3, 4, 1), "add b")
    bad(net:add_node("c", "o1", 2.5, 0, 1), "owner_limit", "third node of o1")
    good(net:add_node("c", "o2", 2.5, 0, 1), "add c")
    good(net:add_node("d", "o2", 0, 0, 1), "add d")
    good(net:add_node("e", "o3", 5, 5, 1), "add e")
    good(net:add_node("f", "o3", 7, 7, 1), "add f")
    good(net:add_node("g", "o4", 36, 48, 1), "add g")
    good(net:add_node("h", "o4", 60, 1, 1), "add h")

    local first = good(net:link("a", "b", 1), "link a-b")
    expect(first.created == true and first.cost == 5, "3-4-5 link must cost 5")
    local again = good(net:link("b", "a", 1), "link b-a")
    expect(again.created == false and again.cost == 5, "reversed duplicate link must not be created twice")
    expect(good(net:link("a", "c", 1), "link a-c").cost == 3, "distance 2.5 rounds half up to 3")
    expect(good(net:link("a", "d", 1), "link a-d").cost == 1, "distance 0 uses the minimum cost 1")
    expect(good(net:link("a", "e", 1), "link a-e").cost == 7, "distance 7.07 rounds to 7")
    expect(good(net:link("a", "f", 1), "link a-f").cost == 10, "distance 9.90 rounds to 10")
    expect(good(net:link("a", "g", 1), "link a-g").cost == 60, "a link of exactly max_link_length is allowed")
    bad(net:link("a", "h", 1), "link_too_long", "link longer than max_link_length")
    bad(net:link("a", "a", 1), "self_link", "self link")
    bad(net:link("a", "zz", 1), "unknown_node", "link to unknown node")
    bad(net:link("a", 7, 1), "invalid_id", "link with numeric id")

    expect_links(good(net:snapshot(1), "snapshot"),
        { { "a", "b", 5 }, { "a", "c", 3 }, { "a", "d", 1 }, { "a", "e", 7 }, { "a", "f", 10 }, { "a", "g", 60 } },
        "links are deduplicated, normalized and ordered")

    expect(good(net:remove_node("b", 2), "remove b").removed_links == 1, "removing b removes its one link")
    good(net:add_node("b2", "o1", 1, 1, 2), "owner slot is free again after removal")
    expect(good(net:unlink("c", "a", 2), "unlink c-a").removed == true, "unlink must report removal")
    expect(good(net:unlink("a", "c", 2), "unlink a-c again").removed == false, "second unlink removes nothing")
    bad(net:unlink("a", "zz", 2), "unknown_node", "unlink unknown node")
    expect(#good(net:snapshot(2), "snapshot").links == 4, "four links remain")

    local defaults = fresh({ max_nodes_per_owner = -1, max_link_length = "far" })
    for index = 1, 4 do good(defaults:add_node("n" .. index, "o1", 0, (index - 1) * 61, 0), "default cap node " .. index) end
    bad(defaults:add_node("n5", "o1", 0, 1, 0), "owner_limit", "fifth node under the default cap of 4")
    good(defaults:add_node("m", "o2", 60, 0, 0), "add m")
    expect(good(defaults:link("n1", "m", 0), "default length 60").cost == 60, "default max_link_length is 60")
    bad(defaults:link("n1", "n2", 0), "link_too_long", "61 units under the default length")
end)

run("cheapest route breaks ties by hops then node order", function()
    local cheap = build(WIDE, { { "s", 0, 0 }, { "a", 10, 0 }, { "b", 20, 0 }, { "t", 30, 0 }, { "q", 15, 26 } },
        { { "s", "q", 30 }, { "q", "t", 30 }, { "s", "a", 10 }, { "a", "b", 10 }, { "b", "t", 10 } }, 1)
    expect_route(cheap, "s", "t", 1, 30, { "s", "a", "b", "t" })

    local hops = build(WIDE, { { "s", 0, 0 }, { "a", 2, 0 }, { "b", 4, 0 }, { "c", 7, 0 }, { "t", 10, 0 } },
        { { "s", "a", 2 }, { "a", "b", 2 }, { "b", "t", 6 }, { "s", "c", 7 }, { "c", "t", 3 } }, 1)
    expect_route(hops, "s", "t", 1, 10, { "s", "c", "t" })
    expect_route(hops, "t", "s", 1, 10, { "t", "c", "s" })

    local skew = build(WIDE, { { "s", 0, 0 }, { "t", 10, 0 }, { "k1", 6, 0 }, { "k2", 3, 0 } },
        { { "s", "k2", 3 }, { "k2", "t", 7 }, { "s", "k1", 6 }, { "k1", "t", 4 } }, 1)
    expect_route(skew, "s", "t", 1, 10, { "s", "k1", "t" })
    expect_route(skew, "t", "s", 1, 10, { "t", "k1", "s" })

    local late = build(WIDE, { { "s", 0, 0 }, { "m2", 5, 1 }, { "m1", 5, 0 }, { "t", 10, 0 } },
        { { "s", "m2", 5 }, { "m2", "t", 5 }, { "s", "m1", 5 }, { "m1", "t", 5 } }, 1)
    expect_route(late, "s", "t", 1, 10, { "s", "m1", "t" })
    local early = build(WIDE, { { "t", 10, 0 }, { "m1", 5, 0 }, { "m2", 5, 1 }, { "s", 0, 0 } },
        { { "m1", "t", 5 }, { "s", "m1", 5 }, { "m2", "t", 5 }, { "s", "m2", 5 } }, 1)
    expect_route(early, "s", "t", 1, 10, { "s", "m1", "t" })

    local deep = build(WIDE, { { "s", 0, 0 }, { "a", 3, 0 }, { "z", 6, 0 }, { "t", 10, 0 }, { "b", 3, 1 }, { "c", 6, 1 } },
        { { "s", "b", 3 }, { "b", "c", 3 }, { "c", "t", 4 }, { "s", "a", 3 }, { "a", "z", 3 }, { "z", "t", 4 } }, 1)
    expect_route(deep, "s", "t", 1, 10, { "s", "a", "z", "t" })
    expect_route(deep, "t", "s", 1, 10, { "t", "c", "b", "s" })
end)

run("blocked and removed nodes leave routing", function()
    local net = build(WIDE, { { "a", 0, 0 }, { "b", 10, 0 }, { "c", 20, 0 }, { "d", 0, 10 }, { "e", 20, 10 } },
        { { "a", "b", 10 }, { "b", "c", 10 }, { "a", "d", 10 }, { "d", "e", 20 }, { "e", "c", 10 } }, 1)
    expect_route(net, "a", "c", 1, 20, { "a", "b", "c" })
    bad(net:route("a", "a", 1), "same_node", "route to itself")
    bad(net:route("a", "zz", 1), "unknown_node", "route to unknown node")
    bad(net:route("a", 5, 1), "invalid_id", "route with a numeric id")

    local blocked = good(net:set_blocked("b", true, 2), "block b")
    expect(blocked.blocked == true and blocked.changed == true, "first block must report a change")
    expect(good(net:set_blocked("b", true, 2), "block b again").changed == false, "repeated block changes nothing")
    bad(net:set_blocked("b", "yes", 2), "invalid_flag", "non-boolean flag")
    bad(net:set_blocked("zz", true, 2), "unknown_node", "block unknown node")
    expect_route(net, "a", "c", 2, 40, { "a", "d", "e", "c" })
    bad(net:route("a", "b", 2), "blocked_endpoint", "blocked destination")
    bad(net:route("b", "c", 2), "blocked_endpoint", "blocked origin")
    bad(net:route("b", "b", 2), "same_node", "same_node is checked before blocked_endpoint")
    local unblocked = good(net:set_blocked("b", false, 3), "unblock b")
    expect(unblocked.blocked == false and unblocked.changed == true, "unblock must report a change")
    expect_route(net, "a", "c", 3, 20, { "a", "b", "c" })

    expect(good(net:remove_node("b", 4), "remove b").removed_links == 2, "removing b removes both of its links")
    expect_route(net, "a", "c", 4, 40, { "a", "d", "e", "c" })
    bad(net:route("a", "b", 4), "unknown_node", "route to removed node")
    local view = good(net:snapshot(4), "snapshot")
    local nodes, links = {}, {}
    for index, node in ipairs(view.nodes) do nodes[index] = node.id end
    for index, link in ipairs(view.links) do links[index] = link.a .. "-" .. link.b end
    expect(table.concat(nodes, ",") == "a,c,d,e", "removed node must leave the snapshot")
    expect(table.concat(links, ",") == "a-d,c-e,d-e", "links of a removed node must disappear, got " .. table.concat(links, ","))

    good(net:add_node("b", "owner", 10, 0, 5), "re-add b")
    expect_route(net, "a", "c", 5, 40, { "a", "d", "e", "c" })
    good(net:set_blocked("b", true, 5), "block the new b")
    expect(good(net:link("a", "b", 5), "link blocked b").created == true, "blocked nodes may still be linked")
    expect(good(net:link("b", "c", 5), "link blocked b to c").created == true, "blocked nodes may still be linked")
    expect_route(net, "a", "c", 5, 40, { "a", "d", "e", "c" })
    good(net:set_blocked("d", true, 6), "block d")
    bad(net:route("a", "c", 6), "no_route", "every route crosses a blocked node")
    good(net:set_blocked("b", false, 7), "unblock b")
    expect_route(net, "a", "c", 7, 20, { "a", "b", "c" })
    expect(good(net:remove_node("d", 8), "remove d").removed_links == 2, "removing d removes two links")
    bad(net:remove_node("d", 8), "unknown_node", "second removal of d")
end)

run("reserve deduplicates prices and honors time boundaries", function()
    local net = build(WIDE, { { "a", 0, 0 }, { "b", 5, 0 }, { "c", 13, 0 } }, { { "a", "b", 5 }, { "b", "c", 8 } }, 100)
    local first = good(net:reserve("r1", "p1", "a", "c", 100), "reserve r1")
    local t1 = first.ticket
    expect(first.duplicate == false and type(t1) == "table", "first reserve creates a ticket")
    expect(type(t1.ticket_id) == "string" and t1.ticket_id ~= "", "ticket_id must be a non-empty string")
    expect(t1.request_id == "r1" and t1.traveler_id == "p1" and t1.from_id == "a" and t1.to_id == "c", "ticket identity fields")
    expect(table.concat(t1.path, ",") == "a,b,c" and t1.cost == 13, "ticket carries the route")
    expect(t1.price == 4, "13 * 0.25 = 3.25 rounds up to 4, got " .. tostring(t1.price))
    expect(t1.status == "reserved" and t1.created_at == 100 and t1.expires_at == 110, "ticket lifetime fields")
    good(net:reserve("rz", "p4", "a", "b", 100), "reserve rz")

    local retry = good(net:reserve("r1", "p1", "a", "c", 101), "retry r1")
    expect(retry.duplicate == true and retry.ticket.ticket_id == t1.ticket_id and retry.ticket.expires_at == 110,
        "a retry must return the same ticket")
    bad(net:reserve("r1", "p2", "a", "c", 101), "request_conflict", "r1 reused by another traveler")
    bad(net:reserve("r1", "p1", "a", "b", 101), "request_conflict", "r1 reused for another destination")
    bad(net:reserve("r2", "p1", "b", "c", 101), "traveler_busy", "second live ticket for p1")
    bad(net:reserve("bad id", "p5", "a", "c", 101), "invalid_id", "malformed request id")

    local t9 = good(net:reserve("r9", "p2", "b", "c", 101), "reserve r9").ticket
    expect(t9.price == 2 and t9.cost == 8, "8 * 0.25 = 2 stays 2, got " .. tostring(t9.price))
    expect(t9.ticket_id ~= t1.ticket_id, "ticket ids must be unique")
    bad(net:reserve("r4", "p3", "a", "zz", 101), "unknown_node", "reserve to unknown node")
    local t4 = good(net:reserve("r4", "p3", "c", "a", 101), "a failed reserve records nothing").ticket
    expect(table.concat(t4.path, ",") == "c,b,a" and t4.price == 4, "reverse trip route and price")
    local queue = good(net:snapshot(101), "snapshot").tickets
    expect(#queue == 4 and queue[1].request_id == "r1" and queue[2].request_id == "rz" and queue[3].request_id == "r4"
        and queue[4].request_id == "r9", "snapshot tickets are ordered by expires_at then request_id")

    local committed = good(net:commit(t1.ticket_id, 105), "commit r1")
    expect(committed.cooldown_until == 135, "cooldown_until = commit time + cooldown")
    local expired = good(net:tick(111), "tick 111").expired
    local rz = good(net:reserve("rz", "p4", "a", "b", 111), "retry rz").ticket
    expect(rz.status == "expired", "a retry reports the current ticket status")
    expect(#expired == 3 and expired[1] == rz.ticket_id and expired[2] == t4.ticket_id and expired[3] == t9.ticket_id,
        "tick orders expiry by expires_at then request_id, got " .. table.concat(expired, ","))
    expect(#good(net:tick(111), "second tick").expired == 0, "a ticket expires exactly once")
    local closed = bad(net:commit(t9.ticket_id, 112), "ticket_closed", "commit of an expired ticket")
    expect(closed.status == "expired", "ticket_closed must carry the status")

    local t10 = good(net:reserve("r10", "p2", "b", "c", 112), "expiry starts no cooldown").ticket
    local t11 = good(net:reserve("r11", "p3", "a", "b", 112), "reserve r11").ticket
    expect(t11.price == 2, "5 * 0.25 = 1.25 rounds up to 2, got " .. tostring(t11.price))
    expect(good(net:commit(t11.ticket_id, 121.5), "commit just before expiry").cooldown_until == 151.5, "fractional cooldown")
    expect(bad(net:commit(t10.ticket_id, 122), "ticket_closed", "commit at expires_at").status == "expired",
        "now == expires_at is already expired")

    local cooling = bad(net:reserve("r5", "p1", "a", "c", 134.5), "cooldown", "reserve during cooldown")
    expect(cooling.retry_at == 135, "cooldown rejection carries retry_at")
    local t5 = good(net:reserve("r5", "p1", "a", "c", 135), "now == cooldown_until is allowed").ticket
    expect(t5.expires_at == 145, "new ticket lifetime")
    good(net:reserve("r6", "p1", "a", "b", 145), "an expired ticket frees its traveler without tick")
    expect(#good(net:tick(145), "tick 145").expired == 0, "lazily expired tickets are not reported again")
end)

run("commit is exactly once and rejects changed routes", function()
    local net = build(WIDE, { { "a", 0, 0 }, { "b", 5, 0 }, { "c", 13, 0 }, { "d", 0, 6 }, { "e", 13, 6 } },
        { { "a", "b", 5 }, { "b", "c", 8 }, { "a", "d", 6 }, { "d", "e", 13 }, { "e", "c", 6 } }, 100)
    bad(net:commit("T404", 100), "unknown_ticket", "commit of unknown ticket")
    bad(net:commit(12, 100), "invalid_id", "numeric ticket id")
    bad(net:abort("T404", 100), "unknown_ticket", "abort of unknown ticket")

    local t1 = good(net:reserve("r1", "p1", "a", "c", 100), "reserve r1").ticket
    local done = good(net:commit(t1.ticket_id, 105), "commit r1")
    expect(done.duplicate == false and done.ticket.status == "committed" and done.cooldown_until == 135, "first commit")
    local replay = good(net:commit(t1.ticket_id, 120), "repeat commit")
    expect(replay.duplicate == true and replay.cooldown_until == 135, "a repeated commit must not restart the cooldown")
    expect(bad(net:reserve("r1b", "p1", "a", "c", 134), "cooldown", "p1 cooling down").retry_at == 135,
        "cooldown boundary must still be 135")
    expect(bad(net:abort(t1.ticket_id, 134), "ticket_closed", "abort after commit").status == "committed",
        "abort of a committed ticket reports its status")

    local t2 = good(net:reserve("r2", "p2", "a", "c", 134), "reserve r2").ticket
    local aborted = good(net:abort(t2.ticket_id, 134), "abort r2")
    expect(aborted.duplicate == false and aborted.ticket.status == "aborted", "first abort")
    expect(good(net:abort(t2.ticket_id, 134), "repeat abort").duplicate == true, "abort is idempotent")
    expect(bad(net:commit(t2.ticket_id, 134), "ticket_closed", "commit after abort").status == "aborted",
        "commit of an aborted ticket reports its status")

    local t3 = good(net:reserve("r3", "p2", "a", "c", 134), "abort starts no cooldown").ticket
    good(net:set_blocked("b", true, 135), "block b")
    bad(net:commit(t3.ticket_id, 135), "route_changed", "commit through a blocked hop")
    expect(bad(net:commit(t3.ticket_id, 135), "ticket_closed", "second commit").status == "invalidated",
        "a rejected ticket is closed as invalidated")
    local t4 = good(net:reserve("r4", "p2", "a", "c", 135), "route_changed releases the traveler without cooldown").ticket
    expect(table.concat(t4.path, ",") == "a,d,e,c" and t4.cost == 25 and t4.price == 7, "detour costs 25 and is priced 7")
    local live = good(net:snapshot(135), "snapshot").tickets
    expect(#live == 1 and live[1].ticket_id == t4.ticket_id, "only the live ticket is listed")
    good(net:abort(t4.ticket_id, 135), "abort r4")

    good(net:set_blocked("b", false, 136), "unblock b")
    local t5 = good(net:reserve("r5", "p3", "a", "c", 136), "reserve r5").ticket
    expect(table.concat(t5.path, ",") == "a,b,c", "r5 uses a,b,c")
    expect(good(net:link("a", "c", 136), "direct link").cost == 13, "direct link costs 13")
    local kept = good(net:commit(t5.ticket_id, 137), "a new cheaper-or-equal link does not invalidate a ticket")
    expect(table.concat(kept.ticket.path, ",") == "a,b,c" and kept.ticket.price == 4, "committed ticket keeps its route and price")

    local t6 = good(net:reserve("r6", "p4", "a", "c", 137), "reserve r6").ticket
    expect(table.concat(t6.path, ",") == "a,c" and t6.cost == 13, "equal cost prefers the single hop")
    good(net:unlink("a", "c", 137), "unlink a-c")
    bad(net:commit(t6.ticket_id, 137), "route_changed", "commit over a removed link")

    local t7 = good(net:reserve("r7", "p5", "a", "c", 138), "reserve r7").ticket
    expect(table.concat(t7.path, ",") == "a,b,c" and t7.cost == 13, "r7 uses a,b,c")
    good(net:remove_node("b", 138), "remove b")
    good(net:add_node("b", "owner", 5, 3, 138), "re-add b elsewhere")
    expect(good(net:link("a", "b", 138), "relink a-b").cost == 6, "new a-b costs 6")
    expect(good(net:link("b", "c", 138), "relink b-c").cost == 9, "new b-c costs 9")
    bad(net:commit(t7.ticket_id, 138), "route_changed", "same hops with a different total cost")
end)

run("time validation snapshot freshness and save load", function()
    local clock = fresh(WIDE)
    bad(clock:tick("5"), "invalid_time", "string time")
    bad(clock:tick(0 / 0), "invalid_time", "NaN time")
    bad(clock:tick(math.huge), "invalid_time", "infinite time")
    bad(clock:tick(-1), "invalid_time", "time before the initial clock 0")
    bad(clock:add_node("bad id", "o1", 0, 0, 50), "invalid_id", "bad id at time 50")
    bad(clock:tick(49), "invalid_time", "a call rejected after time validation still advances the clock")
    bad(clock:add_node("q", "o1", 0, 0, 40), "invalid_time", "stale add_node")
    expect(#good(clock:snapshot(50), "snapshot at the clock").nodes == 0, "an invalid_time call has no effect")

    local net = fresh(WIDE)
    good(net:add_node("c", "o2", 13, 0, 100), "add c")
    good(net:add_node("x", "o2", 50, 50, 100), "add x")
    good(net:add_node("b", "o1", 5, 0, 100), "add b")
    good(net:add_node("a", "o1", 0, 0, 100), "add a")
    good(net:link("x", "c", 100), "link x-c"); good(net:link("c", "b", 100), "link c-b"); good(net:link("b", "a", 100), "link b-a")
    good(net:set_blocked("x", true, 100), "block x")
    local t4 = good(net:reserve("r4", "p9", "a", "b", 100), "reserve r4").ticket
    good(net:commit(t4.ticket_id, 100), "commit r4")
    local t1 = good(net:reserve("r1", "p1", "a", "c", 100), "reserve r1").ticket
    good(net:commit(t1.ticket_id, 101), "commit r1")
    local t2 = good(net:reserve("r2", "p2", "a", "b", 102), "reserve r2").ticket
    local t3 = good(net:reserve("r3", "p3", "b", "c", 102), "reserve r3").ticket
    good(net:abort(t3.ticket_id, 102), "abort r3")
    t2.path[1] = "hacked"; t2.status = "committed"

    local view = good(net:snapshot(103), "snapshot")
    expect(view.now == 103, "snapshot carries now")
    expect(type(view.nodes) == "table" and #view.nodes == 4 and view.nodes[1].id == "a" and view.nodes[2].id == "b"
        and view.nodes[3].id == "c" and view.nodes[4].id == "x", "nodes are ordered by id")
    expect(view.nodes[1].owner_id == "o1" and view.nodes[3].owner_id == "o2" and view.nodes[3].x == 13
        and view.nodes[3].z == 0 and view.nodes[3].blocked == false and view.nodes[4].blocked == true, "node fields")
    expect_links(view, { { "a", "b", 5 }, { "b", "c", 8 }, { "c", "x", 62 } }, "links are normalized and ordered")
    expect(#view.tickets == 1 and view.tickets[1].ticket_id == t2.ticket_id and view.tickets[1].status == "reserved"
        and table.concat(view.tickets[1].path, ",") == "a,b", "only live tickets, unaffected by caller mutation")
    expect(#view.cooldowns == 2 and view.cooldowns[1].traveler_id == "p1" and view.cooldowns[1].cooldown_until == 131
        and view.cooldowns[2].traveler_id == "p9" and view.cooldowns[2].cooldown_until == 130,
        "cooldowns are ordered by traveler_id")
    local pristine = deep_copy(view)
    view.nodes[1].id = "hacked"; view.tickets[1].path[2] = "hacked"; view.links[1] = nil; view.cooldowns[1].cooldown_until = 0
    expect(deep_equal(good(net:snapshot(103), "second snapshot"), pristine), "snapshots must be fresh tables")

    local saved = good(net:save(104), "save")
    expect(type(saved.data) == "table" and is_plain(saved.data, 0), "save data must be plain strings, numbers, booleans and tables")
    local wire = deep_copy(saved.data)
    scrub(saved.data)
    local expected = good(net:snapshot(104), "snapshot after save")
    expect(#expected.nodes == 4 and #expected.tickets == 1, "mutating saved data must not touch the network")

    expect(type(Network.load) == "function", "module must export Network.load")
    local restored = Network.load(wire, WIDE)
    scrub(wire)
    expect(deep_equal(good(restored:snapshot(104), "restored snapshot"), expected), "load must restore the same snapshot")
    bad(restored:tick(103), "invalid_time", "the clock is restored")
    local retry = good(restored:reserve("r1", "p1", "a", "c", 104), "retry r1 after load")
    expect(retry.duplicate == true and retry.ticket.ticket_id == t1.ticket_id and retry.ticket.status == "committed",
        "request history survives load")
    bad(restored:route("a", "x", 104), "blocked_endpoint", "blocked flag survives load")
    expect(good(restored:abort(t3.ticket_id, 105), "abort r3 after load").duplicate == true, "closed tickets survive load")
    expect(good(restored:commit(t2.ticket_id, 105), "commit r2 after load").cooldown_until == 135, "live tickets survive load")
    local t8 = good(restored:reserve("r8", "p4", "a", "c", 105), "reserve r8 after load").ticket
    expect(t8.ticket_id ~= t1.ticket_id and t8.ticket_id ~= t2.ticket_id and t8.ticket_id ~= t3.ticket_id
        and t8.ticket_id ~= t4.ticket_id, "ticket ids are never reused after load")
    expect(bad(restored:reserve("r9", "p1", "a", "c", 130.5), "cooldown", "p1 cooldown after load").retry_at == 131,
        "cooldowns survive load")
    good(restored:reserve("r9", "p1", "a", "c", 131), "cooldown boundary after load")

    for _, junk in ipairs({ false, "junk" }) do
        local empty = Network.load(junk, WIDE)
        expect(type(empty) == "table" and #good(empty:snapshot(0), "empty snapshot").nodes == 0, "malformed data loads an empty network")
        good(empty:add_node("a", "o1", 0, 0, 0), "empty network is usable")
    end
    local blank = Network.load(nil, WIDE)
    expect(#good(blank:snapshot(0), "nil data snapshot").nodes == 0, "nil data loads an empty network")
end)

return { cases = cases }
