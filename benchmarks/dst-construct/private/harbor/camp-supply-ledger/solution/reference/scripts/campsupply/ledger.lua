-- Pure Lua supply ledger. It has no engine dependency: quotas, idempotent
-- requests, reservations and persistence are decided here, while the world
-- component only performs the actual item delivery.

local Ledger = {}
Ledger.__index = Ledger

local MAX_ID_LENGTH = 64

local function is_identifier(value)
    if type(value) ~= "string" or value == "" or #value > MAX_ID_LENGTH then
        return false
    end
    return string.find(value, "%c") == nil
end

local function is_day(value)
    return type(value) == "number" and value == value and value >= 0
        and value ~= math.huge and math.floor(value) == value
end

local function is_positive_integer(value)
    return type(value) == "number" and value == value and value >= 1
        and value ~= math.huge and math.floor(value) == value
end

local function sorted_keys(map)
    local keys = {}
    for key in pairs(map) do
        keys[#keys + 1] = key
    end
    table.sort(keys, function(left, right)
        return tostring(left) < tostring(right)
    end)
    return keys
end

local function copy_items(items)
    local out = {}
    for index = 1, #items do
        out[index] = { prefab = items[index].prefab, count = items[index].count }
    end
    return out
end

-- Server configuration is normalized once; a malformed bundle is dropped so it
-- can never be claimed.
local function normalize_bundles(raw)
    local bundles = {}
    if type(raw) ~= "table" then
        return bundles
    end
    for bundle_id, entries in pairs(raw) do
        if is_identifier(bundle_id) and type(entries) == "table" then
            local totals, valid = {}, true
            local function add(prefab, count)
                if is_identifier(prefab) and is_positive_integer(count) then
                    totals[prefab] = (totals[prefab] or 0) + count
                else
                    valid = false
                end
            end
            if #entries > 0 then
                for _, entry in ipairs(entries) do
                    if type(entry) == "table" then
                        add(entry.prefab, entry.count)
                    else
                        valid = false
                    end
                end
            else
                for prefab, count in pairs(entries) do
                    add(prefab, count)
                end
            end
            local items = {}
            for _, prefab in ipairs(sorted_keys(totals)) do
                items[#items + 1] = { prefab = prefab, count = totals[prefab] }
            end
            if valid and #items > 0 then
                bundles[bundle_id] = items
            end
        end
    end
    return bundles
end

local function normalize_limits(raw)
    local limits = {}
    if type(raw) == "table" then
        for prefab, limit in pairs(raw) do
            if is_identifier(prefab) and is_positive_integer(limit) then
                limits[prefab] = limit
            end
        end
    end
    return limits
end

function Ledger.new(options)
    local self = setmetatable({}, Ledger)
    options = type(options) == "table" and options or {}
    self.bundles = normalize_bundles(options.bundles)
    self.daily_limits = normalize_limits(options.daily_limits)
    self.day = nil
    self.players = {}
    self.usage = {}
    self.requests = {}
    self.reservations = {}
    self.next_token = 1
    return self
end

function Ledger:_usage(day, player_id, prefab)
    local by_day = self.usage[day]
    if by_day == nil then
        by_day = {}
        self.usage[day] = by_day
    end
    local by_player = by_day[player_id]
    if by_player == nil then
        by_player = {}
        by_day[player_id] = by_player
    end
    local entry = by_player[prefab]
    if entry == nil then
        entry = { reserved = 0, committed = 0 }
        by_player[prefab] = entry
    end
    return entry
end

function Ledger:begin_day(day)
    if not is_day(day) then
        return false
    end
    if self.day ~= nil and day <= self.day then
        return false
    end
    self.day = day
    -- Older days stay only while a pending reservation still settles there.
    local keep = { [day] = true }
    for _, reservation in pairs(self.reservations) do
        if reservation.status == "pending" then
            keep[reservation.day] = true
        end
    end
    for old_day in pairs(self.usage) do
        if not keep[old_day] then
            self.usage[old_day] = nil
        end
    end
    return true
end

function Ledger:set_player(player_id, active)
    if not is_identifier(player_id) then
        return false
    end
    self.players[player_id] = active and true or false
    return true
end

local function request_key(player_id, request_id)
    return player_id .. "\0" .. request_id
end

local function replay(record)
    local out = { ok = record.ok, status = record.status, reason = record.reason, token = record.token }
    if record.items ~= nil then
        out.items = copy_items(record.items)
    end
    return out
end

function Ledger:_reject(key, reason)
    local record = { ok = false, status = "rejected", reason = reason }
    if key ~= nil then
        self.requests[key] = record
    end
    return replay(record)
end

function Ledger:claim(player_id, request_id, bundle_id, day)
    if not is_identifier(player_id) or not is_identifier(request_id) then
        return { ok = false, status = "rejected", reason = "invalid_id" }
    end
    -- The idempotency record is consulted before any quota is touched.
    local key = request_key(player_id, request_id)
    local known = self.requests[key]
    if known ~= nil then
        if known.token ~= nil then
            local reservation = self.reservations[known.token]
            known.status = reservation.status
            known.ok = reservation.status ~= "rolled_back"
        end
        return replay(known)
    end
    -- A stale or foreign day changes nothing, not even the request history.
    if not is_day(day) or self.day == nil or day ~= self.day then
        return { ok = false, status = "rejected", reason = "stale_day" }
    end
    if not is_identifier(bundle_id) or self.bundles[bundle_id] == nil then
        return self:_reject(key, "unknown_bundle")
    end
    if not self.players[player_id] then
        return self:_reject(key, "inactive_player")
    end
    local items = self.bundles[bundle_id]
    for index = 1, #items do
        local item = items[index]
        local limit = self.daily_limits[item.prefab]
        local used = self:_usage(day, player_id, item.prefab)
        if limit == nil or used.reserved + used.committed + item.count > limit then
            return self:_reject(key, "quota_exceeded")
        end
    end

    local token = string.format("supply-%08d", self.next_token)
    self.next_token = self.next_token + 1
    for index = 1, #items do
        local used = self:_usage(day, player_id, items[index].prefab)
        used.reserved = used.reserved + items[index].count
    end
    self.reservations[token] = {
        token = token,
        player_id = player_id,
        request_id = request_id,
        bundle_id = bundle_id,
        day = day,
        items = copy_items(items),
        status = "pending",
    }
    local record = { ok = true, status = "pending", token = token, items = copy_items(items) }
    self.requests[key] = record
    return replay(record)
end

function Ledger:commit(token)
    local reservation = type(token) == "string" and self.reservations[token] or nil
    if reservation == nil then
        return { ok = false, status = "unknown", reason = "unknown_token" }
    end
    if reservation.status == "pending" then
        for index = 1, #reservation.items do
            local item = reservation.items[index]
            local used = self:_usage(reservation.day, reservation.player_id, item.prefab)
            used.reserved = used.reserved - item.count
            used.committed = used.committed + item.count
        end
        reservation.status = "committed"
    end
    return {
        ok = reservation.status == "committed",
        status = reservation.status,
        token = token,
    }
end

function Ledger:rollback(token)
    local reservation = type(token) == "string" and self.reservations[token] or nil
    if reservation == nil then
        return { ok = false, status = "unknown", reason = "unknown_token" }
    end
    if reservation.status == "pending" then
        for index = 1, #reservation.items do
            local item = reservation.items[index]
            local used = self:_usage(reservation.day, reservation.player_id, item.prefab)
            used.reserved = used.reserved - item.count
        end
        reservation.status = "rolled_back"
        return { ok = true, status = "rolled_back", token = token }
    end
    -- Quota is released at most once; a committed token is never released.
    return {
        ok = false,
        status = reservation.status,
        token = token,
        reason = reservation.status == "committed" and "already_committed" or "already_rolled_back",
    }
end

function Ledger:snapshot()
    local players = {}
    for _, player_id in ipairs(sorted_keys(self.players)) do
        local usage = {}
        local today = self.day ~= nil and self.usage[self.day] or nil
        local by_player = today ~= nil and today[player_id] or {}
        for _, prefab in ipairs(sorted_keys(self.daily_limits)) do
            local used = by_player[prefab] or { reserved = 0, committed = 0 }
            usage[#usage + 1] = {
                prefab = prefab,
                limit = self.daily_limits[prefab],
                reserved = used.reserved,
                committed = used.committed,
                remaining = self.daily_limits[prefab] - used.reserved - used.committed,
            }
        end
        players[#players + 1] = { player_id = player_id, active = self.players[player_id], usage = usage }
    end
    local reservations = {}
    for _, token in ipairs(sorted_keys(self.reservations)) do
        local reservation = self.reservations[token]
        reservations[#reservations + 1] = {
            token = token,
            player_id = reservation.player_id,
            request_id = reservation.request_id,
            bundle_id = reservation.bundle_id,
            day = reservation.day,
            status = reservation.status,
            items = copy_items(reservation.items),
        }
    end
    return { day = self.day, players = players, reservations = reservations }
end

function Ledger:save()
    local usage = {}
    for _, day in ipairs(sorted_keys(self.usage)) do
        for _, player_id in ipairs(sorted_keys(self.usage[day])) do
            for _, prefab in ipairs(sorted_keys(self.usage[day][player_id])) do
                local used = self.usage[day][player_id][prefab]
                usage[#usage + 1] = {
                    day = day, player_id = player_id, prefab = prefab,
                    reserved = used.reserved, committed = used.committed,
                }
            end
        end
    end
    local players = {}
    for _, player_id in ipairs(sorted_keys(self.players)) do
        players[#players + 1] = { player_id = player_id, active = self.players[player_id] }
    end
    local requests = {}
    for _, key in ipairs(sorted_keys(self.requests)) do
        local record = self.requests[key]
        requests[#requests + 1] = {
            key = key, ok = record.ok, status = record.status, reason = record.reason,
            token = record.token, items = record.items ~= nil and copy_items(record.items) or nil,
        }
    end
    local snapshot = self:snapshot()
    return {
        version = 1,
        day = self.day,
        next_token = self.next_token,
        players = players,
        usage = usage,
        requests = requests,
        reservations = snapshot.reservations,
    }
end

function Ledger.load(data, options)
    local self = Ledger.new(options)
    if type(data) ~= "table" then
        return self
    end
    if is_day(data.day) then
        self.day = data.day
    end
    if is_positive_integer(data.next_token) then
        self.next_token = data.next_token
    end
    for _, entry in ipairs(type(data.players) == "table" and data.players or {}) do
        if type(entry) == "table" and is_identifier(entry.player_id) then
            self.players[entry.player_id] = entry.active and true or false
        end
    end
    for _, entry in ipairs(type(data.usage) == "table" and data.usage or {}) do
        if type(entry) == "table" and is_day(entry.day) and is_identifier(entry.player_id)
            and is_identifier(entry.prefab) then
            local used = self:_usage(entry.day, entry.player_id, entry.prefab)
            used.reserved = tonumber(entry.reserved) or 0
            used.committed = tonumber(entry.committed) or 0
        end
    end
    for _, entry in ipairs(type(data.reservations) == "table" and data.reservations or {}) do
        if type(entry) == "table" and is_identifier(entry.token) and type(entry.items) == "table" then
            self.reservations[entry.token] = {
                token = entry.token,
                player_id = entry.player_id,
                request_id = entry.request_id,
                bundle_id = entry.bundle_id,
                day = entry.day,
                status = entry.status,
                items = copy_items(entry.items),
            }
        end
    end
    for _, entry in ipairs(type(data.requests) == "table" and data.requests or {}) do
        if type(entry) == "table" and type(entry.key) == "string" then
            if entry.token == nil or self.reservations[entry.token] ~= nil then
                self.requests[entry.key] = {
                    ok = entry.ok, status = entry.status, reason = entry.reason, token = entry.token,
                    items = type(entry.items) == "table" and copy_items(entry.items) or nil,
                }
            end
        end
    end
    return self
end

return Ledger
