-- Pure Lua threat arbiter.
--
-- Decay model: every source -> target entry keeps its own `base` and
-- `updated_at`, the time of the last accepted threat event for that entry.
-- Current threat is `base - decay_per_second * (now - updated_at)`, clamped at
-- zero. It is a pure function of the accepted events and `now`: nothing is
-- folded by tick(), choose(), snapshot() or save(), so results cannot depend
-- on how often those run. An accepted event first decays its own entry to the
-- event time and then adds the new amount; other entries are untouched.

local Arbiter = {}
Arbiter.__index = Arbiter

local HISTORY_LIMIT = 512

local function is_finite(value)
    return type(value) == "number" and value == value and value ~= math.huge and value ~= -math.huge
end

local function is_identifier(value)
    return type(value) == "string" and value ~= "" and #value <= 96 and string.find(value, "%c") == nil
end

local function is_integer(value)
    return is_finite(value) and math.floor(value) == value
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

local function stream_key(source_id, target_id)
    return source_id .. "\t" .. target_id
end

function Arbiter.new(options)
    local self = setmetatable({}, Arbiter)
    local decay = type(options) == "table" and options.decay_per_second or nil
    self.decay_per_second = (is_finite(decay) and decay >= 0) and decay or 1
    self.clock = 0
    self.entities = {}
    self.tables = {}
    self.taunts = {}
    self.sequences = {}
    self.history = {}
    self.history_order = {}
    return self
end

function Arbiter:_advance(now)
    if not is_finite(now) or now < 0 or now < self.clock then
        return nil
    end
    self.clock = now
    local expired = {}
    local source_ids = sorted_keys(self.taunts)
    for index = 1, #source_ids do
        local taunt = self.taunts[source_ids[index]]
        if now >= taunt.expires_at then
            self.taunts[source_ids[index]] = nil
            expired[#expired + 1] = taunt.request_id
        end
    end
    return expired
end

function Arbiter:_is_alive(id)
    local entity = self.entities[id]
    return entity ~= nil and entity.alive and not entity.removed
end

function Arbiter:_threat(threat_table, entry, now)
    local elapsed = math.max(0, now - (entry.updated_at or threat_table.updated_at))
    return math.max(0, entry.base - self.decay_per_second * elapsed)
end

-- Forget everything the entity takes part in, on either side. Sequence
-- numbers are deliberately kept so an old event can never be replayed.
function Arbiter:_purge(id)
    self.tables[id] = nil
    self.taunts[id] = nil
    for source_id, threat_table in pairs(self.tables) do
        threat_table.entries[id] = nil
        if next(threat_table.entries) == nil then
            self.tables[source_id] = nil
        end
    end
    for source_id, taunt in pairs(self.taunts) do
        if taunt.target_id == id then
            self.taunts[source_id] = nil
        end
    end
end

function Arbiter:observe(entity, now)
    if type(entity) ~= "table" or not is_identifier(entity.id) or type(entity.alive) ~= "boolean"
        or not is_integer(entity.revision) or entity.revision < 0 then
        return false
    end
    local known = self.entities[entity.id]
    if known ~= nil and entity.revision <= known.revision then
        return false
    end
    if self:_advance(now) == nil then
        return false
    end
    self.entities[entity.id] = { id = entity.id, alive = entity.alive, revision = entity.revision, removed = false }
    if not entity.alive then
        self:_purge(entity.id)
    end
    return { ok = true, id = entity.id, alive = entity.alive, revision = entity.revision }
end

function Arbiter:last_seq(source_id, target_id)
    if not is_identifier(source_id) or not is_identifier(target_id) then
        return nil
    end
    return self.sequences[stream_key(source_id, target_id)] or 0
end

function Arbiter:add_threat(source_id, target_id, amount, seq, now)
    if not is_identifier(source_id) or not is_identifier(target_id) or source_id == target_id then
        return false
    end
    if not is_finite(amount) or amount <= 0 or not is_integer(seq) or seq < 0 then
        return false
    end
    if self:_advance(now) == nil then
        return false
    end
    local key = stream_key(source_id, target_id)
    if seq <= (self.sequences[key] or -1) then
        return false
    end
    -- A well-formed, in-order event is consumed even when it is then dropped,
    -- so it cannot be replayed once a dead participant comes back.
    self.sequences[key] = seq
    if not self:_is_alive(source_id) or not self:_is_alive(target_id) then
        return false
    end

    local threat_table = self.tables[source_id]
    if threat_table == nil then
        threat_table = { source_id = source_id, updated_at = now, entries = {} }
        self.tables[source_id] = threat_table
    end
    for existing_id, entry in pairs(threat_table.entries) do
        if self:_threat(threat_table, entry, now) <= 0 then
            threat_table.entries[existing_id] = nil
        end
    end
    threat_table.updated_at = now
    local entry = threat_table.entries[target_id]
    if entry == nil then
        entry = { target_id = target_id, base = 0, first_seen = now, updated_at = now }
        threat_table.entries[target_id] = entry
    end
    entry.base = self:_threat(threat_table, entry, now) + amount
    entry.updated_at = now
    return { ok = true, source_id = source_id, target_id = target_id, threat = entry.base }
end

function Arbiter:_remember(request_id, result)
    if self.history[request_id] == nil then
        self.history_order[#self.history_order + 1] = request_id
    end
    self.history[request_id] = copy_flat(result)
    while #self.history_order > HISTORY_LIMIT do
        self.history[table.remove(self.history_order, 1)] = nil
    end
    return result
end

function Arbiter:taunt(request_id, source_id, target_id, duration, now)
    if not is_identifier(request_id) then
        return { ok = false, reason = "invalid_request_id" }
    end
    -- A retry is answered from history before anything else is looked at: a
    -- delayed duplicate may legitimately carry an older timestamp.
    if self.history[request_id] ~= nil then
        return copy_flat(self.history[request_id])
    end
    if self:_advance(now) == nil then
        return { ok = false, reason = "invalid_time" }
    end
    if not is_identifier(source_id) or not is_identifier(target_id) or source_id == target_id then
        return { ok = false, reason = "invalid_identifier" }
    end
    if not is_finite(duration) or duration <= 0 then
        return { ok = false, reason = "invalid_duration" }
    end
    if not self:_is_alive(source_id) or not self:_is_alive(target_id) then
        return self:_remember(request_id, { ok = false, reason = "participant_unavailable", request_id = request_id })
    end
    local taunt = {
        request_id = request_id,
        source_id = source_id,
        target_id = target_id,
        started_at = now,
        expires_at = now + duration,
    }
    self.taunts[source_id] = taunt
    return self:_remember(request_id, {
        ok = true, request_id = request_id, source_id = source_id,
        target_id = target_id, expires_at = taunt.expires_at,
    })
end

function Arbiter:remove(target_id, now)
    if not is_identifier(target_id) or self:_advance(now) == nil then
        return false
    end
    local known = self.entities[target_id]
    if known == nil then
        return false
    end
    known.alive = false
    known.removed = true
    self:_purge(target_id)
    return true
end

function Arbiter:_ranked(source_id, now)
    local ranked = {}
    local threat_table = self.tables[source_id]
    if threat_table ~= nil then
        local target_ids = sorted_keys(threat_table.entries)
        for index = 1, #target_ids do
            local entry = threat_table.entries[target_ids[index]]
            local threat = self:_threat(threat_table, entry, now)
            if threat > 0 and self:_is_alive(entry.target_id) then
                ranked[#ranked + 1] = { target_id = entry.target_id, threat = threat, first_seen = entry.first_seen }
            end
        end
    end
    table.sort(ranked, function(left, right)
        if left.threat ~= right.threat then
            return left.threat > right.threat
        end
        if left.first_seen ~= right.first_seen then
            return left.first_seen < right.first_seen
        end
        return left.target_id < right.target_id
    end)
    return ranked
end

function Arbiter:choose(source_id, now)
    if not is_identifier(source_id) or self:_advance(now) == nil or not self:_is_alive(source_id) then
        return nil
    end
    local ranked = self:_ranked(source_id, now)
    local taunt = self.taunts[source_id]
    if taunt ~= nil and now < taunt.expires_at and self:_is_alive(taunt.target_id) then
        local threat = 0
        for index = 1, #ranked do
            if ranked[index].target_id == taunt.target_id then
                threat = ranked[index].threat
            end
        end
        return {
            source_id = source_id, target_id = taunt.target_id, threat = threat,
            taunted = true, expires_at = taunt.expires_at,
        }
    end
    if ranked[1] == nil then
        return nil
    end
    return { source_id = source_id, target_id = ranked[1].target_id, threat = ranked[1].threat, taunted = false }
end

function Arbiter:tick(now)
    local expired = self:_advance(now)
    if expired == nil then
        return { ok = false, reason = "invalid_time" }
    end
    return { ok = true, now = now, expired_taunts = expired }
end

function Arbiter:snapshot(now)
    if self:_advance(now) == nil then
        now = self.clock
    end
    local rows = {}
    local source_ids = sorted_keys(self.tables)
    for index = 1, #source_ids do
        local source_id = source_ids[index]
        local taunt = self.taunts[source_id]
        local ranked = self:_ranked(source_id, now)
        for rank = 1, #ranked do
            rows[#rows + 1] = {
                source_id = source_id,
                target_id = ranked[rank].target_id,
                threat = ranked[rank].threat,
                first_seen = ranked[rank].first_seen,
                taunted = taunt ~= nil and taunt.target_id == ranked[rank].target_id,
            }
        end
    end
    return rows
end

function Arbiter:save(now)
    self:_advance(now)
    local data = {
        version = 1, clock = self.clock,
        entities = {}, tables = {}, taunts = {}, sequences = {}, history = {},
    }
    for _, id in ipairs(sorted_keys(self.entities)) do
        data.entities[#data.entities + 1] = copy_flat(self.entities[id])
    end
    for _, source_id in ipairs(sorted_keys(self.tables)) do
        local threat_table = self.tables[source_id]
        local entries = {}
        for _, target_id in ipairs(sorted_keys(threat_table.entries)) do
            entries[#entries + 1] = copy_flat(threat_table.entries[target_id])
        end
        data.tables[#data.tables + 1] = { source_id = source_id, updated_at = threat_table.updated_at, entries = entries }
    end
    for _, source_id in ipairs(sorted_keys(self.taunts)) do
        data.taunts[#data.taunts + 1] = copy_flat(self.taunts[source_id])
    end
    for _, key in ipairs(sorted_keys(self.sequences)) do
        data.sequences[#data.sequences + 1] = { stream = key, seq = self.sequences[key] }
    end
    for index = 1, #self.history_order do
        local request_id = self.history_order[index]
        data.history[#data.history + 1] = { request_id = request_id, result = copy_flat(self.history[request_id]) }
    end
    return data
end

local function list(value)
    return type(value) == "table" and value or {}
end

function Arbiter.load(data, options, now)
    local self = Arbiter.new(options)
    if type(data) ~= "table" or data.version ~= 1 then
        return self
    end
    if is_finite(data.clock) and data.clock >= 0 then
        self.clock = data.clock
    end
    for _, entity in ipairs(list(data.entities)) do
        if type(entity) == "table" and is_identifier(entity.id) and type(entity.alive) == "boolean"
            and is_integer(entity.revision) then
            self.entities[entity.id] = {
                id = entity.id, alive = entity.alive, revision = entity.revision,
                removed = entity.removed == true,
            }
        end
    end
    for _, saved in ipairs(list(data.tables)) do
        if type(saved) == "table" and is_identifier(saved.source_id) and is_finite(saved.updated_at)
            and self:_is_alive(saved.source_id) then
            local threat_table = { source_id = saved.source_id, updated_at = saved.updated_at, entries = {} }
            for _, entry in ipairs(list(saved.entries)) do
                if type(entry) == "table" and is_identifier(entry.target_id) and is_finite(entry.base)
                    and entry.base > 0 and is_finite(entry.first_seen) and self:_is_alive(entry.target_id) then
                    threat_table.entries[entry.target_id] = {
                        target_id = entry.target_id, base = entry.base, first_seen = entry.first_seen,
                        updated_at = is_finite(entry.updated_at) and entry.updated_at or saved.updated_at,
                    }
                end
            end
            if next(threat_table.entries) ~= nil then
                self.tables[saved.source_id] = threat_table
            end
        end
    end
    for _, taunt in ipairs(list(data.taunts)) do
        if type(taunt) == "table" and is_identifier(taunt.request_id) and is_identifier(taunt.source_id)
            and is_identifier(taunt.target_id) and is_finite(taunt.expires_at)
            and self:_is_alive(taunt.source_id) and self:_is_alive(taunt.target_id) then
            self.taunts[taunt.source_id] = copy_flat(taunt)
        end
    end
    for _, saved in ipairs(list(data.sequences)) do
        if type(saved) == "table" and type(saved.stream) == "string" and is_integer(saved.seq) then
            self.sequences[saved.stream] = saved.seq
        end
    end
    for _, saved in ipairs(list(data.history)) do
        if type(saved) == "table" and is_identifier(saved.request_id) and type(saved.result) == "table"
            and self.history[saved.request_id] == nil then
            self.history[saved.request_id] = copy_flat(saved.result)
            self.history_order[#self.history_order + 1] = saved.request_id
        end
    end
    self:_advance(now)
    return self
end

return Arbiter
