-- Fresh opaque core states; protocol tests are separate from native actions.
return function(M)
    local out={}
    local function copy(v)if type(v)~='table'then return v end;local r={};for k,x in pairs(v)do r[k]=copy(x)end;return r end
    local function full(s,id)
        id=id or 's';M.begin(s,id);M.register(s,id,id..'a',3);M.register(s,id,id..'b',5);M.register(s,id,id..'c',7);return s
    end
    local function run(name,fn)local ok,value=pcall(fn);out[name]=ok and value or {candidate_protocol_exception=tostring(value):sub(1,240)}end
    run('pure',function()local s=full(M.new());return {before=copy(M.view(s)),again=M.begin(s,'s'),duplicate=M.register(s,'s','sa',3),after=M.view(s),other=M.view(M.new())}end)
    run('two_choices',function()
        local s=full(M.new());local first=M.commit(s,'s','sb','t1');local second=M.commit(s,'s','sc','t2');M.close(s,'s')
        local pending=copy(M.view(s));local payments={M.settle(s,'t2'),M.settle(s,'t1')}
        return {first=first,second=second,pending=pending,payments=payments,view=M.view(s)}
    end)
    run('close_pending',function()
        local s=full(M.new());M.commit(s,'s','sb','t');M.close(s,'s');local before=copy(M.view(s))
        local close=M.close(s,'s');local payment=M.settle(s,'t');local repeated=M.settle(s,'t')
        return {before=before,close=close,payment=payment,repeated=repeated,view=M.view(s)}
    end)
    run('skip',function()local s=full(M.new());M.close(s,'s');return M.view(s)end)
    run('next_session',function()local s=full(M.new());M.close(s,'s');full(s,'u');M.commit(s,'u','ua','t');M.settle(s,'t');return M.view(s)end)
    run('commit_replay',function()
        local s=full(M.new());local first=M.commit(s,'s','sa','t');M.settle(s,'t');M.close(s,'s')
        local again=M.commit(s,'s','sa','t');local conflict=M.commit(s,'s','sb','t')
        return {first=first,again=again,conflict=conflict,view=M.view(s)}
    end)
    run('selected_atomic',function()
        local s=full(M.new());M.commit(s,'s','sa','t');local before=copy(M.view(s));local result=M.commit(s,'s','sa','new')
        local after=copy(M.view(s));local reuse=M.commit(s,'s','sb','new')
        return {result=result,before=before,after=after,reuse=reuse,view=M.view(s)}
    end)
    run('limits',function()
        local s=full(M.new());local results={M.register(s,'s','extra',3),M.register(s,'s','sa',5),M.commit(s,'s','absent','x')}
        M.commit(s,'s','sa','a');M.commit(s,'s','sb','b')
        results[#results+1]=M.commit(s,'s','sc','x');results[#results+1]=M.register(s,'s','extra',3)
        return {results=results,view=M.view(s)}
    end)
    run('incomplete',function()
        local s=M.new();M.begin(s,'s');M.register(s,'s','sa',3);local before=copy(M.view(s));local result=M.commit(s,'s','sa','t')
        M.register(s,'s','sb',5);M.register(s,'s','sc',7);local reuse=M.commit(s,'s','sa','t')
        return {before=before,result=result,reuse=reuse,view=M.view(s)}
    end)
    run('invalid',function()
        local s=full(M.new());return {results={M.begin(s,''),M.register(s,'s','x',4),M.commit(s,'s','sa',{}),M.close(s,false),M.close(s,'missing'),M.settle(s,'missing')},view=M.view(s)}
    end)
    run('view_alias',function()
        local s=full(M.new());M.commit(s,'s','sa','t');local v=M.view(s)
        v.paid=999;v.sessions[1].remaining=9;v.sessions[1].previews[1].selected=false;v.tickets[1].settled=true
        return M.view(s)
    end)
    run('receipt_alias',function()
        local s=full(M.new());local r=M.commit(s,'s','sa','t');r.amount=99;r.ticket='changed'
        return {replay=M.commit(s,'s','sa','t'),view=M.view(s)}
    end)
    run('closed',function()
        local s=full(M.new());M.close(s,'s');return {commit=M.commit(s,'s','sa','t'),register=M.register(s,'s','extra',3),begin=M.begin(s,'s'),view=M.view(s)}
    end)
    run('interleave',function()
        local s=full(M.new());full(s,'u');M.commit(s,'s','sa','a');M.commit(s,'u','uc','c');M.close(s,'u');M.settle(s,'a');M.settle(s,'c')
        return {conflict=M.register(s,'u','sa',3),view=M.view(s)}
    end)
    return out
end
