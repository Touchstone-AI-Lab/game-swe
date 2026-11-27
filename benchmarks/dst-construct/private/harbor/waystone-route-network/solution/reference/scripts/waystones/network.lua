-- Pure Lua waystone route network. Time always arrives through the `now`
-- argument; every call first validates it, advances the clock and expires
-- tickets at their exact boundary, so results never depend on tick frequency.

local Network = {}
Network.__index = Network

local DEFAULTS = {
    max_nodes_per_owner = 4,
    max_link_length = 60,
    cost_per_unit = 0.25,
    ticket_ttl = 10,
    cooldown = 30,
}

local function is_finite(value)
    return type(value) == "number" and value == value and value ~= math.huge and value ~= -math.huge
end

local function is_id(value)
    return type(value) == "string" and #value >= 1 and #value <= 64
        and string.find(value, "[^%w_%.:%-]") == nil
end

local function option(options, key, integral)
    local value = type(options) == "table" and options[key] or nil
    if is_finite(value) and value > 0 and (not integral or value == math.floor(value)) then
        return value
    end
    return DEFAULTS[key]
end

local function fail(code, extra)
    local result = extra or {}
    result.ok = false
    result.code = code
    return result
end

local function sorted_keys(map)
    local keys = {}
    for key in pairs(map) do
        keys[#keys + 1] = key
    end
    table.sort(keys)
    return keys
end

local function link_cost(a, b)
    local dx, dz = a.x - b.x, a.z - b.z
    return math.max(1, math.floor(math.sqrt(dx * dx + dz * dz) + 0.5))
end

function Network.new(options)
    local self = setmetatable({}, Network)
    self.max_nodes_per_owner = option(options, "max_nodes_per_owner", true)
    self.max_link_length = option(options, "max_link_length")
    self.cost_per_unit = option(options, "cost_per_unit")
    self.ticket_ttl = option(options, "ticket_ttl")
    self.cooldown = option(options, "cooldown")
    self.clock = 0
    self.seq = 0
    self.nodes = {}      -- node_id -> { id, owner_id, x, z, blocked }
    self.links = {}      -- node_id -> { neighbour_id -> cost }
    self.tickets = {}    -- ticket_id -> ticket
    self.requests = {}   -- request_id -> { traveler_id, from_id, to_id, ticket_id }
    self.live = {}       -- traveler_id -> ticket_id of the live ticket
    self.cooldowns = {}  -- traveler_id -> cooldown_until
    return self
end

local function ticket_view(ticket)
    local path = {}
    for index = 1, #ticket.path do
        path[index] = ticket.path[index]
    end
    return {
        ticket_id = ticket.ticket_id,
        request_id = ticket.request_id,
        traveler_id = ticket.traveler_id,
        from_id = ticket.from_id,
        to_id = ticket.to_id,
        path = path,
        cost = ticket.cost,
        price = ticket.price,
        status = ticket.status,
        created_at = ticket.created_at,
        expires_at = ticket.expires_at,
    }
end

local function by_expiry(a, b)
    if a.expires_at ~= b.expires_at then
        return a.expires_at < b.expires_at
    end
    return a.request_id < b.request_id
end

function Network:_live_tickets()
    local list = {}
    for _, ticket_id in pairs(self.live) do
        list[#list + 1] = self.tickets[ticket_id]
    end
    table.sort(list, by_expiry)
    return list
end

function Network:_close(ticket, status)
    ticket.status = status
    if self.live[ticket.traveler_id] == ticket.ticket_id then
        self.live[ticket.traveler_id] = nil
    end
end

function Network:_expire(now)
    local expired = {}
    local live = self:_live_tickets()
    for index = 1, #live do
        local ticket = live[index]
        if now >= ticket.expires_at then
            self:_close(ticket, "expired")
            expired[#expired + 1] = ticket.ticket_id
        end
    end
    return expired
end

-- Shared prologue: returns a failure table, or nil plus the expired list.
function Network:_begin(now)
    if not is_finite(now) or now < self.clock then
        return fail("invalid_time")
    end
    self.clock = now
    return nil, self:_expire(now)
end

function Network:add_node(node_id, owner_id, x, z, now)
    local failure = self:_begin(now)
    if failure then
        return failure
    end
    if not is_id(node_id) or not is_id(owner_id) then
        return fail("invalid_id")
    end
    if not is_finite(x) or not is_finite(z) then
        return fail("invalid_position")
    end
    if self.nodes[node_id] ~= nil then
        return fail("duplicate_node")
    end
    local owned = 0
    for _, node in pairs(self.nodes) do
        if node.owner_id == owner_id then
            owned = owned + 1
        end
    end
    if owned >= self.max_nodes_per_owner then
        return fail("owner_limit")
    end
    self.nodes[node_id] = { id = node_id, owner_id = owner_id, x = x, z = z, blocked = false }
    self.links[node_id] = {}
    return { ok = true, node_id = node_id }
end

function Network:remove_node(node_id, now)
    local failure = self:_begin(now)
    if failure then
        return failure
    end
    if not is_id(node_id) then
        return fail("invalid_id")
    end
    if self.nodes[node_id] == nil then
        return fail("unknown_node")
    end
    local removed = 0
    for other in pairs(self.links[node_id]) do
        self.links[other][node_id] = nil
        removed = removed + 1
    end
    self.links[node_id] = nil
    self.nodes[node_id] = nil
    return { ok = true, removed_links = removed }
end

function Network:set_blocked(node_id, blocked, now)
    local failure = self:_begin(now)
    if failure then
        return failure
    end
    if not is_id(node_id) then
        return fail("invalid_id")
    end
    if type(blocked) ~= "boolean" then
        return fail("invalid_flag")
    end
    local node = self.nodes[node_id]
    if node == nil then
        return fail("unknown_node")
    end
    local changed = node.blocked ~= blocked
    node.blocked = blocked
    return { ok = true, blocked = blocked, changed = changed }
end

function Network:_pair(a_id, b_id)
    if not is_id(a_id) or not is_id(b_id) then
        return nil, nil, fail("invalid_id")
    end
    if a_id == b_id then
        return nil, nil, fail("self_link")
    end
    local a, b = self.nodes[a_id], self.nodes[b_id]
    if a == nil or b == nil then
        return nil, nil, fail("unknown_node")
    end
    return a, b, nil
end

function Network:link(a_id, b_id, now)
    local failure = self:_begin(now)
    if failure then
        return failure
    end
    local a, b, invalid = self:_pair(a_id, b_id)
    if invalid then
        return invalid
    end
    local existing = self.links[a_id][b_id]
    if existing ~= nil then
        return { ok = true, created = false, cost = existing }
    end
    local dx, dz = a.x - b.x, a.z - b.z
    if dx * dx + dz * dz > self.max_link_length * self.max_link_length then
        return fail("link_too_long")
    end
    local cost = link_cost(a, b)
    self.links[a_id][b_id] = cost
    self.links[b_id][a_id] = cost
    return { ok = true, created = true, cost = cost }
end

function Network:unlink(a_id, b_id, now)
    local failure = self:_begin(now)
    if failure then
        return failure
    end
    local _, _, invalid = self:_pair(a_id, b_id)
    if invalid then
        return invalid
    end
    local removed = self.links[a_id][b_id] ~= nil
    self.links[a_id][b_id] = nil
    self.links[b_id][a_id] = nil
    return { ok = true, removed = removed }
end

-- Label-setting search from the destination over (cost, hops); the path is
-- then rebuilt from the origin by always taking the smallest neighbour id that
-- stays on an optimal route, which yields the lexicographically smallest one.
function Network:_search(from_id, to_id)
    local best = { [to_id] = { cost = 0, hops = 0 } }
    local done = {}
    while true do
        local current, label = nil, nil
        for id, candidate in pairs(best) do
            if not done[id] and (label == nil or candidate.cost < label.cost
                    or (candidate.cost == label.cost and candidate.hops < label.hops)) then
                current, label = id, candidate
            end
        end
        if current == nil then
            break
        end
        done[current] = true
        for other, cost in pairs(self.links[current]) do
            if not done[other] and not self.nodes[other].blocked then
                local known = best[other]
                local total, hops = label.cost + cost, label.hops + 1
                if known == nil or total < known.cost or (total == known.cost and hops < known.hops) then
                    best[other] = { cost = total, hops = hops }
                end
            end
        end
    end
    local origin = best[from_id]
    if origin == nil then
        return nil
    end
    local path, cursor = { from_id }, from_id
    while cursor ~= to_id do
        local here, chosen = best[cursor], nil
        for other, cost in pairs(self.links[cursor]) do
            local there = best[other]
            if there ~= nil and there.cost + cost == here.cost and there.hops + 1 == here.hops
                and (chosen == nil or other < chosen) then
                chosen = other
            end
        end
        cursor = chosen
        path[#path + 1] = cursor
    end
    return { cost = origin.cost, hops = origin.hops, path = path }
end

function Network:_route(from_id, to_id)
    if not is_id(from_id) or not is_id(to_id) then
        return nil, fail("invalid_id")
    end
    local from, to = self.nodes[from_id], self.nodes[to_id]
    if from == nil or to == nil then
        return nil, fail("unknown_node")
    end
    if from_id == to_id then
        return nil, fail("same_node")
    end
    if from.blocked or to.blocked then
        return nil, fail("blocked_endpoint")
    end
    local found = self:_search(from_id, to_id)
    if found == nil then
        return nil, fail("no_route")
    end
    return found, nil
end

function Network:route(from_id, to_id, now)
    local failure = self:_begin(now)
    if failure then
        return failure
    end
    local found, invalid = self:_route(from_id, to_id)
    if invalid then
        return invalid
    end
    return { ok = true, cost = found.cost, hops = found.hops, path = found.path }
end

function Network:reserve(request_id, traveler_id, from_id, to_id, now)
    local failure = self:_begin(now)
    if failure then
        return failure
    end
    if not (is_id(request_id) and is_id(traveler_id) and is_id(from_id) and is_id(to_id)) then
        return fail("invalid_id")
    end
    local seen = self.requests[request_id]
    if seen ~= nil then
        if seen.traveler_id ~= traveler_id or seen.from_id ~= from_id or seen.to_id ~= to_id then
            return fail("request_conflict")
        end
        return { ok = true, duplicate = true, ticket = ticket_view(self.tickets[seen.ticket_id]) }
    end
    local cooldown_until = self.cooldowns[traveler_id]
    if cooldown_until ~= nil and now < cooldown_until then
        return fail("cooldown", { retry_at = cooldown_until })
    end
    if self.live[traveler_id] ~= nil then
        return fail("traveler_busy")
    end
    local found, invalid = self:_route(from_id, to_id)
    if invalid then
        return invalid
    end
    self.seq = self.seq + 1
    local ticket = {
        ticket_id = string.format("T%d", self.seq),
        request_id = request_id,
        traveler_id = traveler_id,
        from_id = from_id,
        to_id = to_id,
        path = found.path,
        cost = found.cost,
        price = math.ceil(found.cost * self.cost_per_unit),
        status = "reserved",
        created_at = now,
        expires_at = now + self.ticket_ttl,
    }
    self.tickets[ticket.ticket_id] = ticket
    self.live[traveler_id] = ticket.ticket_id
    self.requests[request_id] = {
        traveler_id = traveler_id, from_id = from_id, to_id = to_id, ticket_id = ticket.ticket_id,
    }
    return { ok = true, duplicate = false, ticket = ticket_view(ticket) }
end

-- A ticketed route stays valid while every hop still exists unblocked, every
-- consecutive pair is still linked and the current costs add up to the ticket.
function Network:_still_valid(ticket)
    local total = 0
    for index = 1, #ticket.path do
        local node = self.nodes[ticket.path[index]]
        if node == nil or node.blocked then
            return false
        end
        if index > 1 then
            local cost = self.links[ticket.path[index - 1]][ticket.path[index]]
            if cost == nil then
                return false
            end
            total = total + cost
        end
    end
    return total == ticket.cost
end

function Network:_ticket(ticket_id, now)
    local failure = self:_begin(now)
    if failure then
        return nil, failure
    end
    if not is_id(ticket_id) then
        return nil, fail("invalid_id")
    end
    local ticket = self.tickets[ticket_id]
    if ticket == nil then
        return nil, fail("unknown_ticket")
    end
    return ticket, nil
end

function Network:commit(ticket_id, now)
    local ticket, failure = self:_ticket(ticket_id, now)
    if failure then
        return failure
    end
    if ticket.status == "committed" then
        return { ok = true, duplicate = true, ticket = ticket_view(ticket), cooldown_until = ticket.cooldown_until }
    end
    if ticket.status ~= "reserved" then
        return fail("ticket_closed", { status = ticket.status })
    end
    if not self:_still_valid(ticket) then
        self:_close(ticket, "invalidated")
        return fail("route_changed")
    end
    self:_close(ticket, "committed")
    ticket.cooldown_until = now + self.cooldown
    self.cooldowns[ticket.traveler_id] = ticket.cooldown_until
    return { ok = true, duplicate = false, ticket = ticket_view(ticket), cooldown_until = ticket.cooldown_until }
end

function Network:abort(ticket_id, now)
    local ticket, failure = self:_ticket(ticket_id, now)
    if failure then
        return failure
    end
    if ticket.status == "aborted" then
        return { ok = true, duplicate = true, ticket = ticket_view(ticket) }
    end
    if ticket.status ~= "reserved" then
        return fail("ticket_closed", { status = ticket.status })
    end
    self:_close(ticket, "aborted")
    return { ok = true, duplicate = false, ticket = ticket_view(ticket) }
end

function Network:tick(now)
    local failure, expired = self:_begin(now)
    if failure then
        return failure
    end
    return { ok = true, expired = expired }
end

function Network:snapshot(now)
    local failure = self:_begin(now)
    if failure then
        return failure
    end
    local nodes, links, tickets, cooldowns = {}, {}, {}, {}
    local ids = sorted_keys(self.nodes)
    for index = 1, #ids do
        local node = self.nodes[ids[index]]
        nodes[#nodes + 1] = { id = node.id, owner_id = node.owner_id, x = node.x, z = node.z, blocked = node.blocked }
        local others = sorted_keys(self.links[node.id])
        for position = 1, #others do
            if node.id < others[position] then
                links[#links + 1] = { a = node.id, b = others[position], cost = self.links[node.id][others[position]] }
            end
        end
    end
    local live = self:_live_tickets()
    for index = 1, #live do
        tickets[index] = ticket_view(live[index])
    end
    local travelers = sorted_keys(self.cooldowns)
    for index = 1, #travelers do
        local cooldown_until = self.cooldowns[travelers[index]]
        if now < cooldown_until then
            cooldowns[#cooldowns + 1] = { traveler_id = travelers[index], cooldown_until = cooldown_until }
        end
    end
    return { ok = true, now = now, nodes = nodes, links = links, tickets = tickets, cooldowns = cooldowns }
end

function Network:save(now)
    local view = self:snapshot(now)
    if not view.ok then
        return view
    end
    local data = { version = 1, clock = self.clock, seq = self.seq, nodes = view.nodes, links = {},
        tickets = {}, requests = {}, cooldowns = {} }
    for index = 1, #view.links do
        data.links[index] = { a = view.links[index].a, b = view.links[index].b }
    end
    local ticket_ids = sorted_keys(self.tickets)
    for index = 1, #ticket_ids do
        local ticket = self.tickets[ticket_ids[index]]
        local row = ticket_view(ticket)
        row.cooldown_until = ticket.cooldown_until
        data.tickets[index] = row
    end
    local request_ids = sorted_keys(self.requests)
    for index = 1, #request_ids do
        local seen = self.requests[request_ids[index]]
        data.requests[index] = { request_id = request_ids[index], traveler_id = seen.traveler_id,
            from_id = seen.from_id, to_id = seen.to_id, ticket_id = seen.ticket_id }
    end
    local travelers = sorted_keys(self.cooldowns)
    for index = 1, #travelers do
        data.cooldowns[index] = { traveler_id = travelers[index], cooldown_until = self.cooldowns[travelers[index]] }
    end
    return { ok = true, data = data }
end

local STATUSES = { reserved = true, committed = true, aborted = true, expired = true, invalidated = true }

local function rows(value)
    return type(value) == "table" and value or {}
end

local function load_ticket(row)
    if type(row) ~= "table" or not (is_id(row.ticket_id) and is_id(row.request_id) and is_id(row.traveler_id)
            and is_id(row.from_id) and is_id(row.to_id)) or not STATUSES[row.status]
        or not (is_finite(row.cost) and is_finite(row.price) and is_finite(row.created_at)
            and is_finite(row.expires_at)) or type(row.path) ~= "table" then
        return nil
    end
    local ticket = ticket_view(row)
    for index = 1, #ticket.path do
        if not is_id(ticket.path[index]) then
            return nil
        end
    end
    ticket.cooldown_until = is_finite(row.cooldown_until) and row.cooldown_until or nil
    return ticket
end

function Network.load(data, options)
    local self = Network.new(options)
    if type(data) ~= "table" or data.version ~= 1 or not is_finite(data.clock) or data.clock < 0
        or not is_finite(data.seq) or data.seq < 0 then
        return self
    end
    self.clock = data.clock
    self.seq = math.floor(data.seq)
    for _, row in ipairs(rows(data.nodes)) do
        if type(row) == "table" and is_id(row.id) and is_id(row.owner_id) and is_finite(row.x)
            and is_finite(row.z) and self.nodes[row.id] == nil then
            self.nodes[row.id] = { id = row.id, owner_id = row.owner_id, x = row.x, z = row.z,
                blocked = row.blocked == true }
            self.links[row.id] = {}
        end
    end
    for _, row in ipairs(rows(data.links)) do
        local a = type(row) == "table" and self.nodes[row.a] or nil
        local b = type(row) == "table" and self.nodes[row.b] or nil
        if a ~= nil and b ~= nil and a ~= b then
            local cost = link_cost(a, b)
            self.links[a.id][b.id] = cost
            self.links[b.id][a.id] = cost
        end
    end
    for _, row in ipairs(rows(data.tickets)) do
        local ticket = load_ticket(row)
        if ticket ~= nil and self.tickets[ticket.ticket_id] == nil then
            self.tickets[ticket.ticket_id] = ticket
            if ticket.status == "reserved" and self.live[ticket.traveler_id] == nil then
                self.live[ticket.traveler_id] = ticket.ticket_id
            end
        end
    end
    for _, row in ipairs(rows(data.requests)) do
        if type(row) == "table" and is_id(row.request_id) and self.tickets[row.ticket_id] ~= nil then
            self.requests[row.request_id] = { traveler_id = row.traveler_id, from_id = row.from_id,
                to_id = row.to_id, ticket_id = row.ticket_id }
        end
    end
    for _, row in ipairs(rows(data.cooldowns)) do
        if type(row) == "table" and is_id(row.traveler_id) and is_finite(row.cooldown_until) then
            self.cooldowns[row.traveler_id] = row.cooldown_until
        end
    end
    return self
end

return Network
