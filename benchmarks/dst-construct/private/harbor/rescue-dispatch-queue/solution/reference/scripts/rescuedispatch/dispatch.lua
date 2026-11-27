-- Pure Lua rescue dispatcher. Time is always supplied by the caller; every
-- operation first advances the clock and expires leases at their boundary, so
-- the outcome never depends on how often tick() happens to run.

local Dispatch = {}
Dispatch.__index = Dispatch

local DEFAULTS = {
    lease_ttl = 15,
    aging_interval = 30,
    max_severity = 5,
    recovery_threshold = 0.75,
    history_limit = 512,
}

local function is_finite(value)
    return type(value) == "number" and value == value and value ~= math.huge and value ~= -math.huge
end

local function is_identifier(value)
    return type(value) == "string" and value ~= "" and #value <= 96 and string.find(value, "%c") == nil
end

local function positive_option(options, key)
    local value = type(options) == "table" and options[key] or nil
    if is_finite(value) and value > 0 then
        return value
    end
    return DEFAULTS[key]
end

local function copy_flat(source)
    local out = {}
    for key, value in pairs(source) do
        out[key] = value
    end
    return out
end

local function sorted_keys(map)
    local keys = {}
    for key in pairs(map) do
        keys[#keys + 1] = key
    end
    table.sort(keys)
    return keys
end

local function failure(reason)
    return { ok = false, reason = reason }
end

function Dispatch.new(options)
    local self = setmetatable({}, Dispatch)
    self.lease_ttl = positive_option(options, "lease_ttl")
    self.aging_interval = positive_option(options, "aging_interval")
    self.max_severity = math.floor(positive_option(options, "max_severity"))
    self.recovery_threshold = positive_option(options, "recovery_threshold")
    self.history_limit = math.floor(positive_option(options, "history_limit"))
    self.clock = 0
    self.lease_sequence = 0
    self.players = {}
    self.incidents = {}
    self.leases = {}
    self.helper_lease = {}
    self.history = {}
    self.history_order = {}
    return self
end

-- Idempotency history -------------------------------------------------------

function Dispatch:_recall(key)
    local stored = self.history[key]
    if stored == nil then
        return nil
    end
    return copy_flat(stored)
end

function Dispatch:_record(key, result)
    if self.history[key] == nil then
        self.history_order[#self.history_order + 1] = key
    end
    self.history[key] = copy_flat(result)
    while #self.history_order > self.history_limit do
        local evicted = table.remove(self.history_order, 1)
        self.history[evicted] = nil
    end
    return result
end

-- Time and leases -----------------------------------------------------------

function Dispatch:_release(lease, requeue)
    self.leases[lease.lease_id] = nil
    if self.helper_lease[lease.helper_id] == lease.lease_id then
        self.helper_lease[lease.helper_id] = nil
    end
    local incident = self.incidents[lease.target_id]
    if incident ~= nil and incident.lease_id == lease.lease_id then
        incident.lease_id = nil
        if requeue then
            incident.requeues = incident.requeues + 1
        end
    end
end

function Dispatch:_close(target_id)
    local incident = self.incidents[target_id]
    if incident == nil then
        return false
    end
    if incident.lease_id ~= nil and self.leases[incident.lease_id] ~= nil then
        self:_release(self.leases[incident.lease_id], false)
    end
    self.incidents[target_id] = nil
    return true
end

function Dispatch:_advance(now)
    if not is_finite(now) or now < 0 or now < self.clock then
        return nil
    end
    self.clock = now
    local expired = {}
    local lease_ids = sorted_keys(self.leases)
    for index = 1, #lease_ids do
        local lease = self.leases[lease_ids[index]]
        if now >= lease.expires_at then
            self:_release(lease, true)
            expired[#expired + 1] = lease.lease_id
        end
    end
    return expired
end

function Dispatch:_effective_severity(incident, now)
    local waited = math.max(0, now - incident.created_at)
    return incident.severity + math.floor(waited / self.aging_interval)
end

function Dispatch:_ordered_incidents(now)
    local ordered = {}
    local target_ids = sorted_keys(self.incidents)
    for index = 1, #target_ids do
        local incident = self.incidents[target_ids[index]]
        ordered[#ordered + 1] = {
            incident = incident,
            effective = self:_effective_severity(incident, now),
        }
    end
    table.sort(ordered, function(left, right)
        if left.effective ~= right.effective then
            return left.effective > right.effective
        end
        if left.incident.created_at ~= right.incident.created_at then
            return left.incident.created_at < right.incident.created_at
        end
        return left.incident.target_id < right.incident.target_id
    end)
    return ordered
end

-- Players -------------------------------------------------------------------

function Dispatch:update_player(record, now)
    if type(record) ~= "table" or not is_identifier(record.id) then
        return failure("invalid_player")
    end
    if not is_finite(record.revision) or record.revision < 0 or math.floor(record.revision) ~= record.revision then
        return failure("invalid_revision")
    end
    if type(record.connected) ~= "boolean" or type(record.alive) ~= "boolean" then
        return failure("invalid_player")
    end
    if not is_finite(record.health_percent) or record.health_percent < 0 or record.health_percent > 1 then
        return failure("invalid_health")
    end
    local known = self.players[record.id]
    if known ~= nil and record.revision <= known.revision then
        return failure("stale_revision")
    end
    if self:_advance(now) == nil then
        return failure("invalid_time")
    end

    self.players[record.id] = {
        id = record.id,
        revision = record.revision,
        connected = record.connected,
        alive = record.alive,
        health_percent = record.health_percent,
    }

    local available = record.connected and record.alive
    -- As a helper: leaving or dying frees the lease and requeues the target once.
    local held = self.helper_lease[record.id]
    if held ~= nil and not available and self.leases[held] ~= nil then
        self:_release(self.leases[held], true)
    end
    -- As a target: leaving, dying or recovering ends the incident.
    if self.incidents[record.id] ~= nil
        and (not available or record.health_percent >= self.recovery_threshold) then
        self:_close(record.id)
    end
    return { ok = true, id = record.id, revision = record.revision }
end

-- Requests ------------------------------------------------------------------

function Dispatch:request(request_id, target_id, severity, now)
    if not is_identifier(request_id) or not is_identifier(target_id) then
        return failure("invalid_identifier")
    end
    if not is_finite(severity) or severity < 1 or severity > self.max_severity
        or math.floor(severity) ~= severity then
        return failure("invalid_severity")
    end
    if self:_advance(now) == nil then
        return failure("invalid_time")
    end
    local key = "request\t" .. request_id
    local remembered = self:_recall(key)
    if remembered ~= nil then
        return remembered
    end

    local player = self.players[target_id]
    if player == nil or not player.connected or not player.alive then
        return self:_record(key, { ok = false, reason = "target_unavailable", target_id = target_id })
    end
    if player.health_percent >= self.recovery_threshold then
        return self:_record(key, { ok = false, reason = "target_not_in_need", target_id = target_id })
    end

    local incident = self.incidents[target_id]
    if incident ~= nil then
        -- One incident per target; a worse report may only raise its severity.
        if severity > incident.severity then
            incident.severity = severity
        end
        return self:_record(key, {
            ok = true, target_id = target_id, severity = incident.severity,
            created_at = incident.created_at, merged = true,
        })
    end
    self.incidents[target_id] = {
        target_id = target_id,
        severity = severity,
        created_at = now,
        lease_id = nil,
        requeues = 0,
    }
    return self:_record(key, {
        ok = true, target_id = target_id, severity = severity, created_at = now, merged = false,
    })
end

function Dispatch:volunteer(request_id, helper_id, now)
    if not is_identifier(request_id) or not is_identifier(helper_id) then
        return failure("invalid_identifier")
    end
    if self:_advance(now) == nil then
        return failure("invalid_time")
    end
    local key = "volunteer\t" .. helper_id .. "\t" .. request_id
    local remembered = self:_recall(key)
    if remembered ~= nil then
        return remembered
    end

    local helper = self.players[helper_id]
    if helper == nil or not helper.connected or not helper.alive then
        return self:_record(key, { ok = false, reason = "helper_unavailable", helper_id = helper_id })
    end
    if self.helper_lease[helper_id] ~= nil then
        return self:_record(key, { ok = false, reason = "helper_busy", helper_id = helper_id })
    end

    local ordered = self:_ordered_incidents(now)
    for index = 1, #ordered do
        local incident = ordered[index].incident
        if incident.lease_id == nil and incident.target_id ~= helper_id then
            self.lease_sequence = self.lease_sequence + 1
            local lease = {
                lease_id = string.format("lease-%08d", self.lease_sequence),
                target_id = incident.target_id,
                helper_id = helper_id,
                granted_at = now,
                expires_at = now + self.lease_ttl,
            }
            self.leases[lease.lease_id] = lease
            self.helper_lease[helper_id] = lease.lease_id
            incident.lease_id = lease.lease_id
            return self:_record(key, {
                ok = true, lease_id = lease.lease_id, target_id = lease.target_id,
                helper_id = helper_id, expires_at = lease.expires_at,
            })
        end
    end
    return self:_record(key, { ok = false, reason = "no_incident", helper_id = helper_id })
end

function Dispatch:_live_lease(lease_id, helper_id)
    if not is_identifier(lease_id) or not is_identifier(helper_id) then
        return nil, "invalid_identifier"
    end
    local lease = self.leases[lease_id]
    if lease == nil then
        return nil, "lease_not_active"
    end
    if lease.helper_id ~= helper_id then
        return nil, "not_lease_holder"
    end
    return lease, nil
end

function Dispatch:heartbeat(lease_id, helper_id, now)
    if self:_advance(now) == nil then
        return failure("invalid_time")
    end
    local lease, problem = self:_live_lease(lease_id, helper_id)
    if lease == nil then
        return failure(problem)
    end
    lease.expires_at = now + self.lease_ttl
    return { ok = true, lease_id = lease_id, target_id = lease.target_id, expires_at = lease.expires_at }
end

function Dispatch:complete(lease_id, helper_id, now)
    if self:_advance(now) == nil then
        return failure("invalid_time")
    end
    local lease, problem = self:_live_lease(lease_id, helper_id)
    if lease == nil then
        return failure(problem)
    end
    local target_id = lease.target_id
    self:_close(target_id)
    return { ok = true, lease_id = lease_id, target_id = target_id }
end

function Dispatch:cancel(target_id, now)
    if not is_identifier(target_id) then
        return failure("invalid_identifier")
    end
    if self:_advance(now) == nil then
        return failure("invalid_time")
    end
    if not self:_close(target_id) then
        return failure("no_incident")
    end
    return { ok = true, target_id = target_id }
end

function Dispatch:tick(now)
    local expired = self:_advance(now)
    if expired == nil then
        return failure("invalid_time")
    end
    return { ok = true, now = self.clock, expired = expired }
end

-- Views ---------------------------------------------------------------------

function Dispatch:snapshot(now)
    if self:_advance(now) == nil then
        now = self.clock
    end
    local queue, leases = {}, {}
    local ordered = self:_ordered_incidents(now)
    for index = 1, #ordered do
        local incident = ordered[index].incident
        if incident.lease_id == nil then
            queue[#queue + 1] = {
                target_id = incident.target_id,
                severity = incident.severity,
                effective_severity = ordered[index].effective,
                created_at = incident.created_at,
                requeues = incident.requeues,
            }
        end
    end
    local lease_ids = sorted_keys(self.leases)
    for index = 1, #lease_ids do
        local lease = self.leases[lease_ids[index]]
        leases[#leases + 1] = {
            lease_id = lease.lease_id,
            target_id = lease.target_id,
            helper_id = lease.helper_id,
            expires_at = lease.expires_at,
        }
    end
    return { now = now, queue = queue, leases = leases }
end

function Dispatch:save(now)
    self:_advance(now)
    local players, incidents, leases, history = {}, {}, {}, {}
    local player_ids = sorted_keys(self.players)
    for index = 1, #player_ids do
        players[#players + 1] = copy_flat(self.players[player_ids[index]])
    end
    local target_ids = sorted_keys(self.incidents)
    for index = 1, #target_ids do
        incidents[#incidents + 1] = copy_flat(self.incidents[target_ids[index]])
    end
    local lease_ids = sorted_keys(self.leases)
    for index = 1, #lease_ids do
        leases[#leases + 1] = copy_flat(self.leases[lease_ids[index]])
    end
    for index = 1, #self.history_order do
        local key = self.history_order[index]
        history[#history + 1] = { key = key, result = copy_flat(self.history[key]) }
    end
    return {
        version = 1,
        clock = self.clock,
        lease_sequence = self.lease_sequence,
        players = players,
        incidents = incidents,
        leases = leases,
        history = history,
    }
end

function Dispatch.load(data, options)
    local self = Dispatch.new(options)
    if type(data) ~= "table" or data.version ~= 1 then
        return self
    end
    if is_finite(data.clock) and data.clock >= 0 then
        self.clock = data.clock
    end
    if is_finite(data.lease_sequence) and data.lease_sequence >= 0 then
        self.lease_sequence = math.floor(data.lease_sequence)
    end
    for _, player in ipairs(type(data.players) == "table" and data.players or {}) do
        if type(player) == "table" and is_identifier(player.id) and is_finite(player.revision)
            and type(player.connected) == "boolean" and type(player.alive) == "boolean"
            and is_finite(player.health_percent) then
            self.players[player.id] = copy_flat(player)
        end
    end
    for _, incident in ipairs(type(data.incidents) == "table" and data.incidents or {}) do
        if type(incident) == "table" and is_identifier(incident.target_id)
            and is_finite(incident.severity) and is_finite(incident.created_at) then
            self.incidents[incident.target_id] = {
                target_id = incident.target_id,
                severity = incident.severity,
                created_at = incident.created_at,
                lease_id = nil,
                requeues = is_finite(incident.requeues) and incident.requeues or 0,
            }
        end
    end
    for _, lease in ipairs(type(data.leases) == "table" and data.leases or {}) do
        -- A lease is only restored when it is still consistent with both maps.
        if type(lease) == "table" and is_identifier(lease.lease_id) and is_identifier(lease.helper_id)
            and is_identifier(lease.target_id) and is_finite(lease.expires_at)
            and self.incidents[lease.target_id] ~= nil
            and self.incidents[lease.target_id].lease_id == nil
            and self.helper_lease[lease.helper_id] == nil then
            self.leases[lease.lease_id] = {
                lease_id = lease.lease_id,
                target_id = lease.target_id,
                helper_id = lease.helper_id,
                granted_at = is_finite(lease.granted_at) and lease.granted_at or self.clock,
                expires_at = lease.expires_at,
            }
            self.helper_lease[lease.helper_id] = lease.lease_id
            self.incidents[lease.target_id].lease_id = lease.lease_id
        end
    end
    for _, entry in ipairs(type(data.history) == "table" and data.history or {}) do
        if type(entry) == "table" and type(entry.key) == "string" and type(entry.result) == "table"
            and self.history[entry.key] == nil then
            self.history[entry.key] = copy_flat(entry.result)
            self.history_order[#self.history_order + 1] = entry.key
        end
    end
    return self
end

return Dispatch
