local loaded, Arbiter = pcall(load_submission, "scripts/lootroll/arbiter.lua")
if not loaded or type(Arbiter) ~= "table" then Arbiter = {} end
local cases = {}
local function expect(v, m) if not v then error(m or "expectation failed", 0) end end
local function run(name, body) local ok,msg=pcall(body); cases[#cases+1]={name=name,passed=ok,message=ok and "ok" or tostring(msg)} end

local function options(extra)
    local o = { window = 10, allowed_items = { "gears", "goldnugget" } }
    if extra then for k, v in pairs(extra) do o[k] = v end end
    return o
end
local function fresh(extra)
    expect(type(Arbiter.new) == "function", "module must export Arbiter.new")
    return Arbiter.new(options(extra))
end
local function describe(result)
    if type(result) ~= "table" then return type(result) end
    if result.ok == true then return "ok = true" end
    return "code " .. tostring(result.code)
end
local function code_of(result, code, label)
    expect(type(result) == "table" and result.ok == false and result.code == code,
        (label or code) .. ": expected code " .. code .. ", got " .. describe(result))
end
local function ok_of(result, label)
    expect(type(result) == "table" and result.ok == true, (label or "call") .. " failed: got " .. describe(result))
    return result
end
-- Compares the published draw log: a flat list of tier, round, player_id, roll.
local function expect_rolls(result, flat, label)
    expect(type(result.rolls) == "table", label .. ": result.rolls missing")
    local count = math.floor(#flat / 4)
    expect(#result.rolls == count, label .. ": expected " .. count .. " draws, got " .. #result.rolls)
    for i = 1, #result.rolls do
        local entry, base = result.rolls[i], (i - 1) * 4
        expect(type(entry) == "table" and entry.tier == flat[base + 1] and entry.round == flat[base + 2]
            and entry.player_id == flat[base + 3] and entry.roll == flat[base + 4],
            label .. ": draw " .. i .. " differs from the published generator")
    end
end
local function expect_list(actual, expected, label)
    expect(type(actual) == "table" and #actual == #expected, label .. ": wrong length")
    for i = 1, #expected do expect(actual[i] == expected[i], label .. ": wrong element " .. i) end
end
local function choose_all(a, roll_id, picks, now)
    for _, pick in ipairs(picks) do ok_of(a:choose(roll_id, pick[1], pick[2], 1, now), "choose " .. pick[1]) end
end
local function all_need(a, roll_id, now)
    choose_all(a, roll_id, { { "p1", "need" }, { "p2", "need" }, { "p3", "need" } }, now)
end
local function same_result(x, y, label)
    expect(x.ok == y.ok and x.status == y.status and x.winner == y.winner and x.tier == y.tier
        and x.roll_id == y.roll_id and x.item == y.item, label .. ": result changed")
    expect(#x.rolls == #y.rolls, label .. ": draw log changed")
    for i = 1, #x.rolls do
        expect(x.rolls[i].roll == y.rolls[i].roll and x.rolls[i].player_id == y.rolls[i].player_id
            and x.rolls[i].round == y.rolls[i].round and x.rolls[i].tier == y.rolls[i].tier, label .. ": draw changed")
    end
end
-- Copies a saved table the way the game serializer would: only plain data survives.
local function plain_copy(value, depth)
    depth = depth or 0
    expect(depth < 32, "saved data is too deep or cyclic")
    local kind = type(value)
    if kind == "table" then
        expect(getmetatable(value) == nil, "saved data must not carry metatables")
        local out = {}
        for k, v in pairs(value) do
            expect(type(k) == "string" or type(k) == "number", "saved keys must be strings or numbers")
            out[k] = plain_copy(v, depth + 1)
        end
        return out
    end
    expect(kind == "string" or kind == "number" or kind == "boolean", "saved data contains a " .. kind)
    return value
end
local function mentions(value, words, depth)
    depth = depth or 0
    if depth > 16 then return false end
    if type(value) == "string" then return words[value] == true end
    if type(value) ~= "table" then return false end
    for k, v in pairs(value) do
        if mentions(k, words, depth + 1) or mentions(v, words, depth + 1) then return true end
    end
    return false
end

run("open freezes a deduplicated eligible set", function()
    local a = fresh()
    code_of(a:open("r1", "log", { "p1" }, 1, 100), "item_not_allowed")
    code_of(a:open("r1", "gears", {}, 1, 100), "invalid_eligible", "empty eligible set")
    code_of(a:open("r1", "gears", { "p1", "" }, 1, 100), "invalid_eligible", "empty player id")
    code_of(a:open("r1", "gears", { "p1", 7 }, 1, 100), "invalid_eligible", "non-string player id")
    code_of(a:open("r1", "gears", { "p1" }, 1.5, 100), "invalid_seed", "fractional seed")
    code_of(a:open("r1", "gears", { "p1" }, -1, 100), "invalid_seed", "negative seed")
    code_of(a:open("r1", "gears", { "p1" }, 4294967296, 100), "invalid_seed", "seed above 4294967295")
    code_of(a:open("r1", "gears", { "p1" }, 1, math.huge), "invalid_time", "infinite now")
    code_of(a:open("r1", "gears", { "p1" }, 1, 0 / 0), "invalid_time", "NaN now")
    code_of(a:open("", "gears", { "p1" }, 1, 100), "invalid_roll_id")
    -- None of the rejected calls may have consumed the identifier.
    local source = { "p3", "p1", "p3", "p2", "p1" }
    local opened = ok_of(a:open("r1", "gears", source, 1, 100), "open r1")
    expect(opened.roll_id == "r1" and opened.item == "gears", "open must echo roll_id and item")
    expect(opened.deadline == 110, "deadline must be now + window")
    expect(opened.total == 3, "duplicates must be removed from the eligible set")
    expect_list(opened.eligible, { "p1", "p2", "p3" }, "eligible")
    code_of(a:open("r1", "gears", { "p9" }, 2, 101), "duplicate_roll")
    code_of(a:open("r1", "log", {}, -1, 101), "duplicate_roll", "published validation order of open")
    -- Later mutation of the caller's array or of the returned list changes nothing.
    source[#source + 1] = "p4"; opened.eligible[1] = "p4"
    code_of(a:choose("r1", "p4", "need", 1, 101), "not_eligible")
    code_of(a:choose("r1", "p9", "need", 1, 101), "not_eligible")
    code_of(a:choose("nope", "p1", "need", 1, 101), "unknown_roll")
    local picked = ok_of(a:choose("r1", "p1", "need", 1, 101), "eligible choose")
    expect(picked.chosen == 1 and picked.total == 3 and picked.complete == false, "choose must report chosen/total/complete")
end)

run("choices obey revisions and the deadline boundary", function()
    local a = fresh()
    ok_of(a:open("r1", "gears", { "p1", "p2", "p3" }, 0, 100), "open")
    code_of(a:choose("r1", "p1", "banana", 9, 101), "invalid_choice")
    code_of(a:choose("nope", "zz", "banana", -1, 101), "unknown_roll", "published validation order of choose")
    code_of(a:choose("r1", "zz", "banana", -1, 101), "not_eligible", "published validation order of choose")
    code_of(a:choose("r1", "p1", "banana", -1, 101), "invalid_choice", "published validation order of choose")
    code_of(a:choose("r1", "p1", "need", -1, 101), "invalid_revision", "negative revision")
    code_of(a:choose("r1", "p1", "need", 1.5, 101), "invalid_revision", "fractional revision")
    code_of(a:choose("r1", "p1", "need", 1, 0 / 0), "invalid_time")
    -- The rejected revision 9 must not have been recorded.
    ok_of(a:choose("r1", "p1", "greed", 0, 101), "revision 0 is a valid first revision")
    ok_of(a:choose("r1", "p1", "need", 4, 102), "higher revision")
    code_of(a:choose("r1", "p1", "pass", 4, 103), "stale_revision", "duplicate revision")
    code_of(a:choose("r1", "p1", "pass", 2, 103), "stale_revision", "older revision")
    local second = ok_of(a:choose("r1", "p2", "greed", 1, 109.5), "choice just before the deadline")
    expect(second.chosen == 2 and second.complete == false, "a changed choice must not be counted twice")
    code_of(a:resolve("r1", 109.5), "not_ready")
    code_of(a:resolve("r1", 0 / 0), "invalid_time")
    code_of(a:choose("r1", "p3", "need", 1, 110), "roll_closed", "choice at the deadline")
    local result = ok_of(a:resolve("r1", 110), "resolve at the deadline")
    -- p1 kept "need" (revision 4), p2 chose greed, p3 never chose and counts as pass.
    expect(result.status == "awarded" and result.winner == "p1" and result.tier == "need", "latest accepted choices must decide")
    expect_rolls(result, { "need", 1, "p1", 72 }, "r1")
    expect(#result.choices == 3 and result.choices[1].player_id == "p1" and result.choices[1].choice == "need"
        and result.choices[2].player_id == "p2" and result.choices[2].choice == "greed"
        and result.choices[3].player_id == "p3" and result.choices[3].choice == "pass", "result.choices must list final choices by player id")
    code_of(a:choose("r1", "p3", "need", 1, 111), "roll_closed", "choice after resolution")

    -- A complete roll may be resolved before its deadline; tick resolves what is due, in id order.
    local b = fresh()
    ok_of(b:open("t2", "gears", { "p1" }, 7, 100)); ok_of(b:open("t1", "gears", { "p1", "p2" }, 7, 100))
    ok_of(b:open("t3", "gears", { "p1", "p2" }, 7, 105))
    ok_of(b:choose("t3", "p1", "greed", 1, 106))
    code_of(b:tick(0 / 0), "invalid_time", "tick with NaN")
    local early = ok_of(b:tick(107), "tick before any deadline")
    expect(type(early.resolved) == "table" and #early.resolved == 0, "tick must not resolve an incomplete roll early")
    local last = ok_of(b:choose("t3", "p2", "pass", 1, 107))
    expect(last.complete == true, "complete must be true once everyone has chosen")
    local due = ok_of(b:tick(110), "tick at the deadline")
    expect(#due.resolved == 3 and due.resolved[1].roll_id == "t1" and due.resolved[2].roll_id == "t2"
        and due.resolved[3].roll_id == "t3", "tick must resolve due and complete rolls in ascending roll id order")
    expect(due.resolved[1].status == "unclaimed" and due.resolved[1].winner == nil and #due.resolved[1].rolls == 0,
        "a roll nobody answered is unclaimed without draws")
    expect(due.resolved[3].status == "awarded" and due.resolved[3].winner == "p1" and due.resolved[3].tier == "greed", "t3 winner")
    expect(#ok_of(b:tick(111)).resolved == 0, "tick must not resolve twice")
end)

run("published generator decides tiers and tie re-rolls", function()
    local a = fresh()
    ok_of(a:open("g1", "gears", { "p3", "p2", "p1" }, 0, 100))
    choose_all(a, "g1", { { "p3", "need" }, { "p2", "greed" }, { "p1", "need" } }, 100)
    local g1 = ok_of(a:resolve("g1", 100), "resolve complete roll")
    expect(g1.status == "awarded" and g1.winner == "p3" and g1.tier == "need", "need must beat greed; winner p3")
    expect_rolls(g1, { "need", 1, "p1", 72, "need", 1, "p3", 95 }, "g1")

    -- Seed normalisation: seed % 2147483646 + 1.
    ok_of(a:open("g2", "gears", { "p1", "p3" }, 2147483646, 100)); choose_all(a, "g2", { { "p1", "greed" }, { "p3", "greed" } }, 100)
    local g2 = ok_of(a:resolve("g2", 100))
    expect(g2.winner == "p3" and g2.tier == "greed", "g2 winner"); expect_rolls(g2, { "greed", 1, "p1", 72, "greed", 1, "p3", 95 }, "g2")
    ok_of(a:open("g3", "gears", { "p1", "p3" }, 4294967295, 100)); choose_all(a, "g3", { { "p1", "need" }, { "p3", "need" } }, 100)
    local g3 = ok_of(a:resolve("g3", 100))
    expect(g3.winner == "p1", "g3 winner"); expect_rolls(g3, { "need", 1, "p1", 85, "need", 1, "p3", 77 }, "g3")

    -- Only the tied leaders roll again, with the continuing generator state.
    ok_of(a:open("g4", "gears", { "p1", "p2", "p3" }, 61, 100)); all_need(a, "g4", 100)
    local g4 = ok_of(a:resolve("g4", 100))
    expect(g4.winner == "p3", "the re-roll decides between the tied leaders: p3 (23) beats p2 (10)")
    expect_rolls(g4, { "need", 1, "p1", 3, "need", 1, "p2", 94, "need", 1, "p3", 94, "need", 2, "p2", 10, "need", 2, "p3", 23 }, "g4")

    -- Still tied after max_rounds (default 3): the smallest tied id wins, no fourth round.
    ok_of(a:open("g5", "gears", { "p1", "p2", "p3" }, 139629, 100)); all_need(a, "g5", 100)
    local g5 = ok_of(a:resolve("g5", 100))
    expect(g5.winner == "p1", "g5 fallback winner")
    expect_rolls(g5, { "need", 1, "p1", 90, "need", 1, "p2", 90, "need", 1, "p3", 79, "need", 2, "p1", 46, "need", 2, "p2", 46,
        "need", 3, "p1", 49, "need", 3, "p2", 49 }, "g5")

    local single = fresh({ max_rounds = 1 })
    ok_of(single:open("g6", "gears", { "p1", "p2", "p3" }, 61, 100)); all_need(single, "g6", 100)
    local g6 = ok_of(single:resolve("g6", 100))
    expect(g6.winner == "p2", "with max_rounds = 1 the smallest id among the tied leaders wins")
    expect_rolls(g6, { "need", 1, "p1", 3, "need", 1, "p2", 94, "need", 1, "p3", 94 }, "g6")

    ok_of(a:open("g7", "gears", { "p1", "p2" }, 5, 100)); choose_all(a, "g7", { { "p1", "pass" }, { "p2", "pass" } }, 100)
    local g7 = ok_of(a:resolve("g7", 100))
    expect(g7.status == "unclaimed" and g7.winner == nil and g7.tier == nil and #g7.rolls == 0, "all pass is unclaimed without draws")
end)

run("resolution is idempotent and failed delivery re-awards once", function()
    local a = fresh()
    ok_of(a:open("d1", "gears", { "p1", "p2", "p3" }, 17, 100)); all_need(a, "d1", 101)
    local first = ok_of(a:resolve("d1", 101))
    local expected = { "need", 1, "p1", 79, "need", 1, "p2", 46, "need", 1, "p3", 79, "need", 2, "p1", 15, "need", 2, "p3", 40 }
    expect(first.status == "awarded" and first.winner == "p3" and first.tier == "need", "d1 winner"); expect_rolls(first, expected, "d1")
    -- Results are fresh copies and a later resolve never draws again.
    first.rolls[1].roll = 1; first.rolls[#first.rolls + 1] = { tier = "need", round = 9, player_id = "p3", roll = 100 }; first.winner = "p2"
    local again = ok_of(a:resolve("d1", 150), "second resolve")
    expect(again.status == "awarded" and again.winner == "p3", "second resolve must return the same winner"); expect_rolls(again, expected, "d1 again")
    code_of(a:cancel("d1", 151), "roll_closed", "cancel after resolution")
    code_of(a:open("d1", "gears", { "p1" }, 1, 152), "duplicate_roll", "resolved id reuse")

    -- Ranking compares round 1 first: p1 (79, 15) is ahead of p2 (46).
    code_of(a:mark_delivered("d1", true, 0 / 0), "invalid_time", "mark_delivered with NaN")
    local step = ok_of(a:mark_delivered("d1", false, 153), "first failure")
    expect(step.status == "awarded" and step.winner == "p1" and step.tier == "need", "next-best must be p1")
    expect_list(step.failed, { "p3" }, "failed"); expect_rolls(step, expected, "no new draws inside a ranked tier")
    same_result(ok_of(a:resolve("d1", 154)), step, "resolve after re-award")
    step = ok_of(a:mark_delivered("d1", false, 155), "second failure")
    expect(step.winner == "p2" and step.status == "awarded", "third candidate must be p2")
    step = ok_of(a:mark_delivered("d1", false, 156), "third failure")
    expect(step.status == "unclaimed" and step.winner == nil and step.tier == nil, "nobody left means unclaimed")
    expect_list(step.failed, { "p3", "p1", "p2" }, "failed order")
    code_of(a:mark_delivered("d1", true, 157), "not_awarded", "delivery after unclaimed")
    expect(ok_of(a:resolve("d1", 158)).status == "unclaimed", "unclaimed is final")

    -- When the need tier is exhausted the greed tier rolls with the continuing state.
    ok_of(a:open("d2", "gears", { "p1", "p2", "p3" }, 2024, 200))
    choose_all(a, "d2", { { "p1", "need" }, { "p2", "greed" }, { "p3", "greed" } }, 201)
    local d2 = ok_of(a:resolve("d2", 201)); expect(d2.winner == "p1" and d2.tier == "need", "d2 winner")
    expect_rolls(d2, { "need", 1, "p1", 76 }, "a single candidate still draws once")
    code_of(a:mark_delivered("missing", true, 202), "unknown_roll")
    d2 = ok_of(a:mark_delivered("d2", false, 202))
    expect(d2.status == "awarded" and d2.winner == "p2" and d2.tier == "greed", "greed tier takes over")
    expect_rolls(d2, { "need", 1, "p1", 76, "greed", 1, "p2", 67, "greed", 1, "p3", 52 }, "d2 greed contest")
    d2 = ok_of(a:mark_delivered("d2", true, 203)); expect(d2.status == "delivered" and d2.winner == "p2", "delivered")
    code_of(a:mark_delivered("d2", false, 204), "not_awarded", "failure report after delivery")
    local final = ok_of(a:resolve("d2", 900)); expect(final.status == "delivered" and final.winner == "p2", "delivered is final")
    expect_list(final.failed, { "p1" }, "d2 failed")

    -- Cancel is final, draws nothing and the identifier stays burned.
    ok_of(a:open("d3", "gears", { "p1", "p2" }, 3, 1000)); ok_of(a:open("d4", "gears", { "p1" }, 3, 1000))
    ok_of(a:choose("d3", "p1", "need", 1, 1001)); code_of(a:cancel("d3", math.huge), "invalid_time", "cancel with infinity")
    local canceled = ok_of(a:cancel("d3", 1002), "cancel")
    expect(canceled.status == "canceled" and canceled.winner == nil and #canceled.rolls == 0 and #canceled.choices == 0, "canceled result")
    code_of(a:cancel("d3", 1003), "roll_closed", "second cancel"); code_of(a:choose("d3", "p2", "need", 1, 1003), "roll_closed")
    expect(ok_of(a:resolve("d3", 1100)).status == "canceled", "resolve after cancel reports canceled")
    code_of(a:mark_delivered("d3", true, 1100), "not_awarded"); code_of(a:open("d3", "gears", { "p1" }, 3, 1200), "duplicate_roll")
    -- Passing the deadline changes nothing by itself: d4 (deadline 1010) is still open and can be canceled.
    expect(ok_of(a:cancel("d4", 1300), "cancel of an overdue but unsettled roll").status == "canceled", "d4 canceled")
end)

run("fairness ledger demotes need at the published boundary", function()
    local function with_one_win(extra)
        local a = fresh(extra)
        ok_of(a:open("w1", "gears", { "p1", "p2" }, 0, 0)); choose_all(a, "w1", { { "p1", "need" }, { "p2", "pass" } }, 1)
        local won = ok_of(a:resolve("w1", 2)); expect(won.winner == "p1" and #won.demoted == 0, "w1 winner")
        expect(#ok_of(a:snapshot(4)).wins == 0, "an award is not a win until it is delivered")
        ok_of(a:mark_delivered("w1", true, 5))
        return a
    end
    local a = with_one_win({ max_wins_per_window = 1, fairness_window = 100 })
    -- Demotion is evaluated at min(now, deadline), however late the roll is resolved.
    ok_of(a:open("w2", "gears", { "p1", "p2", "p3" }, 0, 94)); choose_all(a, "w2", { { "p1", "need" }, { "p2", "greed" } }, 95)
    ok_of(a:open("w3", "gears", { "p1", "p2", "p3" }, 0, 95)); choose_all(a, "w3", { { "p1", "need" }, { "p2", "greed" } }, 96)
    local wins = ok_of(a:snapshot(104)).wins
    expect(#wins == 1 and wins[1].player_id == "p1" and wins[1].count == 1, "a win 99 seconds old still counts")
    expect(#ok_of(a:snapshot(105)).wins == 0, "a win exactly fairness_window seconds old no longer counts")
    ok_of(a:snapshot(200))
    local due = ok_of(a:tick(200)).resolved
    expect(#due == 2 and due[1].roll_id == "w2" and due[2].roll_id == "w3", "tick resolves both overdue rolls")
    local w2 = ok_of(a:resolve("w2", 200))
    same_result(due[1], w2, "tick and resolve report the same result")
    expect(w2.winner == "p2" and w2.tier == "greed", "at deadline 104 the win is 99 seconds old: p1 is demoted")
    expect_list(w2.demoted, { "p1" }, "w2 demoted"); expect_rolls(w2, { "greed", 1, "p1", 72, "greed", 1, "p2", 95 }, "w2")
    expect(w2.choices[1].choice == "need", "choices keep the original choice of a demoted player")
    local w3 = ok_of(a:resolve("w3", 200))
    expect(w3.winner == "p1" and w3.tier == "need" and #w3.demoted == 0, "at deadline 105 the win is 100 seconds old: no demotion")
    expect_rolls(w3, { "need", 1, "p1", 72 }, "w3")

    -- A complete roll resolved early is evaluated at now.
    local b = with_one_win({ max_wins_per_window = 1, fairness_window = 100 })
    ok_of(b:open("w4", "gears", { "p1", "p2" }, 0, 50)); choose_all(b, "w4", { { "p1", "need" }, { "p2", "greed" } }, 51)
    local w4 = ok_of(b:resolve("w4", 55)); expect(w4.winner == "p2", "w4 demotion"); expect_list(w4.demoted, { "p1" }, "w4 demoted")

    -- Default max_wins_per_window is 2: the first win does not demote, the second does.
    local c = with_one_win({ fairness_window = 100 })
    ok_of(c:open("w5", "gears", { "p1", "p2" }, 0, 50)); choose_all(c, "w5", { { "p1", "need" }, { "p2", "greed" } }, 51)
    local w5 = ok_of(c:resolve("w5", 52)); expect(w5.winner == "p1" and #w5.demoted == 0, "one win is below the default limit")
    ok_of(c:mark_delivered("w5", true, 56))
    ok_of(c:open("w6", "gears", { "p1", "p2" }, 0, 60)); choose_all(c, "w6", { { "p1", "need" }, { "p2", "greed" } }, 61)
    local w6 = ok_of(c:resolve("w6", 62)); expect(w6.winner == "p2" and w6.tier == "greed", "two wins demote"); expect_list(w6.demoted, { "p1" }, "w6 demoted")
    local counted = ok_of(c:snapshot(62)).wins
    expect(#counted == 1 and counted[1].player_id == "p1" and counted[1].count == 2, "snapshot counts trailing wins per player")
    -- A failed delivery is never a win.
    ok_of(c:mark_delivered("w6", false, 63))
    expect(#ok_of(c:snapshot(63)).wins == 1, "failed delivery must not enter the ledger")
    -- wins is ordered by player id, not by who won first.
    ok_of(c:open("w7", "gears", { "p1", "p0" }, 0, 70)); choose_all(c, "w7", { { "p0", "need" }, { "p1", "pass" } }, 71)
    expect(ok_of(c:resolve("w7", 72)).winner == "p0", "w7 winner"); ok_of(c:mark_delivered("w7", true, 73))
    local ordered = ok_of(c:snapshot(73)).wins
    expect(#ordered == 2 and ordered[1].player_id == "p0" and ordered[1].count == 1 and ordered[2].player_id == "p1"
        and ordered[2].count == 2, "wins must be ordered by player id")
end)

run("snapshot hides choices and save load preserves state", function()
    local opts = { fairness_window = 100 }
    local a = fresh(opts)
    ok_of(a:open("s0", "goldnugget", { "p1" }, 7, 90)); ok_of(a:choose("s0", "p1", "greed", 1, 91))
    ok_of(a:resolve("s0", 92)); ok_of(a:mark_delivered("s0", true, 95))
    ok_of(a:open("s3", "gears", { "p1", "p2", "p3" }, 2024, 100)); ok_of(a:open("s2", "gears", { "p1", "p2", "p3" }, 17, 100))
    ok_of(a:open("s1", "gears", { "p1", "p2", "p3" }, 2024, 100))
    choose_all(a, "s3", { { "p1", "need" }, { "p2", "greed" }, { "p3", "greed" } }, 101); all_need(a, "s2", 101)
    ok_of(a:choose("s1", "p1", "need", 3, 101)); ok_of(a:choose("s1", "p2", "greed", 1, 101))
    ok_of(a:resolve("s3", 102)); ok_of(a:resolve("s2", 102))

    code_of(a:snapshot(0 / 0), "invalid_time", "snapshot with NaN"); code_of(a:save(-math.huge), "invalid_time", "save with -infinity")
    local snap = ok_of(a:snapshot(104), "snapshot")
    expect(type(snap.rolls) == "table" and #snap.rolls == 4, "snapshot lists every roll")
    for i, id in ipairs({ "s0", "s1", "s2", "s3" }) do expect(snap.rolls[i].roll_id == id, "snapshot rolls must be ordered by roll id") end
    local open_entry = snap.rolls[2]
    expect(open_entry.status == "open" and open_entry.item == "gears" and open_entry.deadline == 110 and open_entry.remaining == 6
        and open_entry.total == 3 and open_entry.chosen == 2 and open_entry.winner == nil, "open snapshot entry")
    expect(not mentions(open_entry, { need = true, greed = true, pass = true, p1 = true, p2 = true, p3 = true }),
        "an open roll must not reveal choices or who chose")
    expect(snap.rolls[1].status == "delivered" and snap.rolls[1].winner == "p1" and snap.rolls[1].tier == "greed"
        and snap.rolls[1].remaining == 0, "delivered snapshot entry")
    expect(snap.rolls[3].status == "awarded" and snap.rolls[3].winner == "p3" and snap.rolls[3].tier == "need", "awarded snapshot entry")
    snap.rolls[2].chosen = 99; snap.rolls[2].status = "canceled"; snap.wins[1].count = 99
    local again = ok_of(a:snapshot(104))
    expect(again.rolls[2].chosen == 2 and again.rolls[2].status == "open" and again.wins[1].count == 1, "snapshots must be fresh tables")

    expect(type(Arbiter.load) == "function", "module must export Arbiter.load")
    local saved = plain_copy(a:save(105))
    local keep = plain_copy(saved)
    opts.now = 1000
    local b = Arbiter.load(saved, options(opts))
    -- Every stored time moved by 1000 - 105 = 895: the s1 deadline is now 1005, the s0 win is at 990.
    local entry = ok_of(b:snapshot(1001)).rolls[2]
    expect(entry.roll_id == "s1" and entry.deadline == 1005 and entry.remaining == 4 and entry.chosen == 2, "rebased snapshot")
    code_of(b:choose("s1", "p1", "pass", 3, 1001), "stale_revision", "revisions survive load")
    -- Ranking, delivery phase and generator state continue after load.
    local s2 = ok_of(b:resolve("s2", 1002)); expect(s2.status == "awarded" and s2.winner == "p3" and #s2.rolls == 5, "awarded roll survives load")
    s2 = ok_of(b:mark_delivered("s2", false, 1002)); expect(s2.winner == "p1", "ranking survives load"); expect_list(s2.failed, { "p3" }, "s2 failed")
    local s3 = ok_of(b:mark_delivered("s3", false, 1002))
    expect(s3.winner == "p2" and s3.tier == "greed", "s3 greed winner")
    expect_rolls(s3, { "need", 1, "p1", 76, "greed", 1, "p2", 67, "greed", 1, "p3", 52 }, "generator state survives load")
    local s0 = ok_of(b:resolve("s0", 1003)); expect(s0.status == "delivered" and s0.winner == "p1", "delivered result survives load")
    expect_rolls(s0, { "greed", 1, "p1", 69 }, "s0"); code_of(b:mark_delivered("s0", true, 1003), "not_awarded")
    code_of(b:open("s0", "gears", { "p1" }, 1, 1003), "duplicate_roll", "closed ids stay burned after load")
    code_of(b:resolve("s1", 1004.5), "not_ready", "rebased deadline")
    code_of(b:choose("s1", "p3", "need", 1, 1005), "roll_closed", "rebased deadline boundary")
    local s1 = ok_of(b:resolve("s1", 1005)); expect(s1.winner == "p1" and s1.tier == "need", "s1 winner"); expect_rolls(s1, { "need", 1, "p1", 76 }, "s1")
    expect(#ok_of(b:snapshot(1089)).wins == 1 and #ok_of(b:snapshot(1090)).wins == 0, "ledger times are rebased too")

    -- Without options.now every stored time is kept verbatim.
    opts.now = nil
    local c = Arbiter.load(keep, options(opts))
    ok_of(c:choose("s1", "p3", "greed", 1, 109.5), "verbatim deadline"); code_of(c:choose("s1", "p3", "need", 2, 110), "roll_closed")
    expect(#ok_of(c:snapshot(194)).wins == 1 and #ok_of(c:snapshot(195)).wins == 0, "verbatim ledger times")
    local empty = Arbiter.load(nil, options(opts))
    ok_of(empty:open("s1", "gears", { "p1" }, 1, 0), "load without data starts empty")
end)

return {cases=cases}
