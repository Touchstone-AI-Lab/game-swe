-- Threat arbiter without any engine dependency.
--
-- The arbiter is a bundle of closures over one private state table; nothing
-- outside this file can reach that state except through the returned methods.
-- Threat is kept as a flat list of edges (source -> target) with an `amount`
-- and a `stamp`; the current level of an edge is
--     max(0, amount - decay_per_second * (now - stamp))
-- All edges of one source share one decay clock: an accepted threat event for
-- that source restarts it for every edge of the source. Nothing else rewrites
-- an edge, so tick(), choose(), snapshot() and save() never change a level.

local Arbiter = {}

local ID_LIMIT = 128
local ANSWER_LIMIT = 256
local FORMAT = 1

local function finite(value)
    return type(value) == "number" and value == value and value ~= math.huge and value ~= -math.huge
end

local function valid_id(value)
    return type(value) == "string" and #value > 0 and #value <= ID_LIMIT and string.find(value, "%c") == nil
end

local function valid_time(value)
    return finite(value) and value >= 0
end

local function whole(value)
    return finite(value) and value % 1 == 0
end

local function shallow(source)
    local copy = {}
    for key, value in pairs(source) do
        copy[key] = value
    end
    return copy
end

local function ordered_keys(map)
    local keys = {}
    for key in pairs(map) do
        keys[#keys + 1] = key
    end
    table.sort(keys)
    return keys
end

local function array_of(value)
    if type(value) == "table" then
        return value
    end
    return {}
end

local function read_decay(options)
    local decay = type(options) == "table" and options.decay_per_second or nil
    if finite(decay) and decay >= 0 then
        return decay
    end
    return 1
end

-- Builds the method table around `state`.
local function assemble(state)
    local api = {}

    local function living(id)
        local entry = state.roster[id]
        return entry ~= nil and entry.alive == true and entry.gone ~= true
    end

    local function level(edge, now)
        local elapsed = now - edge.stamp
        if elapsed < 0 then
            elapsed = 0
        end
        local value = edge.amount - state.decay * elapsed
        if value < 0 then
            return 0
        end
        return value
    end

    local function find_edge(source_id, target_id)
        for index = 1, #state.edges do
            local edge = state.edges[index]
            if edge.source == source_id and edge.target == target_id then
                return edge, index
            end
        end
        return nil, nil
    end

    local function drop_edges(predicate)
        local dropped = 0
        for index = #state.edges, 1, -1 do
            if predicate(state.edges[index]) then
                table.remove(state.edges, index)
                dropped = dropped + 1
            end
        end
        return dropped
    end

    -- Mutations move the horizon forward; a mutation stamped before the
    -- horizon is refused so that state never runs backwards in time.
    local function advance(now)
        if not valid_time(now) or now < state.horizon then
            return false
        end
        state.horizon = now
        return true
    end

    local function expire_leases(now)
        local ended = {}
        local sources = ordered_keys(state.leases)
        for index = 1, #sources do
            local lease = state.leases[sources[index]]
            if now >= lease.expires_at then
                ended[#ended + 1] = lease.request_id
                state.leases[sources[index]] = nil
            end
        end
        return ended
    end

    -- Death and removal wipe every edge and lease the entity takes part in.
    -- The replay guard is left alone on purpose.
    local function forget(id)
        drop_edges(function(edge)
            return edge.source == id or edge.target == id
        end)
        local sources = ordered_keys(state.leases)
        for index = 1, #sources do
            local lease = state.leases[sources[index]]
            if lease.source_id == id or lease.target_id == id then
                state.leases[sources[index]] = nil
            end
        end
    end

    local function last_seq(source_id, target_id)
        local by_target = state.guard[source_id]
        if by_target == nil then
            return nil
        end
        return by_target[target_id]
    end

    -- Returns the edge that receives `amount`. The source's shared decay clock
    -- restarts here: edges of the source that already reached zero are
    -- released, the remaining ones keep their amount and are stamped `now`.
    local function edge_for_event(source_id, target_id, now)
        drop_edges(function(edge)
            return edge.source == source_id and level(edge, now) <= 0
        end)
        for index = 1, #state.edges do
            if state.edges[index].source == source_id then
                state.edges[index].stamp = now
            end
        end
        local edge = find_edge(source_id, target_id)
        if edge == nil then
            edge = { source = source_id, target = target_id, amount = 0, stamp = now, first_seen = now }
            state.edges[#state.edges + 1] = edge
        end
        return edge
    end

    local function ranking(source_id, now)
        local rows = {}
        for index = 1, #state.edges do
            local edge = state.edges[index]
            if edge.source == source_id and living(edge.target) then
                local threat = level(edge, now)
                if threat > 0 then
                    rows[#rows + 1] = { target_id = edge.target, threat = threat, first_seen = edge.first_seen }
                end
            end
        end
        table.sort(rows, function(left, right)
            if left.threat ~= right.threat then
                return left.threat > right.threat
            end
            if left.first_seen ~= right.first_seen then
                return left.first_seen < right.first_seen
            end
            return left.target_id < right.target_id
        end)
        return rows
    end

    local function remember(request_id, answer)
        if state.answers[request_id] == nil then
            state.answer_queue[#state.answer_queue + 1] = request_id
        end
        state.answers[request_id] = shallow(answer)
        while #state.answer_queue > ANSWER_LIMIT do
            local oldest = table.remove(state.answer_queue, 1)
            state.answers[oldest] = nil
        end
        return answer
    end

    function api.observe(_, entity, now)
        if type(entity) ~= "table" or not valid_id(entity.id) or type(entity.alive) ~= "boolean" then
            return false
        end
        if not whole(entity.revision) or entity.revision < 0 then
            return false
        end
        local known = state.roster[entity.id]
        if known ~= nil and entity.revision <= known.revision then
            return false
        end
        if not advance(now) then
            return false
        end
        state.roster[entity.id] = { alive = entity.alive, revision = entity.revision, gone = false }
        if not entity.alive then
            forget(entity.id)
        end
        return { ok = true, id = entity.id, alive = entity.alive, revision = entity.revision }
    end

    function api.add_threat(_, source_id, target_id, amount, seq, now)
        if not valid_id(source_id) or not valid_id(target_id) or source_id == target_id then
            return false
        end
        if not finite(amount) or amount <= 0 or not whole(seq) or seq < 0 then
            return false
        end
        if not advance(now) then
            return false
        end
        local previous = last_seq(source_id, target_id)
        if previous ~= nil and seq <= previous then
            return false
        end
        -- The number is spent even if the event is then refused, so it can
        -- never be replayed after one of the participants returns.
        state.guard[source_id] = state.guard[source_id] or {}
        state.guard[source_id][target_id] = seq
        if not living(source_id) or not living(target_id) then
            return false
        end
        local edge = edge_for_event(source_id, target_id, now)
        edge.amount = edge.amount + amount
        return { ok = true, source_id = source_id, target_id = target_id, seq = seq, threat = edge.amount }
    end

    function api.taunt(_, request_id, source_id, target_id, duration, now)
        if not valid_id(request_id) then
            return { ok = false, reason = "bad_request_id" }
        end
        -- A retry is answered from the request history before anything else,
        -- including its (possibly older) timestamp, is looked at.
        local earlier = state.answers[request_id]
        if earlier ~= nil then
            return shallow(earlier)
        end
        if not valid_id(source_id) or not valid_id(target_id) or source_id == target_id then
            return { ok = false, reason = "bad_identifier", request_id = request_id }
        end
        if not finite(duration) or duration <= 0 then
            return { ok = false, reason = "bad_duration", request_id = request_id }
        end
        if not advance(now) then
            return { ok = false, reason = "bad_time", request_id = request_id }
        end
        if not living(source_id) or not living(target_id) then
            return remember(request_id, { ok = false, reason = "not_alive", request_id = request_id })
        end
        local lease = {
            request_id = request_id,
            source_id = source_id,
            target_id = target_id,
            granted_at = now,
            expires_at = now + duration,
        }
        state.leases[source_id] = lease
        return remember(request_id, {
            ok = true,
            request_id = request_id,
            source_id = source_id,
            target_id = target_id,
            granted_at = now,
            expires_at = lease.expires_at,
        })
    end

    function api.remove(_, target_id, now)
        if not valid_id(target_id) or state.roster[target_id] == nil then
            return false
        end
        if not advance(now) then
            return false
        end
        local entry = state.roster[target_id]
        entry.alive = false
        entry.gone = true
        forget(target_id)
        return true
    end

    function api.choose(_, source_id, now)
        if not valid_id(source_id) or not valid_time(now) or not living(source_id) then
            return nil
        end
        local rows = ranking(source_id, now)
        local lease = state.leases[source_id]
        if lease ~= nil and now < lease.expires_at and living(lease.target_id) then
            local threat = 0
            for index = 1, #rows do
                if rows[index].target_id == lease.target_id then
                    threat = rows[index].threat
                end
            end
            return {
                source_id = source_id,
                target_id = lease.target_id,
                threat = threat,
                reason = "taunt",
                expires_at = lease.expires_at,
            }
        end
        if rows[1] == nil then
            return nil
        end
        return { source_id = source_id, target_id = rows[1].target_id, threat = rows[1].threat, reason = "threat" }
    end

    -- Housekeeping only: ends leases that reached their boundary and releases
    -- edges that are already at zero. Neither changes what choose() answers.
    function api.tick(_, now)
        if not advance(now) then
            return { ok = false, reason = "bad_time" }
        end
        local ended = expire_leases(now)
        local released = drop_edges(function(edge)
            return level(edge, now) <= 0
        end)
        return { ok = true, now = now, expired = ended, released = released }
    end

    function api.snapshot(_, now)
        if not valid_time(now) then
            now = state.horizon
        end
        local view = { now = now, entities = {}, threats = {}, taunts = {} }
        local ids = ordered_keys(state.roster)
        for index = 1, #ids do
            local entry = state.roster[ids[index]]
            view.entities[#view.entities + 1] = {
                id = ids[index], alive = entry.alive, revision = entry.revision, removed = entry.gone == true,
            }
            local rows = ranking(ids[index], now)
            for rank = 1, #rows do
                view.threats[#view.threats + 1] = {
                    source_id = ids[index],
                    target_id = rows[rank].target_id,
                    threat = rows[rank].threat,
                    first_seen = rows[rank].first_seen,
                    rank = rank,
                }
            end
        end
        local sources = ordered_keys(state.leases)
        for index = 1, #sources do
            local lease = state.leases[sources[index]]
            if now < lease.expires_at then
                view.taunts[#view.taunts + 1] = shallow(lease)
            end
        end
        return view
    end

    function api.save(_, now)
        if not valid_time(now) then
            now = state.horizon
        end
        local data = {
            format = FORMAT,
            saved_at = now,
            horizon = math.max(state.horizon, now),
            roster = {},
            threats = {},
            taunts = {},
            guard = {},
            answers = {},
        }
        local ids = ordered_keys(state.roster)
        for index = 1, #ids do
            local entry = state.roster[ids[index]]
            data.roster[#data.roster + 1] = {
                id = ids[index], alive = entry.alive, revision = entry.revision, gone = entry.gone == true,
            }
        end
        -- Only what is still in effect at `now` is written, already decayed.
        local edges = {}
        for index = 1, #state.edges do
            local edge = state.edges[index]
            local threat = level(edge, now)
            if threat > 0 then
                edges[#edges + 1] = {
                    source = edge.source, target = edge.target, threat = threat,
                    first_seen = edge.first_seen, at = math.max(now, edge.stamp),
                }
            end
        end
        table.sort(edges, function(left, right)
            if left.source ~= right.source then
                return left.source < right.source
            end
            return left.target < right.target
        end)
        data.threats = edges
        local sources = ordered_keys(state.leases)
        for index = 1, #sources do
            local lease = state.leases[sources[index]]
            if now < lease.expires_at then
                data.taunts[#data.taunts + 1] = shallow(lease)
            end
        end
        local guarded = ordered_keys(state.guard)
        for index = 1, #guarded do
            local targets = ordered_keys(state.guard[guarded[index]])
            for inner = 1, #targets do
                data.guard[#data.guard + 1] = {
                    source = guarded[index], target = targets[inner],
                    seq = state.guard[guarded[index]][targets[inner]],
                }
            end
        end
        for index = 1, #state.answer_queue do
            local request_id = state.answer_queue[index]
            data.answers[#data.answers + 1] = { request_id = request_id, answer = shallow(state.answers[request_id]) }
        end
        return data
    end

    return api
end

local function empty_state(options)
    return {
        decay = read_decay(options),
        horizon = 0,
        roster = {},
        edges = {},
        leases = {},
        guard = {},
        answers = {},
        answer_queue = {},
    }
end

function Arbiter.new(options)
    return assemble(empty_state(options))
end

function Arbiter.load(data, options, now)
    local state = empty_state(options)
    if type(data) ~= "table" or data.format ~= FORMAT then
        return assemble(state)
    end
    if valid_time(data.horizon) then
        state.horizon = data.horizon
    end
    if valid_time(now) and now > state.horizon then
        state.horizon = now
    end
    local present = state.horizon
    if valid_time(now) then
        present = now
    end

    local roster = array_of(data.roster)
    for index = 1, #roster do
        local entry = roster[index]
        if type(entry) == "table" and valid_id(entry.id) and type(entry.alive) == "boolean"
            and whole(entry.revision) and entry.revision >= 0 then
            state.roster[entry.id] = { alive = entry.alive, revision = entry.revision, gone = entry.gone == true }
        end
    end
    local function usable(id)
        local entry = valid_id(id) and state.roster[id] or nil
        return entry ~= nil and entry.alive and not entry.gone
    end

    local threats = array_of(data.threats)
    local seen = {}
    for index = 1, #threats do
        local row = threats[index]
        if type(row) == "table" and usable(row.source) and usable(row.target) and row.source ~= row.target
            and finite(row.threat) and row.threat > 0 and valid_time(row.first_seen) and valid_time(row.at) then
            local key = row.source .. "\n" .. row.target
            if not seen[key] then
                seen[key] = true
                state.edges[#state.edges + 1] = {
                    source = row.source, target = row.target, amount = row.threat,
                    stamp = row.at, first_seen = row.first_seen,
                }
            end
        end
    end

    local taunts = array_of(data.taunts)
    for index = 1, #taunts do
        local lease = taunts[index]
        if type(lease) == "table" and valid_id(lease.request_id) and usable(lease.source_id)
            and usable(lease.target_id) and valid_time(lease.expires_at) and present < lease.expires_at then
            state.leases[lease.source_id] = {
                request_id = lease.request_id,
                source_id = lease.source_id,
                target_id = lease.target_id,
                granted_at = valid_time(lease.granted_at) and lease.granted_at or present,
                expires_at = lease.expires_at,
            }
        end
    end

    local guard = array_of(data.guard)
    for index = 1, #guard do
        local row = guard[index]
        if type(row) == "table" and valid_id(row.source) and valid_id(row.target) and whole(row.seq) then
            state.guard[row.source] = state.guard[row.source] or {}
            local current = state.guard[row.source][row.target]
            if current == nil or row.seq > current then
                state.guard[row.source][row.target] = row.seq
            end
        end
    end

    local answers = array_of(data.answers)
    for index = 1, #answers do
        local row = answers[index]
        if type(row) == "table" and valid_id(row.request_id) and type(row.answer) == "table"
            and state.answers[row.request_id] == nil then
            state.answers[row.request_id] = shallow(row.answer)
            state.answer_queue[#state.answer_queue + 1] = row.request_id
        end
    end
    return assemble(state)
end

return Arbiter
