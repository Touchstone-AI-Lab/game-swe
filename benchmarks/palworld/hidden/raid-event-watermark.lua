local loaded, Core = pcall(load_submission, "scripts/watermark/core.lua")
if not loaded or type(Core) ~= "table" then Core = {} end
local cases = {}
local function expect(value, message) if not value then error(message or "contract violation", 0) end end
local function run(name, body)
    local ok, message = pcall(body)
    cases[#cases+1] = {name=name,passed=ok,message=ok and "ok" or tostring(message)}
end
local function clone(x)
    if type(x)~="table" then return x end
    local r={}; for k,v in pairs(x) do r[k]=clone(v) end; return r
end
local function same(a,b)
    expect(type(a)==type(b),"type mismatch")
    if type(a)~="table" then expect(a==b,"value mismatch: "..tostring(a).." / "..tostring(b)); return end
    for k,v in pairs(a) do expect(b[k]~=nil,"unexpected field "..tostring(k)); same(v,b[k]) end
    for k in pairs(b) do expect(a[k]~=nil,"missing field "..tostring(k)) end
end
local function poison(x)
    for k,v in pairs(x) do if type(v)=="table" then poison(v) else x[k]="poison" end end
end
local function fresh() return Core.new() end

local function event(key,revision,amount,deleted,tick,member)
    return {id=key or "hit",member=member or "m1",tick=tick or 9,
        revision=revision or 0,amount=amount or 7,deleted=deleted or false}
end
run("out-of-order revisions replace rather than add",function()
    local c=fresh()
    c:observe(event("a",2,7))
    expect(c:observe(event("a",1,90)).code=="stale_revision")
    c:observe(event("b",0,7,false,9,"m2")); c:advance(10)
    same(c:result(0),{window=0,member="m1",amount=7})
end)
run("tombstone before create prevents resurrection until a higher revision",function()
    local c=fresh()
    c:observe(event("a",2,99,true))
    expect(c:observe(event("a",1,99)).code=="stale_revision")
    c:advance(10); same(c:result(0),{window=0,amount=0})
    c=fresh(); c:observe(event("a",2,99,true)); c:observe(event("a",3,4)); c:advance(10)
    same(c:result(0),{window=0,member="m1",amount=4})
end)
run("identity conflict and equal-revision payload conflict have stable precedence",function()
    local c=fresh(); c:observe(event()); c:advance(10)
    expect(c:observe(event("hit",0,7,false,8)).code=="identity_conflict")
    expect(c:observe(event("hit",0,8)).code=="revision_conflict")
    expect(c:observe(event()).duplicate)
    expect(c:observe(event("hit",1,8)).code=="late_event")
end)
run("watermark uses strict event bound and closed window bound",function()
    local c=fresh(); c:advance(10)
    expect(c:observe(event("old",0,7,false,9)).code=="late_event")
    expect(c:observe(event("edge",0,7,false,10)).ok)
    expect(c:result(1).code=="not_final")
    expect(c:advance(9).code=="stale_watermark")
    c:advance(19); expect(c:result(1).code=="not_final")
    c:advance(20); same(c:result(1),{window=1,member="m1",amount=7})
end)
run("zero amount participates but a fully retracted window remains empty",function()
    local c=fresh(); c:observe(event("a",0,0,false,0,"z")); c:observe(event("b",0,0,false,0,"a"))
    c:observe(event("c",0,10,true,10)); c:advance(100)
    same(c:result(0),{window=0,member="a",amount=0})
    same(c:result(1),{window=1,amount=0})
    same(c:result(9),{window=9,amount=0})
    expect(#c:snapshot().results==1)
end)
run("all event permutations and intermediate restarts give identical finality",function()
    local events={event("a",0,90),event("a",1,9),event("b",0,4),event("b",2,4,true)}
    local used,order={},{}
    local function visit()
        if #order==#events then
            local c=fresh()
            for _,i in ipairs(order) do c:observe(events[i]); c=Core.load(c:save()) end
            c:advance(10); same(c:result(0),{window=0,member="m1",amount=9})
            return
        end
        for i=1,#events do
            if not used[i] then used[i]=true; order[#order+1]=i; visit(); order[#order]=nil; used[i]=nil end
        end
    end
    visit()
end)
run("partial windows and checkpoint retain all pending corrections",function()
    local c=fresh(); c:observe(event()); c:advance(9)
    local data=c:save(); c=Core.load(data); poison(data)
    expect(c:observe(event("hit",1,3)).ok)
    c:advance(10); same(c:result(0),{window=0,member="m1",amount=3})
    local r=c:result(0); poison(r); same(c:result(0),{window=0,member="m1",amount=3})
end)
run("invalid input and aliases never mutate accepted contributions",function()
    local c=fresh(); local e=event(); c:observe(e); poison(e)
    e=event(); e.amount=0/0; expect(c:observe(e).code=="invalid_request")
    e=event(); e.deleted=nil; expect(c:observe(e).code=="invalid_request")
    expect(c:advance(-1).code=="invalid_request")
    c:advance(10); same(c:result(0),{window=0,member="m1",amount=7})
    local snap=c:snapshot(); poison(snap); expect(c:snapshot().watermark==10)
end)

run("save version is explicit and unsupported versions fail closed",function()
    local data=fresh():save(); expect(data.version==1)
    data.version=999
    local ok,err=pcall(Core.load,data)
    expect(not ok and tostring(err):find("invalid_state",1,true)~=nil)
end)
return {cases=cases}
