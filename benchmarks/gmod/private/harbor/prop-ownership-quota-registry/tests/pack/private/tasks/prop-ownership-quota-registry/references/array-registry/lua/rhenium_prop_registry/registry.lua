local Registry = {}
Registry.__index = Registry

local operations = { physgun = true, tool = true, property_remover = true, delete = true }

local function clone(value)
    if type(value) ~= "table" then return value end
    local result = {}
    for key, item in pairs(value) do result[clone(key)] = clone(item) end
    return result
end

local function valid_id(value)
    return type(value) == "string" and #value > 0 and #value <= 128
        and value:match("^[A-Za-z0-9][A-Za-z0-9_.:%-]*$") ~= nil
end

local function integer(value, minimum)
    return type(value) == "number" and value == math.floor(value) and value >= minimum
end

local function time_value(value)
    return type(value) == "number" and value == value and value >= 0 and value < math.huge
end

local function answer(ok, code, data) return ok, code, clone(data or {}) end

local function sort_entities(left, right)
    return left.entity_id < right.entity_id
        or (left.entity_id == right.entity_id and left.revision < right.revision)
end

local function array_shape(value)
    if type(value) ~= "table" then return false end
    local count = 0
    for key in pairs(value) do
        if not integer(key, 1) then return false end
        count = count + 1
    end
    return count == #value
end

function Registry:_entity_index(entity_id)
    for index, item in ipairs(self.entity_rows) do
        if item.entity_id == entity_id then return index, item end
    end
    return nil, nil
end

function Registry:_latest(entity_id)
    for _, item in ipairs(self.latest_rows) do
        if item.entity_id == entity_id then return item.revision end
    end
    return 0
end

function Registry:_set_latest(entity_id, revision)
    for _, item in ipairs(self.latest_rows) do
        if item.entity_id == entity_id then
            item.revision = math.max(item.revision, revision)
            return
        end
    end
    self.latest_rows[#self.latest_rows + 1] = { entity_id = entity_id, revision = revision }
end

function Registry:_owner_count(player_id, except_entity_id)
    local count = 0
    for _, item in ipairs(self.entity_rows) do
        if item.owner_id == player_id and item.entity_id ~= except_entity_id then count = count + 1 end
    end
    return count
end

function Registry:_pending_index(player_id)
    for index, item in ipairs(self.pending_rows) do
        if item.player_id == player_id then return index, item end
    end
    return nil, nil
end

function Registry:_request(request_id, method, arguments)
    for _, item in ipairs(self.request_rows) do
        if item.request_id == request_id then
            local same = item.method == method and #item.arguments == #arguments
            for index, value in ipairs(arguments) do same = same and item.arguments[index] == value end
            if not same then return false, "request_conflict", {} end
            return item.ok, item.code, clone(item.data)
        end
    end
    return nil
end

function Registry:_record(request_id, method, arguments, ok, code, data)
    self.request_rows[#self.request_rows + 1] = {
        request_id = request_id, method = method, arguments = clone(arguments),
        ok = ok, code = code, data = clone(data or {}),
    }
    return answer(ok, code, data)
end

function Registry:_advance(now)
    if not time_value(now) then return nil, "invalid_now" end
    self.last_now = math.max(self.last_now, now)
    return self.last_now
end

local function restore(self, state)
    if type(state) ~= "table" or state.schema_version ~= 1 then
        return false, "invalid_state"
    end
    if state.max_props ~= self.max_props or state.cleanup_delay ~= self.cleanup_delay then
        return false, "state_configuration_mismatch"
    end
    if not time_value(state.last_now) or not integer(state.next_entity_sequence, 1) then
        return false, "invalid_state"
    end
    if not array_shape(state.entities) or not array_shape(state.latest_revisions)
        or not array_shape(state.pending_cleanup) or not array_shape(state.requests) then
        return false, "invalid_state"
    end
    self.entity_rows = clone(state.entities)
    self.latest_rows = clone(state.latest_revisions)
    self.pending_rows = clone(state.pending_cleanup)
    self.request_rows = clone(state.requests)
    self.last_now = state.last_now
    self.next_entity_sequence = state.next_entity_sequence
    local entities, latest, pending, requests, owners = {}, {}, {}, {}, {}
    for _, item in ipairs(self.entity_rows) do
        if type(item) ~= "table" or not valid_id(item.entity_id) or not valid_id(item.owner_id)
            or not integer(item.revision, 1) or entities[item.entity_id] then
            return false, "invalid_state"
        end
        entities[item.entity_id] = item.revision
        owners[item.owner_id] = (owners[item.owner_id] or 0) + 1
        if owners[item.owner_id] > self.max_props then return false, "invalid_state" end
    end
    for _, item in ipairs(self.latest_rows) do
        if type(item) ~= "table" or not valid_id(item.entity_id)
            or not integer(item.revision, 1) or latest[item.entity_id]
            or (entities[item.entity_id] and item.revision < entities[item.entity_id]) then
            return false, "invalid_state"
        end
        latest[item.entity_id] = item.revision
    end
    for entity_id in pairs(entities) do
        if not latest[entity_id] then return false, "invalid_state" end
    end
    for _, item in ipairs(self.pending_rows) do
        if type(item) ~= "table" or not valid_id(item.player_id)
            or not time_value(item.cleanup_at) or item.cleanup_at <= state.last_now
            or pending[item.player_id] then return false, "invalid_state" end
        pending[item.player_id] = true
    end
    for _, item in ipairs(self.request_rows) do
        if type(item) ~= "table" or not valid_id(item.request_id) or requests[item.request_id]
            or (item.method ~= "register" and item.method ~= "remove")
            or not array_shape(item.arguments) or type(item.ok) ~= "boolean"
            or type(item.code) ~= "string" or item.code == "" or type(item.data) ~= "table" then
            return false, "invalid_state"
        end
        if item.method == "register" and (#item.arguments ~= 3
            or not valid_id(item.arguments[1]) or not valid_id(item.arguments[2])
            or not integer(item.arguments[3], 1)) then return false, "invalid_state" end
        if item.method == "remove" and (#item.arguments ~= 2
            or not valid_id(item.arguments[1])
            or not integer(item.arguments[2], 1)) then return false, "invalid_state" end
        requests[item.request_id] = true
    end
    return true
end

function Registry.new(options)
    if type(options) ~= "table" or options.max_props ~= 2 or options.cleanup_delay ~= 5 then
        return nil, "invalid_options"
    end
    local self = setmetatable({ max_props = options.max_props,
        cleanup_delay = options.cleanup_delay, storage = options.storage,
        entity_rows = {}, latest_rows = {}, pending_rows = {}, request_rows = {},
        last_now = 0, next_entity_sequence = 1, stopped = false }, Registry)
    local state = options.state
    if state == nil and type(options.storage) == "table" and type(options.storage.load) == "function" then
        state = options.storage:load()
    end
    if state ~= nil then
        local ok, code = restore(self, state)
        if not ok then return nil, code end
    end
    return self
end

function Registry:register(request_id, player_id, entity_id, revision)
    if self.stopped then return answer(false, "shutdown") end
    if not valid_id(request_id) then return answer(false, "invalid_request_id") end
    if not valid_id(player_id) then return answer(false, "invalid_player_id") end
    if not valid_id(entity_id) then return answer(false, "invalid_entity_id") end
    if not integer(revision, 1) then return answer(false, "invalid_revision") end
    local arguments = { player_id, entity_id, revision }
    local prior_ok, prior_code, prior_data = self:_request(request_id, "register", arguments)
    if prior_ok ~= nil then return answer(prior_ok, prior_code, prior_data) end
    local index, current = self:_entity_index(entity_id)
    if (current and revision <= current.revision) or (not current and revision <= self:_latest(entity_id)) then
        return self:_record(request_id, "register", arguments, false, "stale_revision")
    end
    if self:_owner_count(player_id, current and entity_id or nil) >= self.max_props then
        return self:_record(request_id, "register", arguments, false, "quota_exceeded")
    end
    if index then table.remove(self.entity_rows, index) end
    self.entity_rows[#self.entity_rows + 1] = {
        entity_id = entity_id, revision = revision, owner_id = player_id,
    }
    self:_set_latest(entity_id, revision)
    local data = { entity_id = entity_id, revision = revision, owner_id = player_id,
        count = self:_owner_count(player_id) }
    return self:_record(request_id, "register", arguments, true, "registered", data)
end

function Registry:can_modify(player_id, entity_id, revision, operation)
    if self.stopped then return false, "shutdown" end
    if not valid_id(player_id) then return false, "invalid_player_id" end
    if not valid_id(entity_id) then return false, "invalid_entity_id" end
    if not integer(revision, 1) then return false, "invalid_revision" end
    if not operations[operation] then return false, "invalid_operation" end
    local _, current = self:_entity_index(entity_id)
    if not current then
        if revision < self:_latest(entity_id) then return false, "stale_revision" end
        return false, "not_found"
    end
    if current.revision ~= revision then return false, "stale_revision" end
    if current.owner_id ~= player_id then return false, "not_owner" end
    return true, "allowed"
end

function Registry:remove(request_id, entity_id, revision)
    if self.stopped then return answer(false, "shutdown") end
    if not valid_id(request_id) then return answer(false, "invalid_request_id") end
    if not valid_id(entity_id) then return answer(false, "invalid_entity_id") end
    if not integer(revision, 1) then return answer(false, "invalid_revision") end
    local arguments = { entity_id, revision }
    local prior_ok, prior_code, prior_data = self:_request(request_id, "remove", arguments)
    if prior_ok ~= nil then return answer(prior_ok, prior_code, prior_data) end
    local index, current = self:_entity_index(entity_id)
    if not current then
        local code = revision < self:_latest(entity_id) and "stale_revision" or "not_found"
        return self:_record(request_id, "remove", arguments, false, code)
    end
    if current.revision ~= revision then
        return self:_record(request_id, "remove", arguments, false, "stale_revision")
    end
    table.remove(self.entity_rows, index)
    self:_set_latest(entity_id, revision)
    local data = clone(current)
    data.count = self:_owner_count(current.owner_id)
    return self:_record(request_id, "remove", arguments, true, "removed", data)
end

function Registry:disconnect(player_id, now)
    if self.stopped then return answer(false, "shutdown") end
    if not valid_id(player_id) then return answer(false, "invalid_player_id") end
    local effective, code = self:_advance(now)
    if not effective then return answer(false, code) end
    local _, pending = self:_pending_index(player_id)
    if not pending then
        pending = { player_id = player_id, cleanup_at = effective + self.cleanup_delay }
        self.pending_rows[#self.pending_rows + 1] = pending
    end
    return answer(true, "scheduled", { cleanup_at = pending.cleanup_at })
end

function Registry:reconnect(player_id, now)
    if self.stopped then return answer(false, "shutdown") end
    if not valid_id(player_id) then return answer(false, "invalid_player_id") end
    local effective, code = self:_advance(now)
    if not effective then return answer(false, code) end
    local index = self:_pending_index(player_id)
    if index then table.remove(self.pending_rows, index) end
    return answer(true, index and "canceled" or "connected", { now = effective })
end

function Registry:tick(now)
    if self.stopped then return answer(false, "shutdown") end
    local effective, code = self:_advance(now)
    if not effective then return answer(false, code) end
    local removed = {}
    local pending_index = #self.pending_rows
    while pending_index >= 1 do
        local pending = self.pending_rows[pending_index]
        if effective >= pending.cleanup_at then
            local entity_index = #self.entity_rows
            while entity_index >= 1 do
                local item = self.entity_rows[entity_index]
                if item.owner_id == pending.player_id then
                    removed[#removed + 1] = clone(item)
                    self:_set_latest(item.entity_id, item.revision)
                    table.remove(self.entity_rows, entity_index)
                end
                entity_index = entity_index - 1
            end
            table.remove(self.pending_rows, pending_index)
        end
        pending_index = pending_index - 1
    end
    table.sort(removed, sort_entities)
    return answer(true, "ticked", { now = effective, removed = removed })
end

function Registry:snapshot(now)
    if not self.stopped then
        local ok, code = self:tick(now)
        if not ok then return nil, code end
    elseif not time_value(now) then return nil, "invalid_now" end
    local entities = clone(self.entity_rows)
    table.sort(entities, sort_entities)
    local owner_set = {}
    for _, item in ipairs(entities) do owner_set[item.owner_id] = true end
    for _, item in ipairs(self.pending_rows) do owner_set[item.player_id] = true end
    local owners = {}
    for player_id in pairs(owner_set) do
        local _, pending = self:_pending_index(player_id)
        owners[#owners + 1] = { player_id = player_id, count = self:_owner_count(player_id),
            disconnected = pending ~= nil, cleanup_at = pending and pending.cleanup_at or nil }
    end
    table.sort(owners, function(a, b) return a.player_id < b.player_id end)
    local pending = clone(self.pending_rows)
    table.sort(pending, function(a, b) return a.player_id < b.player_id end)
    return { schema_version = 1, now = self.last_now, owners = owners,
        entities = entities, pending_cleanup = pending }
end

function Registry:save(now)
    if not self.stopped then
        local ok, code = self:tick(now)
        if not ok then return nil, code end
    elseif not time_value(now) then return nil, "invalid_now" end
    local state = { schema_version = 1, max_props = self.max_props,
        cleanup_delay = self.cleanup_delay, last_now = self.last_now,
        next_entity_sequence = self.next_entity_sequence, entities = clone(self.entity_rows),
        latest_revisions = clone(self.latest_rows), pending_cleanup = clone(self.pending_rows),
        requests = clone(self.request_rows) }
    table.sort(state.entities, sort_entities)
    table.sort(state.latest_revisions, sort_entities)
    table.sort(state.pending_cleanup, function(a, b) return a.player_id < b.player_id end)
    table.sort(state.requests, function(a, b) return a.request_id < b.request_id end)
    if type(self.storage) == "table" and type(self.storage.save) == "function"
        and self.storage:save(clone(state)) == false then return nil, "storage_error" end
    return clone(state)
end

function Registry:shutdown()
    self.stopped = true
    return true, "shutdown"
end

return Registry
