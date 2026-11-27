-- Isolated public-core protocol calls; these are not native gameplay claims.
return function(M)
    local cases={}
    local function copy(v)
        if type(v)~='table'then return v end
        local r={};for k,x in pairs(v)do r[k]=copy(x)end;return r
    end
    local function run(name,fn)
        local ok,value=pcall(fn)
        cases[name]=ok and value or {candidate_protocol_exception=tostring(value):sub(1,240)}
    end
    local function one(kind)
        local s=M.new();M.add(s,'owner',kind);return s
    end
    run('formula',function()
        local values={}
        for f=0,2 do for r=0,2 do for c=0,2 do
            local s=M.new()
            for i=1,f do M.add(s,'f'..i,'flat')end
            for i=1,r do M.add(s,'r'..i,'ratio')end
            for i=1,c do M.add(s,'c'..i,'coupon')end
            for b=1,25 do
                values[#values+1]=M.quote(s,'item',b,'eligible_joker').quote.price
                values[#values+1]=M.quote(s,'item',b,'other').quote.price
            end
        end end end
        return values
    end)
    run('ownership',function()
        local s=M.new();M.add(s,'a','flat');M.add(s,'b','ratio');M.add(s,'c','coupon');M.remove(s,'b')
        return M.view(s)
    end)
    run('pure_query',function()
        local s=one('coupon');local before=M.view(s);local prices={}
        for i=1,4 do prices[i]=M.quote(s,'i'..i,10,'eligible_joker').quote.price end
        return {before=before,after=M.view(s),prices=prices}
    end)
    run('view_alias',function()
        local s=one('coupon');local view=M.view(s);view.version=999;view.sources[1].available=false;view.sources[1].kind='flat'
        return {view=M.view(s),price=M.quote(s,'offer',10,'eligible_joker').quote.price}
    end)
    run('versions',function()
        local s=one('coupon');M.add(s,'other','coupon')
        local q=M.quote(s,'first',10,'eligible_joker').quote
        local result=M.commit(s,'tx',q,20)
        return {receipt=result,view=M.view(s),next_price=M.quote(s,'next',10,'eligible_joker').quote.price}
    end)
    run('noneligible',function()
        local s=one('coupon');M.add(s,'flat','flat')
        local q=M.quote(s,'planet',3,'other').quote
        return {receipt=M.commit(s,'tx',q,20),view=M.view(s),next_price=M.quote(s,'joker',8,'eligible_joker').quote.price}
    end)
    run('stale',function()
        local s=M.new();local q=M.quote(s,'planet',3,'other').quote;M.add(s,'owner','flat')
        local before=M.view(s);local result=M.commit(s,'tx',q,20)
        return {result=result,before=before,after=M.view(s)}
    end)
    run('funds_atomic',function()
        local s=one('coupon');local q=M.quote(s,'item',10,'eligible_joker').quote
        local before=M.view(s);local refused=M.commit(s,'tx',q,0);local after=M.view(s)
        return {refused=refused,before=before,after=after,retry=M.commit(s,'tx',q,20)}
    end)
    run('quote_atomic',function()
        local s=one('coupon');local q=M.quote(s,'item',10,'eligible_joker').quote;local forged=copy(q);forged.price=1
        local before=M.view(s);local refused=M.commit(s,'tx',forged,20);local after=M.view(s)
        return {refused=refused,before=before,after=after,retry=M.commit(s,'tx',q,20)}
    end)
    run('dedup',function()
        local s=one('coupon');local q=M.quote(s,'item',10,'eligible_joker').quote
        local first=M.commit(s,'tx',q,20);M.add(s,'flat','flat')
        local repeated=M.commit(s,'tx',copy(q),20);local conflict=M.commit(s,'tx',copy(q),21)
        local next_quote=M.quote(s,'item',10,'eligible_joker').quote
        local other=M.commit(s,'different',next_quote,20)
        return {first=first,repeated=repeated,conflict=conflict,other=other,view=M.view(s)}
    end)
    run('receipt_alias',function()
        local s=one('coupon');local q=M.quote(s,'item',10,'eligible_joker').quote;local original=copy(q)
        local receipt=M.commit(s,'tx',q,20);q.price=777;q.offer_id='changed';receipt.debit=999;receipt.version=777
        return {repeated=M.commit(s,'tx',original,20),view=M.view(s)}
    end)
    run('invalid_atomic',function()
        local s=M.new();local q=M.quote(s,'item',10,'eligible_joker').quote;local extra=copy(q);extra.bad=true
        local results={M.add(s,'','flat'),M.add(s,'valid','unknown'),M.remove(s,'absent'),
            M.quote(s,'item',0,'eligible_joker'),M.quote(s,'item',1,'unknown'),M.commit(s,'tx',extra,20),M.commit(s,'tx',q,-1)}
        M.add(s,'owner','flat');results[#results+1]=M.add(s,'owner','coupon')
        return {results=results,view=M.view(s)}
    end)
    run('order',function()
        local definitions={{'a','flat'},{'b','ratio'},{'c','ratio'},{'d','coupon'}};local values={}
        for shift=0,3 do
            local s=M.new()
            for j=1,4 do local d=definitions[(j+shift-1)%4+1];M.add(s,d[1],d[2])end
            values[#values+1]=M.quote(s,'item',10,'eligible_joker').quote.price
        end
        return values
    end)
    return cases
end
