local loaded, Ballot = pcall(load_submission, "scripts/ruleballot/ballot.lua")
if not loaded or type(Ballot) ~= "table" then Ballot = {} end
local cases = {}
local function expect(v, m) if not v then error(m or "expectation failed", 0) end end
local function run(name, body) local ok,msg=pcall(body); cases[#cases+1]={name=name,passed=ok,message=ok and "ok" or tostring(msg)} end
local function fresh()
    expect(type(Ballot.new) == "function", "module must export Ballot.new")
    return Ballot.new({})
end
local proposal = { id="lights", choices={"off", "on"}, deadline=20, quorum=2 }

run("electorate and choices are frozen", function()
    local b=fresh(); expect(b:open(proposal,{"p1","p2","p3"},10).ok)
    expect(b:cast("outsider","lights","on",1,11).ok==false)
    expect(b:cast("p1","lights","forged",1,11).ok==false)
    expect(b:cast("p1","lights","on",1,11).ok)
end)

run("newer vote revision replaces old vote", function()
    local b=fresh(); b:open(proposal,{"p1","p2"},10)
    expect(b:cast("p1","lights","off",1,11).ok)
    expect(b:cast("p1","lights","on",2,12).ok)
    expect(b:cast("p1","lights","off",1,13).ok==false)
    b:cast("p2","lights","on",1,13)
    local result=b:close("lights",20)
    expect(result.status=="passed" and result.choice_id=="on")
end)

run("quorum and top ties are deterministic", function()
    local b=fresh(); b:open(proposal,{"p1","p2","p3"},10)
    b:cast("p1","lights","on",1,11)
    expect(b:close("lights",20).status=="no_quorum")
    local c=fresh(); c:open(proposal,{"p1","p2"},10)
    c:cast("p1","lights","on",1,11); c:cast("p2","lights","off",1,11)
    expect(c:close("lights",20).status=="tie")
end)

run("deadline boundary and close are idempotent", function()
    local b=fresh(); b:open(proposal,{"p1","p2"},10)
    b:cast("p1","lights","on",1,19); b:cast("p2","lights","on",1,19)
    expect(b:cast("p1","lights","off",2,20).ok==false, "deadline vote accepted")
    local first=b:close("lights",99); local second=b:close("lights",100)
    expect(first.status=="passed" and first.choice_id=="on", "late close changed the deadline result")
    expect(first.status==second.status and first.choice_id==second.choice_id)
end)

run("cancel is final and identifier cannot reopen", function()
    local b=fresh(); b:open(proposal,{"p1","p2"},10)
    expect(b:cancel("lights",12).status=="canceled")
    expect(b:close("lights",20).status=="canceled")
    expect(b:open(proposal,{"p1","p2"},21).ok==false)
end)

run("snapshot hides votes and save load preserves result", function()
    local b=fresh(); b:open(proposal,{"p1","p2"},10)
    b:cast("p1","lights","on",1,11); b:cast("p2","lights","on",1,11)
    local snap=b:snapshot(12)
    expect(snap.votes==nil and snap.electorate==nil, "snapshot leaked private ballots")
    if snap.counts then snap.counts[1].count=999 end
    expect(type(Ballot.load)=="function")
    local restored=Ballot.load(b:save(12),{})
    expect(b:snapshot(12).counts[1].count~=999, "snapshot exposed internal counts")
    expect(restored:close("lights",20).choice_id=="on")
end)

return {cases=cases}
