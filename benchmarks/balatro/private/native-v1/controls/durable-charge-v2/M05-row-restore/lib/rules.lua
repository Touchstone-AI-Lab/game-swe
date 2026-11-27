local R={}
function R.copy(v)
    if type(v)~='table' then return v end
    local out={};for k,x in pairs(v)do out[k]=R.copy(x)end;return out
end
function R.exact(v,names)
    if type(v)~='table' or getmetatable(v)~=nil then return false end
    local n=0;for k in pairs(v)do if not names[k]then return false end;n=n+1 end
    local expected=0;for _ in pairs(names)do expected=expected+1 end
    return n==expected
end
function R.id(s)return type(s)=='string' and #s>0 and #s<=96 and s:match('^[%w_.:-]+$')~=nil end
function R.valid(e)
    return R.exact(e,{id=true,kind=true,owner=true}) and R.id(e.id) and R.id(e.owner)
        and (e.kind=='add' or e.kind=='remove' or e.kind=='discard' or e.kind=='consume')
end
function R.error(code)return {ok=false,code=code}end
function R.empty()return {history={},owners={},retired={},receipts={}}end
function R.step(d,e)
    if not R.valid(e)then return R.error('INVALID')end
    local prior=d.receipts[e.id]
    if prior then
        if prior.event.kind~=e.kind or prior.event.owner~=e.owner then return R.error('EVENT_CONFLICT')end
        return R.copy(prior.result)
    end
    local old=d.owners[e.owner]
    if e.kind=='add' then
        if old~=nil then return R.error('OWNER_EXISTS')end
        if d.retired[e.owner]then return R.error('OWNER_RETIRED')end
    elseif old==nil then return R.error('OWNER_MISSING')end
    if #d.history>=4096 then return R.error('LIMIT')end
    local value=0;local active=e.kind~='remove'
    if e.kind=='discard'then value=math.min(6,old+2)end
    if active then d.owners[e.owner]=value else d.owners[e.owner]=nil;d.retired[e.owner]=true end
    d.history[#d.history+1]=R.copy(e)
    local receipt={ok=true,seq=#d.history,charge=value,active=active}
    d.receipts[e.id]={event=R.copy(e),result=R.copy(receipt)}
    return receipt
end
function R.view(d)
    local ids={};for id in pairs(d.owners)do ids[#ids+1]=id end;table.sort(ids)
    local owners={};for _,id in ipairs(ids)do owners[#owners+1]={id=id,charge=d.owners[id]}end
    return {seq=#d.history,owners=owners}
end
function R.import(snapshot)
    if type(snapshot)=='table' and type(snapshot.version)=='number' and snapshot.version~=1 then
        return nil,R.error('UNSUPPORTED_VERSION')
    end
    if not R.exact(snapshot,{version=true,events=true}) or snapshot.version~=1
        or type(snapshot.events)~='table' or getmetatable(snapshot.events)~=nil then
        return nil,R.error('SNAPSHOT_INVALID')
    end
    local n=0;for k in pairs(snapshot.events)do
        if type(k)~='number' or k%1~=0 or k<1 or k>4096 then return nil,R.error('SNAPSHOT_INVALID')end
        n=n+1
    end
    local d=R.empty()
    for i=1,n do
        local e=snapshot.events[i]
        if not R.valid(e) or d.receipts[e.id]then return nil,R.error('SNAPSHOT_INVALID')end
        local r=R.step(d,e);if not r.ok then return nil,R.error('SNAPSHOT_INVALID')end
    end
    return d,{ok=true}
end
return R
