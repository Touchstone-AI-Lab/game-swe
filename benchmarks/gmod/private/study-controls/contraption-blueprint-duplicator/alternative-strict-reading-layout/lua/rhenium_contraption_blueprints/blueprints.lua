local Blueprints = {}
Blueprints.__index = Blueprints

local class_allowed = { prop_physics = true }
local model_allowed = {
    ["models/props_c17/oildrum001.mdl"] = true,
    ["models/props_c17/furniturechair001a.mdl"] = true,
    ["models/props_c17/furnituretable001a.mdl"] = true,
}
local constraint_allowed = { Weld = true, NoCollide = true }

local function clone(value)
    if type(value) ~= "table" then return value end
    local result = {}
    for key, item in pairs(value) do result[clone(key)] = clone(item) end
    return result
end
local function identifier(value)
    return type(value) == "string" and #value > 0 and #value <= 128
        and value:match("^[%w][%w_.:%-]*$") ~= nil
end
local function blueprint_name(value)
    return type(value) == "string" and #value > 0 and #value <= 32
        and value:match("^[%w_-]+$") ~= nil
end
local function number(value)
    return type(value) == "number" and value == value and value < math.huge and value > -math.huge
end
local function integer(value, minimum) return number(value) and value % 1 == 0 and value >= minimum end
local function vector(value)
    if type(value) ~= "table" or not number(value.x) or not number(value.y) or not number(value.z) then return false end
    for key in pairs(value) do if key ~= "x" and key ~= "y" and key ~= "z" then return false end end
    return true
end
local function is_array(value)
    if type(value) ~= "table" then return false end
    local count = 0
    for key in pairs(value) do if not integer(key, 1) then return false end; count = count + 1 end
    return count == #value
end
local function fields(value, allowed)
    local count = 0
    for key in pairs(value) do if not allowed[key] then return false end; count = count + 1 end
    return count
end
local function quantize(value)
    local scaled = value * 1000000
    return (scaled >= 0 and math.floor(scaled + .5) or math.ceil(scaled - .5)) / 1000000
end
local function encode(value)
    if type(value) ~= "table" then return type(value) .. ":" .. tostring(value) end
    local keys = {}
    for key in pairs(value) do keys[#keys + 1] = key end
    table.sort(keys, function(a, b)
        return type(a) .. ":" .. tostring(a) < type(b) .. ":" .. tostring(b)
    end)
    local out = { "{" }
    for _, key in ipairs(keys) do out[#out + 1] = encode(key) .. "=" .. encode(value[key]) .. ";" end
    out[#out + 1] = "}"
    return table.concat(out)
end
local function hash(value)
    local result = 17
    for index = 1, #value do result = (result * 131 + value:byte(index)) % 4294967291 end
    return string.format("%08x", result)
end
local function parameters(value)
    if value == nil then return {} end
    if type(value) ~= "table" then return nil end
    local result = {}
    for key, item in pairs(value) do
        if (key == "Bone1" or key == "Bone2") and integer(item, 0) then result[key] = item
        elseif key == "forcelimit" and number(item) and item >= 0 then result[key] = item
        elseif key == "nocollide" and type(item) == "boolean" then result[key] = item
        else return nil end
    end
    return result
end
local function schema_digest(nodes, edges)
    local values = { "schema:1" }
    for _, node in ipairs(nodes) do values[#values + 1] = encode(node) end
    for _, edge in ipairs(edges) do values[#values + 1] = encode(edge) end
    return hash(table.concat(values, "|"))
end

local function normalize(graph)
    if type(graph) ~= "table" or fields(graph, { entities = true, constraints = true }) ~= 2
        or not is_array(graph.entities) or #graph.entities < 1 or #graph.entities > 16
        or not is_array(graph.constraints) or #graph.constraints > 24 then return nil, "invalid_graph" end
    local input = clone(graph.entities)
    for _, entity in ipairs(input) do
        if type(entity) ~= "table" or type(entity.source_id) ~= "string"
            or not identifier(entity.source_id) then return nil, "unsupported_entity" end
    end
    table.sort(input, function(a, b) return a.source_id < b.source_id end)
    local sources, nodes = {}, {}
    for index, entity in ipairs(input) do
        local model = type(entity.model) == "string" and string.lower(entity.model) or ""
        if fields(entity, { source_id = true, class = true, model = true, pos = true, ang = true }) ~= 5
            or sources[entity.source_id] or not class_allowed[entity.class] or not model_allowed[model]
            or not vector(entity.pos) or not vector(entity.ang) then return nil, "unsupported_entity" end
        local local_id = "e" .. index
        sources[entity.source_id] = local_id
        nodes[#nodes + 1] = { id = local_id, class = entity.class, model = model,
            pos = { x = quantize(entity.pos.x), y = quantize(entity.pos.y), z = quantize(entity.pos.z) },
            ang = { x = quantize(entity.ang.x), y = quantize(entity.ang.y), z = quantize(entity.ang.z) } }
    end
    local edges = {}
    for _, constraint in ipairs(graph.constraints) do
        if type(constraint) ~= "table"
            or fields(constraint, { type = true, a = true, b = true, params = true }) ~= 4
            or type(constraint.a) ~= "string" or type(constraint.b) ~= "string" then
            return nil, "invalid_endpoint"
        end
        local left, right = sources[constraint.a], sources[constraint.b]
        local params = parameters(constraint.params)
        if not constraint_allowed[constraint.type] or not left or not right or left == right or not params then
            return nil, "invalid_endpoint"
        end
        if right < left then left, right = right, left end
        edges[#edges + 1] = { type = constraint.type, a = left, b = right, params = params }
    end
    table.sort(edges, function(a, b)
        return a.type .. a.a .. a.b .. encode(a.params) < b.type .. b.a .. b.b .. encode(b.params)
    end)
    for index, edge in ipairs(edges) do edge.id = "c" .. index end
    local schema = { schema_version = 1, entities = nodes, constraints = edges }
    schema.hash = schema_digest(nodes, edges)
    return schema
end

local function schema_valid(schema)
    if type(schema) ~= "table"
        or fields(schema, { schema_version = true, entities = true, constraints = true, hash = true }) ~= 4
        or schema.schema_version ~= 1 or not is_array(schema.entities) or #schema.entities < 1
        or #schema.entities > 16 or not is_array(schema.constraints) or #schema.constraints > 24
        or type(schema.hash) ~= "string" then return false end
    local ids = {}
    for index, node in ipairs(schema.entities) do
        if type(node) ~= "table" or fields(node, { id = true, class = true, model = true, pos = true, ang = true }) ~= 5
            or node.id ~= "e" .. index or not class_allowed[node.class] or not model_allowed[node.model]
            or not vector(node.pos) or not vector(node.ang)
            or quantize(node.pos.x) ~= node.pos.x or quantize(node.pos.y) ~= node.pos.y
            or quantize(node.pos.z) ~= node.pos.z or quantize(node.ang.x) ~= node.ang.x
            or quantize(node.ang.y) ~= node.ang.y or quantize(node.ang.z) ~= node.ang.z then return false end
        ids[node.id] = true
    end
    local previous = nil
    for index, edge in ipairs(schema.constraints) do
        local params = type(edge) == "table" and parameters(edge.params) or nil
        if type(edge) ~= "table" or fields(edge, { id = true, type = true, a = true, b = true, params = true }) ~= 5
            or edge.id ~= "c" .. index or not constraint_allowed[edge.type]
            or not ids[edge.a] or not ids[edge.b] or edge.a >= edge.b
            or not params or encode(params) ~= encode(edge.params) then return false end
        local key = edge.type .. edge.a .. edge.b .. encode(params)
        if previous and key < previous then return false end
        previous = key
    end
    return schema.hash == schema_digest(schema.entities, schema.constraints)
end

local function serializable(value, seen)
    local kind = type(value)
    if kind == "nil" or kind == "string" or kind == "boolean" then return true end
    if kind == "number" then return number(value) end
    if kind ~= "table" then return false end
    seen = seen or {}; if seen[value] then return false end; seen[value] = true
    for key, item in pairs(value) do
        if (type(key) ~= "string" and type(key) ~= "number")
            or not serializable(key, seen) or not serializable(item, seen) then return false end
    end
    seen[value] = nil
    return true
end
local function find_blueprint(rows, owner_id, name)
    for _, row in ipairs(rows) do if row.owner_id == owner_id and row.name == name then return row end end
end
local function find_request(rows, request_id)
    for _, row in ipairs(rows) do if row.id == request_id then return row end end
end
local function find_paste(rows, request_id)
    for _, row in ipairs(rows) do if row.id == request_id then return row end end
end

local function restore(self, state)
    if type(state) ~= "table" or state.schema_version ~= 1
        or fields(state, { schema_version = true, blueprint_rows = true, requests = true, pastes = true }) ~= 4
        or not is_array(state.blueprint_rows) or not is_array(state.requests) or not is_array(state.pastes) then return false end
    local blueprints, requests, pastes, owner_counts = {}, {}, {}, {}
    for _, row in ipairs(state.blueprint_rows) do
        local key = type(row) == "table" and tostring(row.owner_id) .. "\0" .. tostring(row.name) or ""
        if type(row) ~= "table" or fields(row, { owner_id = true, name = true, revision = true, schema = true }) ~= 4
            or not identifier(row.owner_id) or not blueprint_name(row.name) or blueprints[key]
            or not integer(row.revision, 1) or not schema_valid(row.schema) then return false end
        blueprints[key] = true
        owner_counts[row.owner_id] = (owner_counts[row.owner_id] or 0) + 1
        if owner_counts[row.owner_id] > 8 then return false end
    end
    for _, row in ipairs(state.requests) do
        if type(row) ~= "table" or fields(row, { id = true, key = true, ok = true, code = true, data = true }) ~= 5
            or not identifier(row.id) or requests[row.id] or type(row.key) ~= "string" or row.key == ""
            or type(row.ok) ~= "boolean" or type(row.code) ~= "string" or row.code == ""
            or type(row.data) ~= "table" or not serializable(row.data) then return false end
        requests[row.id] = true
    end
    for _, row in ipairs(state.pastes) do
        if type(row) ~= "table" or fields(row, { id = true, result = true }) ~= 2
            or not identifier(row.id) or pastes[row.id] or type(row.result) ~= "table"
            or fields(row.result, { entities = true, constraints = true }) ~= 2
            or not integer(row.result.entities, 0) or not integer(row.result.constraints, 0) then return false end
        pastes[row.id] = true
    end
    self.blueprint_rows = clone(state.blueprint_rows)
    self.request_rows = clone(state.requests)
    self.paste_rows = clone(state.pastes)
    return true
end

function Blueprints.new(options)
    options = options or {}
    local self = setmetatable({ blueprint_rows = {}, request_rows = {}, paste_rows = {}, stopped = false }, Blueprints)
    if options.state ~= nil and not restore(self, options.state) then return nil, "invalid_state" end
    return self
end
function Blueprints:_old(request_id, method, arguments)
    if not identifier(request_id) then return false, "invalid_request_id", {} end
    local key = method .. "|" .. encode(arguments)
    local old = find_request(self.request_rows, request_id)
    if old then if old.key ~= key then return false, "request_conflict", {} end; return old.ok, old.code, clone(old.data) end
    return nil, key
end
function Blueprints:_put(request_id, key, ok, code, data)
    self.request_rows[#self.request_rows + 1] = {
        id = request_id, key = key, ok = ok, code = code, data = clone(data or {}),
    }
    return ok, code, clone(data or {})
end

function Blueprints:capture(request_id, owner_id, name, revision, graph)
    if self.stopped then return false, "shutdown", {} end
    if not identifier(request_id) then return false, "invalid_request_id", {} end
    local schema, graph_error = normalize(graph)
    local signature = schema and { owner_id, name, revision, schema.hash }
        or { owner_id, name, revision, encode(graph) }
    local old, key, data = self:_old(request_id, "capture", signature)
    if old ~= nil then return old, key, data end
    if not identifier(owner_id) or not blueprint_name(name) or not integer(revision, 1) then
        return self:_put(request_id, key, false, "invalid_request", {})
    end
    if not schema then return self:_put(request_id, key, false, graph_error, {}) end
    local current = find_blueprint(self.blueprint_rows, owner_id, name)
    if current and revision <= current.revision then return self:_put(request_id, key, false, "stale_revision", {}) end
    local count = 0
    for _, row in ipairs(self.blueprint_rows) do if row.owner_id == owner_id then count = count + 1 end end
    if not current and count >= 8 then return self:_put(request_id, key, false, "blueprint_limit", {}) end
    if current then current.revision = revision; current.schema = schema
    else self.blueprint_rows[#self.blueprint_rows + 1] = {
        owner_id = owner_id, name = name, revision = revision, schema = schema,
    } end
    return self:_put(request_id, key, true, "captured", {
        name = name, revision = revision, hash = schema.hash,
        entities = #schema.entities, constraints = #schema.constraints,
    })
end
function Blueprints:list(owner_id)
    local result = {}
    for _, row in ipairs(self.blueprint_rows) do
        if row.owner_id == owner_id then result[#result + 1] = {
            name = row.name, revision = row.revision, hash = row.schema.hash,
        } end
    end
    table.sort(result, function(a, b) return a.name < b.name end)
    return result
end
function Blueprints:get(owner_id, name)
    local row = find_blueprint(self.blueprint_rows, owner_id, name)
    if not row then return nil, "not_found" end
    return { revision = row.revision, schema = clone(row.schema) }
end
function Blueprints:plan(request_id, owner_id, name, revision, target)
    if self.stopped then return false, "shutdown", {} end
    local old, key, data = self:_old(request_id, "plan", { owner_id, name, revision, encode(target) })
    if old ~= nil then return old, key, data end
    if not identifier(owner_id) or not blueprint_name(name) or not integer(revision, 1) then
        return self:_put(request_id, key, false, "invalid_request", {})
    end
    local row = find_blueprint(self.blueprint_rows, owner_id, name)
    if not row then return self:_put(request_id, key, false, "not_found", {}) end
    if revision ~= row.revision then return self:_put(request_id, key, false, "stale_revision", {}) end
    if not vector(target) then return self:_put(request_id, key, false, "invalid_transform", {}) end
    local plan = clone(row.schema)
    for _, entity in ipairs(plan.entities) do
        entity.pos.x = quantize(entity.pos.x + target.x)
        entity.pos.y = quantize(entity.pos.y + target.y)
        entity.pos.z = quantize(entity.pos.z + target.z)
    end
    plan.request_id = request_id
    return self:_put(request_id, key, true, "planned", plan)
end
function Blueprints:record_paste(request_id, result)
    if self.stopped then return false, "shutdown", {} end
    if not identifier(request_id) then return false, "invalid_request_id", {} end
    local old = find_paste(self.paste_rows, request_id)
    if old then return true, "duplicate", clone(old.result) end
    if type(result) ~= "table" or fields(result, { entities = true, constraints = true }) ~= 2
        or not integer(result.entities, 0) or not integer(result.constraints, 0) then
        return false, "invalid_result", {}
    end
    self.paste_rows[#self.paste_rows + 1] = { id = request_id, result = clone(result) }
    return true, "recorded", clone(result)
end
function Blueprints:save()
    local blueprints, requests, pastes = clone(self.blueprint_rows), clone(self.request_rows), clone(self.paste_rows)
    table.sort(blueprints, function(a, b)
        return a.owner_id == b.owner_id and a.name < b.name or a.owner_id < b.owner_id
    end)
    table.sort(requests, function(a, b) return a.id < b.id end)
    table.sort(pastes, function(a, b) return a.id < b.id end)
    return { schema_version = 1, blueprint_rows = blueprints, requests = requests, pastes = pastes }
end
function Blueprints:shutdown() self.stopped = true; return true, "shutdown" end

return Blueprints
