local Queue = {}
Queue.__index = Queue

local function valid_id(value)
    return type(value) == "string" and value ~= ""
end

local function nonnegative_integer(value)
    return type(value) == "number" and value >= 0 and value % 1 == 0
end

local function valid_now(value)
    return type(value) == "number" and value == value
end

local function copy(value, seen)
    if type(value) ~= "table" then return value end
    seen = seen or {}
    if seen[value] then return seen[value] end
    local result = {}
    seen[value] = result
    for key, item in pairs(value) do result[copy(key, seen)] = copy(item, seen) end
    return result
end

local function rejected(code)
    return { ok = false, code = code }
end

local function options_of(options)
    options = type(options) == "table" and options or {}
    local lease_seconds = options.lease_seconds
    local max_attempts = options.max_attempts
    if not valid_now(lease_seconds) or lease_seconds <= 0 then lease_seconds = 30 end
    if not nonnegative_integer(max_attempts) or max_attempts < 1 then max_attempts = 3 end
    return { lease_seconds = lease_seconds, max_attempts = max_attempts }
end

function Queue.new(options)
    local self = setmetatable({}, Queue)
    self.options = options_of(options)
    self.requests = {}
    self.tokens = {}
    self.worker_tokens = {}
    self.sequence = 0
    self.token_sequence = 0
    self.last_now = nil
    return self
end

function Queue.load(data, options)
    local self = Queue.new(options)
    if type(data) ~= "table" then return self end
    if type(data.requests) == "table" then self.requests = copy(data.requests) end
    if type(data.tokens) == "table" then self.tokens = copy(data.tokens) end
    if type(data.worker_tokens) == "table" then self.worker_tokens = copy(data.worker_tokens) end
    if nonnegative_integer(data.sequence) then self.sequence = data.sequence end
    if nonnegative_integer(data.token_sequence) then self.token_sequence = data.token_sequence end
    if valid_now(data.last_now) then self.last_now = data.last_now end
    return self
end

function Queue:_advance(now)
    if not valid_now(now) then return false, "invalid_now" end
    if self.last_now ~= nil and now < self.last_now then return false, "stale_now" end
    self.last_now = now
    return true
end

function Queue:_ordered_ready()
    local ready = {}
    for _, request in pairs(self.requests) do
        if request.state == "ready" then ready[#ready + 1] = request end
    end
    table.sort(ready, function(left, right)
        if left.priority ~= right.priority then return left.priority > right.priority end
        return left.sequence < right.sequence
    end)
    return ready
end

function Queue:_expire_due(now)
    local expired, exhausted = 0, 0
    local active_tokens = {}
    for token, lease in pairs(self.tokens) do
        if lease.state == "active" and now >= lease.expires_at then
            active_tokens[#active_tokens + 1] = token
        end
    end
    table.sort(active_tokens)
    for _, token in ipairs(active_tokens) do
        local lease = self.tokens[token]
        local request = self.requests[lease.request_id]
        lease.state = "expired"
        self.worker_tokens[lease.worker_id] = nil
        if request ~= nil and request.state == "leased" then
            request.token = nil
            request.worker_id = nil
            request.expires_at = nil
            if request.attempts >= self.options.max_attempts then
                request.state = "exhausted"
                exhausted = exhausted + 1
            else
                request.state = "ready"
                expired = expired + 1
            end
        end
    end
    return expired, exhausted
end

function Queue:enqueue(request_id, member_id, priority, now)
    if not valid_id(request_id) or not valid_id(member_id)
        or not nonnegative_integer(priority) or not valid_now(now) then
        return rejected("invalid_request")
    end
    if self.requests[request_id] ~= nil then
        local result = copy(self.requests[request_id].enqueue_result)
        result.duplicate = true
        return result
    end
    local advanced, code = self:_advance(now)
    if not advanced then return rejected(code) end
    self.sequence = self.sequence + 1
    local request = {
        request_id = request_id,
        member_id = member_id,
        priority = priority,
        sequence = self.sequence,
        attempts = 0,
        state = "ready",
        enqueue_result = {
            ok = true,
            duplicate = false,
            request_id = request_id,
            state = "ready",
        },
    }
    self.requests[request_id] = request
    return copy(request.enqueue_result)
end

function Queue:lease(worker_id, now)
    if not valid_id(worker_id) then return rejected("invalid_worker") end
    local advanced, code = self:_advance(now)
    if not advanced then return rejected(code) end
    self:_expire_due(now)
    local current = self.worker_tokens[worker_id]
    if current ~= nil and self.tokens[current] and self.tokens[current].state == "active" then
        return rejected("worker_busy")
    end
    local ready = self:_ordered_ready()
    if #ready == 0 then return rejected("empty") end

    local request = ready[1]
    request.attempts = request.attempts + 1
    request.state = "leased"
    self.token_sequence = self.token_sequence + 1
    local token = "raid-lease-" .. tostring(self.token_sequence)
    local expires_at = now + self.options.lease_seconds
    request.token = token
    request.worker_id = worker_id
    request.expires_at = expires_at
    self.tokens[token] = {
        token = token,
        request_id = request.request_id,
        worker_id = worker_id,
        expires_at = expires_at,
        state = "active",
    }
    self.worker_tokens[worker_id] = token
    return {
        ok = true,
        token = token,
        request_id = request.request_id,
        member_id = request.member_id,
        priority = request.priority,
        attempt = request.attempts,
        expires_at = expires_at,
    }
end

function Queue:renew(token, now)
    if not valid_id(token) then return rejected("unknown_token") end
    local advanced, code = self:_advance(now)
    if not advanced then return rejected(code) end
    self:_expire_due(now)
    local lease = self.tokens[token]
    if lease == nil or lease.state ~= "active" then return rejected("unknown_token") end
    lease.expires_at = now + self.options.lease_seconds
    local request = self.requests[lease.request_id]
    if request ~= nil then request.expires_at = lease.expires_at end
    return { ok = true, token = token, expires_at = lease.expires_at }
end

function Queue:complete(token, outcome, now)
    if not valid_id(token) or not valid_id(outcome) then return rejected("invalid_request") end
    local advanced, code = self:_advance(now)
    if not advanced then return rejected(code) end
    self:_expire_due(now)
    local lease = self.tokens[token]
    if lease == nil or lease.state ~= "active" then return rejected("unknown_token") end
    local request = self.requests[lease.request_id]
    lease.state = "completed"
    self.worker_tokens[lease.worker_id] = nil
    request.state = "completed"
    request.outcome = outcome
    request.token = nil
    request.worker_id = nil
    request.expires_at = nil
    return { ok = true, request_id = request.request_id, outcome = outcome, state = "completed" }
end

function Queue:release(token, now)
    if not valid_id(token) then return rejected("unknown_token") end
    local advanced, code = self:_advance(now)
    if not advanced then return rejected(code) end
    self:_expire_due(now)
    local lease = self.tokens[token]
    if lease == nil or lease.state ~= "active" then return rejected("unknown_token") end
    local request = self.requests[lease.request_id]
    lease.state = "released"
    self.worker_tokens[lease.worker_id] = nil
    request.state = "ready"
    request.token = nil
    request.worker_id = nil
    request.expires_at = nil
    return { ok = true, request_id = request.request_id, state = "ready" }
end

function Queue:expire(now)
    local advanced, code = self:_advance(now)
    if not advanced then return rejected(code) end
    local expired, exhausted = self:_expire_due(now)
    return { ok = true, expired = expired, exhausted = exhausted }
end

function Queue:snapshot(now)
    if valid_now(now) and (self.last_now == nil or now >= self.last_now) then
        self.last_now = now
        self:_expire_due(now)
    end
    local ready = self:_ordered_ready()
    local result = {
        ready = #ready,
        leased = 0,
        completed = 0,
        exhausted = 0,
        order = {},
    }
    for index, request in ipairs(ready) do result.order[index] = request.request_id end
    for _, request in pairs(self.requests) do
        if request.state == "leased" then result.leased = result.leased + 1 end
        if request.state == "completed" then result.completed = result.completed + 1 end
        if request.state == "exhausted" then result.exhausted = result.exhausted + 1 end
    end
    return result
end

function Queue:save(now)
    if valid_now(now) and (self.last_now == nil or now >= self.last_now) then
        self.last_now = now
        self:_expire_due(now)
    end
    return {
        requests = copy(self.requests),
        tokens = copy(self.tokens),
        worker_tokens = copy(self.worker_tokens),
        sequence = self.sequence,
        token_sequence = self.token_sequence,
        last_now = self.last_now,
    }
end

return Queue
