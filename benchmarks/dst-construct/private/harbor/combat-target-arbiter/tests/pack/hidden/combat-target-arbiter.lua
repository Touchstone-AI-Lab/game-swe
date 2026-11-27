local loaded, Arbiter = pcall(load_submission, "scripts/combatarbiter/arbiter.lua")
if not loaded or type(Arbiter) ~= "table" then Arbiter = {} end
local cases={}
local function expect(v,m) if not v then error(m or "expectation failed",0) end end
local function run(name,body) local ok,msg=pcall(body); cases[#cases+1]={name=name,passed=ok,message=ok and "ok" or tostring(msg)} end
local options={decay_per_second=1}
local function fresh()
    expect(type(Arbiter.new)=="function","module must export Arbiter.new")
    local a=Arbiter.new(options)
    for _,id in ipairs({"mob","a","b"}) do expect(a:observe({id=id,alive=true,revision=1},0)~=false) end
    return a
end

run("duplicate and out of order threat is rejected",function()
    local a=fresh(); expect(a:add_threat("mob","a",10,2,0)~=false)
    expect(a:add_threat("mob","a",50,2,1)==false)
    expect(a:add_threat("mob","a",50,1,1)==false)
    expect(a:choose("mob",1).target_id=="a")
    expect(a:choose("mob",1).threat==9)
end)

run("decay is independent of tick frequency",function()
    local a=fresh(); local b=fresh()
    a:add_threat("mob","a",20,1,0); b:add_threat("mob","a",20,1,0)
    a:tick(3); a:tick(7)
    expect(a:choose("mob",10).threat==b:choose("mob",10).threat)
end)

run("ties use first seen then lexical id",function()
    local a=fresh(); a:add_threat("mob","b",10,1,0); a:add_threat("mob","a",9,1,1)
    expect(a:choose("mob",2).target_id=="b","first-seen tie break failed")
    local c=fresh(); c:add_threat("mob","b",10,1,0); c:add_threat("mob","a",10,1,0)
    expect(c:choose("mob",0).target_id=="a","lexical tie break failed")
end)

run("taunt overrides until exact expiry",function()
    local a=fresh(); a:add_threat("mob","a",100,1,0); a:add_threat("mob","b",1,1,0)
    local lease=a:taunt("t1","mob","b",5,1); expect(lease.ok)
    expect(a:choose("mob",5.999).target_id=="b")
    expect(a:choose("mob",6).target_id=="a")
    expect(a:taunt("t1","mob","a",99,2).expires_at==lease.expires_at)
end)

run("death blocks delayed resurrection",function()
    local a=fresh(); a:add_threat("mob","a",10,5,0)
    a:observe({id="a",alive=false,revision=2},1)
    expect(a:choose("mob",1)==nil)
    expect(a:add_threat("mob","a",50,4,2)==false)
    expect(a:observe({id="a",alive=true,revision=1},2)==false)
end)

run("save load preserves effective threat and defensive state",function()
    local a=fresh(); a:add_threat("mob","a",20,1,0); a:taunt("t1","mob","a",10,1)
    local snap=a:snapshot(3); if snap[1] then snap[1].threat=999 end
    expect(type(Arbiter.load)=="function")
    local restored=Arbiter.load(a:save(3),options,3)
    expect(restored:choose("mob",4).threat==16)
    expect(restored:choose("mob",4).target_id=="a")
end)

return {cases=cases}
