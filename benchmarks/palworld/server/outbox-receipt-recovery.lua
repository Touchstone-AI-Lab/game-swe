return function(ctx)
    ctx:case("dedicated server world and documented API are available",function()
        local world=ctx.world or ctx.helpers.GetWorld()
        assert(world and world:IsValid())
        assert(ctx.helpers.GetKismetSystemLibrary():IsDedicatedServer(world))
        assert(type(ExecuteInGameThread)=="function")
    end)
    ctx:case("service exposes complete trusted protocol",function()
        assert(type(RheniumService)=="table")
        for _,name in ipairs({"Submit","Drain","Status","Reset","Save","Load","Snapshot","Unmount"}) do assert(type(RheniumService[name])=="function",name) end
    end)
    ctx:case("server executes distinguishing protocol sequence",function()
        local s=assert(RheniumService)
        assert(s:Reset().ok)

        local stored,receipt,delivered=nil,"absent",0
        local journal=function(data) stored=data; return true end
        local adapter={lookup=function() return receipt end,deliver=function()
            delivered=delivered+1; receipt="applied"; return "unknown" end}
        assert(s:Submit({id="r",member="m",bundle="food",count=1},journal).ok)
        assert(s:Drain(adapter,journal).code=="delivery_uncertain")
        s:Load(stored)
        assert(s:Drain(adapter,journal).completed==1 and delivered==1)
        assert(s:Status("r").state=="applied")

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
