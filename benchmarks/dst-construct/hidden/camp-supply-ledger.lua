local loaded, Ledger = pcall(load_submission, "scripts/campsupply/ledger.lua")
if not loaded or type(Ledger) ~= "table" then Ledger = {} end

local cases = {}
local function expect(value, message) if not value then error(message or "expectation failed", 0) end end
local function run(name, body)
    local ok, message = pcall(body)
    cases[#cases + 1] = { name = name, passed = ok, message = ok and "ok" or tostring(message) }
end
local options = {
    bundles = {
        basic = { { prefab = "twigs", count = 2 }, { prefab = "cutgrass", count = 1 } },
        twig = { { prefab = "twigs", count = 2 } },
    },
    daily_limits = { twigs = 3, cutgrass = 2 },
}
local function fresh()
    expect(type(Ledger.new) == "function", "module must export Ledger.new")
    local ledger = Ledger.new(options)
    expect(type(ledger) == "table", "Ledger.new must return a table")
    expect(ledger:begin_day(7) ~= false, "begin_day rejected initial day")
    expect(ledger:set_player("p1", true) ~= false, "set_player rejected valid player")
    return ledger
end

run("claim reserves configured quota", function()
    local ledger = fresh()
    local result = ledger:claim("p1", "r1", "basic", 7)
    expect(type(result) == "table" and result.ok == true and type(result.token) == "string")
    expect(type(result.items) == "table" and #result.items == 2)
    local blocked = ledger:claim("p1", "r2", "twig", 7)
    expect(type(blocked) == "table" and blocked.ok == false, "pending quota was not reserved")
end)

run("rollback releases quota exactly once", function()
    local ledger = fresh()
    local first = ledger:claim("p1", "r1", "basic", 7)
    expect(ledger:rollback(first.token).ok == true)
    local duplicate = ledger:rollback(first.token)
    expect(type(duplicate) == "table" and duplicate.status == "rolled_back")
    expect(ledger:claim("p1", "r2", "twig", 7).ok == true, "rollback did not restore quota")
end)

run("commit and request retries are idempotent", function()
    local ledger = fresh()
    local first = ledger:claim("p1", "same", "basic", 7)
    local retry = ledger:claim("p1", "same", "twig", 7)
    expect(retry.token == first.token, "retry created another reservation")
    expect(ledger:commit(first.token).status == "committed")
    expect(ledger:commit(first.token).status == "committed", "duplicate commit changed outcome")
    expect(ledger:rollback(first.token).ok == false, "committed token was rolled back")
end)

run("inactive and forged bundles are rejected", function()
    local ledger = fresh()
    expect(ledger:set_player("p1", false) ~= false)
    expect(ledger:claim("p1", "r1", "basic", 7).ok == false)
    expect(ledger:set_player("p1", true) ~= false)
    expect(ledger:claim("p1", "r2", "dragonfly", 7).ok == false)
end)

run("day rollover is monotonic", function()
    local ledger = fresh()
    local claim = ledger:claim("p1", "r1", "basic", 7)
    expect(ledger:commit(claim.token).ok == true)
    expect(ledger:begin_day(8) ~= false)
    expect(ledger:claim("p1", "r2", "basic", 8).ok == true, "new day did not reset quota")
    expect(ledger:begin_day(7) == false, "stale day was accepted")
end)

run("save load preserves reservations and defensive copies", function()
    local ledger = fresh()
    local claim = ledger:claim("p1", "persist", "basic", 7)
    local snapshot = ledger:snapshot()
    snapshot.day = 999
    snapshot.players = {}
    expect(type(Ledger.load) == "function", "module must export Ledger.load")
    local restored = Ledger.load(ledger:save(), options)
    local retry = restored:claim("p1", "persist", "basic", 7)
    expect(retry.token == claim.token, "pending request did not survive load")
    expect(restored:commit(claim.token).status == "committed")
    expect(restored:snapshot().day == 7, "snapshot mutated internal state")
end)

return { cases = cases }
