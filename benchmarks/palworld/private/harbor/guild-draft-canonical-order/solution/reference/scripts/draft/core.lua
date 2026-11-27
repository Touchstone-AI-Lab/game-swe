local Core = {}
Core.__index = Core
local function plain(x) return type(x)=="table" and getmetatable(x)==nil end
local function keys(x, allowed)
    if not plain(x) then return false end
    for k in pairs(x) do if not allowed[k] then return false end end
    return true
end
local function dense(x, maximum)
    if not plain(x) or #x>maximum then return nil end
    local n,count=#x,0
    for k in pairs(x) do
        if type(k)~="number" or k%1~=0 or k<1 or k>n then return nil end
        count=count+1
    end
    if count~=n then return nil end
    return n
end
local function integer(x,lo,hi)
    return type(x)=="number" and x==x and x%1==0 and x>=lo and x<=hi
end
local function id(x) return type(x)=="string" and #x<=32 and x:match("^[A-Za-z0-9_-]+$") end
local function copy(x)
    if type(x)~="table" then return x end
    local y={}; for k,v in pairs(x) do y[k]=copy(v) end; return y
end
local function same(a,b)
    if type(a)~=type(b) then return false end
    if type(a)~="table" then return a==b end
    if not plain(a) then return false end
    for k,v in pairs(a) do if b[k]==nil or not same(v,b[k]) then return false end end
    for k in pairs(b) do if a[k]==nil then return false end end
    return true
end
local function normalize(x)
    if not keys(x,{revision=true,items=true,votes=true,before=true}) or
       not integer(x.revision,0,1000000000) or not dense(x.items,16) or
       not dense(x.votes,256) or not dense(x.before,128) then return nil end
    local r={revision=x.revision,items={},votes={},before={}}
    local ids,votes,edges={},{},{}
    for _,v in ipairs(x.items) do
        if not id(v) or ids[v] then return nil end
        ids[v]=true; r.items[#r.items+1]=v
    end
    for _,v in ipairs(x.votes) do
        if not keys(v,{id=true,from=true,to=true,weight=true}) or not id(v.id) or votes[v.id] or
           not ids[v.from] or not ids[v.to] or v.from==v.to or not integer(v.weight,0,1000000) then return nil end
        votes[v.id]=true; r.votes[#r.votes+1]=copy(v)
    end
    for _,v in ipairs(x.before) do
        if not keys(v,{from=true,to=true}) or not ids[v.from] or not ids[v.to] or v.from==v.to then return nil end
        local key=v.from.."\0"..v.to
        if edges[key] then return nil end
        edges[key]=true; r.before[#r.before+1]=copy(v)
    end
    table.sort(r.items)
    table.sort(r.votes,function(a,b) return a.id<b.id end)
    table.sort(r.before,function(a,b) return a.from==b.from and a.to<b.to or a.from<b.from end)
    return r
end
local function solve(x,baseline)
    local n=#x.items
    local index,bits,bit_index,positions,pred,weights={},{},{},{},{},{}
    for i,v in ipairs(x.items) do
        index[v]=i; bits[i]=1<<(i-1); bit_index[bits[i]]=i; pred[i]=0; weights[i]={}
        for j=1,n do weights[i][j]=0 end
    end
    for i,v in ipairs(baseline) do positions[index[v]]=i end
    for _,v in ipairs(x.before) do pred[index[v.to]]=pred[index[v.to]]|bits[index[v.from]] end
    for _,v in ipairs(x.votes) do
        local row=weights[index[v.from]]; local j=index[v.to]
        row[j]=row[j]+v.weight
    end
    local full=(1<<n)-1
    local count={[1]=0}
    for mask=1,full do
        local rest=mask&(mask-1)
        count[mask+1]=count[rest+1]+1
    end
    local sums={}
    for j=1,n do
        local row={[1]=0}; sums[j]=row
        for mask=1,full do
            local low=mask&(-mask)
            row[mask+1]=row[(mask~low)+1]+weights[j][bit_index[low]]
        end
    end
    local function optimize(bound, detailed)
        local cost={[full+1]=0}; local movement=detailed and {[full+1]=0} or nil
        for mask=full-1,0,-1 do
            local position=count[mask+1]+1
            local best,second=nil,nil
            for j=1,n do
                if mask&bits[j]==0 and mask&pred[j]==pred[j] then
                    local distance=math.abs(position-positions[j])
                    if distance<=bound then
                        local child=(mask|bits[j])+1
                        local suffix=cost[child]
                        if suffix~=nil then
                            local value=sums[j][mask+1]+suffix
                            local other=movement and distance+movement[child] or 0
                            if best==nil or value<best or (value==best and other<second) then
                                best,second=value,other
                            end
                        end
                    end
                end
            end
            cost[mask+1]=best
            if movement then movement[mask+1]=second end
        end
        return cost[1],cost,movement
    end
    local best=optimize(n,false)
    if best==nil then return nil end
    local low,high=0,math.max(0,n-1)
    while low<high do
        local middle=(low+high)//2
        if optimize(middle,false)==best then high=middle else low=middle+1 end
    end
    local _,cost,movement=optimize(low,true)
    local result={ok=true,revision=x.revision,penalty=best,worst=0,movement=movement[1],order={}}
    local mask=0
    for position=1,n do
        local found=false
        for j=1,n do
            local distance=math.abs(position-positions[j])
            if mask&bits[j]==0 and mask&pred[j]==pred[j] and distance<=low then
                local child=(mask|bits[j])+1
                if cost[child]~=nil and sums[j][mask+1]+cost[child]==cost[mask+1] and
                   distance+movement[child]==movement[mask+1] then
                    result.order[position]=x.items[j]
                    result.worst=math.max(result.worst,distance)
                    mask=mask|bits[j]; found=true; break
                end
            end
        end
        assert(found,"no optimum reconstruction")
    end
    return result
end
function Core.new()
    return setmetatable({revision=-1,result={revision=-1,order={}},baseline={}},Core)
end
function Core:plan(input)
    local request=normalize(input)
    if not request then return {ok=false,code="invalid_request"} end
    if request.revision<=self.revision then return {ok=false,code="stale_revision"} end
    local present,used,baseline={},{},{}
    for _,v in ipairs(request.items) do present[v]=true end
    for _,v in ipairs(self.result.order) do
        if present[v] then baseline[#baseline+1]=v; used[v]=true end
    end
    for _,v in ipairs(request.items) do if not used[v] then baseline[#baseline+1]=v end end
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
       dense(data.baseline,16)~=#request.items then invalid() end
    local available={}; for _,v in ipairs(request.items) do available[v]=true end
    for _,v in ipairs(data.baseline) do
        if not available[v] then invalid() end
        available[v]=nil
    end
    local result=solve(request,data.baseline)
    if not result or not same(result,data.result) then invalid() end
    self.revision=request.revision; self.request=request; self.baseline=copy(data.baseline); self.result=result
    return self
end
return Core
