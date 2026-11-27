local Ledger = {}
Ledger.__index = Ledger

local function is_integer(value)
    return type(value) == "number" and value >= 0 and value % 1 == 0
end

local function valid_id(value)
    return type(value) == "string" and value ~= ""
end

local function copy(value, seen)
    if type(value) ~= "table" then
        return value
    end
    seen = seen or {}
    if seen[value] then
        return seen[value]
    end
    local result = {}
    seen[value] = result
    for key, item in pairs(value) do
        result[copy(key, seen)] = copy(item, seen)
    end
    return result
end

local function request_key(member_id, request_id)
    return member_id .. "\31" .. request_id
end

local function rejected(code)
    return { ok = false, code = code, duplicate = false }
end

local function response(value, duplicate)
    local result = copy(value)
    if result.duplicate ~= nil or duplicate then
        result.duplicate = duplicate == true
    end
    return result
end

local function normalized_options(options)
    options = type(options) == "table" and options or {}
    local quota = options.quota
    if not is_integer(quota) then
        quota = 0
    end
    local bundles = {}
    if type(options.bundles) == "table" then
        for bundle_id, entries in pairs(options.bundles) do
            if valid_id(bundle_id) and type(entries) == "table" then
                bundles[bundle_id] = copy(entries)
            end
        end
    end
    return { quota = quota, bundles = bundles }
end

function Ledger.new(options)
    local self = setmetatable({}, Ledger)
    self.options = normalized_options(options)
    self.cycle = nil
    self.members = {}
    self.requests = {}
    self.reservations = {}
    self.token_sequence = 0
    return self
end

function Ledger.load(data, options)
    local self = Ledger.new(options)
    if type(data) ~= "table" then
        return self
    end
    if is_integer(data.cycle) then
        self.cycle = data.cycle
    end
    if type(data.members) == "table" then
        for member_id, member in pairs(data.members) do
            if valid_id(member_id) and type(member) == "table" then
                self.members[member_id] = {
                    active = member.active == true,
                    used = is_integer(member.used) and member.used or 0,
                }
            end
        end
    end
    if type(data.requests) == "table" then
        self.requests = copy(data.requests)
    end
    if type(data.reservations) == "table" then
        self.reservations = copy(data.reservations)
    end
    if is_integer(data.token_sequence) then
        self.token_sequence = data.token_sequence
    end
    return self
end

function Ledger:begin_cycle(cycle)
    if not is_integer(cycle) then
        return { ok = false, code = "invalid_cycle" }
    end
    if self.cycle ~= nil and cycle <= self.cycle then
        return { ok = false, code = "stale_cycle" }
    end
    self.cycle = cycle
    for _, member in pairs(self.members) do
        member.used = 0
    end
    return { ok = true, cycle = cycle }
end

function Ledger:set_member(member_id, active)
    if not valid_id(member_id) or type(active) ~= "boolean" then
        return { ok = false, code = "invalid_member" }
    end
    local member = self.members[member_id]
    if member == nil then
        member = { active = active, used = 0 }
        self.members[member_id] = member
    else
        member.active = active
    end
    return { ok = true, member_id = member_id, active = active }
end

function Ledger:_remember(member_id, request_id, result)
    self.requests[request_key(member_id, request_id)] = copy(result)
    return response(result, false)
end

function Ledger:claim(member_id, request_id, bundle_id, cycle)
    if not valid_id(member_id) or not valid_id(request_id) or not valid_id(bundle_id) then
        return rejected("invalid_request")
    end
    local key = request_key(member_id, request_id)
    local remembered = self.requests[key]
    if remembered ~= nil then
        return response(remembered, true)
    end
    if not is_integer(cycle) or cycle ~= self.cycle then
        return self:_remember(member_id, request_id, rejected("stale_cycle"))
    end

    local bundle = self.options.bundles[bundle_id]
    if type(bundle) ~= "table" then
        return self:_remember(member_id, request_id, rejected("unknown_bundle"))
    end
    local items = {}
    local item_count = 0
    for item_id, count in pairs(bundle) do
        if not valid_id(item_id) or not is_integer(count) or count <= 0 then
            return self:_remember(member_id, request_id, rejected("invalid_request"))
        end
        items[item_id] = count
        item_count = item_count + 1
    end
    if item_count == 0 then
        return self:_remember(member_id, request_id, rejected("invalid_request"))
    end

    local member = self.members[member_id]
    if member == nil or not member.active then
        return self:_remember(member_id, request_id, rejected("inactive_member"))
    end
    if member.used >= self.options.quota then
        return self:_remember(member_id, request_id, rejected("quota_exhausted"))
    end

    self.token_sequence = self.token_sequence + 1
    local token = "guild-reservation-" .. tostring(self.token_sequence)
    member.used = member.used + 1
    local result = {
        ok = true,
        token = token,
        bundle_id = bundle_id,
        items = copy(items),
        duplicate = false,
        state = "pending",
    }
    self.reservations[token] = {
        member_id = member_id,
        request_key = key,
        cycle = cycle,
        state = "pending",
    }
    self.requests[key] = copy(result)
    return response(result, false)
end

function Ledger:commit(token)
    if not valid_id(token) then
        return { ok = false, code = "unknown_token" }
    end
    local reservation = self.reservations[token]
    if reservation == nil then
        return { ok = false, code = "unknown_token" }
    end
    if reservation.state ~= "pending" then
        return { ok = false, code = "token_consumed" }
    end
    reservation.state = "committed"
    local remembered = self.requests[reservation.request_key]
    if remembered then
        remembered.state = "committed"
    end
    return { ok = true, state = "committed" }
end

function Ledger:rollback(token)
    if not valid_id(token) then
        return { ok = false, code = "unknown_token" }
    end
    local reservation = self.reservations[token]
    if reservation == nil then
        return { ok = false, code = "unknown_token" }
    end
    if reservation.state ~= "pending" then
        return { ok = false, code = "token_consumed" }
    end
    reservation.state = "rolled_back"
    if reservation.cycle == self.cycle then
        local member = self.members[reservation.member_id]
        if member and member.used > 0 then
            member.used = member.used - 1
        end
    end
    local remembered = self.requests[reservation.request_key]
    if remembered then
        remembered.ok = false
        remembered.code = "rolled_back"
        remembered.state = "rolled_back"
        remembered.items = nil
    end
    return { ok = true, state = "rolled_back" }
end

function Ledger:snapshot()
    local member_ids = {}
    for member_id in pairs(self.members) do
        member_ids[#member_ids + 1] = member_id
    end
    table.sort(member_ids)
    local members = {}
    for _, member_id in ipairs(member_ids) do
        local member = self.members[member_id]
        members[#members + 1] = {
            member_id = member_id,
            remaining = math.max(0, self.options.quota - member.used),
        }
    end
    local pending, committed, rolled_back = 0, 0, 0
    for _, reservation in pairs(self.reservations) do
        if reservation.state == "pending" then pending = pending + 1 end
        if reservation.state == "committed" then committed = committed + 1 end
        if reservation.state == "rolled_back" then rolled_back = rolled_back + 1 end
    end
    return {
        cycle = self.cycle,
        pending = pending,
        committed = committed,
        rolled_back = rolled_back,
        members = members,
    }
end

function Ledger:save()
    return {
        cycle = self.cycle,
        members = copy(self.members),
        requests = copy(self.requests),
        reservations = copy(self.reservations),
        token_sequence = self.token_sequence,
    }
end

return Ledger
