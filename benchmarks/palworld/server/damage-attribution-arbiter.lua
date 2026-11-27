local function service()
    local published = rawget(_G, "RheniumService")
    assert(type(published) == "table", "main.lua did not publish RheniumService on the dedicated server")
    return published
end

return function(ctx)
    ctx:case("dedicated server context is available", function()
        local helpers = assert(ctx.helpers, "UEHelpers is unavailable")
        local world = ctx.world or helpers.GetWorld()
        assert(world ~= nil and world:IsValid(), "the dedicated server world is unavailable")
        -- Palworld's shipping build strips UGameplayStatics::IsDedicatedServer,
        -- so authority is read from UKismetSystemLibrary instead.
        local kismet = assert(helpers.GetKismetSystemLibrary(), "UKismetSystemLibrary is unavailable")
        assert(kismet:IsDedicatedServer(world), "suite is not running on a dedicated server")
        assert(type(FindFirstOf) == "function", "the UE4SS object lookup API is unavailable")
        assert(type(NotifyOnNewObject) == "function", "the UE4SS object notification API is unavailable")
    end)

    ctx:case("damage arbiter service is published", function()
        local published = service()
        assert(type(published.Observe) == "function", "service is missing Observe")
        assert(type(published.Resolve) == "function", "service is missing Resolve")
        assert(type(published.Sweep) == "function", "service is missing Sweep")
        assert(type(published.Save) == "function" and type(published.Load) == "function",
            "service is missing Save/Load")
    end)

    ctx:case("out-of-order reports resolve deterministically on the server", function()
        local published = service()
        local target = "headless-boss"
        assert(published:Observe({ sequence = 2, attacker_id = "b", target_id = target, amount = 30, tick = 2 }).ok)
        assert(published:Observe({ sequence = 1, attacker_id = "a", target_id = target, amount = 10, tick = 1 }).ok)
        assert(published:Observe({ sequence = 3, attacker_id = "a", target_id = target, amount = 25, tick = 3 }).ok)
        local repeated = published:Observe({ sequence = 3, attacker_id = "a", target_id = target, amount = 25, tick = 3 })
        assert(repeated.duplicate == true, "a repeated sequence was applied on the server")
        local resolved = published:Resolve(target)
        assert(type(resolved) == "table" and resolved.ok == true, "Resolve failed on the dedicated server")
        assert(resolved.attacker_id == "a" and resolved.total == 35, "attribution is not deterministic")
        assert(published:Observe({ sequence = 4, attacker_id = "b", target_id = target, amount = 500, tick = 4 }).ok == false,
            "a resolved target accepted another report")
    end)

    ctx:case("arbiter state reloads", function()
        local published = service()
        local data = published:Save()
        assert(type(data) == "table", "Save must return a table")
        published:Load(data)
        assert(type(published:Save()) == "table", "Load did not restore a serialisable state")
    end)
end
