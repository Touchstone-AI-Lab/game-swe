local loaded, Core = pcall(load_submission, "scripts/epoch/core.lua")
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

local function schedule(c,key,due) return c:schedule({id=key or "x",payload="reward",due=due or 5}) end
run("not mounted and invalid calls do not reserve identifiers",function()
    local c=fresh(); expect(schedule(c).code=="not_mounted")
    expect(c:poll(0,0).code=="stale_epoch")
    expect(c:mount(1,0).ok and schedule(c).ok)
    expect(c:mount(1,1).code=="stale_epoch")
end)
run("due boundary and deterministic ordering include all ready tasks",function()
    local c=fresh(); c:mount(1,0); schedule(c,"z",5); schedule(c,"a",5); schedule(c,"b",4)
    expect(#c:poll(1,3).deliveries==0)
    local r=c:poll(1,5).deliveries
    expect(#r==3 and r[1].id=="b" and r[2].id=="a" and r[3].id=="z")
    expect(#c:poll(1,5).deliveries==0)
end)
run("same-world retry fences the previous delivery generation",function()
    local c=fresh(); c:mount(1,0); schedule(c)
    local old=c:poll(1,5).deliveries[1]; expect(c:ack(old,false).ok)
    local current=c:poll(1,5).deliveries[1]
    expect(current.generation==old.generation+1)
    expect(c:ack(old,true).code=="stale_token")
    expect(c:ack(current,true).state=="done")
    expect(c:ack(current,true).code=="stale_token")
end)
run("restart and new epoch fence old callbacks without resurrecting terminal tasks",function()
    local c=fresh(); c:mount(1,0); schedule(c,"x"); schedule(c,"y")
    local r=c:poll(1,5).deliveries; c:ack(r[2],true)
    local data=c:save(); c=Core.load(data); poison(data)
    expect(c:mount(2,5).ok)
    expect(c:ack(r[1],true).code=="stale_epoch")
    local next=c:poll(2,5).deliveries
    expect(#next==1 and next[1].id=="x" and next[1].epoch==2 and next[1].generation==2)
    expect(c:snapshot().done==1)
end)
run("old epoch with future time cannot poison live clock",function()
    local c=fresh(); c:mount(2,5); schedule(c)
    expect(c:poll(1,999).code=="stale_epoch")
    expect(c:snapshot().now==5)
    expect(c:mount(3,4).code=="stale_now")
    expect(c:snapshot().epoch==2)
    expect(c:poll(2,5).ok)
end)
run("cancel wins over delayed ack and never releases an ID for reuse",function()
    local c=fresh(); c:mount(1,0); schedule(c)
    local token=c:poll(1,5).deliveries[1]
    expect(c:cancel("x").ok and c:cancel("x").ok)
    expect(c:ack(token,true).code=="stale_token")
    expect(schedule(c).state=="canceled")
    expect(c:schedule({id="x",payload="other",due=5}).code=="request_conflict")
    c:mount(2,5); expect(#c:poll(2,5).deliveries==0)
end)
run("validation precedes fencing and done cancellation is refused",function()
    local c=fresh(); c:mount(1,0); schedule(c)
    local token=c:poll(1,5).deliveries[1]
    expect(c:ack(token,"true").code=="invalid_request")
    expect(c:ack(token,true).ok)
    expect(c:cancel("x").code=="already_done")
    expect(c:cancel("ghost").code=="unknown_task")
    expect(c:poll(0,-1).code=="invalid_request")
    expect(c:poll(1,4).code=="stale_now")
end)
run("snapshot save and deliveries are detached from state",function()
    local c=fresh(); c:mount(1,0)
    local request={id="x",payload="reward",due=5}; c:schedule(request); poison(request)
    local r=c:poll(1,5); local token=clone(r.deliveries[1]); poison(r)
    expect(c:ack(token,false).ok)
    local snapshot=c:snapshot(); poison(snapshot)
    expect(c:snapshot().pending==1)
    c=Core.load(c:save()); expect(c:poll(1,5).deliveries[1].generation==2)
end)

run("save version is explicit and unsupported versions fail closed",function()
    local data=fresh():save(); expect(data.version==1)
    data.version=999
    local ok,err=pcall(Core.load,data)
    expect(not ok and tostring(err):find("invalid_state",1,true)~=nil)
end)
return {cases=cases}
