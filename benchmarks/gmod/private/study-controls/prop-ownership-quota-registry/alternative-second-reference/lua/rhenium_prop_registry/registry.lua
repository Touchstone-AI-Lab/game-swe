local Registry = {}
Registry.__index = Registry

local ID_PATTERN = "^[A-Za-z0-9][A-Za-z0-9_.:%-]*$"
local OPERATIONS = {
    physgun = true,
    tool = true,
    property_remover = true,
    delete = true,
}

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
    return type(value) == "string"
        and #value >= 1
        and #value <= 128
        and string.match(value, ID_PATTERN) ~= nil
end

local function valid_integer(value, minimum)
    return type(value) == "number" and value == math.floor(value) and value >= minimum
end

local function valid_now(value)
    return type(value) == "number" and value >= 0 and value == value and value < math.huge
end

local function same_array(left, right)
    if #left ~= #right then return false end
    for index = 1, #left do if left[index] ~= right[index] then return false end end
    return true
end

local function response(ok, code, data)
    return ok, code, copy(data or {})
end

local function entity_sort(left, right)
    if left.entity_id == right.entity_id then return left.revision < right.revision end
    return left.entity_id < right.entity_id
end

local function request_sort(left, right) return left.request_id < right.request_id end

local function array_shape(value)
    if type(value) ~= "table" then return false end
    local count = 0
    for key in pairs(value) do
        if not valid_integer(key, 1) then return false end
        count = count + 1
    end
    return count == #value
end

function Registry:_clock(now)
    if not valid_now(now) then return nil, "invalid_now" end
    if now > self.last_now then self.last_now = now end
    return self.last_now
end

function Registry:_count(player_id)
    local count = 0
    for _, entity in pairs(self.entities) do
        if entity.owner_id == player_id then count = count + 1 end
    end
    return count
end

function Registry:_request(request_id, method, arguments)
    local previous = self.requests[request_id]
    if not previous then return nil end
    if previous.method ~= method or not same_array(previous.arguments, arguments) then
        return { false, "request_conflict", {} }
    end
    return { previous.ok, previous.code, copy(previous.data) }
end

function Registry:_remember(request_id, method, arguments, ok, code, data)
    self.requests[request_id] = {
        request_id = request_id,
        method = method,
        arguments = copy(arguments),
        ok = ok,
        code = code,
        data = copy(data or {}),
    }
    return response(ok, code, data)
end

function Registry:_remove_entity(entity_id)
    local entity = self.entities[entity_id]
    if not entity then return nil end
    self.entities[entity_id] = nil
    self.latest_revision[entity_id] = math.max(self.latest_revision[entity_id] or 0, entity.revision)
    return entity
end

local function load_state(self, state)
    if type(state) ~= "table" or state.schema_version ~= 1 then return false, "invalid_state" end
    if state.max_props ~= self.max_props or state.cleanup_delay ~= self.cleanup_delay then
        return false, "state_configuration_mismatch"
    end
    if not valid_now(state.last_now) or not valid_integer(state.next_entity_sequence, 1) then
        return false, "invalid_state"
    end
    if not array_shape(state.entities) or not array_shape(state.latest_revisions)
        or not array_shape(state.pending_cleanup) or not array_shape(state.requests) then
        return false, "invalid_state"
    end
    local entities = {}
    local latest = {}
    local owner_counts = {}
    for _, item in ipairs(state.entities) do
        if type(item) ~= "table" or not valid_id(item.entity_id) or not valid_id(item.owner_id)
            or not valid_integer(item.revision, 1) or entities[item.entity_id] then
            return false, "invalid_state"
        end
        entities[item.entity_id] = copy(item)
        latest[item.entity_id] = item.revision
        owner_counts[item.owner_id] = (owner_counts[item.owner_id] or 0) + 1
        if owner_counts[item.owner_id] > self.max_props then return false, "invalid_state" end
    end
    local latest_seen = {}
    for _, item in ipairs(state.latest_revisions) do
        if type(item) ~= "table" or not valid_id(item.entity_id)
            or not valid_integer(item.revision, 1) or latest_seen[item.entity_id]
            or (latest[item.entity_id] and item.revision < latest[item.entity_id]) then
            return false, "invalid_state"
        end
        latest_seen[item.entity_id] = true
        latest[item.entity_id] = item.revision
    end
    for entity_id in pairs(entities) do
        if not latest_seen[entity_id] then return false, "invalid_state" end
    end
    local pending = {}
    for _, item in ipairs(state.pending_cleanup) do
        if type(item) ~= "table" or not valid_id(item.player_id)
            or not valid_now(item.cleanup_at) or item.cleanup_at <= state.last_now
            or pending[item.player_id] ~= nil then
            return false, "invalid_state"
        end
        pending[item.player_id] = item.cleanup_at
    end
    local requests = {}
    for _, item in ipairs(state.requests) do
        if type(item) ~= "table" or not valid_id(item.request_id) or requests[item.request_id]
            or (item.method ~= "register" and item.method ~= "remove")
            or not array_shape(item.arguments) or type(item.ok) ~= "boolean"
            or type(item.code) ~= "string" or item.code == "" or type(item.data) ~= "table" then
            return false, "invalid_state"
        end
        if item.method == "register" and (#item.arguments ~= 3
            or not valid_id(item.arguments[1]) or not valid_id(item.arguments[2])
            or not valid_integer(item.arguments[3], 1)) then return false, "invalid_state" end
        if item.method == "remove" and (#item.arguments ~= 2
            or not valid_id(item.arguments[1])
            or not valid_integer(item.arguments[2], 1)) then return false, "invalid_state" end
        requests[item.request_id] = copy(item)
    end
    self.entities = entities
    self.latest_revision = latest
    self.pending_cleanup = pending
    self.requests = requests
    self.last_now = state.last_now
    self.next_entity_sequence = state.next_entity_sequence
    return true
end

function Registry.new(options)
    if type(options) ~= "table" or options.max_props ~= 2 or options.cleanup_delay ~= 5 then
        return nil, "invalid_options"
    end
    local self = setmetatable({
        max_props = options.max_props,
        cleanup_delay = options.cleanup_delay,
        storage = options.storage,
        entities = {}, latest_revision = {}, pending_cleanup = {}, requests = {},
        last_now = 0, next_entity_sequence = 1, stopped = false,
    }, Registry)
    local state = options.state
    if state == nil and type(options.storage) == "table" and type(options.storage.load) == "function" then
        state = options.storage:load()
    end
    if state ~= nil then
        local ok, code = load_state(self, state)
        if not ok then return nil, code end
    end
    return self
end

function Registry:register(request_id, player_id, entity_id, revision)
    if self.stopped then return response(false, "shutdown") end
    if not valid_id(request_id) then return response(false, "invalid_request_id") end
    if not valid_id(player_id) then return response(false, "invalid_player_id") end
    if not valid_id(entity_id) then return response(false, "invalid_entity_id") end
    if not valid_integer(revision, 1) then return response(false, "invalid_revision") end
    local arguments = { player_id, entity_id, revision }
    local prior = self:_request(request_id, "register", arguments)
    if prior then return response(prior[1], prior[2], prior[3]) end
    local current = self.entities[entity_id]
    local latest = self.latest_revision[entity_id] or 0
    if (current and revision <= current.revision) or (not current and revision <= latest) then
        return self:_remember(request_id, "register", arguments, false, "stale_revision")
    end
    local prospective = self:_count(player_id)
    if current and current.owner_id == player_id then prospective = prospective - 1 end
    if prospective >= self.max_props then
        return self:_remember(request_id, "register", arguments, false, "quota_exceeded")
    end
    if current then self:_remove_entity(entity_id) end
    self.entities[entity_id] = {
        entity_id = entity_id, revision = revision, owner_id = player_id,
    }
    self.latest_revision[entity_id] = revision
    local data = {
        entity_id = entity_id, revision = revision, owner_id = player_id,
        count = self:_count(player_id),
    }
    return self:_remember(request_id, "register", arguments, true, "registered", data)
end

function Registry:can_modify(player_id, entity_id, revision, operation)
    if self.stopped then return false, "shutdown" end
    if not valid_id(player_id) then return false, "invalid_player_id" end
    if not valid_id(entity_id) then return false, "invalid_entity_id" end
    if not valid_integer(revision, 1) then return false, "invalid_revision" end
    if not OPERATIONS[operation] then return false, "invalid_operation" end
    local entity = self.entities[entity_id]
    if not entity then
        if revision < (self.latest_revision[entity_id] or 0) then return false, "stale_revision" end
        return false, "not_found"
    end
    if revision ~= entity.revision then return false, "stale_revision" end
    if player_id ~= entity.owner_id then return false, "not_owner" end
    return true, "allowed"
end

function Registry:remove(request_id, entity_id, revision)
    if self.stopped then return response(false, "shutdown") end
    if not valid_id(request_id) then return response(false, "invalid_request_id") end
    if not valid_id(entity_id) then return response(false, "invalid_entity_id") end
    if not valid_integer(revision, 1) then return response(false, "invalid_revision") end
    local arguments = { entity_id, revision }
    local prior = self:_request(request_id, "remove", arguments)
    if prior then return response(prior[1], prior[2], prior[3]) end
    local entity = self.entities[entity_id]
    if not entity then
        local code = revision < (self.latest_revision[entity_id] or 0)
            and "stale_revision" or "not_found"
        return self:_remember(request_id, "remove", arguments, false, code)
    end
    if revision ~= entity.revision then
        return self:_remember(request_id, "remove", arguments, false, "stale_revision")
    end
    local removed = self:_remove_entity(entity_id)
    local data = copy(removed)
    data.count = self:_count(removed.owner_id)
    return self:_remember(request_id, "remove", arguments, true, "removed", data)
end

function Registry:disconnect(player_id, now)
    if self.stopped then return response(false, "shutdown") end
    if not valid_id(player_id) then return response(false, "invalid_player_id") end
    local effective, error_code = self:_clock(now)
    if not effective then return response(false, error_code) end
    if self.pending_cleanup[player_id] == nil then
        self.pending_cleanup[player_id] = effective + self.cleanup_delay
    end
    return response(true, "scheduled", { cleanup_at = self.pending_cleanup[player_id] })
end

function Registry:reconnect(player_id, now)
    if self.stopped then return response(false, "shutdown") end
    if not valid_id(player_id) then return response(false, "invalid_player_id") end
    local effective, error_code = self:_clock(now)
    if not effective then return response(false, error_code) end
    local canceled = self.pending_cleanup[player_id] ~= nil
    self.pending_cleanup[player_id] = nil
    return response(true, canceled and "canceled" or "connected", { now = effective })
end

function Registry:tick(now)
    if self.stopped then return response(false, "shutdown") end
    local effective, error_code = self:_clock(now)
    if not effective then return response(false, error_code) end
    local due = {}
    for player_id, cleanup_at in pairs(self.pending_cleanup) do
        if effective >= cleanup_at then due[#due + 1] = player_id end
    end
    table.sort(due)
    local removed = {}
    for _, player_id in ipairs(due) do
        local ids = {}
        for entity_id, entity in pairs(self.entities) do
            if entity.owner_id == player_id then ids[#ids + 1] = entity_id end
        end
        table.sort(ids)
        for _, entity_id in ipairs(ids) do
            local entity = self:_remove_entity(entity_id)
            removed[#removed + 1] = copy(entity)
        end
        self.pending_cleanup[player_id] = nil
    end
    table.sort(removed, entity_sort)
    return response(true, "ticked", { now = effective, removed = removed })
end

function Registry:snapshot(now)
    if not self.stopped then
        local ok, code = self:tick(now)
        if not ok then return nil, code end
    elseif not valid_now(now) then return nil, "invalid_now" end
    local entities, owners, pending = {}, {}, {}
    local owner_ids = {}
    for _, entity in pairs(self.entities) do
        entities[#entities + 1] = copy(entity)
        owner_ids[entity.owner_id] = true
    end
    for player_id in pairs(self.pending_cleanup) do owner_ids[player_id] = true end
    table.sort(entities, entity_sort)
    for player_id in pairs(owner_ids) do
        owners[#owners + 1] = {
            player_id = player_id,
            count = self:_count(player_id),
            disconnected = self.pending_cleanup[player_id] ~= nil,
            cleanup_at = self.pending_cleanup[player_id],
        }
    end
    table.sort(owners, function(a, b) return a.player_id < b.player_id end)
    for player_id, cleanup_at in pairs(self.pending_cleanup) do
        pending[#pending + 1] = { player_id = player_id, cleanup_at = cleanup_at }
    end
    table.sort(pending, function(a, b) return a.player_id < b.player_id end)
    return { schema_version = 1, now = self.last_now, owners = owners,
        entities = entities, pending_cleanup = pending }
end

function Registry:save(now)
    if not self.stopped then
        local ok, code = self:tick(now)
        if not ok then return nil, code end
    elseif not valid_now(now) then return nil, "invalid_now" end
    local entities, latest, pending, requests = {}, {}, {}, {}
    for _, entity in pairs(self.entities) do entities[#entities + 1] = copy(entity) end
    table.sort(entities, entity_sort)
    for entity_id, revision in pairs(self.latest_revision) do
        latest[#latest + 1] = { entity_id = entity_id, revision = revision }
    end
    table.sort(latest, entity_sort)
    for player_id, cleanup_at in pairs(self.pending_cleanup) do
        pending[#pending + 1] = { player_id = player_id, cleanup_at = cleanup_at }
    end
    table.sort(pending, function(a, b) return a.player_id < b.player_id end)
    for _, item in pairs(self.requests) do requests[#requests + 1] = copy(item) end
    table.sort(requests, request_sort)
    local state = { schema_version = 1, max_props = self.max_props,
        cleanup_delay = self.cleanup_delay, last_now = self.last_now,
        next_entity_sequence = self.next_entity_sequence, entities = entities,
        latest_revisions = latest, pending_cleanup = pending, requests = requests }
    if type(self.storage) == "table" and type(self.storage.save) == "function" then
        local ok = self.storage:save(copy(state))
        if ok == false then return nil, "storage_error" end
    end
    return copy(state)
end

function Registry:shutdown()
    if self.stopped then return true, "shutdown" end
    self.stopped = true
    return true, "shutdown"
end

return Registry
