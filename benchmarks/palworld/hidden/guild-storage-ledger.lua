local loaded, Ledger = pcall(load_submission, "scripts/guildledger/ledger.lua")
if not loaded or type(Ledger) ~= "table" then Ledger = {} end
local cases = {}
local function expect(v, m) if not v then error(m or "expectation failed", 0) end end
local function run(name, body) local ok,msg=pcall(body); cases[#cases+1]={name=name,passed=ok,message=ok and "ok" or tostring(msg)} end
local options = { quota = 2, bundles = { basic = { wood = 2, stone = 1 } } }
local function fresh()
    expect(type(Ledger.new) == "function", "module must export Ledger.new")
    local ledger = Ledger.new(options)
    expect(ledger:begin_cycle(1).ok, "begin_cycle(1) must succeed")
    expect(ledger:set_member("m1", true).ok)
    expect(ledger:set_member("m2", true).ok)
    return ledger
end

run("cycles are strictly monotonic and stale cycles are inert", function()
    local ledger = fresh()
    expect(ledger:begin_cycle(1).ok == false, "repeated cycle accepted")
    expect(ledger:begin_cycle(0).ok == false, "older cycle accepted")
    expect(ledger:begin_cycle(-1).ok == false, "negative cycle accepted")
    expect(ledger:begin_cycle(1.5).ok == false, "fractional cycle accepted")
    expect(ledger:claim("m1", "r1", "basic", 1).ok, "claim in the current cycle must succeed")
    expect(ledger:claim("m1", "r2", "basic", 0).ok == false, "stale cycle claim accepted")
    expect(ledger:begin_cycle(2).ok, "next cycle must be accepted")
end)

run("bundles, members and counts are validated on the server", function()
    local ledger = fresh()
    expect(ledger:claim("m1", "r1", "missing", 1).code == "unknown_bundle")
    expect(ledger:set_member("m2", false).ok)
    expect(ledger:claim("m2", "r2", "basic", 1).code == "inactive_member")
    expect(ledger:claim("ghost", "r3", "basic", 1).ok == false, "unknown member accepted")
    expect(ledger:claim("m1", "", "basic", 1).ok == false, "empty request id accepted")
    local granted = ledger:claim("m1", "r4", "basic", 1)
    expect(granted.ok and granted.items.wood == 2 and granted.items.stone == 1, "bundle contents wrong")
    granted.items.wood = 999
    expect(ledger:claim("m1", "r5", "basic", 1).items.wood == 2, "bundle table is shared with the caller")
end)

run("retries never double-spend quota", function()
    local ledger = fresh()
    local first = ledger:claim("m1", "r1", "basic", 1)
    local retry = ledger:claim("m1", "r1", "basic", 1)
    expect(first.ok and retry.ok, "retry must repeat the original outcome")
    expect(retry.duplicate == true, "retry must be marked duplicate")
    expect(retry.token == first.token, "retry must not mint a second token")
    expect(ledger:claim("m1", "r2", "basic", 1).ok, "second distinct request must fit the quota")
    local third = ledger:claim("m1", "r3", "basic", 1)
    expect(third.ok == false and third.code == "quota_exhausted", "quota was not enforced")
    expect(ledger:snapshot().members[1].remaining == 0, "remaining quota is wrong")
end)

run("commit and rollback each consume a token exactly once", function()
    local ledger = fresh()
    local granted = ledger:claim("m1", "r1", "basic", 1)
    expect(ledger:commit(granted.token).state == "committed")
    expect(ledger:commit(granted.token).ok == false, "commit is not single-use")
    expect(ledger:rollback(granted.token).ok == false, "committed token was rolled back")
    local second = ledger:claim("m1", "r2", "basic", 1)
    expect(ledger:rollback(second.token).state == "rolled_back")
    expect(ledger:rollback(second.token).ok == false, "rollback is not single-use")
    expect(ledger:claim("m1", "r3", "basic", 1).ok, "rollback did not release quota")
    expect(ledger:commit("forged-token").ok == false, "forged token accepted")
end)

run("snapshot is fresh, ordered and free of private structures", function()
    local ledger = fresh()
    ledger:claim("m2", "r1", "basic", 1)
    ledger:claim("m1", "r2", "basic", 1)
    local snapshot = ledger:snapshot()
    expect(snapshot.requests == nil and snapshot.reservations == nil and snapshot.tokens == nil,
        "snapshot leaked private structures")
    expect(snapshot.members[1].member_id == "m1" and snapshot.members[2].member_id == "m2",
        "members are not ordered by member_id")
    snapshot.members[1].remaining = 999
    snapshot.pending = 999
    local again = ledger:snapshot()
    expect(again.members[1].remaining ~= 999 and again.pending ~= 999, "snapshot is not a fresh table")
end)

run("save and load round-trip quota, outcomes and token sequencing", function()
    local ledger = fresh()
    local granted = ledger:claim("m1", "r1", "basic", 1)
    ledger:commit(granted.token)
    local pending = ledger:claim("m2", "r2", "basic", 1)
    expect(type(Ledger.load) == "function", "module must export Ledger.load")
    local restored = Ledger.load(ledger:save(), options)
    expect(restored:claim("m1", "r1", "basic", 1).duplicate == true, "committed request was not restored")
    expect(restored:commit(granted.token).ok == false, "committed token survived reload as live")
    expect(restored:rollback(pending.token).state == "rolled_back", "pending reservation was lost")
    expect(restored:begin_cycle(1).ok == false, "cycle position was lost")
    local reissued = restored:claim("m1", "r9", "basic", 1)
    expect(reissued.ok and reissued.token ~= granted.token and reissued.token ~= pending.token,
        "token sequencing restarted after reload")
end)

return {cases=cases}
