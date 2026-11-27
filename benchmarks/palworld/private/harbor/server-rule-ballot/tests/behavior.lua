local loaded, Ballot = pcall(load_submission, "scripts/ruleballot/ballot.lua")
if not loaded or type(Ballot) ~= "table" then Ballot = {} end
local cases = {}
local function expect(v, m) if not v then error(m or "expectation failed", 0) end end
local function run(name, body) local ok,msg=pcall(body); cases[#cases+1]={name=name,passed=ok,message=ok and "ok" or tostring(msg)} end
local function fresh()
    expect(type(Ballot.new) == "function", "module must export Ballot.new")
    return Ballot.new({})
end
local proposal = { id = "pvp", choices = { "off", "on" }, deadline = 20, quorum = 2 }

run("electorate and choices are frozen at open", function()
    local ballot = fresh()
    expect(ballot:open(proposal, { "p1", "p2", "p3", "p1" }, 10).ok, "open rejected a valid proposal")
    expect(ballot:cast("outsider", "pvp", "on", 1, 11).code == "not_a_voter")
    expect(ballot:cast("p1", "pvp", "forged", 1, 11).code == "unknown_choice")
    expect(ballot:cast("p1", "pvp", "on", 1, 11).ok, "a frozen voter was rejected")
    expect(ballot:open({ id = "pvp", choices = { "a", "b" }, deadline = 30, quorum = 1 }, { "p1" }, 12).ok == false,
        "an open proposal identifier was reused")
end)

run("proposals are validated before any state changes", function()
    local ballot = fresh()
    expect(ballot:open({ id = "x", choices = { "only" }, deadline = 20, quorum = 1 }, { "p1" }, 1).ok == false,
        "a single-choice proposal was accepted")
    expect(ballot:open({ id = "y", choices = { "a", "a" }, deadline = 20, quorum = 1 }, { "p1" }, 1).ok == false,
        "duplicate choices were accepted")
    expect(ballot:open({ id = "z", choices = { "a", "b" }, quorum = 1 }, { "p1" }, 1).ok == false,
        "a proposal without a deadline was accepted")
    expect(ballot:open(proposal, {}, 1).ok == false, "an empty electorate was accepted")
end)

run("newer vote revisions replace older ones", function()
    local ballot = fresh()
    ballot:open(proposal, { "p1", "p2" }, 10)
    expect(ballot:cast("p1", "pvp", "off", 1, 11).ok)
    expect(ballot:cast("p1", "pvp", "on", 2, 12).revision == 2)
    expect(ballot:cast("p1", "pvp", "off", 1, 13).code == "stale_revision")
    expect(ballot:cast("p1", "pvp", "off", 2, 13).code == "stale_revision", "an equal revision was accepted")
    ballot:cast("p2", "pvp", "on", 1, 13)
    local result = ballot:close("pvp", 20)
    expect(result.status == "passed" and result.choice_id == "on", "latest votes were not counted")
end)

run("quorum, ties and count ordering are deterministic", function()
    local ballot = fresh()
    ballot:open(proposal, { "p1", "p2", "p3" }, 10)
    ballot:cast("p1", "pvp", "on", 1, 11)
    expect(ballot:close("pvp", 20).status == "no_quorum", "quorum was not enforced")
    local tied = fresh()
    tied:open(proposal, { "p1", "p2" }, 10)
    tied:cast("p1", "pvp", "on", 1, 11)
    tied:cast("p2", "pvp", "off", 1, 11)
    local result = tied:close("pvp", 20)
    expect(result.status == "tie" and result.choice_id == nil, "a top tie applied a rule")
    expect(result.counts[1].choice_id == "off" and result.counts[2].choice_id == "on",
        "counts are not ordered lexicographically by choice_id")
end)

run("deadline boundary and close are idempotent", function()
    local ballot = fresh()
    ballot:open(proposal, { "p1", "p2" }, 10)
    ballot:cast("p1", "pvp", "on", 1, 19)
    ballot:cast("p2", "pvp", "on", 1, 19)
    expect(ballot:cast("p1", "pvp", "off", 2, 20).code == "past_deadline", "a deadline-instant vote was accepted")
    local first = ballot:close("pvp", 99)
    local second = ballot:close("pvp", 100)
    expect(first.status == second.status and first.choice_id == second.choice_id, "close is not idempotent")
    expect(first.status == "passed" and first.choice_id == "on")
end)

run("cancel is final and identifiers can never be reused", function()
    local ballot = fresh()
    ballot:open(proposal, { "p1", "p2" }, 10)
    expect(ballot:cancel("pvp", 12).status == "canceled")
    expect(ballot:close("pvp", 20).status == "canceled", "a canceled proposal was settled")
    expect(ballot:cast("p1", "pvp", "on", 1, 13).ok == false, "a canceled proposal accepted a vote")
    expect(ballot:open(proposal, { "p1", "p2" }, 21).ok == false, "a canceled identifier was reused")
end)

run("snapshot hides individual ballots and save/load keeps the result", function()
    local ballot = fresh()
    ballot:open(proposal, { "p1", "p2" }, 10)
    ballot:cast("p1", "pvp", "on", 1, 11)
    ballot:cast("p2", "pvp", "on", 1, 11)
    local snapshot = ballot:snapshot(12)
    expect(snapshot.votes == nil and snapshot.electorate == nil, "snapshot leaked private ballots")
    snapshot.counts[1].count = 999
    expect(ballot:snapshot(12).counts[1].count ~= 999, "snapshot is not a fresh table")
    expect(type(Ballot.load) == "function", "module must export Ballot.load")
    local restored = Ballot.load(ballot:save(12), {})
    expect(restored:close("pvp", 20).choice_id == "on", "the electorate or votes were lost across reload")
    expect(restored:cast("p1", "pvp", "off", 5, 13).ok == false, "a reloaded ballot accepted a late vote")
end)

return {cases=cases}
