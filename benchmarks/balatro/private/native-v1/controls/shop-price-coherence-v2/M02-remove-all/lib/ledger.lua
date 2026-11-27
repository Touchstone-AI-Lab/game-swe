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
    function M.new()return {v=0,owners={},receipts={},offers={}}end
    function M.view(s)
        local sources={};for _,v in pairs(s.owners)do sources[#sources+1]=copy(v)end
        table.sort(sources,function(a,b)return a.id<b.id end)
        return {version=s.v,sources=sources}
    end
    function M.add(s,owner,kind)
        if not id(owner) or not (kind=='flat' or kind=='ratio' or kind=='coupon')then return failure('INVALID')end
        if s.owners[owner]then return failure('OWNER_EXISTS')end
        s.owners[owner]={id=owner,kind=kind,available=true};s.v=s.v+1
        return {ok=true,version=s.v}
    end
    function M.remove(s,owner)
        if not id(owner)then return failure('INVALID')end
        if not s.owners[owner]then return failure('OWNER_MISSING')end
        s.owners={};s.v=s.v+1;return {ok=true,version=s.v}
    end
    function M.quote(s,offer,base,kind)
        if not id(offer) or not integer(base,1) or not category(kind)then return failure('INVALID')end
        return {ok=true,quote={offer_id=offer,base=base,category=kind,
            price=price(base,kind,s.owners),version=s.v,protocol=2}}
    end
    function M.commit(s,tx,q,money)
        if not id(tx) or not integer(money,0) or not valid_quote(q)then return failure('INVALID')end
        local old=s.receipts[tx]
        if old then
            if old.money==money and equal(old.quote,q)then return copy(old.receipt)end
            return failure('TRANSACTION_CONFLICT')
        end
        if s.offers[q.offer_id]then return failure('OFFER_COMMITTED')end
        if q.version~=s.v then return failure('STALE_QUOTE')end
        if q.price~=price(q.base,q.category,s.owners)then return failure('QUOTE_MISMATCH')end
        if money<q.price then return failure('INSUFFICIENT_FUNDS')end
        local changed=false
        if q.category=='eligible_joker'then
            for _,source in pairs(s.owners)do
                if source.kind=='coupon' and source.available then source.available=false;changed=true end
            end
        end
        if changed then s.v=s.v+1 end
        local receipt={ok=true,debit=q.price,version=s.v}
        s.receipts[tx]={money=money,quote=copy(q),receipt=copy(receipt)};s.offers[q.offer_id]=tx
        return receipt
    end
    return M
end
