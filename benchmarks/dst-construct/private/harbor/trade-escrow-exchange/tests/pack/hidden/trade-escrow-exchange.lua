local loaded, Escrow = pcall(load_submission, "scripts/tradeescrow/escrow.lua")
if not loaded or type(Escrow) ~= "table" then Escrow = {} end

local cases = {}
local function expect(value, message) if not value then error(message or "expectation failed", 0) end end
local function run(name, body)
    local ok, message = pcall(body)
    cases[#cases + 1] = { name = name, passed = ok, message = ok and "ok" or tostring(message) }
end

local options = {
    allowed_prefabs = { twigs = true, cutgrass = true, flint = true, log = true },
    max_distinct = 2,
    ttl = 30,
}

local function fresh()
    expect(type(Escrow.new) == "function", "module must export Escrow.new")
    local escrow = Escrow.new(options)
    expect(type(escrow) == "table", "Escrow.new must return a table")
    return escrow
end

-- Asserts the published result contract: a table with boolean ok and string code.
local function check(result, ok, code, label)
    label = label or code
    expect(type(result) == "table", label .. ": result must be a table")
    expect(result.ok == ok, label .. ": expected ok=" .. tostring(ok) .. " got " .. tostring(result.ok)
        .. " (code " .. tostring(result.code) .. ")")
    expect(result.code == code, label .. ": expected code " .. code .. " got " .. tostring(result.code))
    return result
end

local function trade_view(escrow, trade_id, now)
    local snapshot = escrow:snapshot(now)
    expect(type(snapshot) == "table" and type(snapshot.trades) == "table", "snapshot must return { trades = ... }")
    for _, view in ipairs(snapshot.trades) do
        if view.trade_id == trade_id then return view end
    end
    error("snapshot is missing trade " .. trade_id, 0)
end

local function party_view(view, party_id)
    expect(type(view.parties) == "table", "trade view must list parties")
    for _, party in ipairs(view.parties) do
        if party.id == party_id then return party end
    end
    error("trade view is missing party " .. party_id, 0)
end

local function confirmed(escrow, trade_id, party_id, now)
    return party_view(trade_view(escrow, trade_id, now), party_id).confirmed
end

local function deep_equal(left, right)
    if type(left) ~= type(right) then return false end
    if type(left) ~= "table" then return left == right end
    for key, value in pairs(left) do
        if not deep_equal(value, right[key]) then return false end
    end
    for key in pairs(right) do
        if left[key] == nil then return false end
    end
    return true
end

local function is_plain(value, depth)
    if depth > 24 then return false end
    local kind = type(value)
    if kind == "string" or kind == "number" or kind == "boolean" then return true end
    if kind ~= "table" or getmetatable(value) ~= nil then return false end
    for key, field in pairs(value) do
        if type(key) ~= "string" and type(key) ~= "number" then return false end
        if not is_plain(field, depth + 1) then return false end
    end
    return true
end

local function scribble(value, depth)
    if type(value) ~= "table" or depth > 24 then return end
    local keys = {}
    for key, field in pairs(value) do
        scribble(field, depth + 1)
        keys[#keys + 1] = key
    end
    for _, key in ipairs(keys) do value[key] = nil end
end

run("rejected offers leave revision and confirmations untouched", function()
    local escrow = fresh()
    check(escrow:open("t1", "alice", "bob", 10), true, "opened")
    local first = check(escrow:offer("t1", "alice", { twigs = 3 }, 1, 11), true, "offered")
    expect(first.revision == 1 and first.phase == "open", "accepted offer must report revision and phase")
    check(escrow:confirm("t1", "bob", 1, 12), true, "confirmed")

    check(escrow:offer("t1", "alice", { goldnugget = 1 }, 2, 13), false, "prefab_not_allowed")
    check(escrow:offer("t1", "alice", { [""] = 1 }, 2, 13), false, "prefab_not_allowed", "empty prefab key")
    check(escrow:offer("t1", "alice", { [7] = 1 }, 2, 13), false, "prefab_not_allowed", "numeric prefab key")
    check(escrow:offer("t1", "alice", { twigs = 0 }, 2, 13), false, "invalid_count", "zero count")
    check(escrow:offer("t1", "alice", { twigs = 1.5 }, 2, 13), false, "invalid_count", "fractional count")
    check(escrow:offer("t1", "alice", { twigs = -2 }, 2, 13), false, "invalid_count", "negative count")
    check(escrow:offer("t1", "alice", { twigs = "3" }, 2, 13), false, "invalid_count", "string count")
    local wide = check(escrow:offer("t1", "alice", { twigs = 1, cutgrass = 1, flint = 1 }, 2, 13), false, "too_many_prefabs")
    expect(wide.phase == "open", "a rejection on an existing trade must carry phase")
    check(escrow:offer("t1", "alice", { twigs = 1 }, 0, 13), false, "invalid_argument", "revision 0")
    check(escrow:offer("t1", "alice", { twigs = 1 }, 1.5, 13), false, "invalid_argument", "fractional revision")
    check(escrow:offer("t1", "alice", "twigs", 2, 13), false, "invalid_argument", "items not a table")
    check(escrow:offer("t1", "", { twigs = 1 }, 2, 13), false, "invalid_argument", "empty party id")
    check(escrow:offer("t1", "alice", { twigs = 1 }, 2, "13"), false, "invalid_argument", "now not a number")
    check(escrow:offer("nope", "alice", { twigs = 1 }, 2, 13), false, "unknown_trade")
    local stranger = check(escrow:offer("t1", "mallory", { twigs = 1 }, 2, 13), false, "not_a_party")
    expect(stranger.phase == "open", "not_a_party must carry phase")

    local view = trade_view(escrow, "t1", 13)
    local alice = party_view(view, "alice")
    expect(alice.revision == 1, "a rejected offer consumed a revision")
    expect(#alice.items == 1 and alice.items[1].prefab == "twigs" and alice.items[1].count == 3,
        "a rejected offer changed the stored items")
    expect(party_view(view, "bob").confirmed == true, "a rejected offer voided a confirmation")

    local mine = { twigs = 2, cutgrass = 1 }
    check(escrow:offer("t1", "alice", mine, 2, 14), true, "offered", "offer at the distinct cap")
    mine.twigs = 99
    mine.flint = 5
    alice = party_view(trade_view(escrow, "t1", 14), "alice")
    expect(#alice.items == 2 and alice.items[2].prefab == "twigs" and alice.items[2].count == 2,
        "the escrow must keep its own copy of the offered items")
    check(escrow:offer("t1", "bob", {}, 1, 15), true, "offered", "empty offer")
end)

run("any accepted offer change voids both confirmations", function()
    local escrow = fresh()
    check(escrow:open("t1", "alice", "bob", 0), true, "opened")
    check(escrow:offer("t1", "alice", { twigs = 3 }, 1, 1), true, "offered")
    check(escrow:offer("t1", "bob", { flint = 1 }, 1, 1), true, "offered")
    expect(check(escrow:confirm("t1", "alice", 1, 2), true, "confirmed").ready == false, "one confirmation is not ready")
    expect(check(escrow:confirm("t1", "bob", 1, 2), true, "confirmed").ready == true, "two confirmations must be ready")

    -- Same content under a new revision is still an accepted change.
    check(escrow:offer("t1", "bob", { flint = 1 }, 2, 3), true, "offered")
    expect(confirmed(escrow, "t1", "alice", 3) == false, "counterparty confirmation survived an offer change")
    expect(confirmed(escrow, "t1", "bob", 3) == false, "own confirmation survived an offer change")
    expect(check(escrow:begin_settle("t1", 3), false, "not_ready").phase == "open", "not_ready must stay open")

    check(escrow:confirm("t1", "alice", 1, 4), false, "stale_confirmation")
    expect(confirmed(escrow, "t1", "alice", 4) == false, "a stale confirmation was recorded")
    expect(check(escrow:confirm("t1", "bob", 1, 4), true, "confirmed").ready == false, "only bob has confirmed")
    expect(check(escrow:confirm("t1", "alice", 2, 4), true, "confirmed").ready == true, "both confirmed current revisions")

    check(escrow:offer("t1", "alice", { twigs = 1 }, 2, 5), true, "offered")
    expect(confirmed(escrow, "t1", "alice", 5) == false and confirmed(escrow, "t1", "bob", 5) == false,
        "alice's change must void both confirmations")
    expect(check(escrow:confirm("t1", "bob", 2, 6), true, "confirmed").ready == false, "bob alone is not ready")
    check(escrow:confirm("t1", "alice", 3, 6), false, "stale_confirmation", "future revision")
    expect(confirmed(escrow, "t1", "bob", 6) == true, "a failed confirmation must not change confirmations")
    expect(check(escrow:confirm("t1", "alice", 2, 6), true, "confirmed").ready == true, "ready after both re-confirm")

    check(escrow:open("t2", "carol", "dave", 6), true, "opened")
    check(escrow:confirm("t2", "carol", 1, 7), false, "stale_confirmation", "counterparty never offered")
    expect(check(escrow:confirm("t2", "carol", 0, 7), true, "confirmed").ready == false, "revision 0 is confirmable")
    expect(check(escrow:confirm("t2", "dave", 0, 7), true, "confirmed").ready == true, "empty offers can be ready")
    check(escrow:confirm("t2", "dave", -1, 7), false, "invalid_argument", "negative seen_revision")
end)

run("replays are idempotent and revisions strictly increase", function()
    local escrow = fresh()
    local opened = check(escrow:open("t1", "alice", "bob", 5), true, "opened")
    expect(opened.trade_id == "t1" and opened.expires_at == 35 and opened.phase == "open", "open must report trade_id, expires_at and phase")
    opened.expires_at, opened.phase, opened.ok = -1, "settled", false
    expect(check(escrow:open("t1", "alice", "bob", 9), true, "opened", "repeated open").expires_at == 35,
        "a repeated open refreshed the deadline")
    expect(check(escrow:open("t1", "bob", "alice", 9), true, "opened", "repeated open, swapped order").expires_at == 35,
        "a repeated open refreshed the deadline")
    expect(check(escrow:open("t1", "alice", "carol", 9), false, "trade_exists").phase == "open", "trade_exists must carry phase")
    check(escrow:open("t2", "alice", "carol", 9), false, "party_busy")
    check(escrow:offer("t2", "carol", {}, 1, 9), false, "unknown_trade", "party_busy must not create the trade")
    check(escrow:open("t9", "alice", "alice", 9), false, "invalid_argument", "identical parties")
    check(escrow:open("", "erin", "frank", 9), false, "invalid_argument", "empty trade id")

    expect(check(escrow:offer("t1", "alice", { twigs = 2 }, 3, 10), true, "offered").revision == 3, "revisions may skip")
    check(escrow:confirm("t1", "bob", 3, 10), true, "confirmed")
    expect(check(escrow:confirm("t1", "alice", 0, 10), true, "confirmed").ready == true, "both confirmed")

    expect(check(escrow:offer("t1", "alice", { twigs = 2 }, 3, 11), true, "offered", "identical replay").revision == 3,
        "a replay must report the current revision")
    expect(confirmed(escrow, "t1", "alice", 11) == true and confirmed(escrow, "t1", "bob", 11) == true,
        "an identical replay voided confirmations")
    check(escrow:offer("t1", "alice", { twigs = 5 }, 3, 11), false, "revision_conflict")
    check(escrow:offer("t1", "alice", { goldnugget = 1 }, 3, 11), false, "revision_conflict", "replay check precedes validation")
    check(escrow:offer("t1", "alice", { twigs = 2 }, 2, 11), false, "stale_revision")
    expect(confirmed(escrow, "t1", "alice", 11) == true and confirmed(escrow, "t1", "bob", 11) == true,
        "rejected replays voided confirmations")
    expect(check(escrow:confirm("t1", "bob", 3, 11), true, "confirmed", "repeated confirm").ready == true,
        "a repeated confirmation must stay ready")

    expect(check(escrow:cancel("t1", "bob", 12), true, "canceled").phase == "canceled", "cancel must close the trade")
    expect(check(escrow:cancel("t1", "alice", 12), true, "canceled", "repeated cancel").phase == "canceled",
        "a repeated cancel by either party is idempotent")
    expect(check(escrow:cancel("t1", "mallory", 12), false, "not_a_party").phase == "canceled", "party check precedes phase")
    check(escrow:cancel("zz", "alice", 12), false, "unknown_trade")
    expect(check(escrow:offer("t1", "alice", { twigs = 1 }, 4, 12), false, "trade_closed").phase == "canceled",
        "closed trades reject offers")
    check(escrow:confirm("t1", "alice", 0, 12), false, "trade_closed")
    check(escrow:begin_settle("t1", 12), false, "trade_closed")
    check(escrow:finish_settle("t1", true, 12), false, "trade_closed", "finish(true) on canceled")
    check(escrow:finish_settle("t1", false, 12), false, "trade_closed", "finish(false) on canceled")
    check(escrow:open("t1", "alice", "bob", 12), false, "trade_closed", "closed id reuse")
    check(escrow:open("t3", "alice", "carol", 12), true, "opened", "cancel must release both parties")
end)

run("expiry boundary is exact and tick is deterministic", function()
    local escrow = fresh()
    check(escrow:open("tb", "alice", "bob", 10), true, "opened")
    check(escrow:open("ta", "carol", "dave", 10), true, "opened")
    check(escrow:open("tc", "erin", "frank", 15), true, "opened")

    local early = check(escrow:tick(39), true, "ticked")
    expect(type(early.expired) == "table" and #early.expired == 0, "nothing expires before the deadline")
    check(escrow:offer("ta", "carol", { twigs = 1 }, 1, 39.5), true, "offered", "just before the deadline")
    check(escrow:open("tz", "alice", "gina", 39.5), false, "party_busy")
    check(escrow:offer("ta", "carol", {}, 0, 40), false, "invalid_argument", "invalid calls do no expiry work")

    local due = check(escrow:tick(40), true, "ticked")
    expect(#due.expired == 2 and due.expired[1] == "ta" and due.expired[2] == "tb",
        "now == expires_at must expire, ids ascending")
    expect(#check(escrow:tick(40), true, "ticked").expired == 0, "tick must report an expiry only once")
    expect(trade_view(escrow, "ta", 40).phase == "expired" and trade_view(escrow, "tc", 40).phase == "open",
        "only trades at their deadline expire")

    expect(check(escrow:offer("tb", "alice", { twigs = 1 }, 1, 41), false, "trade_closed").phase == "expired",
        "expired trades reject offers")
    check(escrow:cancel("tb", "alice", 41), false, "trade_closed", "cancel after expiry")
    check(escrow:begin_settle("tb", 41), false, "trade_closed", "begin_settle after expiry")
    check(escrow:finish_settle("tb", true, 41), false, "trade_closed", "finish(true) after expiry")
    check(escrow:finish_settle("tb", false, 41), false, "trade_closed", "finish(false) after expiry")
    check(escrow:open("tb", "alice", "bob", 41), false, "trade_closed", "expired id reuse")
    expect(check(escrow:open("tz", "alice", "gina", 41), true, "opened", "expiry must release parties").expires_at == 71,
        "expires_at is now + ttl")

    -- Expiry also happens implicitly inside other calls, and is then not re-reported.
    expect(check(escrow:confirm("tc", "erin", 0, 45), false, "trade_closed").phase == "expired",
        "a call at the deadline must expire the trade first")
    expect(#check(escrow:tick(45), true, "ticked").expired == 0, "implicit expiry must not be reported later")

    check(escrow:open("ty", "hank", "ivy", 100), true, "opened")
    expect(trade_view(escrow, "ty", 129).phase == "open", "still open one second early")
    expect(trade_view(escrow, "ty", 130).phase == "expired", "snapshot applies expiry first")
    expect(#check(escrow:tick(130), true, "ticked").expired == 0, "snapshot expiry must not be reported by tick")
    check(escrow:open("tw", "kim", "lee", 200), true, "opened")
    expect(type(escrow:save(230)) == "table", "save must return a table")
    expect(#check(escrow:tick(230), true, "ticked").expired == 0, "save applies expiry first")
    expect(trade_view(escrow, "tw", 230).phase == "expired", "save applies expiry first")
    check(escrow:tick("soon"), false, "invalid_argument")
end)

run("settlement plan is ordered and settling is exclusive", function()
    local escrow = fresh()
    check(escrow:open("t1", "zed", "amy", 0), true, "opened")
    check(escrow:offer("t1", "zed", { twigs = 2, flint = 1 }, 1, 1), true, "offered")
    check(escrow:offer("t1", "amy", { log = 4, cutgrass = 1 }, 1, 1), true, "offered")
    check(escrow:begin_settle("t1", 1), false, "not_ready")
    check(escrow:begin_settle("none", 1), false, "unknown_trade")
    check(escrow:confirm("t1", "zed", 1, 2), true, "confirmed")
    check(escrow:begin_settle("t1", 2), false, "not_ready", "one confirmation")
    check(escrow:confirm("t1", "amy", 1, 2), true, "confirmed")

    local expected = {
        { from = "amy", to = "zed", prefab = "cutgrass", count = 1 },
        { from = "amy", to = "zed", prefab = "log", count = 4 },
        { from = "zed", to = "amy", prefab = "flint", count = 1 },
        { from = "zed", to = "amy", prefab = "twigs", count = 2 },
    }
    local function check_plan(plan)
        expect(type(plan) == "table" and #plan == #expected, "plan must have one row per offered prefab")
        for index, row in ipairs(expected) do
            local got = plan[index]
            expect(type(got) == "table" and got.from == row.from and got.to == row.to
                and got.prefab == row.prefab and got.count == row.count,
                "plan row " .. index .. " must be " .. row.from .. "/" .. row.prefab)
        end
    end
    local begun = check(escrow:begin_settle("t1", 5), true, "settling")
    expect(begun.phase == "settling", "begin_settle must move to settling")
    check_plan(begun.plan)
    begun.plan[1].count = 99
    begun.plan[5] = { from = "zed", to = "amy", prefab = "log", count = 1 }
    local again = check(escrow:begin_settle("t1", 6), true, "settling", "repeated begin_settle")
    check_plan(again.plan)

    expect(check(escrow:offer("t1", "zed", { twigs = 1 }, 2, 6), false, "trade_locked").phase == "settling", "offers are locked")
    check(escrow:confirm("t1", "amy", 1, 6), false, "trade_locked")
    check(escrow:cancel("t1", "amy", 6), false, "trade_locked")
    check(escrow:open("t7", "zed", "bob", 6), false, "party_busy", "settling keeps parties busy")

    check(escrow:finish_settle("t1", "yes", 20), false, "invalid_argument")
    check(escrow:finish_settle("none", true, 20), false, "unknown_trade")
    expect(check(escrow:finish_settle("t1", false, 20), true, "reopened").phase == "open", "failure reopens")
    local view = trade_view(escrow, "t1", 20)
    expect(party_view(view, "zed").confirmed == false and party_view(view, "amy").confirmed == false,
        "reopening must clear both confirmations")
    expect(party_view(view, "zed").revision == 1 and #party_view(view, "amy").items == 2, "reopening keeps offers")
    check(escrow:finish_settle("t1", false, 20), false, "not_settling")
    check(escrow:finish_settle("t1", true, 20), false, "not_settling")
    check(escrow:begin_settle("t1", 20), false, "not_ready", "must re-confirm after reopening")

    check(escrow:confirm("t1", "zed", 1, 21), true, "confirmed")
    check(escrow:confirm("t1", "amy", 1, 22), true, "confirmed")
    check_plan(check(escrow:begin_settle("t1", 23), true, "settling").plan)
    expect(check(escrow:finish_settle("t1", true, 24), true, "settled").phase == "settled", "success settles")
    check(escrow:finish_settle("t1", true, 24), true, "settled", "repeated finish")
    check(escrow:finish_settle("t1", false, 24), false, "trade_closed")
    check(escrow:begin_settle("t1", 24), false, "trade_closed")
    check(escrow:cancel("t1", "zed", 24), false, "trade_closed")
    expect(check(escrow:offer("t1", "zed", { twigs = 1 }, 2, 24), false, "trade_closed").phase == "settled", "offer on settled")
    check(escrow:confirm("t1", "amy", 1, 24), false, "trade_closed", "confirm on settled")

    -- A reopened trade keeps its original deadline.
    check(escrow:open("t2", "zed", "amy", 25), true, "opened", "settled trades release parties")
    check(escrow:confirm("t2", "zed", 0, 26), true, "confirmed")
    check(escrow:confirm("t2", "amy", 0, 26), true, "confirmed")
    check(escrow:begin_settle("t2", 30), true, "settling")
    expect(#check(escrow:tick(1000), true, "ticked").expired == 0, "settling must never expire")
    expect(trade_view(escrow, "t2", 1000).phase == "settling", "settling must never expire")
    expect(check(escrow:finish_settle("t2", false, 1000), true, "reopened").phase == "open", "reopened past the deadline")
    expect(check(escrow:confirm("t2", "zed", 0, 1000), false, "trade_closed").phase == "expired",
        "a reopened trade keeps its original expires_at")
end)

run("snapshot is fresh and save load round-trips settling", function()
    local escrow = fresh()
    check(escrow:open("t-open", "alice", "bob", 1), true, "opened")
    check(escrow:offer("t-open", "alice", { twigs = 3, cutgrass = 1 }, 2, 1), true, "offered")
    check(escrow:confirm("t-open", "bob", 2, 1), true, "confirmed")
    check(escrow:open("t-settle", "dave", "carol", 2), true, "opened")
    check(escrow:offer("t-settle", "carol", { flint = 2 }, 1, 2), true, "offered")
    check(escrow:offer("t-settle", "dave", { log = 1 }, 1, 2), true, "offered")
    check(escrow:confirm("t-settle", "carol", 1, 2), true, "confirmed")
    check(escrow:confirm("t-settle", "dave", 1, 2), true, "confirmed")
    check(escrow:begin_settle("t-settle", 3), true, "settling")
    check(escrow:open("t-cancel", "erin", "frank", 3), true, "opened")
    check(escrow:cancel("t-cancel", "erin", 4), true, "canceled")

    local snapshot = escrow:snapshot(5)
    expect(#snapshot.trades == 3 and snapshot.trades[1].trade_id == "t-cancel"
        and snapshot.trades[2].trade_id == "t-open" and snapshot.trades[3].trade_id == "t-settle",
        "trades must be ordered by trade_id and include closed trades")
    local open_view = snapshot.trades[2]
    expect(open_view.phase == "open" and open_view.opened_at == 1 and open_view.expires_at == 31, "trade view fields")
    expect(#open_view.parties == 2 and open_view.parties[1].id == "alice" and open_view.parties[2].id == "bob",
        "parties must be ordered by id")
    local alice = open_view.parties[1]
    expect(alice.revision == 2 and alice.confirmed == false and #alice.items == 2
        and alice.items[1].prefab == "cutgrass" and alice.items[1].count == 1
        and alice.items[2].prefab == "twigs" and alice.items[2].count == 3, "items must be ordered by prefab")
    expect(open_view.parties[2].revision == 0 and open_view.parties[2].confirmed == true
        and #open_view.parties[2].items == 0, "bob's view")
    expect(snapshot.trades[3].parties[1].id == "carol" and snapshot.trades[3].phase == "settling"
        and snapshot.trades[1].phase == "canceled", "settling and canceled views")

    open_view.phase = "settled"
    alice.items[1].count = 99
    open_view.parties[2].confirmed = false
    table.remove(snapshot.trades, 1)
    local second = escrow:snapshot(5)
    expect(not rawequal(second, snapshot) and #second.trades == 3, "snapshot must be a fresh table")
    expect(second.trades[2].phase == "open" and second.trades[2].parties[1].items[1].count == 1
        and second.trades[2].parties[2].confirmed == true, "mutating a snapshot changed internal state")

    local saved = escrow:save(5)
    expect(type(saved) == "table" and is_plain(saved, 0), "save must return plain serialisable data")
    expect(type(Escrow.load) == "function", "module must export Escrow.load")
    local restored = Escrow.load(saved, options)
    scribble(saved, 0)
    expect(deep_equal(escrow:snapshot(5), second), "mutating saved data changed the saving instance")
    expect(deep_equal(restored:snapshot(5), second), "load must restore every trade exactly")

    check(restored:offer("t-settle", "carol", {}, 2, 6), false, "trade_locked", "settling survives load")
    local begun = check(restored:begin_settle("t-settle", 6), true, "settling", "begin_settle after load")
    expect(#begun.plan == 2 and begun.plan[1].from == "carol" and begun.plan[1].to == "dave"
        and begun.plan[1].prefab == "flint" and begun.plan[1].count == 2
        and begun.plan[2].from == "dave" and begun.plan[2].prefab == "log" and begun.plan[2].count == 1,
        "the plan must survive load")
    check(restored:open("t-x", "alice", "zoe", 6), false, "party_busy", "occupancy survives load")
    check(restored:open("t-x", "carol", "zoe", 6), false, "party_busy", "settling occupancy survives load")
    check(restored:finish_settle("t-settle", true, 6), true, "settled")
    check(restored:open("t-cancel", "erin", "frank", 6), false, "trade_closed", "tombstones survive load")
    check(restored:open("t-y", "erin", "zoe", 6), true, "opened")
    check(restored:offer("t-open", "alice", { twigs = 1 }, 2, 6), false, "revision_conflict", "revisions survive load")
    check(restored:offer("t-open", "alice", { twigs = 1 }, 1, 6), false, "stale_revision", "revisions survive load")
    expect(check(restored:confirm("t-open", "alice", 0, 6), true, "confirmed").ready == true, "confirmations survive load")
    local due = check(restored:tick(32), true, "ticked")
    expect(#due.expired == 1 and due.expired[1] == "t-open", "deadlines survive load")
    expect(trade_view(escrow, "t-settle", 6).phase == "settling", "the loaded instance must not share state")

    local empty = Escrow.load(nil, options)
    expect(type(empty) == "table" and #empty:snapshot(0).trades == 0, "load(nil) must return an empty escrow")
    check(empty:open("t1", "alice", "bob", 0), true, "opened")
end)

return { cases = cases }
