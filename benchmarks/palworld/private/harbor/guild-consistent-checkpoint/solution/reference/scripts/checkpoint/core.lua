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
local function equal(a, b)
    for k, v in pairs(a) do if b[k] ~= v then return false end end
    for k, v in pairs(b) do if a[k] ~= v then return false end end
    return true
end
function Core.new(shards)
    local logs = {}
    assert(type(shards) == "table" and #shards >= 1 and #shards <= 16, "invalid_options")
    local count = 0
    for key in pairs(shards) do
        assert(type(key) == "number" and key % 1 == 0 and key >= 1 and key <= #shards, "invalid_options")
        count = count + 1
    end
    assert(count == #shards, "invalid_options")
    for _, shard in ipairs(shards) do
        assert(id(shard) and not logs[shard], "invalid_options")
        logs[shard] = {}
    end
    return setmetatable({logs = logs}, Core)
end
function Core.load(data)
    assert(type(data) == "table" and data.version == 1, "invalid_state")
    return setmetatable({logs = copy(data.logs)}, Core)
end
function Core:save() return {version = 1, logs = copy(self.logs)} end
function Core:append(e)
    if type(e) ~= "table" or not id(e.shard) or not self.logs[e.shard]
        or not integer(e.seq) or e.seq == 0 or type(e.deps) ~= "table" then return fail("invalid_request") end
    for shard, seq in pairs(e.deps) do
        if not self.logs[shard] or not integer(seq) or (shard == e.shard and seq >= e.seq) then
            return fail("invalid_request")
        end
    end
    local old = self.logs[e.shard][e.seq]
    if old then
        if not equal(old, e.deps) then return fail("event_conflict") end
        return {ok = true, duplicate = true}
    end
    self.logs[e.shard][e.seq] = copy(e.deps)
    return {ok = true, duplicate = false}
end
function Core:cut(limits)
    if type(limits) ~= "table" then return fail("invalid_request") end
    for shard, limit in pairs(limits) do
        if not self.logs[shard] or not integer(limit) then return fail("invalid_request") end
    end
    local cut = {}
    for shard, log in pairs(self.logs) do
        if limits[shard] == nil then return fail("invalid_request") end
        local prefix = 0
        while prefix < limits[shard] and log[prefix + 1] do prefix = prefix + 1 end
        cut[shard] = prefix
    end
    local changed = true
    while changed do
        changed = false
        for shard, log in pairs(self.logs) do
            for seq = 1, cut[shard] do
                local valid = true
                for dep, at in pairs(log[seq]) do
                    if cut[dep] < at then valid = false end
                end
                if not valid then cut[shard], changed = seq - 1, true; break end
            end
        end
    end
    return {ok = true, vector = cut}
end
function Core:snapshot()
    local result = {shards = {}}
    for shard, log in pairs(self.logs) do
        local count = 0
        for _ in pairs(log) do count = count + 1 end
        result.shards[#result.shards + 1] = {id = shard, count = count}
    end
    table.sort(result.shards, function(a, b) return a.id < b.id end)
    return result
end
return Core
