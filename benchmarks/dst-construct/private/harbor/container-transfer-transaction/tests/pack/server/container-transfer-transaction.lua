local function count(container, prefab)
    local total = 0
    for _, item in pairs(container.components.container.slots) do
        if item ~= nil and item.prefab == prefab then
            total = total + (item.components.stackable ~= nil and item.components.stackable:StackSize() or 1)
        end
    end
    return total
end

return function(ctx)
    ctx:case("world transfer component is attached", function()
        assert(TheWorld.ismastersim)
        assert(TheWorld.components.containertransfer ~= nil, "world is missing containertransfer")
    end)

    ctx:case("real container stacks transfer without loss", function()
        local service = assert(TheWorld.components.containertransfer)
        assert(type(service.Track) == "function" and type(service.Transfer) == "function")
        local source = assert(SpawnPrefab("treasurechest"))
        local destination = assert(SpawnPrefab("treasurechest"))
        source.Transform:SetPosition(0, 0, 0)
        destination.Transform:SetPosition(2, 0, 0)
        local twigs = assert(SpawnPrefab("twigs"))
        if twigs.components.stackable ~= nil then twigs.components.stackable:SetStackSize(5) end
        assert(source.components.container:GiveItem(twigs))
        assert(service:Track(source, "server-source") ~= false)
        assert(service:Track(destination, "server-destination") ~= false)
        local result = service:Transfer({
            request_id = "server-transfer",
            source_id = "server-source",
            destination_id = "server-destination",
            prefab = "twigs",
            count = 4,
        })
        assert(type(result) == "table" and result.ok == true, "server transfer failed")
        assert(count(source, "twigs") == 1 and count(destination, "twigs") == 4, "item conservation failed")
        source:Remove(); destination:Remove()
    end)

    ctx:case("transaction state reloads", function()
        local service = assert(TheWorld.components.containertransfer)
        assert(type(service.OnSave) == "function" and type(service.OnLoad) == "function")
        local data = service:OnSave()
        assert(type(data) == "table")
        service:OnLoad(data)
        assert(type(service.Recover) == "function")
        service:Recover()
    end)
end
