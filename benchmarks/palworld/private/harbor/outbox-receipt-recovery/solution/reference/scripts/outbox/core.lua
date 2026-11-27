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
function Core.new()
    return setmetatable({records = {}, next_seq = 1}, Core)
end
function Core.load(data)
    assert(type(data) == "table" and data.version == 1, "invalid_state")
    local self = Core.new()
    self.records, self.next_seq = copy(data.records), data.next_seq
    return self
end
function Core:save()
    return {version = 1, records = copy(self.records), next_seq = self.next_seq}
end
function Core:submit(request, journal)
    if type(request) ~= "table" or not id(request.id) or not id(request.member)
        or not id(request.bundle) or not integer(request.count) or request.count == 0 then
        return fail("invalid_request")
    end
    local old = self.records[request.id]
    if old then
        if old.member ~= request.member or old.bundle ~= request.bundle or old.count ~= request.count then
            return fail("request_conflict")
        end
        return {ok = true, duplicate = true, state = old.state, seq = old.seq}
    end
    local next_state = self:save()
    local record = copy(request)
    record.seq, record.state = self.next_seq, "pending"
    next_state.records[request.id] = record
    next_state.next_seq = self.next_seq + 1
    local ok, result = pcall(journal, copy(next_state))
    if not ok or result ~= true then return fail("storage_unavailable") end
    self.records, self.next_seq = next_state.records, next_state.next_seq
    return {ok = true, duplicate = false, state = "pending", seq = record.seq}
end
function Core:drain(adapter, journal)
    local order = {}
    for _, r in pairs(self.records) do
        if r.state == "pending" then order[#order + 1] = r end
    end
    table.sort(order, function(a, b) return a.seq < b.seq end)
    local completed = 0
    for _, record in ipairs(order) do
        local ok, receipt = pcall(adapter.lookup, record.id)
        if not ok or receipt == "unknown" then
            return {ok = false, code = "delivery_uncertain", completed = completed}
        end
        if receipt == "absent" then
            ok, receipt = pcall(adapter.deliver, copy(record))
        end
        if not ok or (receipt ~= "applied" and receipt ~= "rejected") then
            return {ok = false, code = "delivery_uncertain", completed = completed}
        end
        local next_state = self:save()
        next_state.records[record.id].state = receipt
        local saved, result = pcall(journal, copy(next_state))
        if not saved or result ~= true then
            return {ok = false, code = "storage_unavailable", completed = completed}
        end
        self.records = next_state.records
        completed = completed + 1
    end
    return {ok = true, completed = completed}
end
function Core:status(key)
    local r = self.records[key]
    if not r then return {state = "unknown"} end
    return {state = r.state, seq = r.seq}
end
function Core:snapshot()
    local result = {pending = 0, applied = 0, rejected = 0}
    for _, r in pairs(self.records) do result[r.state] = result[r.state] + 1 end
    return result
end
return Core
