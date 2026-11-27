-- Calls only isolated public-core states; never invokes a gameplay callback.
return function(M)
    local out={}
    local function copy(v)if type(v)~='table'then return v end;local r={};for k,x in pairs(v)do r[k]=copy(x)end;return r end
    local function event(id,kind,owner)return {id=id,kind=kind,owner=owner or 'a'}end
    local function apply(s,id,kind,owner)return M.apply(s,event(id,kind,owner))end
    local function initial()local s=M.new();apply(s,'a','add');apply(s,'d','discard');return s end
    local function run(name,fn)local ok,value=pcall(fn);out[name]=ok and value or {candidate_protocol_exception=tostring(value):sub(1,240)}end
    run('ownership',function()local s=initial();apply(s,'b','add','b');return {view=M.view(s),other=M.view(M.new())}end)
    run('duplicate',function()
        local s=initial();local first=apply(s,'d','discard');apply(s,'c','consume')
        local again=apply(s,'d','discard');local consumed=apply(s,'c','consume')
        return {first=first,again=again,consumed=consumed,view=M.view(s)}
    end)
    run('conflict',function()local s=initial();local before=copy(M.view(s));local r=apply(s,'d','consume');return {result=r,before=before,after=M.view(s)}end)
    run('invalid_atomic',function()
        local s=initial();local results={M.apply(s,{id='x',kind='discard',owner='a',extra=1}),apply(s,'x','unknown'),
            apply(s,'x','consume','missing'),apply(s,'x','add')}
        results[#results+1]=apply(s,'x','discard')
        return {results=results,view=M.view(s)}
    end)
    run('retired',function()
        local s=initial();local removed=apply(s,'r','remove');local old=apply(s,'a','add')
        return {removed=removed,replay=old,again=apply(s,'new','add'),missing=apply(s,'no','discard'),view=M.view(s)}
    end)
    run('cap_interleave',function()
        local views={}
        for reverse=1,2 do
            local s=M.new();apply(s,'a','add');apply(s,'b','add','b')
            for i=1,4 do
                if reverse==1 then apply(s,'a'..i,'discard');apply(s,'b'..i,'discard','b')
                else apply(s,'b'..i,'discard','b');apply(s,'a'..i,'discard')end
            end
            apply(s,'consume','consume');views[#views+1]=M.view(s)
        end
        return views
    end)
    run('snapshot_alias',function()
        local s=initial();local snap=M.snapshot(s);snap.events[2].kind='consume';snap.events[1].owner='changed'
        return {snapshot=M.snapshot(s),view=M.view(s)}
    end)
    run('view_alias',function()
        local s=initial();local v=M.view(s);v.seq=99;v.owners[1].charge=6;v.owners[1].id='changed'
        return M.view(s)
    end)
    run('receipt_alias',function()
        local s=initial();local r=apply(s,'d','discard');r.charge=99;r.seq=999
        return {receipt=apply(s,'d','discard'),view=M.view(s)}
    end)
    run('input_alias',function()
        local s=M.new();local e=event('a','add');M.apply(s,e);e.owner='changed';e.kind='remove'
        return {snapshot=M.snapshot(s),replay=apply(s,'a','add'),view=M.view(s)}
    end)
    run('restore_input',function()
        local src=initial();local snap=M.snapshot(src);local s=M.new();local result=M.restore(s,snap)
        snap.events[2].kind='consume';snap.events[1].owner='changed'
        return {result=result,view=M.view(s),snapshot=M.snapshot(s)}
    end)
    run('zero_restore',function()
        local src=initial();apply(src,'c','consume');apply(src,'b','add','b');local snap=M.snapshot(src)
        local s=initial();M.restore(s,snap);return {view=M.view(s),replay=apply(s,'c','consume'),snapshot=M.snapshot(s)}
    end)
    run('restored_history',function()
        local src=initial();apply(src,'c','consume');apply(src,'r','remove')
        local s=M.new();M.restore(s,M.snapshot(src))
        return {old=apply(s,'d','discard'),conflict=apply(s,'d','consume'),retired=apply(s,'new','add'),view=M.view(s)}
    end)
    run('restore_atomic',function()
        local s=initial();local bad={version=1,events={event('z','add','z'),event('no','discard','missing')}}
        local before=copy(M.snapshot(s));local result=M.restore(s,bad)
        return {result=result,before=before,after=M.snapshot(s),view=M.view(s),receipt=apply(s,'d','discard')}
    end)
    run('snapshot_validation',function()
        local s=initial();local results={}
        local bad={{version=2,events={}},{version=1,events={},extra=1},{version=1,events={[2]=event('a','add')}},
            {version=1,events={event('a','add'),event('a','add')}},{version='1',events={}}}
        for _,snapshot in ipairs(bad)do results[#results+1]=M.restore(s,snapshot)end
        return {results=results,view=M.view(s)}
    end)
    run('empty_restore',function()local s=initial();return {result=M.restore(s,{version=1,events={}}),view=M.view(s)}end)
    run('limit',function()
        local s=M.new();local events={event('a','add')}
        for i=2,4096 do events[i]=event('d'..i,'discard')end
        M.restore(s,{version=1,events=events})
        return {replay=apply(s,'d2','discard'),limit=apply(s,'overflow','consume'),view=M.view(s)}
    end)
    return out
end
