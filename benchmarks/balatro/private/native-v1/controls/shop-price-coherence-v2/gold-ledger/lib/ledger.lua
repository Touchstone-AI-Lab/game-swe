return function(price)
    local M={}
    local fields={offer_id=true,base=true,category=true,price=true,version=true,protocol=true}
    local function copy(v)
        if type(v)~='table' then return v end
        local r={};for k,x in pairs(v)do r[k]=copy(x)end;return r
    end
    local function equal(a,b)
        if type(a)~=type(b)then return false end
        if type(a)~='table'then return a==b end
        for k,v in pairs(a)do if not equal(v,b[k])then return false end end
        for k in pairs(b)do if a[k]==nil then return false end end
        return true
    end
    local function id(v)return type(v)=='string' and #v>0 and #v<=64 end
    local function integer(v,lo)return type(v)=='number' and v==v and v>=lo and v<=1000000 and v==math.floor(v)end
    local function category(v)return v=='eligible_joker' or v=='other'end
    local function failure(code)return {ok=false,code=code}end
    local function valid_quote(q)
        if type(q)~='table'then return false end
        local count=0;for k in pairs(q)do if not fields[k]then return false end;count=count+1 end
        return count==6 and id(q.offer_id) and integer(q.base,1) and category(q.category)
            and integer(q.price,1) and integer(q.version,0) and q.protocol==2
    end

    local function project(log)
        local p={v=0,owners={},receipts={},offers={}}
        for _,e in ipairs(log)do
            if e.op=='add'then p.owners[e.owner]={id=e.owner,kind=e.kind,available=true};p.v=p.v+1
            elseif e.op=='remove'then p.owners[e.owner]=nil;p.v=p.v+1
            elseif e.op=='purchase'then
                local changed=false
                if e.quote.category=='eligible_joker'then
                    for _,v in pairs(p.owners)do
                        if v.kind=='coupon' and v.available then v.available=false;changed=true end
                    end
                end
                if changed then p.v=p.v+1 end
                p.receipts[e.tx]={money=e.money,quote=copy(e.quote),receipt={ok=true,debit=e.quote.price,version=p.v}}
                p.offers[e.quote.offer_id]=e.tx
            end
        end
        return p
    end
    function M.new()return {}end
    function M.view(log)
        local p=project(log);local a={}
        for _,v in pairs(p.owners)do a[#a+1]=v end
        table.sort(a,function(x,y)return x.id<y.id end)
        return {version=p.v,sources=a}
    end
    function M.add(log,owner,kind)
        if not id(owner) or not(kind=='flat' or kind=='ratio' or kind=='coupon')then return failure('INVALID')end
        local p=project(log);if p.owners[owner]then return failure('OWNER_EXISTS')end
        log[#log+1]={op='add',owner=owner,kind=kind};return {ok=true,version=p.v+1}
    end
    function M.remove(log,owner)
        if not id(owner)then return failure('INVALID')end
        local p=project(log);if not p.owners[owner]then return failure('OWNER_MISSING')end
        log[#log+1]={op='remove',owner=owner};return {ok=true,version=p.v+1}
    end
    function M.quote(log,offer,base,kind)
        if not id(offer) or not integer(base,1) or not category(kind)then return failure('INVALID')end
        local p=project(log)
        return {ok=true,quote={offer_id=offer,base=base,category=kind,price=price(base,kind,p.owners),version=p.v,protocol=2}}
    end
    function M.commit(log,tx,q,money)
        if not id(tx) or not integer(money,0) or not valid_quote(q)then return failure('INVALID')end
        local p=project(log);local old=p.receipts[tx]
        if old then
            if old.money==money and equal(old.quote,q)then return copy(old.receipt)end
            return failure('TRANSACTION_CONFLICT')
        end
        if p.offers[q.offer_id]then return failure('OFFER_COMMITTED')end
        if q.version~=p.v then return failure('STALE_QUOTE')end
        if q.price~=price(q.base,q.category,p.owners)then return failure('QUOTE_MISMATCH')end
        if money<q.price then return failure('INSUFFICIENT_FUNDS')end
        log[#log+1]={op='purchase',tx=tx,quote=copy(q),money=money}
        return project(log).receipts[tx].receipt
    end
    return M
end
