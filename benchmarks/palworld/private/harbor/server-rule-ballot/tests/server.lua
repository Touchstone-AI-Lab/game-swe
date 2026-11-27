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
        assert(type(ExecuteWithDelay) == "function", "the UE4SS delayed execution API is unavailable")
    end)

    ctx:case("rule ballot service is published", function()
        local published = service()
        assert(type(published.Open) == "function", "service is missing Open")
        assert(type(published.Cast) == "function", "service is missing Cast")
        assert(type(published.Close) == "function", "service is missing Close")
        assert(type(published.Save) == "function" and type(published.Load) == "function",
            "service is missing Save/Load")
    end)

    ctx:case("the server derives voter identity and settles a ballot", function()
        local published = service()
        local opened = published:Open({
            id = "headless-rule",
            choices = { "off", "on" },
            deadline_seconds = 60,
            quorum = 2,
        }, { "headless-a", "headless-b" })
        assert(type(opened) == "table" and opened.ok == true, "Open failed on the dedicated server")
        assert(published:CastAs("headless-a", "headless-rule", "on", 1).ok == true, "a frozen voter was rejected")
        assert(published:CastAs("headless-b", "headless-rule", "on", 1).ok == true, "a frozen voter was rejected")
        assert(published:CastAs("headless-outsider", "headless-rule", "on", 1).ok == false,
            "a non-voter was accepted")
        local result = published:Close("headless-rule")
        assert(type(result) == "table" and result.status == "passed" and result.choice_id == "on",
            "the ballot did not settle deterministically")
    end)

    ctx:case("ballot state reloads", function()
        local published = service()
        local data = published:Save()
        assert(type(data) == "table", "Save must return a table")
        published:Load(data)
        assert(type(published:Save()) == "table", "Load did not restore a serialisable state")
    end)
end
