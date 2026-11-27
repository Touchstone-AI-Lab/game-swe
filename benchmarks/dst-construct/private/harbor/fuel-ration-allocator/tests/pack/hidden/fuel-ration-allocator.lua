local loaded, Allocator = pcall(load_submission, "scripts/fuelration/allocator.lua")
if not loaded or type(Allocator) ~= "table" then Allocator = {} end

local cases = {}
local function expect(value, message) if not value then error(message or "expectation failed", 0) end end
local function run(name, body)
    local ok, message = pcall(body)
    cases[#cases + 1] = { name = name, passed = ok, message = ok and "ok" or tostring(message) }
end

local OPTIONS = { depot_capacity = 40, max_units_per_round = 5, reserve_floor = 2 }

local function fresh()
    expect(type(Allocator.new) == "function", "module must export Allocator.new")
    local allocator = Allocator.new(OPTIONS)
    expect(type(allocator) == "table", "Allocator.new must return a table")
    return allocator
end
local function rejected(result, code, label)
    expect(type(result) == "table", label .. ": result must be a table")
    expect(result.ok == false and result.code == code,
        label .. ": expected code " .. code .. ", got " .. tostring(result.code or result.status))
end
local function accepted(result, status, label)
    expect(type(result) == "table", label .. ": result must be a table")
    expect(result.ok == true and result.status == status,
        label .. ": expected status " .. status .. ", got " .. tostring(result.status or result.code))
end
-- Registers a consumer and reports its level at the same time.
local function consumer(allocator, id, priority, capacity, level, now)
    accepted(allocator:register(id, priority, capacity, now), "registered", "register " .. id)
    accepted(allocator:report(id, level, now), "reported", "report " .. id)
end
local function shares_equal(shares, expected, label)
    expect(type(shares) == "table" and #shares == #expected, label .. ": wrong number of shares")
    for index, row in ipairs(expected) do
        local share = shares[index]
        expect(type(share) == "table" and share.consumer_id == row[1] and share.priority == row[2]
            and share.units == row[3], label .. ": share " .. index .. " should be " .. row[1] .. "=" .. row[3])
    end
end
local function depot(allocator, available, reserved, label)
    local snapshot = allocator:snapshot(0)
    expect(type(snapshot) == "table", label .. ": snapshot must be a table")
    expect(snapshot.available == available and snapshot.reserved == reserved,
        label .. ": expected available/reserved " .. available .. "/" .. reserved .. ", got "
        .. tostring(snapshot.available) .. "/" .. tostring(snapshot.reserved))
    expect(snapshot.free == OPTIONS.depot_capacity - available - reserved, label .. ": free is inconsistent")
    expect(snapshot.deposited_total == snapshot.available + snapshot.reserved + snapshot.delivered_total,
        label .. ": units are not conserved")
    return snapshot
end
local function consumer_row(snapshot, id)
    for _, row in ipairs(snapshot.consumers) do
        if row.consumer_id == id then return row end
    end
    return nil
end

run("quantities and time are validated before any state change", function()
    local a = fresh()
    local nan, inf = 0 / 0, 1 / 0
    rejected(a:deposit("t1", "p1", 1, nan), "invalid_time", "NaN time")
    rejected(a:deposit("t2", "p1", 1, inf), "invalid_time", "infinite time")
    rejected(a:deposit("t3", "p1", 1, -1), "invalid_time", "negative time")
    rejected(a:deposit("t4", "p1", 1, "5"), "invalid_time", "string time")
    rejected(a:deposit("t5", "p1", 1, nil), "invalid_time", "missing time")
    accepted(a:deposit("r1", "p1", 3, 10), "accepted", "first deposit")
    rejected(a:deposit("r2", "p1", 1, 9), "time_regressed", "older time")
    accepted(a:deposit("r2", "p1", 1, 10), "accepted", "equal time is allowed")
    for index, units in ipairs({ 2.5, 0, -1, nan, inf, "3" }) do
        rejected(a:deposit("u" .. index, "p1", units, 10), "invalid_units", "bad units #" .. index)
    end
    rejected(a:deposit("", "p1", 1, 10), "invalid_id", "empty request id")
    rejected(a:deposit("r3", 42, 1, 10), "invalid_id", "numeric player id")
    rejected(a:deposit(string.rep("x", 65), "p1", 1, 10), "invalid_id", "65 character id")
    accepted(a:deposit(string.rep("x", 64), "p1", 1, 10), "accepted", "64 character id")
    rejected(a:deposit("", "p1", 2.5, 5), "time_regressed", "time is validated first")
    rejected(a:deposit("", "p1", 2.5, 10), "invalid_id", "ids are validated before units")
    -- A call that fails validation must not advance the clock or be recorded.
    rejected(a:deposit("late", "p1", 2.5, 500), "invalid_units", "fractional units")
    local retry = a:deposit("late", "p1", 1, 11)
    accepted(retry, "accepted", "valid retry of a request that failed validation")
    expect(retry.duplicate ~= true and retry.accepted == 1, "validation failures must not be recorded")
    -- A call that passes validation advances the clock even if it fails afterwards.
    rejected(a:unregister("ghost", 100), "unknown_consumer", "unknown consumer")
    rejected(a:deposit("r4", "p1", 1, 50), "time_regressed", "clock advanced by a validated call")
    rejected(a:register("c", -1, 5, 100), "invalid_priority", "negative priority")
    rejected(a:register("c", 1.5, 5, 100), "invalid_priority", "fractional priority")
    rejected(a:register("c", 1, 0, 100), "invalid_units", "zero capacity")
    rejected(a:register("c", 1, 2.5, 100), "invalid_units", "fractional capacity")
    accepted(a:register("c", 0, 1, 100), "registered", "priority 0 and capacity 1 are valid")
    rejected(a:register("c", 0, 1, 100), "duplicate_consumer", "duplicate consumer")
    rejected(a:report("c", 1.5, 100), "invalid_units", "fractional level")
    rejected(a:report("c", 0, nan), "invalid_time", "NaN report time")
    rejected(a:commit("none", "c", -1, 100), "invalid_units", "negative delivery")
    rejected(a:commit("none", "c", 0.5, 100), "invalid_units", "fractional delivery")
    rejected(a:plan("", 100), "invalid_id", "empty round id")
    local snapshot = depot(a, 6, 0, "after rejected calls")
    expect(snapshot.deposited_total == 6 and #snapshot.consumers == 1, "rejected calls changed state")
end)

run("deposits deduplicate and respect depot capacity", function()
    local a = fresh()
    local first = a:deposit("r1", "alice", 30, 1)
    accepted(first, "accepted", "first deposit")
    expect(first.accepted == 30 and first.duplicate ~= true, "first deposit result is wrong")
    local again = a:deposit("r1", "alice", 5, 2)
    accepted(again, "accepted", "deposit retry")
    expect(again.accepted == 30 and again.duplicate == true, "retry must replay the first result")
    depot(a, 30, 0, "after retry")
    local other = a:deposit("r1", "bob", 4, 3)
    accepted(other, "accepted", "same request id from another player")
    expect(other.accepted == 4 and other.duplicate ~= true, "request ids are scoped per player")
    local partial = a:deposit("r2", "bob", 10, 4)
    accepted(partial, "partial", "deposit larger than the free space")
    expect(partial.accepted == 6, "partial deposit must accept exactly the free space")
    depot(a, 40, 0, "full depot")
    local full = a:deposit("r3", "alice", 1, 5)
    rejected(full, "depot_full", "deposit into a full depot")
    expect(full.accepted == 0, "a rejected deposit accepts nothing")
    local partial_retry = a:deposit("r2", "bob", 10, 6)
    accepted(partial_retry, "partial", "partial retry")
    expect(partial_retry.accepted == 6 and partial_retry.duplicate == true, "partial retry changed")
    expect(type(a.lookup) == "function", "allocator must expose lookup")
    local found = a:lookup("r2", "bob")
    expect(type(found) == "table" and found.ok == true and found.status == "partial" and found.accepted == 6,
        "lookup must return the recorded result")
    expect(a:lookup("missing", "bob") == nil, "lookup of an unknown request must be nil")
    -- Reserved units still occupy the depot.
    consumer(a, "f", 0, 10, 0, 7)
    local plan = a:plan("k1", 7)
    accepted(plan, "planned", "plan")
    shares_equal(plan.shares, { { "f", 0, 5 } }, "plan k1")
    depot(a, 35, 5, "after plan")
    rejected(a:deposit("r4", "alice", 1, 8), "depot_full", "reserved units count against capacity")
    accepted(a:commit("k1", "f", 5, 9), "committed", "commit")
    depot(a, 35, 0, "after commit")
    -- The first outcome of a recorded request is stable even when space exists now.
    local stable = a:deposit("r3", "alice", 1, 10)
    rejected(stable, "depot_full", "recorded rejection")
    expect(stable.duplicate == true and stable.accepted == 0, "recorded rejection must be replayed")
    accepted(a:deposit("r5", "alice", 2, 11), "accepted", "new request after space was freed")
    local snapshot = depot(a, 37, 0, "final")
    expect(snapshot.deposited_total == 42 and snapshot.delivered_total == 5, "totals are wrong")
    local rows = snapshot.contributors
    expect(type(rows) == "table" and #rows == 2, "two contributors expected")
    expect(rows[1].player_id == "alice" and rows[1].units == 32, "alice contributed 32 units")
    expect(rows[2].player_id == "bob" and rows[2].units == 10, "bob contributed 10 units")
end)

run("plan is priority ordered max-min fair with cap and floor", function()
    local a = fresh()
    consumer(a, "z-low", 5, 9, 0, 1)
    consumer(a, "f3", 2, 20, 0, 1)
    consumer(a, "f2", 2, 20, 19, 1)
    consumer(a, "f10", 2, 20, 0, 1)
    consumer(a, "full", 2, 8, 0, 1)
    consumer(a, "pit", 0, 10, 0, 1)
    accepted(a:deposit("d", "p", 13, 8), "accepted", "deposit")
    -- Reports carry measurement time: newer than the last report wins, older is stale,
    -- and they are never compared with the global clock (which is 8 here).
    local newer = a:report("f3", 7, 5)
    accepted(newer, "reported", "report older than the clock but newer than the last report")
    expect(newer.level == 7 and newer.demand == 13, "report result must carry level and demand")
    local stale = a:report("f3", 19, 4)
    accepted(stale, "stale", "report older than the last report")
    expect(consumer_row(a:snapshot(8), "f3").level == 7, "a stale report changed the level")
    accepted(a:report("f3", 0, 5), "reported", "report with an equal time is accepted")
    local clamped = a:report("full", 50, 6)
    accepted(clamped, "reported", "level above capacity")
    expect(clamped.level == 8 and clamped.demand == 0, "level must be clamped to capacity")
    accepted(a:report("pit", 7, 1000), "reported", "future measurement")
    rejected(a:report("nobody", 1, 6), "unknown_consumer", "report for unknown consumer")
    -- budget = 13 - 2 = 11: class 0 takes 3, class 2 water-fills 8, class 5 gets nothing.
    local plan = a:plan("p1", 9)
    accepted(plan, "planned", "report must not advance the global clock")
    shares_equal(plan.shares, { { "pit", 0, 3 }, { "f10", 2, 4 }, { "f2", 2, 1 }, { "f3", 2, 3 } }, "plan p1")
    expect(plan.total == 11 and plan.round_id == "p1", "plan total or round id is wrong")
    depot(a, 2, 11, "after plan p1")
    accepted(a:commit("p1", "pit", 3, 10), "committed", "commit pit")
    accepted(a:commit("p1", "f10", 4, 10), "committed", "commit f10")
    accepted(a:commit("p1", "f2", 1, 10), "committed", "commit f2")
    accepted(a:commit("p1", "f3", 3, 10), "committed", "commit f3")
    accepted(a:close("p1", 11), "closed", "close p1")
    local snapshot = depot(a, 2, 0, "after round p1")
    expect(consumer_row(snapshot, "f2").level == 20 and consumer_row(snapshot, "f10").level == 4,
        "commit must raise the consumer level")
    -- Plenty of fuel: every share is capped at max_units_per_round and the floor stays.
    accepted(a:deposit("d2", "p", 30, 12), "accepted", "second deposit")
    local second = a:plan("p2", 13)
    accepted(second, "planned", "plan p2")
    shares_equal(second.shares, { { "f10", 2, 5 }, { "f3", 2, 5 }, { "z-low", 5, 5 } }, "plan p2")
    expect(second.total == 15, "plan p2 total")
    depot(a, 17, 15, "after plan p2")
end)

run("plan retries are identical and only one round is open", function()
    local a = fresh()
    consumer(a, "a", 1, 10, 0, 1)
    consumer(a, "b", 1, 10, 0, 1)
    accepted(a:deposit("d", "p", 8, 2), "accepted", "deposit")
    local plan = a:plan("r1", 10)
    accepted(plan, "planned", "plan r1")
    expect(plan.duplicate ~= true, "first plan is not a duplicate")
    shares_equal(plan.shares, { { "a", 1, 3 }, { "b", 1, 3 } }, "plan r1")
    rejected(a:plan("r2", 11), "round_open", "second open round")
    local commit = a:commit("r1", "a", 2, 12)
    accepted(commit, "committed", "commit a")
    expect(commit.units == 3 and commit.delivered == 2 and commit.returned == 1, "commit a numbers")
    accepted(a:deposit("x", "p", 10, 13), "accepted", "deposit during the round")
    depot(a, 13, 3, "before retry")
    plan.shares[1].units = 99
    local retry = a:plan("r1", 15)
    accepted(retry, "planned", "plan retry")
    expect(retry.duplicate == true and retry.total == 6, "plan retry must be marked duplicate")
    shares_equal(retry.shares, { { "a", 1, 3 }, { "b", 1, 3 } }, "plan retry")
    local snapshot = depot(a, 13, 3, "retry must not reserve again")
    expect(type(snapshot.round) == "table" and snapshot.round.round_id == "r1" and snapshot.round.total == 6,
        "snapshot must expose the open round")
    local rows = snapshot.round.shares
    expect(#rows == 2 and rows[1].consumer_id == "a" and rows[1].status == "committed"
        and rows[1].delivered == 2 and rows[1].returned == 1, "share a row")
    expect(rows[2].consumer_id == "b" and rows[2].status == "pending" and rows[2].units == 3
        and rows[2].delivered == 0 and rows[2].returned == 0, "share b row")
    local closed = a:close("r1", 16)
    accepted(closed, "closed", "close r1")
    expect(closed.total == 6 and closed.delivered == 2 and closed.returned == 4 and closed.duplicate ~= true,
        "close numbers")
    local after = depot(a, 16, 0, "close returns unsettled shares")
    expect(after.round == nil, "no round is open after close")
    local again = a:close("r1", 16)
    accepted(again, "closed", "close retry")
    expect(again.duplicate == true and again.total == 6 and again.delivered == 2 and again.returned == 4,
        "close retry numbers")
    rejected(a:plan("r1", 17), "round_closed", "closed round id reuse")
    rejected(a:commit("r1", "b", 1, 18), "round_closed", "commit on closed round")
    rejected(a:abort("r1", "b", 18), "round_closed", "abort on closed round")
    rejected(a:commit("nope", "b", 1, 18), "unknown_round", "commit on unknown round")
    rejected(a:close("nope", 18), "unknown_round", "close unknown round")
    depot(a, 16, 0, "rejected round calls")
    local third = a:plan("r3", 19)
    accepted(third, "planned", "plan r3")
    shares_equal(third.shares, { { "a", 1, 5 }, { "b", 1, 5 } }, "plan r3")
    rejected(a:commit("r1", "a", 1, 20), "round_closed", "closed id while another round is open")
    rejected(a:abort("zz", "a", 20), "unknown_round", "unknown id while another round is open")
end)

run("shares settle exactly once and rollback returns units", function()
    local a = fresh()
    for _, id in ipairs({ "d", "c", "b", "a" }) do consumer(a, id, 1, 10, 0, 1) end
    accepted(a:deposit("dep", "p", 14, 2), "accepted", "deposit")
    local plan = a:plan("r", 10)
    shares_equal(plan.shares, { { "a", 1, 3 }, { "b", 1, 3 }, { "c", 1, 3 }, { "d", 1, 3 } }, "plan r")
    depot(a, 2, 12, "after plan")
    rejected(a:commit("r", "a", 4, 11), "over_delivery", "delivery above the planned share")
    depot(a, 2, 12, "over delivery changes nothing")
    accepted(a:report("a", 9, 11), "reported", "report during the round")
    local first = a:commit("r", "a", 3, 12)
    accepted(first, "committed", "commit a")
    expect(first.delivered == 3 and first.returned == 0 and first.duplicate ~= true, "commit a numbers")
    local repeated = a:commit("r", "a", 1, 13)
    accepted(repeated, "committed", "repeated commit")
    expect(repeated.delivered == 3 and repeated.returned == 0 and repeated.duplicate == true,
        "repeated commit must replay the first settlement")
    local crossed = a:abort("r", "a", 14)
    accepted(crossed, "committed", "abort after commit")
    expect(crossed.duplicate == true and crossed.delivered == 3, "abort after commit must replay the commit")
    local over_again = a:commit("r", "a", 99, 14)
    accepted(over_again, "committed", "settled share is checked before over delivery")
    depot(a, 2, 9, "after commit a")
    local aborted = a:abort("r", "b", 15)
    accepted(aborted, "aborted", "abort b")
    expect(aborted.units == 3 and aborted.delivered == 0 and aborted.returned == 3, "abort b numbers")
    local late = a:commit("r", "b", 3, 16)
    accepted(late, "aborted", "commit after abort")
    expect(late.duplicate == true and late.delivered == 0 and late.returned == 3, "commit after abort numbers")
    depot(a, 5, 6, "after abort b")
    rejected(a:commit("r", "zz", 1, 17), "unknown_share", "consumer without a share")
    local gone = a:unregister("c", 18)
    accepted(gone, "unregistered", "unregister c")
    expect(gone.returned == 3, "unregister must return the pending share")
    local snapshot = depot(a, 8, 3, "after unregister c")
    expect(consumer_row(snapshot, "c") == nil, "unregistered consumer is still listed")
    expect(snapshot.round.shares[3].consumer_id == "c" and snapshot.round.shares[3].status == "aborted"
        and snapshot.round.shares[3].returned == 3, "unregistered share must be aborted")
    local orphan = a:commit("r", "c", 1, 19)
    accepted(orphan, "aborted", "commit for an unregistered consumer")
    expect(orphan.duplicate == true, "share of an unregistered consumer is already settled")
    rejected(a:unregister("c", 19), "unknown_consumer", "second unregister")
    accepted(a:register("c", 1, 10, 20), "registered", "register c again")
    local zero = a:commit("r", "d", 0, 21)
    accepted(zero, "committed", "zero delivery is a valid commit")
    expect(zero.delivered == 0 and zero.returned == 3, "zero delivery numbers")
    snapshot = depot(a, 11, 0, "after all shares settled")
    expect(snapshot.delivered_total == 3, "delivered total")
    local row_a, row_c = consumer_row(snapshot, "a"), consumer_row(snapshot, "c")
    expect(row_a.level == 10 and row_a.demand == 0 and row_a.received == 3, "level is clamped to capacity on commit")
    expect(row_c.level == 10 and row_c.demand == 0 and row_c.received == 0, "a new consumer starts with no demand")
    expect(consumer_row(snapshot, "b").received == 0 and consumer_row(snapshot, "d").level == 0, "b and d rows")
    local closed = a:close("r", 22)
    accepted(closed, "closed", "close")
    expect(closed.total == 12 and closed.delivered == 3 and closed.returned == 9, "close numbers")
    depot(a, 11, 0, "after close")
end)

run("snapshots are fresh and save load preserves an open round", function()
    local a = fresh()
    accepted(a:deposit("d1", "bo", 3, 1), "accepted", "deposit bo")
    accepted(a:deposit("d2", "amy", 12, 2), "accepted", "deposit amy")
    local empty = a:plan("r8", 3)
    accepted(empty, "planned", "a plan without shares still opens a round")
    expect(#empty.shares == 0 and empty.total == 0, "empty plan")
    rejected(a:plan("r9", 3), "round_open", "empty round is open")
    local closed_empty = a:close("r8", 4)
    accepted(closed_empty, "closed", "close empty round")
    expect(closed_empty.total == 0 and closed_empty.returned == 0, "empty close numbers")
    consumer(a, "k2", 1, 10, 0, 4.5)
    consumer(a, "k1", 1, 10, 4, 4.5)
    consumer(a, "h", 0, 6, 5, 4.5)
    local plan = a:plan("r9", 5)
    shares_equal(plan.shares, { { "h", 0, 1 }, { "k1", 1, 5 }, { "k2", 1, 5 } }, "plan r9")
    accepted(a:commit("r9", "k1", 2, 6), "committed", "commit k1")

    local snapshot = depot(a, 7, 6, "open round")
    expect(snapshot.clock == 6, "snapshot.clock is the latest accepted time")
    local ids = {}
    for index, row in ipairs(snapshot.consumers) do ids[index] = row.consumer_id end
    expect(table.concat(ids, ",") == "h,k1,k2", "consumers must be sorted by id")
    local k1 = consumer_row(snapshot, "k1")
    expect(k1.priority == 1 and k1.capacity == 10 and k1.level == 6 and k1.demand == 4 and k1.received == 2, "k1 row")
    expect(#snapshot.contributors == 2 and snapshot.contributors[1].player_id == "amy"
        and snapshot.contributors[1].units == 12 and snapshot.contributors[2].player_id == "bo",
        "contributors must be sorted by player id")
    -- Mutating a snapshot must not reach the allocator.
    snapshot.available = 999
    snapshot.consumers[1].level = 0
    snapshot.round.shares[1].units = 99
    snapshot.contributors[1].units = 0
    snapshot.round = nil
    local again = depot(a, 7, 6, "snapshot must be a fresh copy")
    expect(again.consumers[1].level == 5 and again.round.shares[1].units == 1
        and again.contributors[1].units == 12, "snapshot leaked internal tables")

    local data = a:save(7)
    expect(type(data) == "table", "save must return a table")
    local function plain(value, depth)
        expect(depth < 12, "saved data is too deep or cyclic")
        expect(getmetatable(value) == nil, "saved tables must not carry metatables")
        for key, item in pairs(value) do
            expect(type(key) == "string" or type(key) == "number", "saved keys must be strings or numbers")
            local kind = type(item)
            if kind == "table" then
                plain(item, depth + 1)
            elseif kind == "number" then
                expect(item == item and item ~= 1 / 0 and item ~= -1 / 0, "saved numbers must be finite")
            else
                expect(kind == "string" or kind == "boolean", "saved values must be plain data")
            end
        end
    end
    plain(data, 0)
    expect(type(Allocator.load) == "function", "module must export Allocator.load")
    local restored = Allocator.load(data, OPTIONS)
    expect(type(restored) == "table", "Allocator.load must return an allocator")
    -- load must not keep references into the data it was given.
    local function wipe(value)
        for key, item in pairs(value) do
            if type(item) == "table" then wipe(item) end
            value[key] = nil
        end
    end
    wipe(data)

    local loaded_snapshot = depot(restored, 7, 6, "restored depot")
    expect(loaded_snapshot.clock == 6 and loaded_snapshot.deposited_total == 15
        and loaded_snapshot.delivered_total == 2, "restored totals")
    expect(loaded_snapshot.round.round_id == "r9" and loaded_snapshot.round.shares[2].status == "committed"
        and loaded_snapshot.round.shares[3].status == "pending", "restored round")
    rejected(restored:deposit("d9", "amy", 1, 5), "time_regressed", "clock must survive load")
    accepted(restored:report("k2", 9, 4), "stale", "report times must survive load")
    local replay = restored:plan("r9", 8)
    accepted(replay, "planned", "plan retry after load")
    expect(replay.duplicate == true, "restored plan retry must be a duplicate")
    shares_equal(replay.shares, { { "h", 0, 1 }, { "k1", 1, 5 }, { "k2", 1, 5 } }, "restored plan")
    local settled = restored:commit("r9", "k1", 5, 9)
    accepted(settled, "committed", "settled share after load")
    expect(settled.duplicate == true and settled.delivered == 2, "settlement must survive load")
    accepted(restored:commit("r9", "h", 1, 10), "committed", "pending share after load")
    local old_request = restored:deposit("d2", "amy", 1, 11)
    accepted(old_request, "accepted", "deposit retry after load")
    expect(old_request.duplicate == true and old_request.accepted == 12, "request history must survive load")
    local closed = restored:close("r9", 12)
    accepted(closed, "closed", "close after load")
    expect(closed.total == 11 and closed.delivered == 3 and closed.returned == 8, "close after load numbers")
    rejected(restored:plan("r8", 13), "round_closed", "closed ids must survive load")
    rejected(restored:plan("r9", 13), "round_closed", "closed id after load")
    local final = depot(restored, 12, 0, "restored final")
    expect(final.contributors[1].units == 12 and final.contributors[2].units == 3, "contributions must survive load")
    depot(a, 7, 6, "the original allocator is independent of the restored one")
    local blank = Allocator.load(nil, OPTIONS)
    expect(type(blank) == "table", "load without data returns a new allocator")
    depot(blank, 0, 0, "load without data")
end)

return { cases = cases }
