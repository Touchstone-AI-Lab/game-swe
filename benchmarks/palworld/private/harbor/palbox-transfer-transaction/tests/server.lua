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

    ctx:case("palbox transfer service is published", function()
        local published = service()
        assert(type(published.Track) == "function", "service is missing Track")
        assert(type(published.Transfer) == "function", "service is missing Transfer")
        assert(type(published.Recover) == "function", "service is missing Recover")
        assert(type(published.Save) == "function" and type(published.Load) == "function",
            "service is missing Save/Load")
    end)

    ctx:case("the server rejects untrusted transfer requests", function()
        local published = service()
        local same = published:Transfer({
            request_id = "headless-1",
            source_id = "headless-box",
            destination_id = "headless-box",
            pal_id = "lamball",
            count = 1,
        })
        assert(type(same) == "table" and same.ok == false, "a same-container transfer was accepted")
        local malformed = published:Transfer({
            request_id = "headless-2",
            source_id = "headless-box",
            destination_id = "headless-party",
            pal_id = "lamball",
            count = 0,
        })
        assert(malformed.ok == false, "a non-positive count was accepted")
        assert(published:Transfer(same).ok ~= true, "a rejected request became successful on retry")
    end)

    ctx:case("recovery and persistence survive a reload", function()
        local published = service()
        local recovered = published:Recover()
        assert(type(recovered) == "table" and recovered.ok == true, "Recover must succeed on a clean state")
        local data = published:Save()
        assert(type(data) == "table", "Save must return a table")
        published:Load(data)
        assert(published:Recover().ok == true, "Recover is not idempotent after a reload")
    end)
end
