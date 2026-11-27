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
    return setmetatable({watermark = 0, events = {}, final = {}}, Core)
end
function Core.load(data)
    assert(type(data) == "table" and data.version == 1, "invalid_state")
    return setmetatable({watermark = data.watermark, events = copy(data.events), final = copy(data.final)}, Core)
end
function Core:save()
    return {version = 1, watermark = self.watermark, events = copy(self.events), final = copy(self.final)}
end
function Core:observe(e)
    if type(e) ~= "table" or not id(e.id) or not id(e.member) or not integer(e.tick)
        or not integer(e.amount) or not integer(e.revision) or type(e.deleted) ~= "boolean" then
        return fail("invalid_request")
    end
    local old = self.events[e.id]
    if old and (old.member ~= e.member or old.tick ~= e.tick) then return fail("identity_conflict") end
    if old and old.revision == e.revision then
        if old.amount ~= e.amount or old.deleted ~= e.deleted then return fail("revision_conflict") end
        return {ok = true, duplicate = true}
    end
    if old and e.revision < old.revision then return fail("stale_revision") end
    if e.tick < self.watermark then return fail("late_event") end
    self.events[e.id] = copy(e)
    return {ok = true, duplicate = false}
end
function Core:advance(w)
    if not integer(w) then return fail("invalid_request") end
    if w < self.watermark then return fail("stale_watermark") end
    self.watermark = w
    local totals = {}
    for _, e in pairs(self.events) do
        if e.tick < w and not e.deleted then
            local window = e.tick // 10
            totals[window] = totals[window] or {}
            totals[window][e.member] = (totals[window][e.member] or 0) + e.amount
        end
    end
    for window, members in pairs(totals) do
        if (window + 1) * 10 <= w and self.final[window] == nil then
            local winner, score = nil, -1
            for member, amount in pairs(members) do
                if amount > score or (amount == score and member < winner) then winner, score = member, amount end
            end
            self.final[window] = {window = window, member = winner, amount = score}
        end
    end
    return {ok = true, watermark = w}
end
function Core:result(window)
    if not integer(window) then return fail("invalid_request") end
    if (window + 1) * 10 > self.watermark then return fail("not_final") end
    return copy(self.final[window] or {window = window, amount = 0})
end
function Core:snapshot()
    local result = {watermark = self.watermark, results = {}}
    for _, value in pairs(self.final) do result.results[#result.results + 1] = copy(value) end
    table.sort(result.results, function(a, b) return a.window < b.window end)
    return result
end
return Core
