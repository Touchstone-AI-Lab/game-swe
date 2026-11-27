-- Pure loot-roll arbiter. No engine globals: every time value arrives through
-- a `now` argument, and all state is plain tables of strings, numbers and
-- booleans so the world component can persist it unchanged.

local Arbiter = {}
Arbiter.__index = Arbiter

local MODULUS = 2147483647
local MULTIPLIER = 48271
local SEED_RANGE = 2147483646
local MAX_SEED = 4294967295

local CHOICES = { need = true, greed = true, pass = true }

local DEFAULTS = {
    window = 30,
    max_wins_per_window = 2,
    fairness_window = 600,
    max_rounds = 3,
}

local function is_finite(value)
    return type(value) == "number" and value == value
        and value ~= math.huge and value ~= -math.huge
end

local function is_whole(value)
    return is_finite(value) and value == math.floor(value)
end

local function is_id(value)
    return type(value) == "string" and value ~= ""
end

local function fail(code)
    return { ok = false, code = code }
end

local function copy_array(source)
    local target = {}
    for index = 1, #source do
        target[index] = source[index]
    end
    return target
end

local function normalise_options(options)
    options = type(options) == "table" and options or {}
    local config = { allowed = {} }
    if is_finite(options.window) and options.window > 0 then
        config.window = options.window
    else
        config.window = DEFAULTS.window
    end
    if is_finite(options.fairness_window) and options.fairness_window > 0 then
        config.fairness_window = options.fairness_window
    else
        config.fairness_window = DEFAULTS.fairness_window
    end
    if is_whole(options.max_wins_per_window) and options.max_wins_per_window >= 1 then
        config.max_wins = options.max_wins_per_window
    else
        config.max_wins = DEFAULTS.max_wins_per_window
    end
    if is_whole(options.max_rounds) and options.max_rounds >= 1 then
        config.max_rounds = options.max_rounds
    else
        config.max_rounds = DEFAULTS.max_rounds
    end
    if type(options.allowed_items) == "table" then
        for index = 1, #options.allowed_items do
            local item = options.allowed_items[index]
            if is_id(item) then
                config.allowed[item] = true
            end
        end
    end
    return config
end

function Arbiter.new(options)
    local self = setmetatable({}, Arbiter)
    self.config = normalise_options(options)
    self.rolls = {}
    self.ledger = {}
    return self
end

-- Generator -----------------------------------------------------------------

-- Park-Miller MINSTD. state * 48271 stays below 2^53, so the product and the
-- remainder are exact in Lua 5.1 doubles as well as in newer integer builds.
local function draw(roll)
    roll.state = (roll.state * MULTIPLIER) % MODULUS
    return roll.state % 100 + 1
end

local function ranks_before(sequences, left, right, max_rounds)
    local a, b = sequences[left], sequences[right]
    for round = 1, max_rounds do
        local x, y = a[round] or -1, b[round] or -1
        if x ~= y then
            return x > y
        end
    end
    return left < right
end

-- Runs one contest among `members` (ascending ids) and returns them ranked.
local function run_contest(roll, tier, members, max_rounds)
    local sequences = {}
    for index = 1, #members do
        sequences[members[index]] = {}
    end
    local tied = members
    local round = 0
    repeat
        round = round + 1
        local top = 0
        for index = 1, #tied do
            local player_id = tied[index]
            local value = draw(roll)
            sequences[player_id][round] = value
            roll.rolls[#roll.rolls + 1] = {
                tier = tier, round = round, player_id = player_id, roll = value,
            }
            if value > top then
                top = value
            end
        end
        local still_tied = {}
        for index = 1, #tied do
            if sequences[tied[index]][round] == top then
                still_tied[#still_tied + 1] = tied[index]
            end
        end
        tied = still_tied
    until #tied <= 1 or round >= max_rounds
    local ranking = copy_array(members)
    table.sort(ranking, function(left, right)
        return ranks_before(sequences, left, right, max_rounds)
    end)
    return ranking
end

-- Fairness ledger -----------------------------------------------------------

function Arbiter:_recent_wins(player_id, at)
    local times = self.ledger[player_id]
    local count = 0
    if times ~= nil then
        for index = 1, #times do
            if at - times[index] < self.config.fairness_window then
                count = count + 1
            end
        end
    end
    return count
end

-- Entries may only be dropped once no open roll can still look back at them.
function Arbiter:_prune_ledger(now)
    local horizon = now
    for _, roll in pairs(self.rolls) do
        if roll.status == "open" and roll.deadline < horizon then
            horizon = roll.deadline
        end
    end
    for player_id, times in pairs(self.ledger) do
        local kept = {}
        for index = 1, #times do
            if horizon - times[index] < self.config.fairness_window then
                kept[#kept + 1] = times[index]
            end
        end
        self.ledger[player_id] = kept
    end
    for player_id, times in pairs(self.ledger) do
        if #times == 0 then
            self.ledger[player_id] = nil
        end
    end
end

-- Results -------------------------------------------------------------------

local function build_result(roll)
    local result = {
        ok = true,
        roll_id = roll.id,
        item = roll.item,
        status = roll.status,
        winner = roll.winner,
        tier = roll.winner ~= nil and roll.tier or nil,
        rolls = {},
        demoted = copy_array(roll.demoted),
        failed = copy_array(roll.failed),
        choices = {},
    }
    for index = 1, #roll.rolls do
        local entry = roll.rolls[index]
        result.rolls[index] = {
            tier = entry.tier, round = entry.round,
            player_id = entry.player_id, roll = entry.roll,
        }
    end
    if roll.status ~= "canceled" then
        for index = 1, #roll.eligible do
            local player_id = roll.eligible[index]
            result.choices[index] = {
                player_id = player_id,
                choice = roll.choices[player_id] or "pass",
            }
        end
    end
    return result
end

-- Moves to the next candidate: the rest of the current ranking first, then a
-- fresh contest for the greed tier, and finally nobody.
local function advance(self, roll)
    roll.position = roll.position + 1
    if roll.ranking[roll.position] == nil and roll.tier == "need" and #roll.greed > 0 then
        roll.tier = "greed"
        roll.ranking = run_contest(roll, "greed", roll.greed, self.config.max_rounds)
        roll.position = 1
    end
    local winner = roll.ranking[roll.position]
    if winner ~= nil then
        roll.winner = winner
        roll.status = "awarded"
    else
        roll.winner = nil
        roll.status = "unclaimed"
    end
end

local function settle(self, roll, now)
    local at = math.min(now, roll.deadline)
    local need, greed = {}, {}
    for index = 1, #roll.eligible do
        local player_id = roll.eligible[index]
        local choice = roll.choices[player_id]
        if choice == "need" and self:_recent_wins(player_id, at) >= self.config.max_wins then
            roll.demoted[#roll.demoted + 1] = player_id
            choice = "greed"
        end
        if choice == "need" then
            need[#need + 1] = player_id
        elseif choice == "greed" then
            greed[#greed + 1] = player_id
        end
    end
    roll.greed = greed
    roll.position = 0
    if #need > 0 then
        roll.tier = "need"
        roll.ranking = run_contest(roll, "need", need, self.config.max_rounds)
    else
        -- An empty need tier falls straight through to the greed contest.
        roll.tier = "need"
        roll.ranking = {}
    end
    advance(self, roll)
end

local function is_ready(roll, now)
    return roll.chosen >= #roll.eligible or now >= roll.deadline
end

-- Public API ----------------------------------------------------------------

function Arbiter:open(roll_id, item, eligible_ids, seed, now)
    if not is_finite(now) or not is_finite(now + self.config.window) then
        return fail("invalid_time")
    end
    if not is_id(roll_id) then
        return fail("invalid_roll_id")
    end
    if self.rolls[roll_id] ~= nil then
        return fail("duplicate_roll")
    end
    if not is_id(item) or not self.config.allowed[item] then
        return fail("item_not_allowed")
    end
    if type(eligible_ids) ~= "table" then
        return fail("invalid_eligible")
    end
    local eligible, seen = {}, {}
    for index = 1, #eligible_ids do
        local player_id = eligible_ids[index]
        if not is_id(player_id) then
            return fail("invalid_eligible")
        end
        if not seen[player_id] then
            seen[player_id] = true
            eligible[#eligible + 1] = player_id
        end
    end
    if #eligible < 1 then
        return fail("invalid_eligible")
    end
    if not is_whole(seed) or seed < 0 or seed > MAX_SEED then
        return fail("invalid_seed")
    end
    table.sort(eligible)
    self.rolls[roll_id] = {
        id = roll_id,
        item = item,
        status = "open",
        deadline = now + self.config.window,
        eligible = eligible,
        choices = {},
        revisions = {},
        chosen = 0,
        state = seed % SEED_RANGE + 1,
        rolls = {},
        demoted = {},
        failed = {},
        greed = {},
        ranking = {},
        position = 0,
    }
    return {
        ok = true,
        roll_id = roll_id,
        item = item,
        deadline = now + self.config.window,
        total = #eligible,
        eligible = copy_array(eligible),
    }
end

local function is_member(roll, player_id)
    for index = 1, #roll.eligible do
        if roll.eligible[index] == player_id then
            return true
        end
    end
    return false
end

function Arbiter:choose(roll_id, player_id, choice, revision, now)
    if not is_finite(now) then
        return fail("invalid_time")
    end
    local roll = self.rolls[roll_id]
    if roll == nil then
        return fail("unknown_roll")
    end
    if roll.status ~= "open" or now >= roll.deadline then
        return fail("roll_closed")
    end
    if not is_id(player_id) or not is_member(roll, player_id) then
        return fail("not_eligible")
    end
    if type(choice) ~= "string" or not CHOICES[choice] then
        return fail("invalid_choice")
    end
    if not is_whole(revision) or revision < 0 then
        return fail("invalid_revision")
    end
    local previous = roll.revisions[player_id]
    if previous ~= nil and revision <= previous then
        return fail("stale_revision")
    end
    if previous == nil then
        roll.chosen = roll.chosen + 1
    end
    roll.revisions[player_id] = revision
    roll.choices[player_id] = choice
    return {
        ok = true,
        roll_id = roll_id,
        player_id = player_id,
        revision = revision,
        chosen = roll.chosen,
        total = #roll.eligible,
        complete = roll.chosen >= #roll.eligible,
    }
end

function Arbiter:resolve(roll_id, now)
    if not is_finite(now) then
        return fail("invalid_time")
    end
    local roll = self.rolls[roll_id]
    if roll == nil then
        return fail("unknown_roll")
    end
    if roll.status == "open" then
        if not is_ready(roll, now) then
            return fail("not_ready")
        end
        settle(self, roll, now)
    end
    return build_result(roll)
end

function Arbiter:mark_delivered(roll_id, ok, now)
    if not is_finite(now) then
        return fail("invalid_time")
    end
    local roll = self.rolls[roll_id]
    if roll == nil then
        return fail("unknown_roll")
    end
    if roll.status ~= "awarded" then
        return fail("not_awarded")
    end
    if ok == true then
        roll.status = "delivered"
        local times = self.ledger[roll.winner]
        if times == nil then
            times = {}
            self.ledger[roll.winner] = times
        end
        times[#times + 1] = now
    else
        roll.failed[#roll.failed + 1] = roll.winner
        advance(self, roll)
    end
    return build_result(roll)
end

function Arbiter:cancel(roll_id, now)
    if not is_finite(now) then
        return fail("invalid_time")
    end
    local roll = self.rolls[roll_id]
    if roll == nil then
        return fail("unknown_roll")
    end
    if roll.status ~= "open" then
        return fail("roll_closed")
    end
    roll.status = "canceled"
    roll.winner = nil
    return build_result(roll)
end

local function sorted_roll_ids(rolls)
    local ids = {}
    for roll_id in pairs(rolls) do
        ids[#ids + 1] = roll_id
    end
    table.sort(ids)
    return ids
end

function Arbiter:tick(now)
    if not is_finite(now) then
        return fail("invalid_time")
    end
    local resolved = {}
    local ids = sorted_roll_ids(self.rolls)
    for index = 1, #ids do
        local roll = self.rolls[ids[index]]
        if roll.status == "open" and is_ready(roll, now) then
            settle(self, roll, now)
            resolved[#resolved + 1] = build_result(roll)
        end
    end
    self:_prune_ledger(now)
    return { ok = true, resolved = resolved }
end

function Arbiter:snapshot(now)
    if not is_finite(now) then
        return fail("invalid_time")
    end
    local entries = {}
    local ids = sorted_roll_ids(self.rolls)
    for index = 1, #ids do
        local roll = self.rolls[ids[index]]
        local open = roll.status == "open"
        entries[index] = {
            roll_id = roll.id,
            item = roll.item,
            status = roll.status,
            deadline = roll.deadline,
            remaining = open and math.max(0, roll.deadline - now) or 0,
            total = #roll.eligible,
            chosen = roll.chosen,
            winner = roll.winner,
            tier = roll.winner ~= nil and roll.tier or nil,
        }
    end
    local players = {}
    for player_id in pairs(self.ledger) do
        players[#players + 1] = player_id
    end
    table.sort(players)
    local wins = {}
    for index = 1, #players do
        local count = self:_recent_wins(players[index], now)
        if count > 0 then
            wins[#wins + 1] = { player_id = players[index], count = count }
        end
    end
    return { ok = true, rolls = entries, wins = wins }
end

-- Persistence ---------------------------------------------------------------

local function copy_map(source)
    local target = {}
    for key, value in pairs(source) do
        target[key] = value
    end
    return target
end

function Arbiter:save(now)
    if not is_finite(now) then
        return fail("invalid_time")
    end
    local rolls = {}
    local ids = sorted_roll_ids(self.rolls)
    for index = 1, #ids do
        local roll = self.rolls[ids[index]]
        local drawn = {}
        for position = 1, #roll.rolls do
            local entry = roll.rolls[position]
            drawn[position] = {
                tier = entry.tier, round = entry.round,
                player_id = entry.player_id, roll = entry.roll,
            }
        end
        rolls[index] = {
            id = roll.id,
            item = roll.item,
            status = roll.status,
            deadline = roll.deadline,
            eligible = copy_array(roll.eligible),
            choices = copy_map(roll.choices),
            revisions = copy_map(roll.revisions),
            chosen = roll.chosen,
            state = roll.state,
            rolls = drawn,
            demoted = copy_array(roll.demoted),
            failed = copy_array(roll.failed),
            greed = copy_array(roll.greed),
            ranking = copy_array(roll.ranking),
            position = roll.position,
            tier = roll.tier,
            winner = roll.winner,
        }
    end
    local ledger = {}
    for player_id, times in pairs(self.ledger) do
        ledger[player_id] = copy_array(times)
    end
    return { version = 1, saved_at = now, rolls = rolls, ledger = ledger }
end

local function load_roll(record, shift)
    if type(record) ~= "table" or not is_id(record.id) or not is_finite(record.deadline) then
        return nil
    end
    local function array(value)
        return type(value) == "table" and copy_array(value) or {}
    end
    local drawn = {}
    if type(record.rolls) == "table" then
        for index = 1, #record.rolls do
            local entry = record.rolls[index]
            drawn[index] = {
                tier = entry.tier, round = entry.round,
                player_id = entry.player_id, roll = entry.roll,
            }
        end
    end
    return {
        id = record.id,
        item = record.item,
        status = record.status,
        deadline = record.deadline + shift,
        eligible = array(record.eligible),
        choices = type(record.choices) == "table" and copy_map(record.choices) or {},
        revisions = type(record.revisions) == "table" and copy_map(record.revisions) or {},
        chosen = record.chosen or 0,
        state = record.state,
        rolls = drawn,
        demoted = array(record.demoted),
        failed = array(record.failed),
        greed = array(record.greed),
        ranking = array(record.ranking),
        position = record.position or 0,
        tier = record.tier,
        winner = record.winner,
    }
end

function Arbiter.load(data, options)
    local self = Arbiter.new(options)
    if type(data) ~= "table" or type(data.rolls) ~= "table" then
        return self
    end
    -- The engine clock restarts with the process; when the caller supplies the
    -- new clock every stored absolute time keeps its distance from `saved_at`.
    local shift = 0
    if type(options) == "table" and is_finite(options.now) and is_finite(data.saved_at) then
        shift = options.now - data.saved_at
    end
    for index = 1, #data.rolls do
        local roll = load_roll(data.rolls[index], shift)
        if roll ~= nil then
            self.rolls[roll.id] = roll
        end
    end
    if type(data.ledger) == "table" then
        for player_id, times in pairs(data.ledger) do
            if is_id(player_id) and type(times) == "table" then
                local kept = {}
                for position = 1, #times do
                    if is_finite(times[position]) then
                        kept[#kept + 1] = times[position] + shift
                    end
                end
                self.ledger[player_id] = kept
            end
        end
    end
    return self
end

return Arbiter
