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
local function dense(t, limit)
    if type(t) ~= "table" or #t > limit then return false end
    local n = 0
    for k in pairs(t) do
        if type(k) ~= "number" or k % 1 ~= 0 or k < 1 or k > #t then return false end
        n = n + 1
    end
    return n == #t
end
function Core.new() return setmetatable({revision = -1, result = nil}, Core) end
function Core.load(data)
    assert(type(data) == "table" and data.version == 1, "invalid_state")
    return setmetatable({revision = data.revision, result = copy(data.result)}, Core)
end
function Core:save() return {version = 1, revision = self.revision, result = copy(self.result)} end
function Core:snapshot() return copy(self.result or {revision = -1, assignments = {}}) end
function Core:plan(input)
    if type(input) ~= "table" or not integer(input.revision)
        or not dense(input.pals, 12) or not dense(input.jobs, 12) then return fail("invalid_request") end
    local pals, jobs, seen = copy(input.pals), copy(input.jobs), {}
    for _, pal in ipairs(pals) do
        if type(pal) ~= "table" or not id(pal.id) or seen[pal.id] then return fail("invalid_request") end
        seen[pal.id] = true
    end
    seen = {}
    for _, job in ipairs(jobs) do
        if type(job) ~= "table" or not id(job.id) or seen[job.id] or not integer(job.priority)
            or type(job.costs) ~= "table" then return fail("invalid_request") end
        seen[job.id] = true
        for pal, cost in pairs(job.costs) do
            local exists = false
            for _, p in ipairs(pals) do if p.id == pal then exists = true end end
            if not exists or not integer(cost) then return fail("invalid_request") end
        end
    end
    if input.revision <= self.revision then return fail("stale_revision") end
    table.sort(pals, function(a, b) return a.id < b.id end)
    table.sort(jobs, function(a, b) return a.id < b.id end)
    local function better(a, b)
        if not b then return true end
        if a.priority ~= b.priority then return a.priority > b.priority end
        if a.count ~= b.count then return a.count > b.count end
        if a.cost ~= b.cost then return a.cost < b.cost end
        return a.key < b.key
    end
    local states = {[0] = {priority = 0, count = 0, cost = 0, key = "", assignments = {}}}
    for _, job in ipairs(jobs) do
        local next_states = {}
        for mask, old in pairs(states) do
            local skipped = copy(old)
            skipped.key = skipped.key .. "~!"
            if better(skipped, next_states[mask]) then next_states[mask] = skipped end
            for i, pal in ipairs(pals) do
                local bit = 1 << (i - 1)
                local cost = job.costs[pal.id]
                if mask & bit == 0 and cost ~= nil then
                    local candidate = copy(old)
                    candidate.priority = old.priority + job.priority
                    candidate.count = old.count + 1
                    candidate.cost = old.cost + cost
                    candidate.key = old.key .. pal.id .. "!"
                    candidate.assignments[#candidate.assignments + 1] = {job = job.id, pal = pal.id}
                    local target = mask | bit
                    if better(candidate, next_states[target]) then next_states[target] = candidate end
                end
            end
        end
        states = next_states
    end
    local best
    for _, candidate in pairs(states) do if better(candidate, best) then best = candidate end end
    self.revision = input.revision
    self.result = {ok = true, revision = input.revision, priority = best.priority,
        count = best.count, cost = best.cost, assignments = best.assignments}
    return copy(self.result)
end
return Core
