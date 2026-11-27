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
    end)

    ctx:case("guild storage service is published", function()
        local published = service()
        assert(type(published.Claim) == "function", "service is missing Claim")
        assert(type(published.Save) == "function" and type(published.Load) == "function",
            "service is missing Save/Load")
        assert(type(published.BeginCycle) == "function", "service is missing BeginCycle")
    end)

    ctx:case("the server resolves quotas and rolls back failed delivery", function()
        local published = service()
        published:BeginCycle(1)
        local granted = published:Claim("headless-member", "headless-1", "basic")
        assert(type(granted) == "table", "Claim must return a table")
        assert(granted.ok ~= nil, "Claim must report ok")
        local retry = published:Claim("headless-member", "headless-1", "basic")
        assert(retry.duplicate == true, "a retried request was not deduplicated on the server")
        local forged = published:Claim("headless-member", "headless-2", "not-a-real-bundle")
        assert(forged.ok == false, "an unknown bundle was accepted by the server")
    end)

    ctx:case("guild storage state reloads", function()
        local published = service()
        local data = published:Save()
        assert(type(data) == "table", "Save must return a table")
        published:Load(data)
        assert(type(published:Save()) == "table", "Load did not restore a serialisable state")
    end)
end
