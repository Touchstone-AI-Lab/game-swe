local loaded, Core = pcall(load_submission, "scripts/outbox/core.lua")
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

local function request(key) return {id=key or "r1",member="m",bundle="food",count=2} end
local function environment()
    local env = {stored=nil, receipts={}, calls={}, count=0, fail_save=false, uncertain=false}
    env.journal = function(data)
        if env.fail_save then return false end
        env.stored = clone(data)
        data.version = 999
        return true
    end
    env.adapter = {
        lookup=function(key)
            env.calls[#env.calls+1] = "lookup:"..key
            return env.receipts[key] or "absent"
        end,
        deliver=function(record)
            env.calls[#env.calls+1] = "deliver:"..record.id
            if not env.receipts[record.id] then env.count=env.count+1 end
            env.receipts[record.id]="applied"
            record.member="poison"
            return env.uncertain and "unknown" or "applied"
        end,
    }
    return env
end
run("intent must persist before any delivery and failed intent consumes no sequence", function()
    local c,e=fresh(),environment()
    e.fail_save=true
    expect(c:submit(request(),e.journal).code=="storage_unavailable")
    expect(c:status("r1").state=="unknown" and #e.calls==0)
    e.fail_save=false
    local r=c:submit(request(),e.journal)
    expect(r.ok and r.seq==1 and #e.calls==0)
    expect(c:drain(e.adapter,e.journal).completed==1 and e.count==1)
end)
run("uncertain delivery survives crash using receipt instead of replay", function()
    local c,e=fresh(),environment()
    c:submit(request(),e.journal)
    e.uncertain=true
    expect(c:drain(e.adapter,e.journal).code=="delivery_uncertain")
    c=Core.load(e.stored)
    expect(c:drain(e.adapter,e.journal).completed==1)
    expect(e.count==1 and #e.calls==3 and e.calls[3]=="lookup:r1")
    expect(c:status("r1").state=="applied")
end)
run("terminal journal failure retains pending and reload must query receipt", function()
    local c,e=fresh(),environment()
    c:submit(request(),e.journal)
    e.fail_save=true
    expect(c:drain(e.adapter,e.journal).code=="storage_unavailable")
    expect(c:status("r1").state=="pending")
    c=Core.load(e.stored)
    e.fail_save=false
    c:drain(e.adapter,e.journal)
    expect(e.count==1 and c:status("r1").state=="applied")
    expect(c:submit(request(),e.journal).duplicate)
end)
run("unknown lookup blocks later requests and eventually resumes in sequence", function()
    local c,e=fresh(),environment()
    c:submit(request("z"),e.journal); c:submit(request("a"),e.journal)
    e.receipts.z="unknown"
    local r=c:drain(e.adapter,e.journal)
    expect(r.code=="delivery_uncertain" and r.completed==0 and #e.calls==1)
    e.receipts.z="rejected"
    r=c:drain(e.adapter,e.journal)
    expect(r.completed==2 and c:status("z").state=="rejected" and e.count==1)
    expect(e.calls[2]=="lookup:z" and e.calls[3]=="lookup:a")
end)
run("duplicate conflict and invalid input precede external calls", function()
    local c,e=fresh(),environment()
    c:submit(request(),e.journal)
    local bomb=function() error("must not call") end
    expect(c:submit(request(),bomb).duplicate)
    local r=request(); r.count=3
    expect(c:submit(r,bomb).code=="request_conflict")
    r.count=0/0
    expect(c:submit(r,bomb).code=="invalid_request")
    expect(c:status("r1").state=="pending")
end)
run("adapter and storage exceptions fail closed without bypass", function()
    local c,e=fresh(),environment()
    expect(c:submit(request(),function() error("disk") end).code=="storage_unavailable")
    c:submit(request(),e.journal)
    e.adapter.lookup=function() error("transport") end
    expect(c:drain(e.adapter,e.journal).code=="delivery_uncertain")
    expect(c:status("r1").state=="pending" and e.count==0)
    e.adapter.lookup=function() return "absent" end
    e.adapter.deliver=function() error("unknown effect") end
    expect(c:drain(e.adapter,e.journal).code=="delivery_uncertain")
end)
run("all terminal receipts survive multiple reloads and hostile aliases", function()
    local c,e=fresh(),environment()
    c:submit(request(),e.journal)
    c:drain(e.adapter,e.journal)
    local data=c:save(); c=Core.load(data); poison(data)
    expect(c:submit(request(),function() error("duplicate persisted again") end).duplicate)
    local result=c:status("r1"); result.state="pending"
    expect(c:status("r1").state=="applied")
    expect(c:drain(e.adapter,e.journal).completed==0)
    same(c:snapshot(),{pending=0,applied=1,rejected=0})
end)

run("save version is explicit and unsupported versions fail closed",function()
    local data=fresh():save(); expect(data.version==1)
    data.version=999
    local ok,err=pcall(Core.load,data)
    expect(not ok and tostring(err):find("invalid_state",1,true)~=nil)
end)
return {cases=cases}
