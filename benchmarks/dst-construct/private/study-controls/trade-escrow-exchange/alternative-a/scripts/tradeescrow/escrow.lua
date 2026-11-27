-- Two-party escrow written as a closure over private state. Trades live in an
-- append-only ledger; every offer is kept as a prefab-sorted array; the phase
-- rules are a lookup table that mirrors the published phase matrix.

local M = {}

local OPEN, SETTLING, SETTLED, CANCELED, EXPIRED = "open", "settling", "settled", "canceled", "expired"

-- What each gated method does per phase: a string is a rejection code, true
-- means "carry on with the method's own rules".
local GATE = {
    offer = { [OPEN] = true, [SETTLING] = "trade_locked", [SETTLED] = "trade_closed",
        [CANCELED] = "trade_closed", [EXPIRED] = "trade_closed" },
    confirm = { [OPEN] = true, [SETTLING] = "trade_locked", [SETTLED] = "trade_closed",
        [CANCELED] = "trade_closed", [EXPIRED] = "trade_closed" },
    cancel = { [OPEN] = true, [SETTLING] = "trade_locked", [SETTLED] = "trade_closed",
        [CANCELED] = true, [EXPIRED] = "trade_closed" },
    begin_settle = { [OPEN] = true, [SETTLING] = true, [SETTLED] = "trade_closed",
        [CANCELED] = "trade_closed", [EXPIRED] = "trade_closed" },
    finish_ok = { [OPEN] = "not_settling", [SETTLING] = true, [SETTLED] = true,
        [CANCELED] = "trade_closed", [EXPIRED] = "trade_closed" },
    finish_fail = { [OPEN] = "not_settling", [SETTLING] = true, [SETTLED] = "trade_closed",
        [CANCELED] = "trade_closed", [EXPIRED] = "trade_closed" },
}

local function text(value)
    return type(value) == "string" and #value > 0
end

local function number(value)
    return type(value) == "number" and value == value
end

local function whole(value, floor)
    if not number(value) or value < floor or value == math.huge then
        return false
    end
    return value % 1 == 0
end

-- Converts a prefab->count map into a sorted array, or returns a rejection code.
local function normalise(items, allowed, cap)
    local names, bad_name = {}, false
    for name in pairs(items) do
        if text(name) and allowed[name] then
            names[#names + 1] = name
        else
            bad_name = true
        end
    end
    local distinct = #names
    if bad_name then
        distinct = 0
        for _ in pairs(items) do
            distinct = distinct + 1
        end
    end
    if distinct > cap then
        return nil, "too_many_prefabs"
    end
    if bad_name then
        return nil, "prefab_not_allowed"
    end
    table.sort(names)
    local rows = {}
    for index, name in ipairs(names) do
        if not whole(items[name], 1) then
            return nil, "invalid_count"
        end
        rows[index] = { prefab = name, count = items[name] }
    end
    return rows
end

-- Compares a stored sorted offer with a raw prefab->count map.
local function matches(rows, items)
    local seen = 0
    for _ in pairs(items) do
        seen = seen + 1
    end
    if seen ~= #rows then
        return false
    end
    for _, row in ipairs(rows) do
        if items[row.prefab] ~= row.count then
            return false
        end
    end
    return true
end

local function clone_rows(rows)
    local out = {}
    for index, row in ipairs(rows) do
        out[index] = { prefab = row.prefab, count = row.count }
    end
    return out
end

local function build(options, seed)
    options = type(options) == "table" and options or {}
    local allowed = {}
    for name, flag in pairs(type(options.allowed_prefabs) == "table" and options.allowed_prefabs or {}) do
        if flag then
            allowed[name] = true
        end
    end
    local cap = whole(options.max_distinct, 1) and options.max_distinct or 1
    local ttl = (number(options.ttl) and options.ttl > 0) and options.ttl or 1

    local ledger = {}     -- array of trades in creation order
    local by_id = {}      -- trade_id -> index into ledger

    local function live(trade)
        return trade.phase == OPEN or trade.phase == SETTLING
    end

    local function seat(trade, who)
        if trade.seats[1].id == who then
            return trade.seats[1], trade.seats[2]
        elseif trade.seats[2].id == who then
            return trade.seats[2], trade.seats[1]
        end
        return nil, nil
    end

    local function occupied(who)
        for _, trade in ipairs(ledger) do
            if live(trade) and seat(trade, who) ~= nil then
                return true
            end
        end
        return false
    end

    local function sweep(now)
        local gone = {}
        for _, trade in ipairs(ledger) do
            if trade.phase == OPEN and not (now < trade.deadline) then
                trade.phase = EXPIRED
                gone[#gone + 1] = trade.id
            end
        end
        table.sort(gone)
        return gone
    end

    local function answer(ok, code, trade)
        return { ok = ok, code = code, phase = trade ~= nil and trade.phase or nil }
    end

    -- Steps 2-5 of the fixed order. Returns the trade plus the caller's and the
    -- other seat, or nil and the rejection.
    local function enter(gate, trade_id, who, now)
        sweep(now)
        local trade = ledger[by_id[trade_id] or 0]
        if trade == nil then
            return nil, answer(false, "unknown_trade")
        end
        local mine, theirs
        if who ~= nil then
            mine, theirs = seat(trade, who)
            if mine == nil then
                return nil, answer(false, "not_a_party", trade)
            end
        end
        local verdict = GATE[gate][trade.phase]
        if verdict ~= true then
            return nil, answer(false, verdict, trade)
        end
        return trade, mine, theirs
    end

    local function plan_of(trade)
        local first, second = trade.seats[1], trade.seats[2]
        if second.id < first.id then
            first, second = second, first
        end
        local rows = {}
        for _, pair in ipairs({ { first, second }, { second, first } }) do
            for _, row in ipairs(pair[1].offer) do
                rows[#rows + 1] = { from = pair[1].id, to = pair[2].id, prefab = row.prefab, count = row.count }
            end
        end
        return rows
    end

    local api = {}

    function api.open(_, trade_id, a_id, b_id, now)
        if not (text(trade_id) and text(a_id) and text(b_id) and number(now)) or a_id == b_id then
            return answer(false, "invalid_argument")
        end
        sweep(now)
        local known = ledger[by_id[trade_id] or 0]
        if known ~= nil then
            if not live(known) then
                return answer(false, "trade_closed", known)
            end
            if seat(known, a_id) == nil or seat(known, b_id) == nil then
                return answer(false, "trade_exists", known)
            end
            local again = answer(true, "opened", known)
            again.trade_id, again.expires_at = known.id, known.deadline
            return again
        end
        if occupied(a_id) or occupied(b_id) then
            return answer(false, "party_busy")
        end
        local trade = {
            id = trade_id, phase = OPEN, born = now, deadline = now + ttl,
            seats = {
                { id = a_id, rev = 0, agreed = false, offer = {} },
                { id = b_id, rev = 0, agreed = false, offer = {} },
            },
        }
        ledger[#ledger + 1] = trade
        by_id[trade_id] = #ledger
        local out = answer(true, "opened", trade)
        out.trade_id, out.expires_at = trade_id, trade.deadline
        return out
    end

    function api.offer(_, trade_id, party_id, items, revision, now)
        if not (text(trade_id) and text(party_id) and number(now) and whole(revision, 1))
            or type(items) ~= "table" then
            return answer(false, "invalid_argument")
        end
        local trade, mine, theirs = enter("offer", trade_id, party_id, now)
        if trade == nil then
            return mine
        end
        if revision <= mine.rev then
            if revision == mine.rev and matches(mine.offer, items) then
                local replay = answer(true, "offered", trade)
                replay.revision = mine.rev
                return replay
            end
            return answer(false, revision == mine.rev and "revision_conflict" or "stale_revision", trade)
        end
        local rows, problem = normalise(items, allowed, cap)
        if rows == nil then
            return answer(false, problem, trade)
        end
        mine.offer, mine.rev = rows, revision
        mine.agreed, theirs.agreed = false, false
        local out = answer(true, "offered", trade)
        out.revision = revision
        return out
    end

    function api.confirm(_, trade_id, party_id, seen_revision, now)
        if not (text(trade_id) and text(party_id) and number(now) and whole(seen_revision, 0)) then
            return answer(false, "invalid_argument")
        end
        local trade, mine, theirs = enter("confirm", trade_id, party_id, now)
        if trade == nil then
            return mine
        end
        if theirs.rev ~= seen_revision then
            return answer(false, "stale_confirmation", trade)
        end
        mine.agreed = true
        local out = answer(true, "confirmed", trade)
        out.ready = theirs.agreed == true
        return out
    end

    function api.cancel(_, trade_id, party_id, now)
        if not (text(trade_id) and text(party_id) and number(now)) then
            return answer(false, "invalid_argument")
        end
        local trade, mine = enter("cancel", trade_id, party_id, now)
        if trade == nil then
            return mine
        end
        trade.phase = CANCELED
        return answer(true, "canceled", trade)
    end

    function api.begin_settle(_, trade_id, now)
        if not (text(trade_id) and number(now)) then
            return answer(false, "invalid_argument")
        end
        local trade, rejection = enter("begin_settle", trade_id, nil, now)
        if trade == nil then
            return rejection
        end
        if trade.phase == OPEN then
            if not (trade.seats[1].agreed and trade.seats[2].agreed) then
                return answer(false, "not_ready", trade)
            end
            trade.phase = SETTLING
        end
        local out = answer(true, "settling", trade)
        out.plan = plan_of(trade)
        return out
    end

    function api.finish_settle(_, trade_id, ok, now)
        if not (text(trade_id) and number(now)) or type(ok) ~= "boolean" then
            return answer(false, "invalid_argument")
        end
        local trade, rejection = enter(ok and "finish_ok" or "finish_fail", trade_id, nil, now)
        if trade == nil then
            return rejection
        end
        if ok then
            trade.phase = SETTLED
            return answer(true, "settled", trade)
        end
        trade.phase = OPEN
        trade.seats[1].agreed, trade.seats[2].agreed = false, false
        return answer(true, "reopened", trade)
    end

    function api.tick(_, now)
        if not number(now) then
            return answer(false, "invalid_argument")
        end
        local out = answer(true, "ticked")
        out.expired = sweep(now)
        return out
    end

    function api.snapshot(_, now)
        if number(now) then
            sweep(now)
        end
        local views = {}
        for index, trade in ipairs(ledger) do
            local low, high = trade.seats[1], trade.seats[2]
            if high.id < low.id then
                low, high = high, low
            end
            local parties = {}
            for slot, side in ipairs({ low, high }) do
                parties[slot] = { id = side.id, revision = side.rev, confirmed = side.agreed, items = clone_rows(side.offer) }
            end
            views[index] = { trade_id = trade.id, phase = trade.phase, opened_at = trade.born,
                expires_at = trade.deadline, parties = parties }
        end
        table.sort(views, function(left, right) return left.trade_id < right.trade_id end)
        return { trades = views }
    end

    -- Flat rows in creation order; seat order is preserved as written.
    function api.save(_, now)
        if number(now) then
            sweep(now)
        end
        local rows = {}
        for index, trade in ipairs(ledger) do
            local row = { id = trade.id, phase = trade.phase, born = trade.born, deadline = trade.deadline }
            for slot, side in ipairs(trade.seats) do
                row["p" .. slot] = side.id
                row["r" .. slot] = side.rev
                row["c" .. slot] = side.agreed
                row["o" .. slot] = clone_rows(side.offer)
            end
            rows[index] = row
        end
        return { format = "escrow-ledger", rows = rows }
    end

    if type(seed) == "table" and type(seed.rows) == "table" then
        for _, row in ipairs(seed.rows) do
            if type(row) == "table" and text(row.id) and by_id[row.id] == nil and GATE.offer[row.phase] ~= nil
                and number(row.born) and number(row.deadline) and text(row.p1) and text(row.p2) and row.p1 ~= row.p2 then
                local seats = {}
                for slot = 1, 2 do
                    local offer = {}
                    for _, entry in ipairs(type(row["o" .. slot]) == "table" and row["o" .. slot] or {}) do
                        if type(entry) == "table" and text(entry.prefab) and whole(entry.count, 1) then
                            offer[#offer + 1] = { prefab = entry.prefab, count = entry.count }
                        end
                    end
                    table.sort(offer, function(left, right) return left.prefab < right.prefab end)
                    seats[slot] = {
                        id = row["p" .. slot],
                        rev = whole(row["r" .. slot], 0) and row["r" .. slot] or 0,
                        agreed = row["c" .. slot] == true,
                        offer = offer,
                    }
                end
                ledger[#ledger + 1] = { id = row.id, phase = row.phase, born = row.born, deadline = row.deadline, seats = seats }
                by_id[row.id] = #ledger
            end
        end
    end

    return api
end

function M.new(options)
    return build(options, nil)
end

function M.load(data, options)
    return build(options, data)
end

return M
