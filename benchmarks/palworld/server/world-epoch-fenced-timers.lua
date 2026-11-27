return function(ctx)
    ctx:case("dedicated server world and documented API are available",function()
        local world=ctx.world or ctx.helpers.GetWorld()
        assert(world and world:IsValid())
        assert(ctx.helpers.GetKismetSystemLibrary():IsDedicatedServer(world))
        assert(type(ExecuteInGameThread)=="function")
    end)
    ctx:case("service exposes complete trusted protocol",function()
        assert(type(RheniumService)=="table")
        for _,name in ipairs({"Mount","Schedule","Poll","Ack","Cancel","Reset","Save","Load","Snapshot","Unmount"}) do assert(type(RheniumService[name])=="function",name) end
    end)
    ctx:case("server executes distinguishing protocol sequence",function()
        local s=assert(RheniumService)
        assert(s:Reset().ok)

        assert(s:Mount(1,0).ok)
        assert(s:Schedule({id="x",payload="reward",due=5}).ok)
        local old=s:Poll(1,5).deliveries[1]
        assert(s:Ack(old,false).ok)
        local current=s:Poll(1,5).deliveries[1]
        assert(s:Ack(old,true).code=="stale_token")
        assert(s:Mount(2,5).ok)
        assert(s:Ack(current,true).code=="stale_epoch")
        assert(s:Poll(2,5).deliveries[1].generation==3)

    end)
    ctx:case("server saves and restores the protocol without silent reset",function()
        local s=assert(RheniumService)
        local before=s:Snapshot()
        local saved=s:Save()
        assert(saved.version==1)
        assert(s:Load(saved).ok)
        local function equal(a,b)
            if type(a)~=type(b) then return false end
            if type(a)~="table" then return a==b end
            for k,v in pairs(a) do if not equal(v,b[k]) then return false end end
            for k in pairs(b) do if a[k]==nil then return false end end
            return true
        end
        assert(equal(before,s:Snapshot()),"Load discarded protocol state")
        saved.version=999
        assert(not pcall(function() s:Load(saved) end))
        assert(equal(before,s:Snapshot()),"failed Load mutated service")
    end)
end
