local Blueprints = {}
Blueprints.__index = Blueprints

local CLASSES = { prop_physics = true }
local MODELS = {
    ["models/props_c17/oildrum001.mdl"] = true,
    ["models/props_c17/furniturechair001a.mdl"] = true,
    ["models/props_c17/furnituretable001a.mdl"] = true,
}
local CONSTRAINTS = { Weld = true, NoCollide = true }
local PARAMS = { Bone1 = "integer", Bone2 = "integer", forcelimit = "number", nocollide = "boolean" }

local function copy(value, seen)
    if type(value) ~= "table" then return value end
    seen = seen or {}
    if seen[value] then return seen[value] end
    local result = {}
    seen[value] = result
    for key, item in pairs(value) do result[copy(key, seen)] = copy(item, seen) end
    return result
end

local function valid_id(value)
    return type(value) == "string" and #value >= 1 and #value <= 128
        and value:match("^[%w][%w_.:%-]*$") ~= nil
end
local function valid_name(value)
    return type(value) == "string" and #value >= 1 and #value <= 32
        and value:match("^[%w_-]+$") ~= nil
end
local function finite(value)
    return type(value) == "number" and value == value
        and value < math.huge and value > -math.huge
end
local function integer(value, minimum)
    return finite(value) and value % 1 == 0 and value >= minimum
end
local function vector(value)
    if type(value) ~= "table" or not finite(value.x) or not finite(value.y)
        or not finite(value.z) then return false end
    for key in pairs(value) do
        if key ~= "x" and key ~= "y" and key ~= "z" then return false end
    end
    return true
end
local function array(value)
    if type(value) ~= "table" then return false end
    local count = 0
    for key in pairs(value) do
        if not integer(key, 1) then return false end
        count = count + 1
    end
    return count == #value
end
local function field_count(value, allowed)
    local count = 0
    for key in pairs(value) do
        if not allowed[key] then return false end
        count = count + 1
    end
    return count
end
local function quantize(value)
    local scaled = value * 1000000
    return (scaled >= 0 and math.floor(scaled + .5) or math.ceil(scaled - .5)) / 1000000
end

local function encode(value)
    local kind = type(value)
    if kind ~= "table" then return kind .. ":" .. tostring(value) end
    local keys = {}
    for key in pairs(value) do keys[#keys + 1] = key end
    table.sort(keys, function(left, right)
        return type(left) .. ":" .. tostring(left) < type(right) .. ":" .. tostring(right)
    end)
    local parts = { "{" }
    for _, key in ipairs(keys) do
        parts[#parts + 1] = encode(key) .. "=" .. encode(value[key]) .. ";"
    end
    parts[#parts + 1] = "}"
    return table.concat(parts)
end

local function digest(text)
    local value = 17
    for index = 1, #text do value = (value * 131 + text:byte(index)) % 4294967291 end
    return string.format("%08x", value)
end

local function normalize_params(value)
    if value == nil then return {} end
    if type(value) ~= "table" then return nil end
    local result = {}
    for key, item in pairs(value) do
        local expected = PARAMS[key]
        if not expected then return nil end
        if expected == "integer" and not integer(item, 0) then return nil end
        if expected == "number" and (not finite(item) or item < 0) then return nil end
        if expected == "boolean" and type(item) ~= "boolean" then return nil end
        result[key] = item
    end
    return result
end

local function schema_hash(entities, constraints)
    local parts = { "schema:1" }
    for _, entity in ipairs(entities) do
        parts[#parts + 1] = encode(entity)
    end
    for _, constraint in ipairs(constraints) do
        parts[#parts + 1] = encode(constraint)
    end
    return digest(table.concat(parts, "|"))
end

local function canonical(graph)
    if type(graph) ~= "table" or field_count(graph, { entities = true, constraints = true }) ~= 2
        or not array(graph.entities) or #graph.entities < 1 or #graph.entities > 16
        or not array(graph.constraints) or #graph.constraints > 24 then
        return nil, "invalid_graph"
    end
    local source = copy(graph.entities)
    for _, entity in ipairs(source) do
        if type(entity) ~= "table" or type(entity.source_id) ~= "string"
            or not valid_id(entity.source_id) then return nil, "unsupported_entity" end
    end
    table.sort(source, function(left, right) return left.source_id < right.source_id end)
    local ids, entities = {}, {}
    for index, entity in ipairs(source) do
        local fields = field_count(entity, {
            source_id = true, class = true, model = true, pos = true, ang = true,
        })
        local model = type(entity.model) == "string" and string.lower(entity.model) or ""
        if fields ~= 5 or ids[entity.source_id] or not CLASSES[entity.class]
            or not MODELS[model] or not vector(entity.pos) or not vector(entity.ang) then
            return nil, "unsupported_entity"
        end
        local local_id = "e" .. index
        ids[entity.source_id] = local_id
        entities[#entities + 1] = {
            id = local_id,
            class = entity.class,
            model = model,
            pos = { x = quantize(entity.pos.x), y = quantize(entity.pos.y), z = quantize(entity.pos.z) },
            ang = { x = quantize(entity.ang.x), y = quantize(entity.ang.y), z = quantize(entity.ang.z) },
        }
    end
    local constraints = {}
    for _, constraint in ipairs(graph.constraints) do
        if type(constraint) ~= "table"
            or field_count(constraint, { type = true, a = true, b = true, params = true }) ~= 4
            or type(constraint.a) ~= "string" or type(constraint.b) ~= "string" then
            return nil, "invalid_endpoint"
        end
        local a, b = ids[constraint.a], ids[constraint.b]
        local params = normalize_params(constraint.params)
        if not CONSTRAINTS[constraint.type] or not a or not b or a == b or not params then
            return nil, "invalid_endpoint"
        end
        if b < a then a, b = b, a end
        constraints[#constraints + 1] = { type = constraint.type, a = a, b = b, params = params }
    end
    table.sort(constraints, function(left, right)
        return left.type .. left.a .. left.b .. encode(left.params)
            < right.type .. right.a .. right.b .. encode(right.params)
    end)
    for index, constraint in ipairs(constraints) do constraint.id = "c" .. index end
    local schema = { schema_version = 1, entities = entities, constraints = constraints }
    schema.hash = schema_hash(entities, constraints)
    return schema
end

local function valid_schema(schema)
    if type(schema) ~= "table"
        or field_count(schema, { schema_version = true, entities = true, constraints = true, hash = true }) ~= 4
        or schema.schema_version ~= 1 or not array(schema.entities) or #schema.entities < 1
        or #schema.entities > 16 or not array(schema.constraints) or #schema.constraints > 24
        or type(schema.hash) ~= "string" then return false end
    local ids = {}
    for index, entity in ipairs(schema.entities) do
        if type(entity) ~= "table"
            or field_count(entity, { id = true, class = true, model = true, pos = true, ang = true }) ~= 5
            or entity.id ~= "e" .. index or not CLASSES[entity.class]
            or not MODELS[entity.model] or not vector(entity.pos) or not vector(entity.ang)
            or quantize(entity.pos.x) ~= entity.pos.x or quantize(entity.pos.y) ~= entity.pos.y
            or quantize(entity.pos.z) ~= entity.pos.z or quantize(entity.ang.x) ~= entity.ang.x
            or quantize(entity.ang.y) ~= entity.ang.y or quantize(entity.ang.z) ~= entity.ang.z then return false end
        ids[entity.id] = true
    end
    local last_key = nil
    for index, constraint in ipairs(schema.constraints) do
        if type(constraint) ~= "table"
            or field_count(constraint, { id = true, type = true, a = true, b = true, params = true }) ~= 5
            or constraint.id ~= "c" .. index or not CONSTRAINTS[constraint.type]
            or not ids[constraint.a] or not ids[constraint.b] or constraint.a >= constraint.b then return false end
        local params = normalize_params(constraint.params)
        if not params or encode(params) ~= encode(constraint.params) then return false end
        local key = constraint.type .. constraint.a .. constraint.b .. encode(params)
        if last_key and key < last_key then return false end
        last_key = key
    end
    return schema.hash == schema_hash(schema.entities, schema.constraints)
end

local function serializable(value, seen)
    local kind = type(value)
    if kind == "nil" or kind == "string" or kind == "boolean" then return true end
    if kind == "number" then return finite(value) end
    if kind ~= "table" then return false end
    seen = seen or {}
    if seen[value] then return false end
    seen[value] = true
    for key, item in pairs(value) do
        if (type(key) ~= "string" and type(key) ~= "number")
            or not serializable(key, seen) or not serializable(item, seen) then return false end
    end
    seen[value] = nil
    return true
end

local function restore(self, state)
    if type(state) ~= "table" or state.schema_version ~= 1
        or field_count(state, { schema_version = true, owners = true, requests = true, pastes = true }) ~= 4
        or type(state.owners) ~= "table" or type(state.requests) ~= "table"
        or type(state.pastes) ~= "table" then return false end
    for owner_id, box in pairs(state.owners) do
        if not valid_id(owner_id) or type(box) ~= "table" then return false end
        local count = 0
        for blueprint_name, blueprint in pairs(box) do
            count = count + 1
            if count > 8 or not valid_name(blueprint_name) or type(blueprint) ~= "table"
                or field_count(blueprint, { revision = true, schema = true }) ~= 2
                or not integer(blueprint.revision, 1) or not valid_schema(blueprint.schema) then return false end
        end
    end
    for request_id, request in pairs(state.requests) do
        if not valid_id(request_id) or type(request) ~= "table"
            or field_count(request, { key = true, ok = true, code = true, data = true }) ~= 4
            or type(request.key) ~= "string" or request.key == "" or type(request.ok) ~= "boolean"
            or type(request.code) ~= "string" or request.code == ""
            or type(request.data) ~= "table" or not serializable(request.data) then return false end
    end
    for request_id, result in pairs(state.pastes) do
        if not valid_id(request_id) or type(result) ~= "table"
            or field_count(result, { entities = true, constraints = true }) ~= 2
            or not integer(result.entities, 0) or not integer(result.constraints, 0) then return false end
    end
    self.owners = copy(state.owners)
    self.requests = copy(state.requests)
    self.pastes = copy(state.pastes)
    return true
end

local function request_key(method, arguments) return method .. "|" .. encode(arguments) end

function Blueprints.new(options)
    options = options or {}
    local self = setmetatable({ owners = {}, requests = {}, pastes = {}, stopped = false }, Blueprints)
    if options.state ~= nil and not restore(self, options.state) then return nil, "invalid_state" end
    return self
end

function Blueprints:_old(request_id, method, arguments)
    if not valid_id(request_id) then return false, "invalid_request_id", {} end
    local key = request_key(method, arguments)
    local old = self.requests[request_id]
    if old then
        if old.key ~= key then return false, "request_conflict", {} end
        return old.ok, old.code, copy(old.data)
    end
    return nil, key
end

function Blueprints:_done(request_id, key, ok, code, data)
    self.requests[request_id] = { key = key, ok = ok, code = code, data = copy(data or {}) }
    return ok, code, copy(data or {})
end

function Blueprints:capture(request_id, owner_id, blueprint_name, revision, graph)
    if self.stopped then return false, "shutdown", {} end
    if not valid_id(request_id) then return false, "invalid_request_id", {} end
    local schema, graph_error = canonical(graph)
    local signature = schema and { owner_id, blueprint_name, revision, schema.hash }
        or { owner_id, blueprint_name, revision, encode(graph) }
    local old, key, data = self:_old(request_id, "capture", signature)
    if old ~= nil then return old, key, data end
    if not valid_id(owner_id) or not valid_name(blueprint_name)
        or not integer(revision, 1) then return self:_done(request_id, key, false, "invalid_request", {}) end
    if not schema then return self:_done(request_id, key, false, graph_error, {}) end
    local box = self.owners[owner_id] or {}
    self.owners[owner_id] = box
    local current = box[blueprint_name]
    if current and revision <= current.revision then
        return self:_done(request_id, key, false, "stale_revision", {})
    end
    local count = 0
    for _ in pairs(box) do count = count + 1 end
    if not current and count >= 8 then
        return self:_done(request_id, key, false, "blueprint_limit", {})
    end
    box[blueprint_name] = { revision = revision, schema = schema }
    return self:_done(request_id, key, true, "captured", {
        name = blueprint_name, revision = revision, hash = schema.hash,
        entities = #schema.entities, constraints = #schema.constraints,
    })
end

function Blueprints:list(owner_id)
    local result = {}
    for blueprint_name, blueprint in pairs(self.owners[owner_id] or {}) do
        result[#result + 1] = {
            name = blueprint_name, revision = blueprint.revision, hash = blueprint.schema.hash,
        }
    end
    table.sort(result, function(left, right) return left.name < right.name end)
    return result
end

function Blueprints:get(owner_id, blueprint_name)
    local blueprint = (self.owners[owner_id] or {})[blueprint_name]
    if not blueprint then return nil, "not_found" end
    return copy(blueprint)
end

function Blueprints:plan(request_id, owner_id, blueprint_name, revision, target)
    if self.stopped then return false, "shutdown", {} end
    local old, key, data = self:_old(request_id, "plan", {
        owner_id, blueprint_name, revision, encode(target),
    })
    if old ~= nil then return old, key, data end
    if not valid_id(owner_id) or not valid_name(blueprint_name) or not integer(revision, 1) then
        return self:_done(request_id, key, false, "invalid_request", {})
    end
    local blueprint = (self.owners[owner_id] or {})[blueprint_name]
    if not blueprint then return self:_done(request_id, key, false, "not_found", {}) end
    if revision ~= blueprint.revision then
        return self:_done(request_id, key, false, "stale_revision", {})
    end
    if not vector(target) then return self:_done(request_id, key, false, "invalid_transform", {}) end
    local plan = copy(blueprint.schema)
    for _, entity in ipairs(plan.entities) do
        entity.pos.x = quantize(entity.pos.x + target.x)
        entity.pos.y = quantize(entity.pos.y + target.y)
        entity.pos.z = quantize(entity.pos.z + target.z)
    end
    plan.request_id = request_id
    return self:_done(request_id, key, true, "planned", plan)
end

function Blueprints:record_paste(request_id, result)
    if self.stopped then return false, "shutdown", {} end
    if not valid_id(request_id) then return false, "invalid_request_id", {} end
    local previous = self.pastes[request_id]
    if previous then return true, "duplicate", copy(previous) end
    if type(result) ~= "table" or field_count(result, { entities = true, constraints = true }) ~= 2
        or not integer(result.entities, 0) or not integer(result.constraints, 0) then
        return false, "invalid_result", {}
    end
    self.pastes[request_id] = copy(result)
    return true, "recorded", copy(result)
end

function Blueprints:save()
    return { schema_version = 1, owners = copy(self.owners), requests = copy(self.requests), pastes = copy(self.pastes) }
end

function Blueprints:shutdown()
    self.stopped = true
    return true, "shutdown"
end

return Blueprints
