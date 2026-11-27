local loaded, Core = pcall(load_submission, "scripts/draft/core.lua")
if not loaded or type(Core)~="table" then Core={} end
local cases={}
local function expect(v,m) if not v then error(m or "contract violation",0) end end
local function run(name,body)
    local ok,message=pcall(body); cases[#cases+1]={name=name,passed=ok,message=ok and "ok" or tostring(message)}
end
local function clone(x)
    if type(x)~="table" then return x end
    local r={}; for k,v in pairs(x) do r[k]=clone(v) end; return r
end
local function equal(a,b)
    expect(type(a)==type(b),"type differs")
    if type(a)~="table" then expect(a==b,"value differs"); return end
    for k,v in pairs(a) do expect(b[k]~=nil,"extra field"); equal(v,b[k]) end
    for k in pairs(b) do expect(a[k]~=nil,"missing field") end
end
local function sample(revision)
    return {revision=revision or 0,items={"a","b","c","d"},votes={},before={{from="d",to="a"}}}
end
local function oracle(x,prior)
    local items=clone(x.items); table.sort(items)
    local present,baseline,seen={},{},{}
    for _,v in ipairs(items) do present[v]=true end
    for _,v in ipairs(prior or {}) do if present[v] then baseline[#baseline+1]=v; seen[v]=true end end
    for _,v in ipairs(items) do if not seen[v] then baseline[#baseline+1]=v end end
    local old={}; for i,v in ipairs(baseline) do old[v]=i end
    local best,used,order=nil,{},{}
    local function visit()
        if #order==#items then
            local pos={}; for i,v in ipairs(order) do pos[v]=i end
            local cost,worst,total=0,0,0
            for _,v in ipairs(x.votes) do if pos[v.from]>pos[v.to] then cost=cost+v.weight end end
            for i,v in ipairs(order) do local d=math.abs(i-old[v]); worst=math.max(worst,d); total=total+d end
            local better=not best or cost<best.penalty or (cost==best.penalty and worst<best.worst) or
                (cost==best.penalty and worst==best.worst and total<best.movement)
            if best and cost==best.penalty and worst==best.worst and total==best.movement then
                for i,v in ipairs(order) do if v~=best.order[i] then better=v<best.order[i]; break end end
            end
            if better then best={ok=true,revision=x.revision,penalty=cost,worst=worst,movement=total,order=clone(order)} end
            return
        end
        for _,v in ipairs(items) do
            if not used[v] then
                local allowed=true
                for _,e in ipairs(x.before) do if e.to==v and not used[e.from] then allowed=false end end
                if allowed then
                    used[v]=true; order[#order+1]=v; visit(); order[#order]=nil; used[v]=nil
                end
            end
        end
    end
    visit()
    return best or {ok=false,code="infeasible"}
end
run("worst displacement precedes total displacement and lexical order",function()
    local x=sample(); local r=Core.new():plan(x)
    equal(r,oracle(x)); expect(r.worst==2 and r.movement==6)
    equal(r.order,{"b","d","a","c"})
end)
run("weighted cyclic preferences require a global optimum",function()
    local x={revision=0,items={"a","b","c","d"},before={},votes={
        {id="ab",from="a",to="b",weight=4},{id="bc",from="b",to="c",weight=4},
        {id="ca",from="c",to="a",weight=5},{id="da",from="d",to="a",weight=3},
        {id="dc",from="d",to="c",weight=3},{id="ad",from="a",to="d",weight=1}}}
    equal(Core.new():plan(x),oracle(x))
end)
run("hard predecessors dominate soft preferences and cycles preserve state",function()
    local c=Core.new(); local before=c:plan(sample())
    local x=sample(1); x.before={{from="a",to="b"},{from="b",to="a"}}
    equal(c:plan(x),{ok=false,code="infeasible"}); equal(c:snapshot(),before)
    x.before={{from="d",to="a"},{from="a",to="b"}}
    x.votes={{id="v",from="b",to="d",weight=1000000}}
    equal(c:plan(x),oracle(x,before.order))
end)
run("baseline retains surviving order then appends new IDs by raw bytes",function()
    local c=Core.new(); local first=c:plan(sample())
    local x={revision=1,items={"aa","b","a0","a"},votes={},before={{from="b",to="a0"}}}
    local r=c:plan(x); equal(r,oracle(x,first.order))
    local y=clone(x); y.revision=2; y.items={"a0","a","aa","b"}
    equal(c:plan(y),oracle(y,r.order))
end)
run("independent permutation oracle checks all objective levels over histories",function()
    local seed=92237
    local function random(n) seed=(seed*48271)%2147483647; return seed%n end
    local c,prior=Core.new(),{}
    for trial=0,27 do
        local x={revision=trial,items={"a","a0","b","c","d","e"},votes={},before={}}
        for i=1,6 do for j=1,6 do
            if i~=j and random(3)==0 then x.votes[#x.votes+1]={id="v"..i.."_"..j,from=x.items[i],to=x.items[j],weight=random(5)} end
        end end
        if trial%3==0 then x.before={{from="e",to="a"}} end
        local expected=oracle(x,prior)
        equal(c:plan(x),expected); prior=expected.order
        x.items[1],x.items[6]=x.items[6],x.items[1]
        equal(Core.new():plan(x),oracle(x))
    end
end)
run("sixteen-item dense tournament cannot use factorial enumeration",function()
    local x={revision=0,items={},votes={},before={}}
    for i=1,16 do x.items[i]=string.format("p%02d",i) end
    for i=2,16 do for j=1,i-1 do
        x.votes[#x.votes+1]={id="v"..i.."_"..j,from=x.items[i],to=x.items[j],weight=i+j}
    end end
    local r=Core.new():plan(x)
    expect(r.ok and r.penalty==0 and r.worst==15 and r.movement==128)
    for i=1,16 do expect(r.order[i]==string.format("p%02d",17-i)) end
end)
run("malformed requests precede stale checks and never update history",function()
    local c=Core.new(); local before=c:plan(sample())
    local bads={}
    local x=sample(); x.items[2]="a"; bads[#bads+1]=x
    x=sample(); x.items.extra="x"; bads[#bads+1]=x
    x=sample(); x.extra=true; bads[#bads+1]=x
    x=sample(); x.votes={{id="x",from="a",to="a",weight=0}}; bads[#bads+1]=x
    x=sample(); x.votes={{id="x",from="a",to="b",weight=math.huge}}; bads[#bads+1]=x
    x=sample(); x.before={{from="a",to="b"},{from="a",to="b"}}; bads[#bads+1]=x
    for _,bad in ipairs(bads) do expect(c:plan(bad).code=="invalid_request"); equal(c:snapshot(),before) end
    expect(c:plan(sample()).code=="stale_revision")
    x=sample(); x.before={{from="a",to="b"},{from="b",to="a"}}
    expect(c:plan(x).code=="stale_revision")
end)
run("detached recovery revalidates cached optimum and baseline permutations",function()
    local c=Core.new(); local x=sample(); local r=c:plan(x); local expected=clone(r)
    x.items[1]="poison"; r.order[1]="poison"; equal(c:snapshot(),expected)
    local saved=c:save(); local restored=Core.load(saved); saved.baseline[1]="poison"
    equal(restored:snapshot(),expected)
    local bad=c:save(); bad.result.worst=99; expect(not pcall(Core.load,bad))
    bad=c:save(); bad.result.order[1],bad.result.order[2]=bad.result.order[2],bad.result.order[1]
    expect(not pcall(Core.load,bad),"forged canonical order accepted")
    bad=c:save(); bad.baseline[1]=bad.baseline[2]; expect(not pcall(Core.load,bad))
    equal(Core.load(Core.new():save()):snapshot(),{revision=-1,order={}})
    equal(restored:plan({revision=1,items={},votes={},before={}}),
        {ok=true,revision=1,penalty=0,worst=0,movement=0,order={}})
end)
return {cases=cases}
