local loaded, Core = pcall(load_submission, "scripts/containment/core.lua")
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
    return {revision=revision or 0,nodes={{id="a",cost0=9,cost1=0},{id="b",cost0=0,cost1=8}},
        arcs={{id="bridge",from="a",to="b",penalty=20}},requires={}}
end
local function oracle(x,prior)
    x=clone(x); table.sort(x.nodes,function(a,b) return a.id<b.id end)
    prior=prior or {}; local best
    for mask=0,(1<<#x.nodes)-1 do
        local labels,map={},{}; local energy,changes=0,0; local valid=true
        for i,v in ipairs(x.nodes) do
            local bit=(mask>>(i-1))&1; map[v.id]=bit; labels[i]={id=v.id,label=bit}
            if v.locked~=nil and bit~=v.locked then valid=false end
            energy=energy+(bit==0 and v.cost0 or v.cost1)
            if bit~=(prior[v.id] or 0) then changes=changes+1 end
        end
        for _,v in ipairs(x.requires) do if map[v.from]==1 and map[v.to]==0 then valid=false end end
        for _,v in ipairs(x.arcs) do if map[v.from]==1 and map[v.to]==0 then energy=energy+v.penalty end end
        if valid then
            local better=not best or energy<best.energy or (energy==best.energy and changes<best.changes)
            if best and energy==best.energy and changes==best.changes then
                for i,v in ipairs(labels) do
                    if v.label~=best.labels[i].label then better=v.label<best.labels[i].label; break end
                end
            end
            if better then best={ok=true,revision=x.revision,energy=energy,changes=changes,labels=labels} end
        end
    end
    return best or {ok=false,code="infeasible"}
end
run("a coupled global cut defeats independent local choices",function()
    equal(Core.new():plan(sample()),oracle(sample()))
end)
run("hard implications dominate every finite cost and can be infeasible",function()
    local c=Core.new(); local x=sample(); x.nodes[1].locked=1; x.nodes[2].locked=0
    x.requires={{from="a",to="b"},{from="b",to="a"}}
    equal(c:plan(x),{ok=false,code="infeasible"}); equal(c:snapshot(),{revision=-1,labels={}})
    x.nodes[2].locked=nil; equal(c:plan(x),oracle(x))
end)
run("stability precedes lexical preference across accepted revisions",function()
    local c=Core.new(); local x=sample(); x.nodes[1].locked=1; x.nodes[2].locked=1
    local first=c:plan(x); expect(first.ok)
    x.revision=1; x.nodes[1].locked=nil; x.nodes[2].locked=nil; x.arcs={}
    for _,v in ipairs(x.nodes) do v.cost0=0; v.cost1=0 end
    equal(c:plan(x),oracle(x,{a=1,b=1}))
    x.revision=2; x.nodes={{id="a0",cost0=0,cost1=0},{id="a",cost0=0,cost1=0},{id="new",cost0=0,cost1=0}}
    equal(c:plan(x),oracle(x,{a=1,b=1}))
end)
run("parallel arcs zero penalties and raw prefix IDs preserve direction",function()
    local x={revision=0,nodes={{id="a0",cost0=0,cost1=8},{id="a",cost0=7,cost1=0}},
        arcs={{id="e1",from="a",to="a0",penalty=4},{id="e2",from="a",to="a0",penalty=4},
              {id="zero",from="a0",to="a",penalty=0},{id="self",from="a",to="a",penalty=1000000}},requires={}}
    equal(Core.new():plan(x),oracle(x))
end)
run("independent exhaustive oracle covers directed cyclic graphs and history",function()
    local seed=19793
    local function random(n) seed=(seed*48271)%2147483647; return seed%n end
    local c=Core.new(); local prior={}
    for trial=0,39 do
        local x={revision=trial,nodes={},arcs={},requires={}}
        for i=1,6 do x.nodes[i]={id="n"..i,cost0=random(9),cost1=random(9)} end
        for i=1,6 do for j=1,6 do
            if i~=j and random(4)==0 then x.arcs[#x.arcs+1]={id="e"..i.."_"..j,from="n"..i,to="n"..j,penalty=random(15)} end
        end end
        if trial%4==0 then x.requires={{from="n1",to="n2"},{from="n2",to="n1"}} end
        local expected=oracle(x,prior); equal(c:plan(x),expected)
        for _,v in ipairs(expected.labels) do prior[v.id]=v.label end
        local shuffled=clone(x); shuffled.revision=trial+100
        shuffled.nodes[1],shuffled.nodes[6]=shuffled.nodes[6],shuffled.nodes[1]
        local fresh=Core.new(); local zero=oracle(shuffled)
        equal(fresh:plan(shuffled),zero)
    end
end)
run("48-node strongly coupled instance does not enumerate all partitions",function()
    local x={revision=0,nodes={},arcs={},requires={}}
    for i=1,48 do
        x.nodes[i]={id=string.format("n%02d",i),cost0=1000000,cost1=0}
        x.requires[#x.requires+1]={from=string.format("n%02d",i),to=string.format("n%02d",i%48+1)}
    end
    for i=1,48 do for step=1,5 do
        x.arcs[#x.arcs+1]={id="e"..i.."_"..step,from=x.nodes[i].id,to=x.nodes[(i+step-1)%48+1].id,penalty=1000000}
    end end
    local r=Core.new():plan(x); expect(r.ok and r.energy==0 and r.changes==48 and #r.labels==48)
    for _,v in ipairs(r.labels) do expect(v.label==1) end
end)
run("validation precedes stale revision and every rejection is atomic",function()
    local c=Core.new(); local before=c:plan(sample())
    local bads={}
    local x=sample(); x.extra=true; bads[#bads+1]=x
    x=sample(); x.nodes[2].id="a"; bads[#bads+1]=x
    x=sample(); x.arcs[1].to="ghost"; bads[#bads+1]=x
    x=sample(); x.nodes[1].cost1=0/0; bads[#bads+1]=x
    x=sample(); x.nodes.extra={}; bads[#bads+1]=x
    x=sample(); x.requires={{from="a",to="b"},{from="a",to="b"}}; bads[#bads+1]=x
    for _,bad in ipairs(bads) do expect(c:plan(bad).code=="invalid_request"); equal(c:snapshot(),before) end
    expect(c:plan(sample()).code=="stale_revision")
    x=sample(); x.nodes[1].locked=1; x.nodes[2].locked=0; x.requires={{from="a",to="b"}}
    expect(c:plan(x).code=="stale_revision"); equal(c:snapshot(),before)
end)
run("save validates the optimality certificate and isolates aliases",function()
    local c=Core.new(); local input=sample(); local r=c:plan(input); local expected=clone(r)
    input.nodes[1].cost0=0; r.labels[1].label=99; equal(c:snapshot(),expected)
    local data=c:save(); local restored=Core.load(data); data.baseline[1].label=99
    equal(restored:snapshot(),expected)
    local bad=c:save(); bad.result.energy=bad.result.energy+1
    expect(not pcall(Core.load,bad),"forged objective accepted")
    bad=c:save(); bad.result.labels[1].label=1-bad.result.labels[1].label
    expect(not pcall(Core.load,bad),"forged cut accepted")
    bad=c:save(); bad.baseline[1].id="unknown"
    expect(not pcall(Core.load,bad),"forged baseline accepted")
    equal(Core.load(Core.new():save()):snapshot(),{revision=-1,labels={}})
    local empty={revision=1,nodes={},arcs={},requires={}}
    equal(restored:plan(empty),{ok=true,revision=1,energy=0,changes=0,labels={}})
end)
return {cases=cases}
