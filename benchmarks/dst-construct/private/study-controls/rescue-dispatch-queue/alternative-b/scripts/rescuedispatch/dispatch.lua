-- Lease-based rescue dispatcher (plain Lua, no engine globals).
--
-- Design: a dispatcher is a closure over one private state record. Open
-- incidents live in a single array of "tickets"; the lease of an incident is a
-- field of its ticket, so "one target, one helper" is structural. Every public
-- operation first settles the clock, which expires leases at their boundary;
-- nothing depends on how often tick() is called.

local Dispatch = {}

local ID_LIMIT = 128

local function is_finite(value)
    return type(value) == "number" and value == value
        and value < math.huge and value > -math.huge
end

local function is_whole(value)
    return is_finite(value) and value >= 0 and value % 1 == 0
end

local function is_id(value)
    return type(value) == "string" and #value > 0 and #value <= ID_LIMIT
        and not string.find(value, "[%c]")
end

local function pick(options, name, fallback)
    local value = type(options) == "table" and options[name] or nil
    if is_finite(value) and value > 0 then
        return value
    end
    return fallback
end

local function refuse(why, extra)
    local out = extra or {}
    out.ok = false
    out.reason = why
    return out
end

local function clone(result)
    local out = {}
    for field, value in pairs(result) do
        out[field] = value
    end
    return out
end

local function lease_name(serial)
    return string.format("rescue-%06d", math.floor(serial))
end

-- Stable insertion sort; the comparator is a strict total order, so the result
-- never depends on the order in which entries were produced.
local function arrange(list, before)
    for index = 2, #list do
        local moving = list[index]
        local slot = index - 1
        while slot >= 1 and before(moving, list[slot]) do
            list[slot + 1] = list[slot]
            slot = slot - 1
        end
        list[slot + 1] = moving
    end
    return list
end

local function construct(options)
    local config = {
        lease_ttl = pick(options, "lease_ttl", 30),
        aging_interval = pick(options, "aging_interval", 60),
        severity_cap = math.floor(pick(options, "severity_cap", 9)),
        recovery_percent = math.min(1, pick(options, "recovery_percent", 0.8)),
        history_limit = math.floor(pick(options, "history_limit", 1024)),
    }

    local state = {
        clock = 0,
        lease_serial = 0,
        ticket_serial = 0,
        roster = {},          -- id -> { revision, connected, alive, health_percent }
        tickets = {},         -- array, creation order
        request_memo = {},    -- request_id -> result
        volunteer_memo = {},  -- helper_id -> { request_id -> result }
        memo_log = {},        -- array of { kind, helper_id, request_id } in first-seen order
    }

    ---------------------------------------------------------------- helpers

    local function ticket_index_for(target_id)
        for index = 1, #state.tickets do
            if state.tickets[index].target_id == target_id then
                return index
            end
        end
        return nil
    end

    local function ticket_held_by(helper_id)
        for index = 1, #state.tickets do
            local lease = state.tickets[index].lease
            if lease ~= nil and lease.helper_id == helper_id then
                return state.tickets[index]
            end
        end
        return nil
    end

    local function ticket_with_lease(lease_id)
        for index = 1, #state.tickets do
            local lease = state.tickets[index].lease
            if lease ~= nil and lease.lease_id == lease_id then
                return state.tickets[index]
            end
        end
        return nil
    end

    local function requeue(ticket)
        ticket.lease = nil
        ticket.requeues = ticket.requeues + 1
    end

    local function close_ticket(target_id)
        local index = ticket_index_for(target_id)
        if index == nil then
            return false
        end
        table.remove(state.tickets, index)
        return true
    end

    -- Returns nil for an unusable time, otherwise the lease ids that expired.
    local function settle(now)
        if not is_finite(now) or now < 0 or now < state.clock then
            return nil
        end
        state.clock = now
        local lapsed = {}
        for index = 1, #state.tickets do
            local ticket = state.tickets[index]
            if ticket.lease ~= nil and now >= ticket.lease.expires_at then
                lapsed[#lapsed + 1] = ticket.lease.lease_id
                requeue(ticket)
            end
        end
        return lapsed
    end

    local function effective(ticket, now)
        local waited = now - ticket.created_at
        if waited < 0 then
            waited = 0
        end
        return ticket.severity + math.floor(waited / config.aging_interval)
    end

    local function ranked(now)
        local list = {}
        for index = 1, #state.tickets do
            local ticket = state.tickets[index]
            list[#list + 1] = { ticket = ticket, weight = effective(ticket, now) }
        end
        return arrange(list, function(left, right)
            if left.weight ~= right.weight then
                return left.weight > right.weight
            end
            if left.ticket.created_at ~= right.ticket.created_at then
                return left.ticket.created_at < right.ticket.created_at
            end
            return left.ticket.target_id < right.ticket.target_id
        end)
    end

    local function remember(kind, helper_id, request_id, result)
        if kind == "request" then
            state.request_memo[request_id] = clone(result)
        else
            local mine = state.volunteer_memo[helper_id]
            if mine == nil then
                mine = {}
                state.volunteer_memo[helper_id] = mine
            end
            mine[request_id] = clone(result)
        end
        state.memo_log[#state.memo_log + 1] = { kind = kind, helper_id = helper_id, request_id = request_id }
        while #state.memo_log > config.history_limit do
            local oldest = table.remove(state.memo_log, 1)
            if oldest.kind == "request" then
                state.request_memo[oldest.request_id] = nil
            elseif state.volunteer_memo[oldest.helper_id] ~= nil then
                state.volunteer_memo[oldest.helper_id][oldest.request_id] = nil
            end
        end
        return result
    end

    local function usable(player)
        return player ~= nil and player.connected and player.alive
    end

    ---------------------------------------------------------------- object

    local dispatch = {}

    function dispatch.update_player(_, record, now)
        if type(record) ~= "table" or not is_id(record.id) then
            return refuse("bad_record")
        end
        if not is_whole(record.revision) then
            return refuse("bad_revision")
        end
        if type(record.connected) ~= "boolean" or type(record.alive) ~= "boolean" then
            return refuse("bad_record")
        end
        local percent = record.health_percent
        if not is_finite(percent) or percent < 0 or percent > 1 then
            return refuse("bad_health")
        end
        local known = state.roster[record.id]
        if known ~= nil and record.revision <= known.revision then
            return refuse("stale_revision")
        end
        if settle(now) == nil then
            return refuse("bad_time")
        end

        local player = {
            revision = record.revision,
            connected = record.connected,
            alive = record.alive,
            health_percent = percent,
        }
        state.roster[record.id] = player

        if not usable(player) then
            local held = ticket_held_by(record.id)
            if held ~= nil then
                requeue(held)
            end
            close_ticket(record.id)
        elseif percent >= config.recovery_percent then
            close_ticket(record.id)
        end
        return { ok = true, id = record.id, revision = record.revision }
    end

    function dispatch.request(_, request_id, target_id, severity, now)
        if not is_id(request_id) or not is_id(target_id) then
            return refuse("bad_identifier")
        end
        if settle(now) == nil then
            return refuse("bad_time")
        end
        local seen = state.request_memo[request_id]
        if seen ~= nil then
            return clone(seen)
        end
        if not is_whole(severity) or severity < 1 or severity > config.severity_cap then
            return refuse("bad_severity")
        end
        local player = state.roster[target_id]
        if not usable(player) then
            return remember("request", nil, request_id, refuse("target_unavailable", { target_id = target_id }))
        end
        if player.health_percent >= config.recovery_percent then
            return remember("request", nil, request_id, refuse("target_healthy", { target_id = target_id }))
        end

        local index = ticket_index_for(target_id)
        if index ~= nil then
            local ticket = state.tickets[index]
            if severity > ticket.severity then
                ticket.severity = severity
            end
            return remember("request", nil, request_id, {
                ok = true, target_id = target_id, severity = ticket.severity,
                created_at = ticket.created_at, duplicate_target = true,
            })
        end
        state.ticket_serial = state.ticket_serial + 1
        state.tickets[#state.tickets + 1] = {
            serial = state.ticket_serial,
            target_id = target_id,
            severity = severity,
            created_at = now,
            requeues = 0,
            lease = nil,
        }
        return remember("request", nil, request_id, {
            ok = true, target_id = target_id, severity = severity,
            created_at = now, duplicate_target = false,
        })
    end

    function dispatch.volunteer(_, request_id, helper_id, now)
        if not is_id(request_id) or not is_id(helper_id) then
            return refuse("bad_identifier")
        end
        if settle(now) == nil then
            return refuse("bad_time")
        end
        local mine = state.volunteer_memo[helper_id]
        if mine ~= nil and mine[request_id] ~= nil then
            return clone(mine[request_id])
        end
        if not usable(state.roster[helper_id]) then
            return remember("volunteer", helper_id, request_id, refuse("helper_unavailable"))
        end
        if ticket_held_by(helper_id) ~= nil then
            return remember("volunteer", helper_id, request_id, refuse("helper_busy"))
        end
        local order = ranked(now)
        for position = 1, #order do
            local ticket = order[position].ticket
            if ticket.lease == nil and ticket.target_id ~= helper_id then
                state.lease_serial = state.lease_serial + 1
                ticket.lease = {
                    serial = state.lease_serial,
                    lease_id = lease_name(state.lease_serial),
                    helper_id = helper_id,
                    granted_at = now,
                    expires_at = now + config.lease_ttl,
                }
                return remember("volunteer", helper_id, request_id, {
                    ok = true,
                    lease_id = ticket.lease.lease_id,
                    target_id = ticket.target_id,
                    helper_id = helper_id,
                    expires_at = ticket.lease.expires_at,
                })
            end
        end
        return remember("volunteer", helper_id, request_id, refuse("queue_empty"))
    end

    local function owned_lease(lease_id, helper_id, now)
        if not is_id(lease_id) or not is_id(helper_id) then
            return nil, refuse("bad_identifier")
        end
        if settle(now) == nil then
            return nil, refuse("bad_time")
        end
        local ticket = ticket_with_lease(lease_id)
        if ticket == nil then
            return nil, refuse("lease_inactive")
        end
        if ticket.lease.helper_id ~= helper_id then
            return nil, refuse("wrong_helper")
        end
        return ticket, nil
    end

    function dispatch.heartbeat(_, lease_id, helper_id, now)
        local ticket, problem = owned_lease(lease_id, helper_id, now)
        if ticket == nil then
            return problem
        end
        ticket.lease.expires_at = now + config.lease_ttl
        return {
            ok = true, lease_id = lease_id, target_id = ticket.target_id,
            expires_at = ticket.lease.expires_at,
        }
    end

    function dispatch.complete(_, lease_id, helper_id, now)
        local ticket, problem = owned_lease(lease_id, helper_id, now)
        if ticket == nil then
            return problem
        end
        local target_id = ticket.target_id
        close_ticket(target_id)
        return { ok = true, lease_id = lease_id, target_id = target_id }
    end

    function dispatch.cancel(_, target_id, now)
        if not is_id(target_id) then
            return refuse("bad_identifier")
        end
        if settle(now) == nil then
            return refuse("bad_time")
        end
        if not close_ticket(target_id) then
            return refuse("nothing_open", { target_id = target_id })
        end
        return { ok = true, target_id = target_id }
    end

    function dispatch.tick(_, now)
        local lapsed = settle(now)
        if lapsed == nil then
            return refuse("bad_time")
        end
        return { ok = true, now = state.clock, expired = lapsed }
    end

    function dispatch.snapshot(_, now)
        if settle(now) == nil then
            now = state.clock
        end
        local queue, leases = {}, {}
        local order = ranked(now)
        for position = 1, #order do
            local ticket = order[position].ticket
            if ticket.lease == nil then
                queue[#queue + 1] = {
                    target_id = ticket.target_id,
                    severity = ticket.severity,
                    effective_severity = order[position].weight,
                    created_at = ticket.created_at,
                    requeues = ticket.requeues,
                }
            else
                leases[#leases + 1] = {
                    serial = ticket.lease.serial,
                    lease_id = ticket.lease.lease_id,
                    target_id = ticket.target_id,
                    helper_id = ticket.lease.helper_id,
                    expires_at = ticket.lease.expires_at,
                }
            end
        end
        arrange(leases, function(left, right)
            return left.serial < right.serial
        end)
        for position = 1, #leases do
            leases[position].serial = nil
        end
        return { now = now, queue = queue, leases = leases }
    end

    function dispatch.save(_, now)
        settle(now)
        local roster, ids = {}, {}
        for id in pairs(state.roster) do
            ids[#ids + 1] = id
        end
        arrange(ids, function(left, right)
            return left < right
        end)
        for position = 1, #ids do
            local player = state.roster[ids[position]]
            roster[position] = {
                id = ids[position], revision = player.revision, connected = player.connected,
                alive = player.alive, health_percent = player.health_percent,
            }
        end
        local tickets = {}
        for index = 1, #state.tickets do
            local ticket = state.tickets[index]
            local saved = {
                serial = ticket.serial, target_id = ticket.target_id, severity = ticket.severity,
                created_at = ticket.created_at, requeues = ticket.requeues,
            }
            if ticket.lease ~= nil then
                saved.lease = clone(ticket.lease)
            end
            tickets[index] = saved
        end
        local memo = {}
        for index = 1, #state.memo_log do
            local entry = state.memo_log[index]
            local result
            if entry.kind == "request" then
                result = state.request_memo[entry.request_id]
            else
                result = state.volunteer_memo[entry.helper_id][entry.request_id]
            end
            memo[index] = {
                kind = entry.kind, helper_id = entry.helper_id,
                request_id = entry.request_id, result = clone(result),
            }
        end
        return {
            format = "rescuedispatch/1",
            clock = state.clock,
            lease_serial = state.lease_serial,
            ticket_serial = state.ticket_serial,
            roster = roster,
            tickets = tickets,
            memo = memo,
        }
    end

    ---------------------------------------------------------------- restore

    local function restore(data)
        if type(data) ~= "table" or data.format ~= "rescuedispatch/1" then
            return
        end
        if is_finite(data.clock) and data.clock >= 0 then
            state.clock = data.clock
        end
        if is_whole(data.lease_serial) then
            state.lease_serial = data.lease_serial
        end
        if is_whole(data.ticket_serial) then
            state.ticket_serial = data.ticket_serial
        end
        for _, player in ipairs(type(data.roster) == "table" and data.roster or {}) do
            if type(player) == "table" and is_id(player.id) and is_whole(player.revision)
                and type(player.connected) == "boolean" and type(player.alive) == "boolean"
                and is_finite(player.health_percent) then
                state.roster[player.id] = {
                    revision = player.revision, connected = player.connected,
                    alive = player.alive, health_percent = player.health_percent,
                }
            end
        end
        local busy = {}
        for _, saved in ipairs(type(data.tickets) == "table" and data.tickets or {}) do
            if type(saved) == "table" and is_id(saved.target_id) and is_finite(saved.severity)
                and is_finite(saved.created_at) and ticket_index_for(saved.target_id) == nil then
                local ticket = {
                    serial = is_whole(saved.serial) and saved.serial or (#state.tickets + 1),
                    target_id = saved.target_id,
                    severity = saved.severity,
                    created_at = saved.created_at,
                    requeues = is_whole(saved.requeues) and saved.requeues or 0,
                    lease = nil,
                }
                local lease = saved.lease
                if type(lease) == "table" and is_id(lease.lease_id) and is_id(lease.helper_id)
                    and is_finite(lease.expires_at) and not busy[lease.helper_id] then
                    busy[lease.helper_id] = true
                    ticket.lease = {
                        serial = is_whole(lease.serial) and lease.serial or 0,
                        lease_id = lease.lease_id,
                        helper_id = lease.helper_id,
                        granted_at = is_finite(lease.granted_at) and lease.granted_at or state.clock,
                        expires_at = lease.expires_at,
                    }
                end
                state.tickets[#state.tickets + 1] = ticket
            end
        end
        for _, entry in ipairs(type(data.memo) == "table" and data.memo or {}) do
            if type(entry) == "table" and type(entry.result) == "table" and is_id(entry.request_id) then
                if entry.kind == "request" and state.request_memo[entry.request_id] == nil then
                    remember("request", nil, entry.request_id, clone(entry.result))
                elseif entry.kind == "volunteer" and is_id(entry.helper_id)
                    and (state.volunteer_memo[entry.helper_id] == nil
                        or state.volunteer_memo[entry.helper_id][entry.request_id] == nil) then
                    remember("volunteer", entry.helper_id, entry.request_id, clone(entry.result))
                end
            end
        end
    end

    -- Read-only helpers for the host component (not part of the required API).
    function dispatch.clock()
        return state.clock
    end

    function dispatch.player(_, id)
        local player = state.roster[id]
        return player ~= nil and clone(player) or nil
    end

    return dispatch, restore
end

function Dispatch.new(options)
    local dispatch = construct(options)
    return dispatch
end

function Dispatch.load(data, options)
    local dispatch, restore = construct(options)
    restore(data)
    return dispatch
end

return Dispatch
