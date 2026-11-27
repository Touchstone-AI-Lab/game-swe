-- Server-authoritative loot roll arbiter: pure Lua core.
--
-- This chunk is independent from Don't Starve Together. It reads no game
-- global, loads no other module and takes every timestamp from the `now`
-- argument supplied by the caller. It is valid Lua 5.1 and Lua 5.4.
--
-- Each arbiter is a closure based object: a plain table of functions that
-- share local state. Methods are meant to be called with colon syntax, so
-- every method receives (and ignores) the object as its first argument.

local Arbiter = {}

local SAVE_FORMAT = "lootroll.arbiter.save"
local SAVE_VERSION = 1

local RNG_MULTIPLIER = 48271
local RNG_MODULUS = 2147483647
local SEED_LIMIT = 4294967295

local CHOICES = { need = true, greed = true, pass = true }
local STATUSES = {
    open = true,
    awarded = true,
    delivered = true,
    unclaimed = true,
    canceled = true,
}

---------------------------------------------------------------------------
-- Small value helpers
---------------------------------------------------------------------------

local function is_finite(value)
    return type(value) == "number"
        and value == value
        and value ~= math.huge
        and value ~= -math.huge
end

local function is_whole(value)
    return is_finite(value) and value == math.floor(value)
end

local function is_id(value)
    return type(value) == "string" and value ~= ""
end

local function failure(code)
    return { ok = false, code = code }
end

local function copy_array(source)
    local out = {}
    for i = 1, #source do
        out[i] = source[i]
    end
    return out
end

-- Inserts a string into an ascending array, keeping it ascending.
local function insert_sorted(list, value)
    local pos = #list + 1
    while pos > 1 and value < list[pos - 1] do
        list[pos] = list[pos - 1]
        pos = pos - 1
    end
    list[pos] = value
end

-- True when draw sequence `a` ranks strictly above draw sequence `b`.
-- Sequences are compared round by round, a higher roll ranks first and a
-- player that did not take part in a round ranks below any rolled value.
local function outranks(a, b)
    local index = 1
    while true do
        local av, bv = a[index], b[index]
        if av == nil then
            return false
        end
        if bv == nil then
            return true
        end
        if av ~= bv then
            return av > bv
        end
        index = index + 1
    end
end

---------------------------------------------------------------------------
-- Configuration
---------------------------------------------------------------------------

local function read_config(options)
    if type(options) ~= "table" then
        options = {}
    end
    local cfg = {
        window = 30,
        max_wins = 2,
        fairness_window = 600,
        max_rounds = 3,
        allowed = {},
    }
    if is_finite(options.window) then
        cfg.window = options.window
    end
    if is_finite(options.max_wins_per_window) then
        cfg.max_wins = options.max_wins_per_window
    end
    if is_finite(options.fairness_window) then
        cfg.fairness_window = options.fairness_window
    end
    if is_finite(options.max_rounds) then
        cfg.max_rounds = options.max_rounds
    end
    local items = options.allowed_items
    if type(items) == "table" then
        for i = 1, #items do
            if type(items[i]) == "string" then
                cfg.allowed[items[i]] = true
            end
        end
    end
    return cfg
end

---------------------------------------------------------------------------
-- Save data decoding
---------------------------------------------------------------------------

local function decode_string_array(source)
    if type(source) ~= "table" then
        return nil
    end
    local out = {}
    for i = 1, #source do
        if not is_id(source[i]) then
            return nil
        end
        out[i] = source[i]
    end
    return out
end

local function decode_player(source)
    if type(source) ~= "table" or not is_id(source.player_id) then
        return nil
    end
    local record = { failed = source.failed == true, draws = {} }
    if source.choice ~= nil then
        if CHOICES[source.choice] ~= true or not is_whole(source.revision) then
            return nil
        end
        record.choice = source.choice
        record.revision = source.revision
    end
    if source.tier ~= nil then
        if CHOICES[source.tier] ~= true then
            return nil
        end
        record.tier = source.tier
    end
    if type(source.draws) ~= "table" then
        return nil
    end
    for i = 1, #source.draws do
        if not is_whole(source.draws[i]) then
            return nil
        end
        record.draws[i] = math.floor(source.draws[i])
    end
    return record
end

local function decode_roll(source, shift)
    if type(source) ~= "table"
        or not is_id(source.roll_id)
        or type(source.item) ~= "string"
        or STATUSES[source.status] ~= true
        or not is_finite(source.deadline)
        or not is_whole(source.rng)
        or type(source.players) ~= "table"
        or type(source.log) ~= "table" then
        return nil
    end
    local roll = {
        id = source.roll_id,
        item = source.item,
        status = source.status,
        deadline = source.deadline + shift,
        rng = math.floor(source.rng),
        total = 0,
        chosen = 0,
        eligible = {},
        players = {},
        log = {},
    }
    for i = 1, #source.players do
        local record = decode_player(source.players[i])
        local pid = record ~= nil and source.players[i].player_id or nil
        if pid == nil or roll.players[pid] ~= nil then
            return nil
        end
        roll.players[pid] = record
        insert_sorted(roll.eligible, pid)
        roll.total = roll.total + 1
        if record.choice ~= nil then
            roll.chosen = roll.chosen + 1
        end
    end
    if roll.total < 1 then
        return nil
    end
    for i = 1, #source.log do
        local entry = source.log[i]
        if type(entry) ~= "table"
            or (entry.tier ~= "need" and entry.tier ~= "greed")
            or not is_whole(entry.round)
            or not is_whole(entry.roll)
            or roll.players[entry.player_id] == nil then
            return nil
        end
        roll.log[i] = {
            tier = entry.tier,
            round = math.floor(entry.round),
            player_id = entry.player_id,
            roll = math.floor(entry.roll),
        }
    end
    roll.demoted = decode_string_array(source.demoted)
    roll.failed = decode_string_array(source.failed)
    if roll.demoted == nil or roll.failed == nil then
        return nil
    end
    if roll.status == "awarded" or roll.status == "delivered" then
        if roll.players[source.winner] == nil
            or (source.tier ~= "need" and source.tier ~= "greed") then
            return nil
        end
        roll.winner = source.winner
        roll.tier = source.tier
    end
    return roll
end

-- Returns { rolls = <array of roll records>, ledger = <array> } or nil when
-- `data` is not a table produced by save().
local function decode_save(data, target_now)
    if type(data) ~= "table"
        or data.format ~= SAVE_FORMAT
        or data.version ~= SAVE_VERSION
        or type(data.rolls) ~= "table"
        or type(data.ledger) ~= "table" then
        return nil
    end
    local shift = 0
    if is_finite(target_now) and is_finite(data.saved_at) then
        shift = target_now - data.saved_at
    end
    local restored = { rolls = {}, ledger = {} }
    local seen = {}
    for i = 1, #data.rolls do
        local roll = decode_roll(data.rolls[i], shift)
        if roll == nil or seen[roll.id] then
            return nil
        end
        seen[roll.id] = true
        restored.rolls[i] = roll
    end
    for i = 1, #data.ledger do
        local entry = data.ledger[i]
        if type(entry) ~= "table"
            or not is_id(entry.player_id)
            or not is_finite(entry.time) then
            return nil
        end
        restored.ledger[i] = { player_id = entry.player_id, time = entry.time + shift }
    end
    return restored
end

---------------------------------------------------------------------------
-- Arbiter construction
---------------------------------------------------------------------------

local function build(cfg, restored)
    local rolls = {}     -- roll id -> roll record (every id ever opened)
    local order = {}     -- every known roll id, ascending
    local ledger = {}    -- flat array of { player_id = , time = } win records

    -- The ledger is never pruned: an old record can still matter to a roll
    -- whose deadline lies in the past but which has not been resolved yet.

    if restored ~= nil then
        for i = 1, #restored.rolls do
            local roll = restored.rolls[i]
            rolls[roll.id] = roll
            insert_sorted(order, roll.id)
        end
        ledger = restored.ledger
    end

    local function find_roll(roll_id)
        if type(roll_id) ~= "string" then
            return nil
        end
        return rolls[roll_id]
    end

    -- Number of ledger wins of `player_id` still inside the fairness window
    -- when observed from time `at`.
    local function recent_wins(player_id, at)
        local count = 0
        for i = 1, #ledger do
            local entry = ledger[i]
            if entry.player_id == player_id and at - entry.time < cfg.fairness_window then
                count = count + 1
            end
        end
        return count
    end

    local function draw(roll)
        roll.rng = (roll.rng * RNG_MULTIPLIER) % RNG_MODULUS
        return roll.rng % 100 + 1
    end

    -- Runs one contest for every player whose effective tier is `tier`,
    -- appending each draw to the player's own sequence and to the roll log.
    local function run_contest(roll, tier)
        local field = {}
        for i = 1, roll.total do
            local pid = roll.eligible[i]
            if roll.players[pid].tier == tier then
                field[#field + 1] = pid
            end
        end
        local round = 1
        while #field > 0 do
            local top = 0
            local tied = {}
            for i = 1, #field do
                local pid = field[i]
                local value = draw(roll)
                local draws = roll.players[pid].draws
                draws[#draws + 1] = value
                roll.log[#roll.log + 1] = {
                    tier = tier,
                    round = round,
                    player_id = pid,
                    roll = value,
                }
                if value > top then
                    top = value
                    tied = { pid }
                elseif value == top then
                    tied[#tied + 1] = pid
                end
            end
            if #tied > 1 and round < cfg.max_rounds then
                field = tied
                round = round + 1
            else
                field = {}
            end
        end
    end

    -- Best candidate of `tier` that has not failed a delivery, selected on
    -- demand from the stored draw sequences. Scanning ids in ascending order
    -- and replacing only on a strictly better sequence gives equal sequences
    -- to the smaller id.
    local function best_candidate(roll, tier)
        local best_id, best_draws = nil, nil
        for i = 1, roll.total do
            local pid = roll.eligible[i]
            local record = roll.players[pid]
            if record.tier == tier and not record.failed then
                if best_id == nil or outranks(record.draws, best_draws) then
                    best_id, best_draws = pid, record.draws
                end
            end
        end
        return best_id
    end

    local function tier_has_members(roll, tier)
        for i = 1, roll.total do
            if roll.players[roll.eligible[i]].tier == tier then
                return true
            end
        end
        return false
    end

    local function set_unclaimed(roll)
        roll.status = "unclaimed"
        roll.winner = nil
        roll.tier = nil
    end

    -- Closes an open roll: fixes effective tiers (with fairness demotion),
    -- runs the first contest and names the first winner.
    local function settle(roll, now)
        local at = math.min(now, roll.deadline)
        for i = 1, roll.total do
            local pid = roll.eligible[i]
            local record = roll.players[pid]
            local tier = record.choice or "pass"
            if tier == "need" and recent_wins(pid, at) >= cfg.max_wins then
                tier = "greed"
                roll.demoted[#roll.demoted + 1] = pid
            end
            record.tier = tier
        end
        local tier = nil
        if tier_has_members(roll, "need") then
            tier = "need"
        elseif tier_has_members(roll, "greed") then
            tier = "greed"
        end
        if tier == nil then
            set_unclaimed(roll)
            return
        end
        run_contest(roll, tier)
        roll.status = "awarded"
        roll.tier = tier
        roll.winner = best_candidate(roll, tier)
    end

    -- Moves the award exactly one place down after a failed delivery.
    local function advance_winner(roll)
        local record = roll.players[roll.winner]
        record.failed = true
        roll.failed[#roll.failed + 1] = roll.winner
        local successor = best_candidate(roll, roll.tier)
        if successor == nil and roll.tier == "need" and tier_has_members(roll, "greed") then
            roll.tier = "greed"
            run_contest(roll, "greed")
            successor = best_candidate(roll, "greed")
        end
        if successor == nil then
            set_unclaimed(roll)
        else
            roll.winner = successor
        end
    end

    local function is_due(roll, now)
        return roll.status == "open" and (roll.chosen == roll.total or now >= roll.deadline)
    end

    local function result_of(roll)
        local result = {
            ok = true,
            roll_id = roll.id,
            item = roll.item,
            status = roll.status,
            rolls = {},
            demoted = {},
            failed = {},
            choices = {},
        }
        if roll.status == "canceled" then
            return result
        end
        if roll.status == "awarded" or roll.status == "delivered" then
            result.winner = roll.winner
            result.tier = roll.tier
        end
        for i = 1, #roll.log do
            local entry = roll.log[i]
            result.rolls[i] = {
                tier = entry.tier,
                round = entry.round,
                player_id = entry.player_id,
                roll = entry.roll,
            }
        end
        result.demoted = copy_array(roll.demoted)
        result.failed = copy_array(roll.failed)
        for i = 1, roll.total do
            local pid = roll.eligible[i]
            result.choices[i] = {
                player_id = pid,
                choice = roll.players[pid].choice or "pass",
            }
        end
        return result
    end

    local self = {}

    function self.open(_, roll_id, item, eligible_ids, seed, now)
        if not is_finite(now) or not is_finite(now + cfg.window) then
            return failure("invalid_time")
        end
        if not is_id(roll_id) then
            return failure("invalid_roll_id")
        end
        if rolls[roll_id] ~= nil then
            return failure("duplicate_roll")
        end
        if type(item) ~= "string" or cfg.allowed[item] ~= true then
            return failure("item_not_allowed")
        end
        if type(eligible_ids) ~= "table" then
            return failure("invalid_eligible")
        end
        local players, eligible = {}, {}
        for i = 1, #eligible_ids do
            local pid = eligible_ids[i]
            if not is_id(pid) then
                return failure("invalid_eligible")
            end
            if players[pid] == nil then
                players[pid] = { failed = false, draws = {} }
                eligible[#eligible + 1] = pid
            end
        end
        if #eligible < 1 then
            return failure("invalid_eligible")
        end
        if not is_whole(seed) or seed < 0 or seed > SEED_LIMIT then
            return failure("invalid_seed")
        end
        table.sort(eligible)
        local roll = {
            id = roll_id,
            item = item,
            status = "open",
            deadline = now + cfg.window,
            rng = math.floor(seed) % (RNG_MODULUS - 1) + 1,
            total = #eligible,
            chosen = 0,
            eligible = eligible,
            players = players,
            log = {},
            demoted = {},
            failed = {},
        }
        rolls[roll_id] = roll
        insert_sorted(order, roll_id)
        return {
            ok = true,
            roll_id = roll_id,
            item = item,
            deadline = roll.deadline,
            total = roll.total,
            eligible = copy_array(eligible),
        }
    end

    function self.choose(_, roll_id, player_id, choice, revision, now)
        if not is_finite(now) then
            return failure("invalid_time")
        end
        local roll = find_roll(roll_id)
        if roll == nil then
            return failure("unknown_roll")
        end
        if roll.status ~= "open" or now >= roll.deadline then
            return failure("roll_closed")
        end
        local record = nil
        if type(player_id) == "string" then
            record = roll.players[player_id]
        end
        if record == nil then
            return failure("not_eligible")
        end
        if type(choice) ~= "string" or CHOICES[choice] ~= true then
            return failure("invalid_choice")
        end
        if not is_whole(revision) or revision < 0 then
            return failure("invalid_revision")
        end
        if record.revision ~= nil and revision <= record.revision then
            return failure("stale_revision")
        end
        if record.choice == nil then
            roll.chosen = roll.chosen + 1
        end
        record.choice = choice
        record.revision = revision
        return {
            ok = true,
            roll_id = roll_id,
            player_id = player_id,
            revision = revision,
            chosen = roll.chosen,
            total = roll.total,
            complete = roll.chosen == roll.total,
        }
    end

    function self.resolve(_, roll_id, now)
        if not is_finite(now) then
            return failure("invalid_time")
        end
        local roll = find_roll(roll_id)
        if roll == nil then
            return failure("unknown_roll")
        end
        if roll.status == "open" then
            if not is_due(roll, now) then
                return failure("not_ready")
            end
            settle(roll, now)
        end
        return result_of(roll)
    end

    function self.mark_delivered(_, roll_id, ok, now)
        if not is_finite(now) then
            return failure("invalid_time")
        end
        local roll = find_roll(roll_id)
        if roll == nil then
            return failure("unknown_roll")
        end
        if roll.status ~= "awarded" then
            return failure("not_awarded")
        end
        if ok == true then
            roll.status = "delivered"
            ledger[#ledger + 1] = { player_id = roll.winner, time = now }
        else
            advance_winner(roll)
        end
        return result_of(roll)
    end

    function self.cancel(_, roll_id, now)
        if not is_finite(now) then
            return failure("invalid_time")
        end
        local roll = find_roll(roll_id)
        if roll == nil then
            return failure("unknown_roll")
        end
        if roll.status ~= "open" then
            return failure("roll_closed")
        end
        roll.status = "canceled"
        return result_of(roll)
    end

    function self.tick(_, now)
        if not is_finite(now) then
            return failure("invalid_time")
        end
        local resolved = {}
        for i = 1, #order do
            local roll = rolls[order[i]]
            if is_due(roll, now) then
                settle(roll, now)
                resolved[#resolved + 1] = result_of(roll)
            end
        end
        return { ok = true, resolved = resolved }
    end

    function self.snapshot(_, now)
        if not is_finite(now) then
            return failure("invalid_time")
        end
        local entries = {}
        for i = 1, #order do
            local roll = rolls[order[i]]
            local entry = {
                roll_id = roll.id,
                item = roll.item,
                status = roll.status,
                deadline = roll.deadline,
                remaining = 0,
                total = roll.total,
                chosen = roll.chosen,
            }
            if roll.status == "open" then
                entry.remaining = math.max(0, roll.deadline - now)
            elseif roll.status == "awarded" or roll.status == "delivered" then
                entry.winner = roll.winner
                entry.tier = roll.tier
            end
            entries[i] = entry
        end
        local counts, names = {}, {}
        for i = 1, #ledger do
            local win = ledger[i]
            if now - win.time < cfg.fairness_window then
                if counts[win.player_id] == nil then
                    counts[win.player_id] = 0
                    names[#names + 1] = win.player_id
                end
                counts[win.player_id] = counts[win.player_id] + 1
            end
        end
        table.sort(names)
        local wins = {}
        for i = 1, #names do
            wins[i] = { player_id = names[i], count = counts[names[i]] }
        end
        return { ok = true, rolls = entries, wins = wins }
    end

    function self.save(_, now)
        if not is_finite(now) then
            return failure("invalid_time")
        end
        local data = {
            ok = true,
            format = SAVE_FORMAT,
            version = SAVE_VERSION,
            saved_at = now,
            rolls = {},
            ledger = {},
        }
        for i = 1, #order do
            local roll = rolls[order[i]]
            local stored = {
                roll_id = roll.id,
                item = roll.item,
                status = roll.status,
                deadline = roll.deadline,
                rng = roll.rng,
                winner = roll.winner,
                tier = roll.tier,
                players = {},
                log = {},
                demoted = copy_array(roll.demoted),
                failed = copy_array(roll.failed),
            }
            for j = 1, roll.total do
                local pid = roll.eligible[j]
                local record = roll.players[pid]
                stored.players[j] = {
                    player_id = pid,
                    choice = record.choice,
                    revision = record.revision,
                    tier = record.tier,
                    failed = record.failed,
                    draws = copy_array(record.draws),
                }
            end
            for j = 1, #roll.log do
                local entry = roll.log[j]
                stored.log[j] = {
                    tier = entry.tier,
                    round = entry.round,
                    player_id = entry.player_id,
                    roll = entry.roll,
                }
            end
            data.rolls[i] = stored
        end
        for i = 1, #ledger do
            data.ledger[i] = { player_id = ledger[i].player_id, time = ledger[i].time }
        end
        return data
    end

    return self
end

function Arbiter.new(options)
    return build(read_config(options), nil)
end

function Arbiter.load(data, options)
    local target_now = nil
    if type(options) == "table" then
        target_now = options.now
    end
    return build(read_config(options), decode_save(data, target_now))
end

return Arbiter
