local function voter(id)
    local entity = CreateEntity()
    entity.entity:AddTransform()
    entity:AddTag("player")
    entity.userid = id
    return entity
end

return function(ctx)
    ctx:case("server ballot component is attached", function()
        assert(TheWorld.ismastersim)
        assert(TheWorld.components.ruleballot ~= nil, "world is missing ruleballot")
    end)

    ctx:case("component derives voter identity and closes a ballot", function()
        local service = assert(TheWorld.components.ruleballot)
        assert(type(service.Open) == "function" and type(service.Cast) == "function")
        assert(type(service.Close) == "function")
        local a, b = voter("server-a"), voter("server-b")
        local now = GetTime()
        local opened = service:Open({
            id = "server-rule",
            choices = { "off", "on" },
            deadline = now + 20,
            quorum = 2,
        }, { a, b })
        assert(type(opened) == "table" and opened.ok == true)
        assert(service:Cast(a, "server-rule", "on", 1).ok == true)
        assert(service:Cast(b, "server-rule", "on", 1).ok == true)
        local result = service:Close("server-rule")
        assert(type(result) == "table" and result.status == "passed" and result.choice_id == "on")
        a:Remove(); b:Remove()
    end)

    ctx:case("ballot state reloads", function()
        local service = assert(TheWorld.components.ruleballot)
        local data = service:OnSave(); assert(type(data) == "table")
        service:OnLoad(data)
        assert(type(service:OnSave()) == "table")
    end)
end
