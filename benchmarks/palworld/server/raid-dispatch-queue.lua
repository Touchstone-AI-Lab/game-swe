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
        assert(type(LoopAsync) == "function", "the UE4SS asynchronous loop API is unavailable")
    end)

    ctx:case("raid dispatch service is published", function()
        local published = service()
        assert(type(published.Enqueue) == "function", "service is missing Enqueue")
        assert(type(published.Lease) == "function", "service is missing Lease")
        assert(type(published.Sweep) == "function", "service is missing Sweep")
        assert(type(published.Save) == "function" and type(published.Load) == "function",
            "service is missing Save/Load")
    end)

    ctx:case("leases are handed out and swept on the server", function()
        local published = service()
        local queued = published:Enqueue("headless-1", "headless-member", 5)
        assert(type(queued) == "table" and queued.ok == true, "Enqueue failed on the dedicated server")
        assert(published:Enqueue("headless-1", "headless-member", 5).duplicate == true,
            "a duplicate request was queued twice")
        local lease = published:Lease("headless-worker")
        assert(type(lease) == "table" and lease.ok == true, "Lease failed on the dedicated server")
        assert(lease.request_id == "headless-1", "the wrong request was leased")
        assert(published:Lease("headless-worker").ok == false, "one worker held two leases")
        assert(type(published:Sweep()) == "table", "Sweep must return a table")
    end)

    ctx:case("dispatch state reloads", function()
        local published = service()
        local data = published:Save()
        assert(type(data) == "table", "Save must return a table")
        published:Load(data)
        assert(type(published:Save()) == "table", "Load did not restore a serialisable state")
    end)
end
