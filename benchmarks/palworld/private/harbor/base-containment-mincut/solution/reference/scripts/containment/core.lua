local Core = {}
Core.__index = Core
local function plain(x) return type(x) == "table" and getmetatable(x) == nil end
local function keys(x, allowed)
    if not plain(x) then return false end
    for k in pairs(x) do if not allowed[k] then return false end end
    return true
end
local function dense(x, maximum)
    if not plain(x) then return nil end
    local n = #x
    if n > maximum then return nil end
    local count = 0
    for k in pairs(x) do
        if type(k) ~= "number" or k % 1 ~= 0 or k < 1 or k > n then return nil end
        count = count + 1
    end
    if count ~= n then return nil end
    return n
end
local function integer(x, lo, hi)
    return type(x) == "number" and x == x and x % 1 == 0 and x >= lo and x <= hi
end
local function id(x) return type(x) == "string" and #x <= 32 and x:match("^[A-Za-z0-9_-]+$") end
local function copy(x)
    if type(x) ~= "table" then return x end
    local y = {}; for k,v in pairs(x) do y[k] = copy(v) end; return y
end
local function same(a,b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    if not plain(a) then return false end
    for k,v in pairs(a) do if b[k] == nil or not same(v,b[k]) then return false end end
    for k in pairs(b) do if a[k] == nil then return false end end
    return true
end
local function normalize(x)
    if not keys(x,{revision=true,nodes=true,arcs=true,requires=true}) or
       not integer(x.revision,0,1000000000) or not dense(x.nodes,48) or
       not dense(x.arcs,256) or not dense(x.requires,128) then return nil end
    local r = {revision=x.revision,nodes={},arcs={},requires={}}
    local ids, edges, dependencies = {}, {}, {}
    for _,v in ipairs(x.nodes) do
        if not keys(v,{id=true,cost0=true,cost1=true,locked=true}) or not id(v.id) or ids[v.id] or
           not integer(v.cost0,0,1000000) or not integer(v.cost1,0,1000000) or
           (v.locked ~= nil and not integer(v.locked,0,1)) then return nil end
        ids[v.id] = true; r.nodes[#r.nodes+1] = copy(v)
    end
    for _,v in ipairs(x.arcs) do
        if not keys(v,{id=true,from=true,to=true,penalty=true}) or not id(v.id) or edges[v.id] or
           not ids[v.from] or not ids[v.to] or not integer(v.penalty,0,1000000) then return nil end
        edges[v.id] = true; r.arcs[#r.arcs+1] = copy(v)
    end
    for _,v in ipairs(x.requires) do
        if not keys(v,{from=true,to=true}) or not ids[v.from] or not ids[v.to] then return nil end
        local k=v.from.."\0"..v.to
        if dependencies[k] then return nil end
        dependencies[k]=true; r.requires[#r.requires+1]=copy(v)
    end
    table.sort(r.nodes,function(a,b) return a.id<b.id end)
    table.sort(r.arcs,function(a,b) return a.id<b.id end)
    table.sort(r.requires,function(a,b) return a.from==b.from and a.to<b.to or a.from<b.from end)
    return r
end
local function solve(x, baseline)
    local n, index, base = #x.nodes, {}, {}
    local factor, bound = n+1, 0
    for i,v in ipairs(x.nodes) do
        index[v.id]=i; base[i]=baseline[i].label
        bound=bound+v.cost0+v.cost1
    end
    for _,e in ipairs(x.arcs) do bound=bound+e.penalty end
    local infinity=(bound+1)*factor+n+1
    local fixed={}
    local function flow()
        local graph={}; for i=1,n+2 do graph[i]={} end
        local source,sink=n+1,n+2
        local function edge(a,b,c)
            if a==b then return end
            local ab={to=b,cap=c,rev=#graph[b]+1}
            local ba={to=a,cap=0,rev=#graph[a]+1}
            graph[a][#graph[a]+1]=ab; graph[b][#graph[b]+1]=ba
        end
        for i,v in ipairs(x.nodes) do
            edge(source,i,v.cost0*factor+(base[i]==1 and 1 or 0))
            edge(i,sink,v.cost1*factor+(base[i]==0 and 1 or 0))
            if v.locked==1 or fixed[i]==1 then edge(source,i,infinity) end
            if v.locked==0 or fixed[i]==0 then edge(i,sink,infinity) end
        end
        for _,v in ipairs(x.arcs) do edge(index[v.from],index[v.to],v.penalty*factor) end
        for _,v in ipairs(x.requires) do edge(index[v.from],index[v.to],infinity) end
        local total=0
        while total<infinity do
            local level={[source]=0}; local queue={source}; local head=1
            while head<=#queue do
                local u=queue[head]; head=head+1
                for _,e in ipairs(graph[u]) do
                    if e.cap>0 and level[e.to]==nil then
                        level[e.to]=level[u]+1; queue[#queue+1]=e.to
                    end
                end
            end
            if level[sink]==nil then break end
            local cursor={}; for i=1,n+2 do cursor[i]=1 end
            local function push(u, amount)
                if u==sink then return amount end
                while cursor[u]<=#graph[u] do
                    local e=graph[u][cursor[u]]
                    if e.cap>0 and level[e.to]==level[u]+1 then
                        local sent=push(e.to,math.min(amount,e.cap))
                        if sent>0 then
                            e.cap=e.cap-sent
                            local reverse=graph[e.to][e.rev]; reverse.cap=reverse.cap+sent
                            return sent
                        end
                    end
                    cursor[u]=cursor[u]+1
                end
                return 0
            end
            while total<infinity do
                local sent=push(source,infinity-total)
                if sent==0 then break end
                total=total+sent
            end
        end
        return total
    end
    local optimum=flow()
    if optimum>=infinity then return nil end
    for i=1,n do
        fixed[i]=0
        if flow()~=optimum then fixed[i]=1 end
    end
    local result={ok=true,revision=x.revision,energy=0,changes=0,labels={}}
    for i,v in ipairs(x.nodes) do
        local label=fixed[i]
        result.labels[i]={id=v.id,label=label}
        result.energy=result.energy+(label==0 and v.cost0 or v.cost1)
        if label~=base[i] then result.changes=result.changes+1 end
    end
    for _,e in ipairs(x.arcs) do
        if fixed[index[e.from]]==1 and fixed[index[e.to]]==0 then
            result.energy=result.energy+e.penalty
        end
    end
    return result
end
function Core.new()
    return setmetatable({revision=-1,result={revision=-1,labels={}},baseline={}},Core)
end
function Core:plan(input)
    local request=normalize(input)
    if not request then return {ok=false,code="invalid_request"} end
    if request.revision<=self.revision then return {ok=false,code="stale_revision"} end
    local previous={}; for _,v in ipairs(self.result.labels) do previous[v.id]=v.label end
    local baseline={}
    for i,v in ipairs(request.nodes) do baseline[i]={id=v.id,label=previous[v.id] or 0} end
    local result=solve(request,baseline)
    if not result then return {ok=false,code="infeasible"} end
    self.revision=request.revision; self.request=request; self.baseline=baseline; self.result=result
    return copy(result)
end
function Core:snapshot() return copy(self.result) end
function Core:save()
    return {version=1,revision=self.revision,request=copy(self.request),
            baseline=copy(self.baseline),result=copy(self.result)}
end
function Core.load(data)
    local function invalid() error("invalid_state",0) end
    if not keys(data,{version=true,revision=true,request=true,baseline=true,result=true}) or
       data.version~=1 or not integer(data.revision,-1,1000000000) then invalid() end
    local self=Core.new()
    if data.revision==-1 then
        if data.request~=nil or dense(data.baseline,0)~=0 or not same(data.result,self.result) then invalid() end
        return self
    end
    local request=normalize(data.request)
    if not request or request.revision~=data.revision or not same(request,data.request) or
       dense(data.baseline,48)~=#request.nodes then invalid() end
    for i,v in ipairs(data.baseline) do
        if not keys(v,{id=true,label=true}) or v.id~=request.nodes[i].id or not integer(v.label,0,1) then invalid() end
    end
    local result=solve(request,data.baseline)
    if not result or not same(result,data.result) then invalid() end
    self.revision=request.revision; self.request=request; self.baseline=copy(data.baseline); self.result=result
    return self
end
return Core
