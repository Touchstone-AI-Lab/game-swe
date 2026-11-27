return function(ctx)
    ctx:case("real dedicated authority and the native hook API exist",function()
        local world=ctx.world or ctx.helpers.GetWorld()
        assert(world and world:IsValid())
        assert(ctx.helpers.GetKismetSystemLibrary():IsDedicatedServer(world))
        assert(type(RegisterHook)=="function" and type(UnregisterHook)=="function")
    end)
    ctx:case("server publishes the complete optimization service",function()
        assert(type(RheniumService)=="table")
        for _,name in ipairs({"Plan","Reset","Save","Load","Snapshot","Unmount"}) do assert(type(RheniumService[name])=="function",name) end
    end)
    ctx:case("server computes canonical plans and rejects infeasible updates atomically",function()
        local s=assert(RheniumService)
        assert(s:Reset().ok)
        local r=s:Plan({revision=0,items={"a","b","c","d"},votes={},before={{from="d",to="a"}}})
        assert(r.ok and r.penalty==0 and r.worst==2 and r.movement==6)
        assert(table.concat(r.order,",")=="b,d,a,c")
        local stable=s:Plan({revision=1,items={"d","c","b","a"},votes={},before={}})
        assert(stable.ok and stable.worst==0 and table.concat(stable.order,",")=="b,d,a,c")
        local bad=s:Plan({revision=2,items={"a","b"},votes={},before={{from="a",to="b"},{from="b",to="a"}}})
        assert(not bad.ok and bad.code=="infeasible" and s:Snapshot().revision==1)
    end)
    ctx:case("recovery validates certificates and unmount stops mutation",function()
        local s=assert(RheniumService)
        local function equal(a,b)
            if type(a)~=type(b) then return false end
            if type(a)~="table" then return a==b end
            for k,v in pairs(a) do if not equal(v,b[k]) then return false end end
            for k in pairs(b) do if a[k]==nil then return false end end
            return true
        end
        local before=s:Snapshot()
        local saved=s:Save()
        assert(saved.version==1 and s:Reset().ok and s:Load(saved).ok)
        assert(equal(before,s:Snapshot()))
        saved.result.revision=999
        assert(not pcall(function() s:Load(saved) end),"forged certificate accepted")
        assert(equal(before,s:Snapshot()),"failed Load mutated the service")
        s:Unmount(); s:Unmount()
        assert(s:Plan({}).code=="unmounted" and s:Reset().code=="unmounted")
        assert(equal(before,s:Snapshot()))
    end)
end
