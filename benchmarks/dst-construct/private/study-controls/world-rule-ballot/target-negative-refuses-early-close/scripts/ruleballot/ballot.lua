-- Timed rule ballot, engine independent.
--
-- Design: every ballot object is a closure over private state, so callers can
-- never reach individual votes. A proposal keeps a sorted voter roll with
-- parallel "revision" and "pick" columns and a running tally per option; a
-- vote change moves one unit between two tally cells instead of recounting.
-- Only one proposal is open at a time, which matches the single public state
-- the world replicates. Finished proposals stay in the book forever so their
-- identifiers can never be reused and their outcome can always be replayed.

local Ballot = {}

local FORMAT = 2
local PHASE_OPEN = "open"
local PHASE_PASSED = "passed"
local PHASE_TIE = "tie"
local PHASE_NO_QUORUM = "no_quorum"
local PHASE_CANCELED = "canceled"
local FINAL = {
    [PHASE_PASSED] = true,
    [PHASE_TIE] = true,
    [PHASE_NO_QUORUM] = true,
    [PHASE_CANCELED] = true,
}

local function refuse(reason)
    return { ok = false, reason = reason }
end

local function finite(value)
    return type(value) == "number" and value == value and value < math.huge and value > -math.huge
end

local function whole(value)
    return finite(value) and value >= 0 and value % 1 == 0
end

local function name_ok(value)
    return type(value) == "string" and #value > 0 and #value <= 128 and not value:find("%c")
end

-- Sorted, de-duplicated copy of an array of identifiers. The second value is
-- false when an entry is not an identifier, the third when one repeats.
local function sorted_unique(list)
    local seen, out, clean, distinct = {}, {}, true, true
    for position = 1, #list do
        local value = list[position]
        if not name_ok(value) then
            clean = false
        elseif seen[value] then
            distinct = false
        else
            seen[value] = true
            out[#out + 1] = value
        end
    end
    table.sort(out)
    return out, clean, distinct
end

local function positions(list)
    local map = {}
    for position = 1, #list do
        map[list[position]] = position
    end
    return map
end

local function filled(size, value)
    local out = {}
    for position = 1, size do
        out[position] = value
    end
    return out
end

local function duplicate(list)
    local out = {}
    for position = 1, #list do
        out[position] = list[position]
    end
    return out
end

local function build(options, saved)
    options = type(options) == "table" and options or {}
    local abstain_id = name_ok(options.abstain) and options.abstain or nil

    local book = {}      -- proposal id -> entry
    local sequence = {}  -- proposal ids in opening order
    local live = nil     -- id of the proposal that still accepts votes

    local function aggregates(entry)
        local rows = {}
        for position = 1, #entry.choices do
            rows[position] = { choice_id = entry.choices[position], count = entry.tally[position] }
        end
        return rows
    end

    local function verdict(entry)
        if entry.turnout < entry.quorum then
            return PHASE_NO_QUORUM, nil
        end
        local best, leader, shared = -1, nil, false
        for position = 1, #entry.choices do
            local choice_id = entry.choices[position]
            if choice_id ~= abstain_id then
                local count = entry.tally[position]
                if count > best then
                    best, leader, shared = count, choice_id, false
                elseif count == best then
                    shared = true
                end
            end
        end
        if leader == nil or shared then
            return PHASE_TIE, nil
        end
        return PHASE_PASSED, leader
    end

    local function settle(entry, forced, now)
        if forced ~= nil then
            entry.phase, entry.winner = forced, nil
        else
            entry.phase, entry.winner = verdict(entry)
        end
        -- Votes stop at the deadline, so a late settlement is dated to it.
        entry.settled_at = now < entry.deadline and now or entry.deadline
        if live == entry.id then
            live = nil
        end
    end

    local function outcome(entry)
        return {
            ok = true,
            proposal_id = entry.id,
            status = entry.phase,
            choice_id = entry.winner,
            counts = aggregates(entry),
            participants = entry.turnout,
            electorate_size = #entry.roll,
            quorum = entry.quorum,
            settled_at = entry.settled_at,
        }
    end

    local function describe(entry, now)
        local view = outcome(entry)
        view.ok = nil
        view.deadline = entry.deadline
        view.choices = duplicate(entry.choices)
        if entry.phase == PHASE_OPEN and finite(now) then
            view.remaining = entry.deadline > now and entry.deadline - now or 0
        else
            view.remaining = 0
        end
        return view
    end

    local object = {}

    function object.open(_, proposal, electorate, now)
        if not finite(now) then
            return refuse("bad_time")
        end
        if type(proposal) ~= "table" or not name_ok(proposal.id) then
            return refuse("bad_proposal")
        end
        if book[proposal.id] ~= nil then
            return refuse("identifier_used")
        end
        if live ~= nil then
            return refuse("another_proposal_open")
        end
        if type(proposal.choices) ~= "table" then
            return refuse("bad_choices")
        end
        local choices, choices_clean, choices_distinct = sorted_unique(proposal.choices)
        if not choices_clean or not choices_distinct or #choices < 2 then
            return refuse("bad_choices")
        end
        if not finite(proposal.deadline) or proposal.deadline <= now then
            return refuse("bad_deadline")
        end
        if type(electorate) ~= "table" then
            return refuse("bad_electorate")
        end
        local roll, roll_clean = sorted_unique(electorate)
        if not roll_clean or #roll == 0 then
            return refuse("bad_electorate")
        end
        if not whole(proposal.quorum) or proposal.quorum < 1 or proposal.quorum > #roll then
            return refuse("bad_quorum")
        end

        book[proposal.id] = {
            id = proposal.id,
            choices = choices,
            slot = positions(choices),
            deadline = proposal.deadline,
            quorum = proposal.quorum,
            opened_at = now,
            roll = roll,
            seat = positions(roll),
            rev = filled(#roll, -1),
            pick = filled(#roll, 0),
            tally = filled(#choices, 0),
            turnout = 0,
            phase = PHASE_OPEN,
        }
        sequence[#sequence + 1] = proposal.id
        live = proposal.id
        return {
            ok = true,
            proposal_id = proposal.id,
            status = PHASE_OPEN,
            deadline = proposal.deadline,
            electorate_size = #roll,
            quorum = proposal.quorum,
        }
    end

    function object.cast(_, voter_id, proposal_id, choice_id, revision, now)
        local entry = book[proposal_id]
        if entry == nil then
            return refuse("no_such_proposal")
        end
        if entry.phase ~= PHASE_OPEN then
            return refuse("not_open")
        end
        if not finite(now) or now >= entry.deadline then
            return refuse("after_deadline")
        end
        local seat = entry.seat[voter_id]
        if seat == nil then
            return refuse("not_an_elector")
        end
        local slot = entry.slot[choice_id]
        if slot == nil then
            return refuse("not_a_choice")
        end
        if not whole(revision) then
            return refuse("bad_revision")
        end
        if revision <= entry.rev[seat] then
            return refuse("old_revision")
        end

        local previous = entry.pick[seat]
        if previous == 0 then
            entry.turnout = entry.turnout + 1
        else
            entry.tally[previous] = entry.tally[previous] - 1
        end
        entry.tally[slot] = entry.tally[slot] + 1
        entry.pick[seat] = slot
        entry.rev[seat] = revision
        return { ok = true, proposal_id = proposal_id, revision = revision, participants = entry.turnout }
    end

    function object.close(_, proposal_id, now)
        local entry = book[proposal_id]
        if entry == nil then
            return refuse("no_such_proposal")
        end
        if not FINAL[entry.phase] then
            if not finite(now) then
                return refuse("bad_time")
            end
            -- Electors may vote until the deadline, so a proposal is settled
            -- at or after it; ending it early is what cancel is for.
            if now < entry.deadline then
                return refuse("before_deadline")
            end
            settle(entry, nil, now)
        end
        return outcome(entry)
    end

    function object.cancel(_, proposal_id, now)
        local entry = book[proposal_id]
        if entry == nil then
            return refuse("no_such_proposal")
        end
        if not FINAL[entry.phase] then
            if not finite(now) then
                return refuse("bad_time")
            end
            settle(entry, PHASE_CANCELED, now)
        end
        return outcome(entry)
    end

    -- Public view of the most recent proposal plus a short history of the
    -- earlier ones. Aggregates only: no roll, no picks, no revisions.
    function object.snapshot(_, now)
        local history = {}
        for position = 1, #sequence - 1 do
            local entry = book[sequence[position]]
            history[#history + 1] = { proposal_id = entry.id, status = entry.phase, choice_id = entry.winner }
        end
        local current = book[sequence[#sequence]]
        local view = current ~= nil and describe(current, now) or { status = "idle", counts = {}, remaining = 0 }
        view.time = now
        view.history = history
        return view
    end

    -- The proposal that still needs a settlement timer, if any.
    function object.pending(_)
        local entry = live ~= nil and book[live] or nil
        if entry == nil then
            return nil
        end
        return { proposal_id = entry.id, deadline = entry.deadline }
    end

    function object.status(_, proposal_id)
        local entry = book[proposal_id]
        return entry ~= nil and entry.phase or nil
    end

    function object.save(_, now)
        local rows = {}
        for position = 1, #sequence do
            local entry = book[sequence[position]]
            local ballots = {}
            for seat = 1, #entry.roll do
                if entry.pick[seat] ~= 0 then
                    ballots[#ballots + 1] = {
                        voter = entry.roll[seat],
                        choice = entry.choices[entry.pick[seat]],
                        revision = entry.rev[seat],
                    }
                end
            end
            rows[position] = {
                id = entry.id,
                choices = duplicate(entry.choices),
                roll = duplicate(entry.roll),
                deadline = entry.deadline,
                quorum = entry.quorum,
                opened_at = entry.opened_at,
                ballots = ballots,
                phase = entry.phase,
                winner = entry.winner,
                settled_at = entry.settled_at,
            }
        end
        return { format = FORMAT, saved_at = finite(now) and now or nil, rows = rows }
    end

    local function restore(row, shift)
        if type(row) ~= "table" or not name_ok(row.id) or book[row.id] ~= nil then
            return
        end
        if type(row.choices) ~= "table" or type(row.roll) ~= "table" or not finite(row.deadline) then
            return
        end
        local choices = sorted_unique(row.choices)
        local roll = sorted_unique(row.roll)
        if #choices < 2 or #roll == 0 then
            return
        end
        local still_open = row.phase == PHASE_OPEN and live == nil
        if not still_open and not FINAL[row.phase] then
            return
        end
        local entry = {
            id = row.id,
            choices = choices,
            slot = positions(choices),
            deadline = row.deadline + (still_open and shift or 0),
            quorum = whole(row.quorum) and row.quorum or #roll,
            opened_at = finite(row.opened_at) and row.opened_at + (still_open and shift or 0) or nil,
            roll = roll,
            seat = positions(roll),
            rev = filled(#roll, -1),
            pick = filled(#roll, 0),
            tally = filled(#choices, 0),
            turnout = 0,
            phase = row.phase,
            winner = row.phase == PHASE_PASSED and row.winner or nil,
            settled_at = finite(row.settled_at) and row.settled_at or nil,
        }
        for _, ballot in ipairs(type(row.ballots) == "table" and row.ballots or {}) do
            local seat = type(ballot) == "table" and entry.seat[ballot.voter] or nil
            local slot = seat ~= nil and entry.slot[ballot.choice] or nil
            if slot ~= nil and whole(ballot.revision) and entry.pick[seat] == 0 then
                entry.pick[seat], entry.rev[seat] = slot, ballot.revision
                entry.tally[slot] = entry.tally[slot] + 1
                entry.turnout = entry.turnout + 1
            end
        end
        book[entry.id] = entry
        sequence[#sequence + 1] = entry.id
        if still_open then
            live = entry.id
        end
    end

    if type(saved) == "table" and type(saved.rows) == "table" then
        -- A host whose clock restarted passes its current time as options.now;
        -- open deadlines then keep the time they had left when saved.
        local shift = 0
        if finite(options.now) and finite(saved.saved_at) then
            shift = options.now - saved.saved_at
        end
        for position = 1, #saved.rows do
            restore(saved.rows[position], shift)
        end
    end

    return object
end

function Ballot.new(options)
    return build(options, nil)
end

function Ballot.load(data, options)
    return build(options, data)
end

return Ballot
