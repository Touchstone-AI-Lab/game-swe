local loaded, Core = pcall(load_submission, "scripts/checkpoint/core.lua")
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
local function fresh() return Core.new({"a","b","c"}) end

local function append(c,s,n,deps) expect(c:append({shard=s,seq=n,deps=deps or {}}).ok) end
run("cascading rollback must reach a fixed point then recover after filling a hole",function()
    local c=fresh(); append(c,"a",1,{b=2}); append(c,"b",1); append(c,"b",2,{c=1})
    same(c:cut({a=1,b=2,c=1}),{ok=true,vector={a=0,b=1,c=0}})
    append(c,"c",1); same(c:cut({a=1,b=2,c=1}),{ok=true,vector={a=1,b=2,c=1}})
end)
run("mutual dependencies form a valid cut when both events exist",function()
    local c=fresh(); append(c,"a",1,{b=1}); append(c,"b",1,{a=1})
    same(c:cut({a=1,b=1,c=0}).vector,{a=1,b=1,c=0})
    same(c:cut({a=1,b=0,c=0}).vector,{a=0,b=0,c=0})
end)
run("every selected prefix event matters not only its last event",function()
    local c=fresh(); append(c,"a",1,{b=1}); append(c,"a",2)
    same(c:cut({a=2,b=0,c=0}).vector,{a=0,b=0,c=0})
end)
run("holes are not silently skipped and count is not prefix length",function()
    local c=fresh(); append(c,"a",2); append(c,"a",3)
    expect(c:snapshot().shards[1].count==2)
    expect(c:cut({a=3,b=0,c=0}).vector.a==0)
    c=Core.load(c:save()); append(c,"a",1)
    expect(c:cut({a=3,b=0,c=0}).vector.a==3)
end)
run("mapping equality duplicate conflict and exact shard validation",function()
    local c=fresh(); append(c,"a",1,{b=0})
    expect(c:append({shard="a",seq=1,deps={b=0}}).duplicate)
    expect(c:append({shard="a",seq=1,deps={}}).code=="event_conflict")
    expect(c:append({shard="a",seq=2,deps={a=2}}).code=="invalid_request")
    expect(c:append({shard="a",seq=2,deps={ghost=0}}).code=="invalid_request")
    expect(c:cut({a=1,b=1}).code=="invalid_request")
    expect(c:cut({a=1,b=1,c=1,ghost=0}).code=="invalid_request")
end)
run("independent exhaustive vector oracle checks maximality on generated graphs",function()
    local seed=337
    local function random(n) seed=(seed*48271)%2147483647; return seed%n end
    for trial=1,50 do
        local c=fresh(); local logs={a={},b={},c={}}
        for _,s in ipairs({"a","b","c"}) do
            for n=1,3 do
                if random(5)>0 then
                    local deps={}
                    for _,t in ipairs({"a","b","c"}) do
                        if t~=s and random(3)==0 then deps[t]=random(4) end
                    end
                    append(c,s,n,deps); logs[s][n]=deps
                end
            end
        end
        local limits={a=random(4),b=random(4),c=random(4)}
        local expected={a=0,b=0,c=0}
        for a=0,limits.a do for b=0,limits.b do for d=0,limits.c do
            local vector={a=a,b=b,c=d}; local valid=true
            for s,at in pairs(vector) do
                for n=1,at do
                    local deps=logs[s][n]
                    if not deps then valid=false else
                        for t,k in pairs(deps) do if vector[t]<k then valid=false end end
                    end
                end
            end
            if valid then for s,at in pairs(vector) do expected[s]=math.max(expected[s],at) end end
        end end end
        same(c:cut(limits).vector,expected)
        local data=c:save(); c=Core.load(data); poison(data)
        same(c:cut(limits).vector,expected)
    end
end)
run("maximum 16-shard chains preserve complete cut",function()
    local shards={}; for i=1,16 do shards[i]="s"..i end
    local c=Core.new(shards); local limits={}
    for i,s in ipairs(shards) do
        limits[s]=256
        for n=1,256 do
            local deps={}; if i>1 then deps[shards[i-1]]=n end
            append(c,s,n,deps)
        end
    end
    same(c:cut(limits).vector,limits)
    limits.s1=0; local result=c:cut(limits)
    for _,s in ipairs(shards) do expect(result.vector[s]==0) end
end)
run("invalid configuration and hostile aliases cannot change log dependencies",function()
    expect(not pcall(Core.new,{"a","a"}))
    expect(not pcall(Core.new,{"a",extra="b"}))
    local c=fresh(); local e={shard="a",seq=1,deps={b=1}}
    c:append(e); poison(e); append(c,"b",1)
    local result=c:cut({a=1,b=1,c=0}); poison(result)
    same(c:cut({a=1,b=1,c=0}).vector,{a=1,b=1,c=0})
end)

run("save version is explicit and unsupported versions fail closed",function()
    local data=fresh():save(); expect(data.version==1)
    data.version=999
    local ok,err=pcall(Core.load,data)
    expect(not ok and tostring(err):find("invalid_state",1,true)~=nil)
end)
return {cases=cases}
