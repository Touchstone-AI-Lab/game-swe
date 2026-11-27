local loaded, Core = pcall(load_submission, "scripts/workforce/core.lua")
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

local function input() return {revision=0,pals={{id="a"},{id="b"}},jobs={
    {id="cook",priority=5,costs={a=2,b=3}}, {id="mine",priority=5,costs={a=1}}}} end
local function oracle(x)
    local jobs,pals=clone(x.jobs),clone(x.pals)
    table.sort(jobs,function(a,b) return a.id<b.id end)
    table.sort(pals,function(a,b) return a.id<b.id end)
    local best,used,vector=nil,{},{}
    local function better(a,b)
        if not b then return true end
        if a.priority~=b.priority then return a.priority>b.priority end
        if a.count~=b.count then return a.count>b.count end
        if a.cost~=b.cost then return a.cost<b.cost end
        for i=1,#jobs do if a.vector[i]~=b.vector[i] then return a.vector[i]<b.vector[i] end end
        return false
    end
    local function visit(i,p,n,c)
        if i>#jobs then
            local r={priority=p,count=n,cost=c,vector=clone(vector)}
            if better(r,best) then best=r end
            return
        end
        vector[i]="~"; visit(i+1,p,n,c)
        for _,pal in ipairs(pals) do
            local cost=jobs[i].costs[pal.id]
            if cost~=nil and not used[pal.id] then
                used[pal.id]=true; vector[i]=pal.id
                visit(i+1,p+jobs[i].priority,n+1,c+cost)
                used[pal.id]=nil
            end
        end
    end
    visit(1,0,0,0)
    local assignments={}
    for i,p in ipairs(best.vector) do
        if p~="~" then assignments[#assignments+1]={job=jobs[i].id,pal=p} end
    end
    return {ok=true,revision=x.revision,priority=best.priority,count=best.count,cost=best.cost,assignments=assignments}
end
run("global matching beats local cheapest-first",function()
    same(fresh():plan(input()),oracle(input()))
end)
run("priority outranks cardinality cost and lexical preference",function()
    local x={revision=0,pals={{id="a"}},jobs={{id="a",priority=1,costs={a=0}},
        {id="z",priority=100,costs={a=1000000}}}}
    same(fresh():plan(x),oracle(x))
end)
run("zero-priority and zero-cost edges are real work",function()
    local x=input()
    for _,j in ipairs(x.jobs) do j.priority=0; for p in pairs(j.costs) do j.costs[p]=0 end end
    same(fresh():plan(x),oracle(x))
end)
run("lexical ties compare raw prefix IDs and unassigned slots",function()
    local x={revision=1,pals={{id="a0"},{id="a"}},jobs={
        {id="x",priority=1,costs={a=1,a0=1}},{id="y",priority=1,costs={a=1,a0=1}},
        {id="z",priority=1,costs={a=1,a0=1}}}}
    same(fresh():plan(x),oracle(x))
end)
run("independent exhaustive oracle on deterministic generated graphs",function()
    local seed=739
    local function random(n) seed=(seed*48271)%2147483647; return seed%n end
    for trial=1,36 do
        local x={revision=trial,pals={},jobs={}}
        for p=1,5 do x.pals[p]={id="p"..p} end
        for j=1,5 do
            local costs={}
            for p=1,5 do if random(3)>0 then costs["p"..p]=random(7) end end
            x.jobs[j]={id="j"..j,priority=random(5),costs=costs}
        end
        same(fresh():plan(x),oracle(x))
        local first=x.pals[1]; x.pals[1]=x.pals[5]; x.pals[5]=first
        first=x.jobs[1]; x.jobs[1]=x.jobs[5]; x.jobs[5]=first
        same(fresh():plan(x),oracle(x))
    end
end)
run("maximum dense graph has deterministic perfect optimum",function()
    local x={revision=1,pals={},jobs={}}
    for i=1,12 do x.pals[i]={id=string.format("p%02d",i)} end
    for j=1,12 do
        local costs={}
        for p=1,12 do costs[x.pals[p].id]=p==j and 0 or 1 end
        x.jobs[j]={id=string.format("j%02d",j),priority=1,costs=costs}
    end
    local r=fresh():plan(x)
    expect(r.ok and r.count==12 and r.priority==12 and r.cost==0)
    for i,a in ipairs(r.assignments) do expect(a.pal==string.format("p%02d",i)) end
end)
run("invalid input and stale revision preserve the last successful plan",function()
    local c=fresh(); local expected=c:plan(input())
    expect(c:plan(input()).code=="stale_revision")
    local x=input(); x.jobs[1].costs.ghost=1
    expect(c:plan(x).code=="invalid_request")
    x=input(); x.pals[1].id=x.pals[2].id
    expect(c:plan(x).code=="invalid_request")
    x=input(); x.jobs.extra={}
    expect(c:plan(x).code=="invalid_request")
    same(c:snapshot(),expected)
    local data=c:save(); c=Core.load(data); poison(data)
    same(c:snapshot(),expected)
    expect(c:plan(input()).code=="stale_revision")
end)
run("empty matching and all caller-owned tables remain detached",function()
    local c=fresh(); local x=input(); local r=c:plan(x); local expected=clone(r)
    poison(x); poison(r); same(c:snapshot(),expected)
    r=c:snapshot(); poison(r); same(c:snapshot(),expected)
    same(c:plan({revision=1,pals={},jobs={}}),{ok=true,revision=1,priority=0,count=0,cost=0,assignments={}})
end)

run("save version is explicit and unsupported versions fail closed",function()
    local data=fresh():save(); expect(data.version==1)
    data.version=999
    local ok,err=pcall(Core.load,data)
    expect(not ok and tostring(err):find("invalid_state",1,true)~=nil)
end)
return {cases=cases}
