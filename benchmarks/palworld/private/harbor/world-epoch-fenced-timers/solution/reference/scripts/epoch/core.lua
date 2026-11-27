local Core = {}
Core.__index = Core
local function copy(x)
    if type(x) ~= "table" then return x end
    local r = {}
    for k, v in pairs(x) do r[k] = copy(v) end
    return r
end
local function id(x)
    return type(x) == "string" and #x > 0 and #x <= 64 and x:match("^[%w_-]+$") ~= nil
end
local function integer(x)
    return type(x) == "number" and x >= 0 and x <= 1000000 and x % 1 == 0
end
local function fail(code) return {ok = false, code = code} end
function Core.new() return setmetatable({epoch = 0, now = 0, tasks = {}}, Core) end
function Core.load(data)
    assert(type(data) == "table" and data.version == 1, "invalid_state")
    return setmetatable({epoch = data.epoch, now = data.now, tasks = copy(data.tasks)}, Core)
end
function Core:save() return {version = 1, epoch = self.epoch, now = self.now, tasks = copy(self.tasks)} end
function Core:mount(epoch, now)
    if not integer(epoch) or not integer(now) then return fail("invalid_request") end
    if epoch <= self.epoch then return fail("stale_epoch") end
    if now < self.now then return fail("stale_now") end
    self.epoch, self.now = epoch, now
    for _, task in pairs(self.tasks) do
        if task.state == "leased" then task.state = "pending" end
    end
    return {ok = true}
end
function Core:schedule(request)
    if type(request) ~= "table" or not id(request.id) or not id(request.payload)
        or not integer(request.due) then return fail("invalid_request") end
    if self.epoch == 0 then return fail("not_mounted") end
    local old = self.tasks[request.id]
    if old then
        if old.due ~= request.due or old.payload ~= request.payload then return fail("request_conflict") end
        return {ok = true, duplicate = true, state = old.state}
    end
    local task = copy(request)
    task.state, task.generation = "pending", 0
    self.tasks[request.id] = task
    return {ok = true, duplicate = false, state = "pending"}
end
function Core:poll(epoch, now)
    if not integer(epoch) or not integer(now) then return fail("invalid_request") end
    if epoch ~= self.epoch or epoch == 0 then return fail("stale_epoch") end
    if now < self.now then return fail("stale_now") end
    self.now = now
    local ready = {}
    for _, task in pairs(self.tasks) do
        if task.state == "pending" and task.due <= now then ready[#ready + 1] = task end
    end
    table.sort(ready, function(a, b) return a.due < b.due or (a.due == b.due and a.id < b.id) end)
    local result = {ok = true, deliveries = {}}
    for _, task in ipairs(ready) do
        task.generation = task.generation + 1
        task.state = "leased"
        result.deliveries[#result.deliveries + 1] = {
            id = task.id, payload = task.payload, epoch = self.epoch, generation = task.generation,
        }
    end
    return result
end
function Core:ack(token, success)
    if type(token) ~= "table" or not id(token.id) or not integer(token.epoch)
        or not integer(token.generation) or type(success) ~= "boolean" then return fail("invalid_request") end
    if token.epoch ~= self.epoch or token.epoch == 0 then return fail("stale_epoch") end
    local task = self.tasks[token.id]
    if not task or task.state ~= "leased" or task.generation ~= token.generation then return fail("stale_token") end
    task.state = success and "done" or "pending"
    return {ok = true, state = task.state}
end
function Core:cancel(key)
    if not id(key) then return fail("invalid_request") end
    local task = self.tasks[key]
    if not task then return fail("unknown_task") end
    if task.state == "done" then return fail("already_done") end
    task.state = "canceled"
    return {ok = true, state = "canceled"}
end
function Core:snapshot()
    local r = {epoch = self.epoch, now = self.now, pending = 0, leased = 0, done = 0, canceled = 0}
    for _, task in pairs(self.tasks) do r[task.state] = r[task.state] + 1 end
    return r
end
return Core
