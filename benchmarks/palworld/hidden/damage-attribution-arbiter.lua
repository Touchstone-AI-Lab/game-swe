local loaded, Arbiter = pcall(load_submission, "scripts/combat/arbiter.lua")
if not loaded or type(Arbiter) ~= "table" then Arbiter = {} end
local cases = {}
local function expect(v, m) if not v then error(m or "expectation failed", 0) end end
local function run(name, body) local ok,msg=pcall(body); cases[#cases+1]={name=name,passed=ok,message=ok and "ok" or tostring(msg)} end
local options = { claim_seconds = 10 }
local function fresh()
    expect(type(Arbiter.new) == "function", "module must export Arbiter.new")
    return Arbiter.new(options)
end
local function report(sequence, attacker, amount, tick)
    return { sequence = sequence, attacker_id = attacker, target_id = "boss", amount = amount, tick = tick }
end
local reports = {
    report(1, "a", 10, 1),
    report(2, "b", 30, 2),
    report(3, "a", 25, 3),
    report(4, "b", 5, 4),
}

run("malformed reports are rejected before any state change", function()
    local arbiter = fresh()
    expect(arbiter:observe({ attacker_id = "a", target_id = "boss", amount = 1, tick = 1 }).code == "invalid_report")
    expect(arbiter:observe(report(1, "a", -1, 1)).code == "invalid_report", "a negative amount was accepted")
    expect(arbiter:observe(report(1.5, "a", 1, 1)).code == "invalid_report", "a fractional sequence was accepted")
    expect(arbiter:observe(report(1, "", 1, 1)).code == "invalid_report", "an empty attacker was accepted")
    expect(arbiter:observe(report(1, "a", 1, "later")).code == "invalid_report", "a non-numeric tick was accepted")
    expect(#arbiter:snapshot(1).targets == 0, "a rejected report created a target")
end)

run("duplicate and replayed sequences never inflate a total", function()
    local arbiter = fresh()
    expect(arbiter:observe(reports[1]).applied == true)
    local repeated = arbiter:observe(reports[1])
    expect(repeated.duplicate == true and repeated.applied == false, "a repeated sequence was applied")
    expect(arbiter:observe(reports[2]).applied == true)
    local replay = arbiter:observe(report(1, "a", 999, 5))
    expect(replay.duplicate == true and replay.applied == false, "a lower sequence was applied")
    expect(arbiter:snapshot(5).targets[1].total == 40, "totals were inflated by duplicates")
end)

run("totals are identical for every arrival permutation", function()
    local forward = fresh()
    for _, entry in ipairs(reports) do forward:observe(entry) end
    local shuffled = fresh()
    for _, index in ipairs({ 3, 1, 4, 2 }) do shuffled:observe(reports[index]) end
    local a = forward:resolve("boss", 9)
    local b = shuffled:resolve("boss", 9)
    expect(a.ok and b.ok, "resolve failed on an observed target")
    expect(a.total == b.total and a.attacker_id == b.attacker_id, "arrival order changed the outcome")
    expect(forward:snapshot(9).targets[1].total == shuffled:snapshot(9).targets[1].total,
        "arrival order changed the accumulated total")
end)

run("claims are single-owner and expire without an explicit release", function()
    local arbiter = fresh()
    arbiter:observe(reports[1])
    local claim = arbiter:claim("a", "boss", 1)
    expect(claim.ok and claim.expires_at == 11, "claim expiry is wrong")
    expect(arbiter:claim("b", "boss", 2).code == "claimed", "a second attacker claimed the same target")
    expect(arbiter:renew(claim.token, 3).expires_at == 13, "renew did not extend the claim")
    expect(arbiter:renew("forged", 4).code == "unknown_token", "a forged token was renewed")
    local later = arbiter:claim("b", "boss", 30)
    expect(later.ok and later.token ~= claim.token, "an expired claim was not released implicitly")
    expect(arbiter:release(later.token, 31).ok and arbiter:release(later.token, 32).ok == false,
        "release is not single-use")
end)

run("resolution is deterministic and final", function()
    local arbiter = fresh()
    for _, entry in ipairs(reports) do arbiter:observe(entry) end
    local resolved = arbiter:resolve("boss", 9)
    expect(resolved.attacker_id == "a" and resolved.total == 35, "highest attributed total did not win")
    expect(resolved.final == true, "resolution was not marked final")
    expect(arbiter:observe(report(5, "b", 500, 10)).code == "resolved", "a resolved target accepted a report")
    expect(arbiter:resolve("boss", 11).attacker_id == "a", "a resolved target changed owner")
    expect(arbiter:resolve("missing", 11).code == "unknown_target")
    local tied = fresh()
    tied:observe({ sequence = 1, attacker_id = "zed", target_id = "t", amount = 10, tick = 1 })
    tied:observe({ sequence = 2, attacker_id = "amy", target_id = "t", amount = 10, tick = 2 })
    expect(tied:resolve("t", 3).attacker_id == "zed", "earliest first contact must break a total tie")
end)

run("snapshots are fresh, ordered and free of private structures", function()
    local arbiter = fresh()
    arbiter:observe({ sequence = 1, attacker_id = "a", target_id = "zeta", amount = 4, tick = 1 })
    arbiter:observe({ sequence = 1, attacker_id = "a", target_id = "alpha", amount = 2, tick = 2 })
    local snapshot = arbiter:snapshot(3)
    expect(snapshot.reports == nil and snapshot.claims == nil and snapshot.tokens == nil,
        "snapshot leaked private structures")
    expect(snapshot.targets[1].target_id == "alpha" and snapshot.targets[2].target_id == "zeta",
        "targets are not ordered by target_id")
    snapshot.targets[1].total = 999
    expect(arbiter:snapshot(3).targets[1].total ~= 999, "snapshot is not a fresh table")
end)

run("save and load round-trip sequences, claims and resolutions", function()
    local arbiter = fresh()
    for _, entry in ipairs(reports) do arbiter:observe(entry) end
    local claim = arbiter:claim("a", "boss", 5)
    expect(type(Arbiter.load) == "function", "module must export Arbiter.load")
    local restored = Arbiter.load(arbiter:save(5), options)
    expect(restored:observe(reports[4]).duplicate == true, "sequence history was lost across reload")
    expect(restored:renew(claim.token, 6).expires_at == 16, "a live claim was lost across reload")
    expect(restored:claim("b", "boss", 7).code == "claimed", "a reloaded claim stopped blocking others")
    local resolved = restored:resolve("boss", 8)
    expect(resolved.attacker_id == "a" and resolved.total == 35, "totals were lost across reload")
    local again = Arbiter.load(restored:save(8), options)
    expect(again:resolve("boss", 9).final == true, "the resolution was lost across reload")
end)

return {cases=cases}
