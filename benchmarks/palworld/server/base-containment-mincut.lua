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
        local r=s:Plan({revision=0,nodes={{id="a",cost0=9,cost1=0},{id="b",cost0=0,cost1=8}},arcs={{id="bridge",from="a",to="b",penalty=20}},requires={}})
        assert(r.ok and r.energy==8 and r.labels[1].label==1 and r.labels[2].label==1)
        local stable=s:Plan({revision=1,nodes={{id="a",cost0=0,cost1=0},{id="b",cost0=0,cost1=0}},arcs={},requires={}})
        assert(stable.ok and stable.changes==0 and stable.labels[1].label==1 and stable.labels[2].label==1)
        local bad=s:Plan({revision=2,nodes={{id="a",cost0=0,cost1=0,locked=1},{id="b",cost0=0,cost1=0,locked=0}},arcs={},requires={{from="a",to="b"}}})
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
