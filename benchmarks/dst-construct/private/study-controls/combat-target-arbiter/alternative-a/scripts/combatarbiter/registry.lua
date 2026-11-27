-- Two-way map between live entities and their stable ids. The registry owns
-- the three engine listeners of every entity it holds and hands the events to
-- the callbacks it was created with; each binding keeps its own function
-- objects so that exactly those objects are unregistered again.

local Registry = {}

function Registry.new(handlers)
    local by_entity = {}
    local by_id = {}
    local registry = {}

    function registry.id_of(entity)
        local binding = entity ~= nil and by_entity[entity] or nil
        return binding ~= nil and binding.id or nil
    end

    function registry.entity_of(id)
        local binding = id ~= nil and by_id[id] or nil
        return binding ~= nil and binding.entity or nil
    end

    function registry.release(entity)
        local binding = by_entity[entity]
        if binding == nil then
            return nil
        end
        by_entity[entity] = nil
        by_id[binding.id] = nil
        entity:RemoveEventCallback("attacked", binding.attacked)
        entity:RemoveEventCallback("death", binding.death)
        entity:RemoveEventCallback("onremove", binding.onremove)
        return binding.id
    end

    function registry.bind(entity, id)
        local binding = { entity = entity, id = id }
        binding.attacked = function(_, data)
            handlers.attacked(entity, id, data)
        end
        binding.death = function()
            handlers.death(entity, id)
        end
        binding.onremove = function()
            handlers.removed(entity, id)
        end
        entity:ListenForEvent("attacked", binding.attacked)
        entity:ListenForEvent("death", binding.death)
        entity:ListenForEvent("onremove", binding.onremove)
        by_entity[entity] = binding
        by_id[id] = binding
    end

    -- Ids in lexical order, so callers never depend on table iteration.
    function registry.ids()
        local ids = {}
        for id in pairs(by_id) do
            ids[#ids + 1] = id
        end
        table.sort(ids)
        return ids
    end

    function registry.release_all()
        local ids = registry.ids()
        for index = 1, #ids do
            registry.release(by_id[ids[index]].entity)
        end
        return ids
    end

    return registry
end

return Registry
