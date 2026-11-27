local Registry = include("rhenium_prop_registry/registry.lua")

local Server = {}
local registry = nil
local installed = false
local players = {}
local entities = {}
local entity_objects = {}
local hook_prefix = "rhenium_prop_registry"
local timer_name = "rhenium_prop_registry/tick"

local function valid_player(ply)
    return IsValid(ply) and ply:IsPlayer()
end

local function valid_entity(entity)
    return IsValid(entity) and entity:GetClass() == "prop_physics"
end

local function valid_id(value)
    return isstring(value) and #value >= 1 and #value <= 128
        and string.match(value, "^[A-Za-z0-9][A-Za-z0-9_.:%-]*$") ~= nil
end

local function valid_revision(value)
    return isnumber(value) and value == math.floor(value) and value >= 1
end

local function identity(entity)
    return entities[entity]
end

local function player_id(ply)
    return players[ply]
end

local function remove_runtime_entities(removed)
    for _, item in ipairs(removed or {}) do
        local key = item.entity_id .. "@" .. item.revision
        local entity = entity_objects[key]
        entity_objects[key] = nil
        if IsValid(entity) then entity:Remove() end
    end
end

local function tick()
    if registry == nil then return end
    local ok, _, data = registry:tick(CurTime())
    if ok then remove_runtime_entities(data.removed) end
end

function Server.BindPlayer(ply, logical_id)
    if not installed or not valid_player(ply) or not valid_id(logical_id) then
        return false, "invalid_player"
    end
    players[ply] = logical_id
    return registry:reconnect(logical_id, CurTime())
end

function Server.BindEntity(entity, entity_id, revision)
    if not installed or not valid_entity(entity) or not valid_id(entity_id)
        or not valid_revision(revision) then
        return false, "invalid_entity"
    end
    local old = entities[entity]
    if old ~= nil then entity_objects[old.entity_id .. "@" .. old.revision] = nil end
    local value = { entity_id = entity_id, revision = revision }
    entities[entity] = value
    entity_objects[entity_id .. "@" .. revision] = entity
    return true, "bound"
end

function Server.RegisterProp(ply, entity, request_id)
    if not installed then return false, "not_installed", {} end
    local owner = player_id(ply)
    if owner == nil or not valid_entity(entity) then return false, "invalid_context", {} end
    local value = identity(entity)
    if value == nil then
        local sequence = registry.next_entity_sequence
        registry.next_entity_sequence = sequence + 1
        Server.BindEntity(entity, "prop:" .. sequence, 1)
        value = identity(entity)
    end
    local ok, code, data = registry:register(
        request_id, owner, value.entity_id, value.revision
    )
    if not ok and code == "quota_exceeded" and IsValid(entity) then
        entities[entity] = nil
        entity_objects[value.entity_id .. "@" .. value.revision] = nil
        entity:Remove()
    end
    return ok, code, data
end

local function can_modify(ply, entity, operation)
    if not installed then return false end
    local owner = player_id(ply)
    local value = identity(entity)
    if owner == nil or value == nil then return false end
    local allowed = registry:can_modify(owner, value.entity_id, value.revision, operation)
    return allowed
end

function Server.HandleDeleteRequest(ply, entity, request_id, _untrusted_owner_id)
    if not can_modify(ply, entity, "delete") then return false, "not_owner", {} end
    local value = identity(entity)
    local ok, code, data = registry:remove(request_id, value.entity_id, value.revision)
    if ok then
        entities[entity] = nil
        entity_objects[value.entity_id .. "@" .. value.revision] = nil
        if IsValid(entity) then entity:Remove() end
    end
    return ok, code, data
end

function Server.Snapshot()
    if registry == nil then return nil, "not_installed" end
    tick()
    return registry:snapshot(CurTime())
end

function Server.Save()
    if registry == nil then return nil, "not_installed" end
    return registry:save(CurTime())
end

local function remove_hooks()
    hook.Remove("PhysgunPickup", hook_prefix .. ".PhysgunPickup")
    hook.Remove("CanTool", hook_prefix .. ".CanTool")
    hook.Remove("CanProperty", hook_prefix .. ".CanProperty")
    hook.Remove("EntityRemoved", hook_prefix .. ".EntityRemoved")
    hook.Remove("PlayerDisconnected", hook_prefix .. ".PlayerDisconnected")
    hook.Remove("PlayerInitialSpawn", hook_prefix .. ".PlayerInitialSpawn")
end

function Server.Shutdown()
    if not installed then return true, "shutdown" end
    remove_hooks()
    timer.Remove(timer_name)
    if registry ~= nil then registry:shutdown() end
    registry = nil
    installed = false
    players = {}
    entities = {}
    entity_objects = {}
    return true, "shutdown"
end

function Server.Install(options)
    if installed then return Server end
    options = options or {}
    local core_options = {
        max_props = options.max_props or 2,
        cleanup_delay = options.cleanup_delay or 5,
        state = options.state,
        storage = options.storage,
    }
    registry = assert(Registry.new(core_options))
    installed = true
    hook.Add("PhysgunPickup", hook_prefix .. ".PhysgunPickup", function(ply, entity)
        if identity(entity) ~= nil then return can_modify(ply, entity, "physgun") end
    end)
    hook.Add("CanTool", hook_prefix .. ".CanTool", function(ply, trace, _tool)
        local entity = trace and trace.Entity or nil
        if identity(entity) ~= nil then return can_modify(ply, entity, "tool") end
    end)
    hook.Add("CanProperty", hook_prefix .. ".CanProperty", function(ply, property, entity)
        if property == "remover" and identity(entity) ~= nil then
            return can_modify(ply, entity, "property_remover")
        end
    end)
    hook.Add("EntityRemoved", hook_prefix .. ".EntityRemoved", function(entity)
        local value = entities[entity]
        if value == nil then return end
        entities[entity] = nil
        entity_objects[value.entity_id .. "@" .. value.revision] = nil
        registry:remove(
            "entity-removed:" .. value.entity_id .. ":" .. value.revision,
            value.entity_id,
            value.revision
        )
    end)
    hook.Add("PlayerDisconnected", hook_prefix .. ".PlayerDisconnected", function(ply)
        local owner = players[ply]
        if owner ~= nil then registry:disconnect(owner, CurTime()) end
    end)
    hook.Add("PlayerInitialSpawn", hook_prefix .. ".PlayerInitialSpawn", function(ply)
        local owner = players[ply]
        if owner ~= nil then registry:reconnect(owner, CurTime()) end
    end)
    timer.Create(timer_name, 0.1, 0, tick)
    return Server
end

return Server
