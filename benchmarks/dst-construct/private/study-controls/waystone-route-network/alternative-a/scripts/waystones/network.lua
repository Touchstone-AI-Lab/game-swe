-- Waystone network core, closure based. State lives in arrays (node list, edge
-- list, ticket log); lookups are linear scans and routing is a forward label
-- search whose labels carry the whole path, compared as (cost, hops, ids).

local ID_PATTERN = "^[A-Za-z0-9_%.:%-]+$"
local FALLBACK = { max_nodes_per_owner = 4, max_link_length = 60, cost_per_unit = 0.25, ticket_ttl = 10, cooldown = 30 }

local function finite(n)
    return type(n) == "number" and n == n and n < math.huge and n > -math.huge
end

local function ident(s)
    return type(s) == "string" and s:len() > 0 and s:len() <= 64 and s:match(ID_PATTERN) ~= nil
end

local function reject(code)
    return { ok = false, code = code }
end

local function clone(value)
    if type(value) ~= "table" then
        return value
    end
    local out = {}
    for k, v in pairs(value) do
        out[k] = clone(v)
    end
    return out
end

local function settings(options)
    local cfg = {}
    for name, default in pairs(FALLBACK) do
        local given = type(options) == "table" and options[name] or nil
        local usable = finite(given) and given > 0
        if usable and name == "max_nodes_per_owner" and given % 1 ~= 0 then
            usable = false
        end
        cfg[name] = usable and given or default
    end
    return cfg
end

local function round_cost(p, q)
    local dx, dz = p.x - q.x, p.z - q.z
    local rounded = math.floor(math.sqrt(dx * dx + dz * dz) + 0.5)
    if rounded < 1 then
        rounded = 1
    end
    return rounded
end

-- true when label p (cost, hops, path) beats label q
local function better(p, q)
    if p.cost ~= q.cost then
        return p.cost < q.cost
    end
    if p.hops ~= q.hops then
        return p.hops < q.hops
    end
    for i = 1, #p.path do
        if p.path[i] ~= q.path[i] then
            return p.path[i] < q.path[i]
        end
    end
    return false
end

local function build(cfg, state)
    local clock = state.clock
    local counter = state.counter
    local nodes = state.nodes         -- array of { id, owner_id, x, z, blocked }
    local edges = state.edges         -- array of { a, b, cost } with a < b
    local tickets = state.tickets     -- array in creation order
    local cooling = state.cooling     -- array of { traveler_id, cooldown_until }

    local function node_at(id)
        for i = 1, #nodes do
            if nodes[i].id == id then
                return nodes[i], i
            end
        end
        return nil
    end

    local function edge_at(p, q)
        local a, b = p, q
        if b < a then
            a, b = q, p
        end
        for i = 1, #edges do
            if edges[i].a == a and edges[i].b == b then
                return edges[i], i
            end
        end
        return nil
    end

    local function ticket_at(ticket_id)
        for i = 1, #tickets do
            if tickets[i].ticket_id == ticket_id then
                return tickets[i]
            end
        end
        return nil
    end

    local function public(ticket)
        local copy = clone(ticket)
        copy.cooldown_until = nil
        return copy
    end

    local function sweep(now)
        local due = {}
        for i = 1, #tickets do
            local t = tickets[i]
            if t.status == "reserved" and now >= t.expires_at then
                due[#due + 1] = t
            end
        end
        table.sort(due, function(p, q)
            if p.expires_at == q.expires_at then
                return p.request_id < q.request_id
            end
            return p.expires_at < q.expires_at
        end)
        local ids = {}
        for i = 1, #due do
            due[i].status = "expired"
            ids[i] = due[i].ticket_id
        end
        return ids
    end

    -- Wraps a method body with the shared time gate and expiry sweep.
    local function timed(body)
        return function(_, ...)
            local count = select("#", ...)
            local args = { ... }
            local now = args[count]
            if count == 0 or not finite(now) or now < clock then
                return reject("invalid_time")
            end
            clock = now
            local swept = sweep(now)
            return body(args, now, swept)
        end
    end

    local function neighbours(id)
        local out = {}
        for i = 1, #edges do
            local e = edges[i]
            if e.a == id then
                out[#out + 1] = { id = e.b, cost = e.cost }
            elseif e.b == id then
                out[#out + 1] = { id = e.a, cost = e.cost }
            end
        end
        return out
    end

    local function plan(from_id, to_id)
        if not ident(from_id) or not ident(to_id) then
            return nil, "invalid_id"
        end
        local from, to = node_at(from_id), node_at(to_id)
        if not from or not to then
            return nil, "unknown_node"
        end
        if from_id == to_id then
            return nil, "same_node"
        end
        if from.blocked or to.blocked then
            return nil, "blocked_endpoint"
        end
        local open = { { id = from_id, cost = 0, hops = 0, path = { from_id } } }
        local closed = {}
        while #open > 0 do
            local pick = 1
            for i = 2, #open do
                if better(open[i], open[pick]) then
                    pick = i
                end
            end
            local label = table.remove(open, pick)
            if not closed[label.id] then
                closed[label.id] = true
                if label.id == to_id then
                    return label, nil
                end
                local around = neighbours(label.id)
                for i = 1, #around do
                    local step = around[i]
                    if not closed[step.id] and not node_at(step.id).blocked then
                        local path = {}
                        for k = 1, #label.path do
                            path[k] = label.path[k]
                        end
                        path[#path + 1] = step.id
                        open[#open + 1] = { id = step.id, cost = label.cost + step.cost, hops = label.hops + 1, path = path }
                    end
                end
            end
        end
        return nil, "no_route"
    end

    local function cooling_row(traveler_id)
        for i = 1, #cooling do
            if cooling[i].traveler_id == traveler_id then
                return cooling[i]
            end
        end
        return nil
    end

    local function intact(ticket)
        local sum = 0
        for i = 1, #ticket.path do
            local node = node_at(ticket.path[i])
            if not node or node.blocked then
                return false
            end
            if i > 1 then
                local edge = edge_at(ticket.path[i - 1], ticket.path[i])
                if not edge then
                    return false
                end
                sum = sum + edge.cost
            end
        end
        return sum == ticket.cost
    end

    local function resolve_ticket(ticket_id)
        if not ident(ticket_id) then
            return nil, reject("invalid_id")
        end
        local ticket = ticket_at(ticket_id)
        if not ticket then
            return nil, reject("unknown_ticket")
        end
        return ticket, nil
    end

    local function view(now)
        local out = { ok = true, now = now, nodes = clone(nodes), links = clone(edges), tickets = {}, cooldowns = {} }
        table.sort(out.nodes, function(p, q) return p.id < q.id end)
        table.sort(out.links, function(p, q)
            if p.a == q.a then
                return p.b < q.b
            end
            return p.a < q.a
        end)
        for i = 1, #tickets do
            if tickets[i].status == "reserved" then
                out.tickets[#out.tickets + 1] = public(tickets[i])
            end
        end
        table.sort(out.tickets, function(p, q)
            if p.expires_at == q.expires_at then
                return p.request_id < q.request_id
            end
            return p.expires_at < q.expires_at
        end)
        for i = 1, #cooling do
            if now < cooling[i].cooldown_until then
                out.cooldowns[#out.cooldowns + 1] = clone(cooling[i])
            end
        end
        table.sort(out.cooldowns, function(p, q) return p.traveler_id < q.traveler_id end)
        return out
    end

    local api = {}

    api.add_node = timed(function(args)
        local node_id, owner_id, x, z = args[1], args[2], args[3], args[4]
        if not ident(node_id) or not ident(owner_id) then
            return reject("invalid_id")
        end
        if not finite(x) or not finite(z) then
            return reject("invalid_position")
        end
        if node_at(node_id) then
            return reject("duplicate_node")
        end
        local held = 0
        for i = 1, #nodes do
            if nodes[i].owner_id == owner_id then
                held = held + 1
            end
        end
        if held >= cfg.max_nodes_per_owner then
            return reject("owner_limit")
        end
        nodes[#nodes + 1] = { id = node_id, owner_id = owner_id, x = x, z = z, blocked = false }
        return { ok = true, node_id = node_id }
    end)

    api.remove_node = timed(function(args)
        local node_id = args[1]
        if not ident(node_id) then
            return reject("invalid_id")
        end
        local _, index = node_at(node_id)
        if not index then
            return reject("unknown_node")
        end
        table.remove(nodes, index)
        local dropped = 0
        for i = #edges, 1, -1 do
            if edges[i].a == node_id or edges[i].b == node_id then
                table.remove(edges, i)
                dropped = dropped + 1
            end
        end
        return { ok = true, removed_links = dropped }
    end)

    api.set_blocked = timed(function(args)
        local node_id, flag = args[1], args[2]
        if not ident(node_id) then
            return reject("invalid_id")
        end
        if flag ~= true and flag ~= false then
            return reject("invalid_flag")
        end
        local node = node_at(node_id)
        if not node then
            return reject("unknown_node")
        end
        local before = node.blocked
        node.blocked = flag
        return { ok = true, blocked = flag, changed = before ~= flag }
    end)

    local function endpoints(args)
        local a_id, b_id = args[1], args[2]
        if not ident(a_id) or not ident(b_id) then
            return nil, nil, reject("invalid_id")
        end
        if a_id == b_id then
            return nil, nil, reject("self_link")
        end
        local a, b = node_at(a_id), node_at(b_id)
        if not a or not b then
            return nil, nil, reject("unknown_node")
        end
        return a, b, nil
    end

    api.link = timed(function(args)
        local a, b, problem = endpoints(args)
        if problem then
            return problem
        end
        local present = edge_at(a.id, b.id)
        if present then
            return { ok = true, created = false, cost = present.cost }
        end
        local dx, dz = a.x - b.x, a.z - b.z
        if dx * dx + dz * dz > cfg.max_link_length * cfg.max_link_length then
            return reject("link_too_long")
        end
        local low, high = a.id, b.id
        if high < low then
            low, high = high, low
        end
        local cost = round_cost(a, b)
        edges[#edges + 1] = { a = low, b = high, cost = cost }
        return { ok = true, created = true, cost = cost }
    end)

    api.unlink = timed(function(args)
        local a, b, problem = endpoints(args)
        if problem then
            return problem
        end
        local _, index = edge_at(a.id, b.id)
        if index then
            table.remove(edges, index)
        end
        return { ok = true, removed = index ~= nil }
    end)

    api.route = timed(function(args)
        local label, code = plan(args[1], args[2])
        if not label then
            return reject(code)
        end
        return { ok = true, cost = label.cost, hops = label.hops, path = label.path }
    end)

    api.reserve = timed(function(args, now)
        local request_id, traveler_id, from_id, to_id = args[1], args[2], args[3], args[4]
        if not (ident(request_id) and ident(traveler_id) and ident(from_id) and ident(to_id)) then
            return reject("invalid_id")
        end
        for i = 1, #tickets do
            local t = tickets[i]
            if t.request_id == request_id then
                if t.traveler_id == traveler_id and t.from_id == from_id and t.to_id == to_id then
                    return { ok = true, duplicate = true, ticket = public(t) }
                end
                return reject("request_conflict")
            end
        end
        local row = cooling_row(traveler_id)
        if row and now < row.cooldown_until then
            return { ok = false, code = "cooldown", retry_at = row.cooldown_until }
        end
        for i = 1, #tickets do
            if tickets[i].traveler_id == traveler_id and tickets[i].status == "reserved" then
                return reject("traveler_busy")
            end
        end
        local label, code = plan(from_id, to_id)
        if not label then
            return reject(code)
        end
        counter = counter + 1
        local ticket = {
            ticket_id = "wt-" .. string.format("%d", counter),
            request_id = request_id,
            traveler_id = traveler_id,
            from_id = from_id,
            to_id = to_id,
            path = label.path,
            cost = label.cost,
            price = math.ceil(label.cost * cfg.cost_per_unit),
            status = "reserved",
            created_at = now,
            expires_at = now + cfg.ticket_ttl,
        }
        tickets[#tickets + 1] = ticket
        return { ok = true, duplicate = false, ticket = public(ticket) }
    end)

    api.commit = timed(function(args, now)
        local ticket, problem = resolve_ticket(args[1])
        if problem then
            return problem
        end
        if ticket.status == "committed" then
            return { ok = true, duplicate = true, ticket = public(ticket), cooldown_until = ticket.cooldown_until }
        elseif ticket.status ~= "reserved" then
            return { ok = false, code = "ticket_closed", status = ticket.status }
        end
        if not intact(ticket) then
            ticket.status = "invalidated"
            return reject("route_changed")
        end
        ticket.status = "committed"
        ticket.cooldown_until = now + cfg.cooldown
        local row = cooling_row(ticket.traveler_id)
        if row then
            row.cooldown_until = ticket.cooldown_until
        else
            cooling[#cooling + 1] = { traveler_id = ticket.traveler_id, cooldown_until = ticket.cooldown_until }
        end
        return { ok = true, duplicate = false, ticket = public(ticket), cooldown_until = ticket.cooldown_until }
    end)

    api.abort = timed(function(args)
        local ticket, problem = resolve_ticket(args[1])
        if problem then
            return problem
        end
        if ticket.status == "aborted" then
            return { ok = true, duplicate = true, ticket = public(ticket) }
        elseif ticket.status ~= "reserved" then
            return { ok = false, code = "ticket_closed", status = ticket.status }
        end
        ticket.status = "aborted"
        return { ok = true, duplicate = false, ticket = public(ticket) }
    end)

    api.tick = timed(function(_, _, swept)
        return { ok = true, expired = swept }
    end)

    api.snapshot = timed(function(_, now)
        return view(now)
    end)

    api.save = timed(function()
        return { ok = true, data = {
            format = "waystones-2",
            clock = clock,
            counter = counter,
            nodes = clone(nodes),
            edges = clone(edges),
            tickets = clone(tickets),
            cooling = clone(cooling),
        } }
    end)

    -- Read-only helpers for the world component.
    function api.owner_of(_, node_id)
        local node = node_at(node_id)
        return node and node.owner_id or nil
    end

    function api.clock_value()
        return clock
    end

    return api
end

local function blank_state()
    return { clock = 0, counter = 0, nodes = {}, edges = {}, tickets = {}, cooling = {} }
end

local function list_of(value, accept)
    local out = {}
    if type(value) == "table" then
        for i = 1, #value do
            if type(value[i]) == "table" and accept(value[i]) then
                out[#out + 1] = clone(value[i])
            end
        end
    end
    return out
end

local Network = {}

function Network.new(options)
    return build(settings(options), blank_state())
end

function Network.load(data, options)
    if type(data) ~= "table" or data.format ~= "waystones-2" or not finite(data.clock) or not finite(data.counter) then
        return Network.new(options)
    end
    local state = blank_state()
    state.clock = math.max(0, data.clock)
    state.counter = math.max(0, math.floor(data.counter))
    state.nodes = list_of(data.nodes, function(n)
        return ident(n.id) and ident(n.owner_id) and finite(n.x) and finite(n.z) and type(n.blocked) == "boolean"
    end)
    state.edges = list_of(data.edges, function(e)
        return ident(e.a) and ident(e.b) and e.a < e.b and finite(e.cost)
    end)
    state.tickets = list_of(data.tickets, function(t)
        return ident(t.ticket_id) and ident(t.request_id) and ident(t.traveler_id) and type(t.path) == "table"
            and type(t.status) == "string" and finite(t.cost) and finite(t.price) and finite(t.expires_at)
    end)
    state.cooling = list_of(data.cooling, function(c)
        return ident(c.traveler_id) and finite(c.cooldown_until)
    end)
    return build(settings(options), state)
end

return Network
