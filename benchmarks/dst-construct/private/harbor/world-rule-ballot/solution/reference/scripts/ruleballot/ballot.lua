-- Pure Lua ballot state machine. It has no engine dependency so the same
-- module serves the dedicated server component and plain-Lua verification.

local Ballot = {}
Ballot.__index = Ballot

local OPEN, PASSED, TIE, NO_QUORUM, CANCELED = "open", "passed", "tie", "no_quorum", "canceled"

local function fail(reason)
    return { ok = false, reason = reason }
end

local function is_finite(value)
    return type(value) == "number" and value == value
        and value ~= math.huge and value ~= -math.huge
end

local function is_identifier(value)
    return type(value) == "string" and value ~= ""
end

local function is_revision(value)
    return is_finite(value) and value >= 0 and math.floor(value) == value
end

local function copy_array(values)
    local out = {}
    for index = 1, #values do
        out[index] = values[index]
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

-- Counts are always reported in option-ID order so every caller, client and
-- reload observes the same sequence.
local function tally(record)
    local totals = {}
    for index = 1, #record.choices do
        totals[record.choices[index]] = 0
    end
    local participants = 0
    for _, voter_id in ipairs(sorted_keys(record.votes)) do
        local vote = record.votes[voter_id]
        totals[vote.choice_id] = totals[vote.choice_id] + 1
        participants = participants + 1
    end
    local counts = {}
    for _, choice_id in ipairs(sorted_keys(totals)) do
        counts[#counts + 1] = { choice_id = choice_id, count = totals[choice_id] }
    end
    return counts, participants
end

local function copy_counts(counts)
    local out = {}
    for index = 1, #counts do
        out[index] = { choice_id = counts[index].choice_id, count = counts[index].count }
    end
    return out
end

local function copy_result(result)
    return {
        ok = true,
        proposal_id = result.proposal_id,
        status = result.status,
        choice_id = result.choice_id,
        participants = result.participants,
        electorate_size = result.electorate_size,
        quorum = result.quorum,
        counts = copy_counts(result.counts),
        closed_at = result.closed_at,
    }
end

local function finalize(record, status, now)
    local counts, participants = tally(record)
    local choice_id = nil
    if status == nil then
        if participants < record.quorum then
            status = NO_QUORUM
        else
            local best, leaders = -1, 0
            for index = 1, #counts do
                local entry = counts[index]
                if entry.count > best then
                    best, leaders, choice_id = entry.count, 1, entry.choice_id
                elseif entry.count == best then
                    leaders = leaders + 1
                end
            end
            if leaders > 1 then
                status, choice_id = TIE, nil
            else
                status = PASSED
            end
        end
    end
    record.status = status
    record.result = {
        proposal_id = record.id,
        status = status,
        choice_id = choice_id,
        participants = participants,
        electorate_size = record.electorate_size,
        quorum = record.quorum,
        counts = counts,
        -- The outcome is the one that held at the deadline, whenever it is read.
        closed_at = math.min(now, record.deadline),
    }
    return record.result
end

function Ballot.new(options)
    local self = setmetatable({}, Ballot)
    self.options = type(options) == "table" and options or {}
    self.proposals = {}
    self.order = {}
    return self
end

function Ballot:open(proposal, electorate, now)
    if type(proposal) ~= "table" or not is_identifier(proposal.id) then
        return fail("invalid_proposal")
    end
    if not is_finite(now) then
        return fail("invalid_time")
    end
    -- A closed or canceled identifier is never reusable.
    if self.proposals[proposal.id] ~= nil then
        return fail("duplicate_proposal")
    end
    if type(proposal.choices) ~= "table" or #proposal.choices < 2 then
        return fail("invalid_choices")
    end
    local choices, seen_choice = {}, {}
    for index = 1, #proposal.choices do
        local choice_id = proposal.choices[index]
        if not is_identifier(choice_id) or seen_choice[choice_id] then
            return fail("invalid_choices")
        end
        seen_choice[choice_id] = true
        choices[#choices + 1] = choice_id
    end
    if not is_finite(proposal.deadline) or proposal.deadline <= now then
        return fail("invalid_deadline")
    end
    if type(electorate) ~= "table" then
        return fail("invalid_electorate")
    end
    local voters, size = {}, 0
    for index = 1, #electorate do
        local voter_id = electorate[index]
        if is_identifier(voter_id) and not voters[voter_id] then
            voters[voter_id] = true
            size = size + 1
        end
    end
    if size == 0 then
        return fail("invalid_electorate")
    end
    local quorum = proposal.quorum
    if not is_finite(quorum) or quorum < 1 or math.floor(quorum) ~= quorum or quorum > size then
        return fail("invalid_quorum")
    end

    self.proposals[proposal.id] = {
        id = proposal.id,
        choices = choices,
        choice_set = seen_choice,
        deadline = proposal.deadline,
        quorum = quorum,
        opened_at = now,
        electorate = voters,
        electorate_size = size,
        votes = {},
        revisions = {},
        status = OPEN,
        result = nil,
    }
    self.order[#self.order + 1] = proposal.id
    return { ok = true, proposal_id = proposal.id, electorate_size = size, deadline = proposal.deadline }
end

function Ballot:cast(voter_id, proposal_id, choice_id, revision, now)
    local record = self.proposals[proposal_id]
    if record == nil then
        return fail("unknown_proposal")
    end
    if record.status ~= OPEN then
        return fail("closed")
    end
    if not is_finite(now) or now >= record.deadline then
        return fail("late")
    end
    if not is_identifier(voter_id) or not record.electorate[voter_id] then
        return fail("not_in_electorate")
    end
    if not is_identifier(choice_id) or not record.choice_set[choice_id] then
        return fail("invalid_choice")
    end
    if not is_revision(revision) then
        return fail("invalid_revision")
    end
    local last = record.revisions[voter_id]
    if last ~= nil and revision <= last then
        return fail("stale_revision")
    end
    record.revisions[voter_id] = revision
    record.votes[voter_id] = { choice_id = choice_id, revision = revision }
    return { ok = true, proposal_id = proposal_id, revision = revision }
end

function Ballot:close(proposal_id, now)
    local record = self.proposals[proposal_id]
    if record == nil then
        return fail("unknown_proposal")
    end
    if not is_finite(now) then
        return fail("invalid_time")
    end
    if record.result == nil then
        finalize(record, nil, now)
    end
    return copy_result(record.result)
end

function Ballot:cancel(proposal_id, now)
    local record = self.proposals[proposal_id]
    if record == nil then
        return fail("unknown_proposal")
    end
    if not is_finite(now) then
        return fail("invalid_time")
    end
    if record.result == nil then
        finalize(record, CANCELED, now)
    end
    return copy_result(record.result)
end

function Ballot:is_open(proposal_id)
    local record = self.proposals[proposal_id]
    return record ~= nil and record.status == OPEN
end

function Ballot:open_proposals()
    local out = {}
    for index = 1, #self.order do
        local record = self.proposals[self.order[index]]
        if record.status == OPEN then
            out[#out + 1] = { id = record.id, deadline = record.deadline }
        end
    end
    return out
end

-- Shift every pending deadline, used when the engine clock restarts on load.
function Ballot:rebase(offset)
    if not is_finite(offset) then
        return
    end
    for index = 1, #self.order do
        local record = self.proposals[self.order[index]]
        if record.status == OPEN then
            record.deadline = record.deadline + offset
            record.opened_at = record.opened_at + offset
        end
    end
end

local function public_state(record)
    local counts, participants
    if record.result ~= nil then
        counts, participants = copy_counts(record.result.counts), record.result.participants
    else
        counts, participants = tally(record)
    end
    return {
        proposal_id = record.id,
        status = record.status,
        choice_id = record.result ~= nil and record.result.choice_id or nil,
        deadline = record.deadline,
        quorum = record.quorum,
        electorate_size = record.electorate_size,
        participants = participants,
        choices = copy_array(record.choices),
        counts = counts,
    }
end

-- Aggregates only: individual choices and the electorate never leave here.
function Ballot:snapshot(now)
    local proposals = {}
    for index = 1, #self.order do
        proposals[#proposals + 1] = public_state(self.proposals[self.order[index]])
    end
    local latest = proposals[#proposals]
    local snapshot = { time = now, proposals = proposals }
    if latest ~= nil then
        for key, value in pairs(latest) do
            snapshot[key] = value
        end
        snapshot.counts = copy_counts(latest.counts)
    else
        snapshot.counts = {}
    end
    return snapshot
end

function Ballot:save(now)
    local proposals = {}
    for index = 1, #self.order do
        local record = self.proposals[self.order[index]]
        local votes = {}
        for _, voter_id in ipairs(sorted_keys(record.votes)) do
            local vote = record.votes[voter_id]
            votes[#votes + 1] = { voter_id = voter_id, choice_id = vote.choice_id, revision = vote.revision }
        end
        local revisions = {}
        for _, voter_id in ipairs(sorted_keys(record.revisions)) do
            revisions[#revisions + 1] = { voter_id = voter_id, revision = record.revisions[voter_id] }
        end
        local result = nil
        if record.result ~= nil then
            result = copy_result(record.result)
            result.ok = nil
        end
        proposals[#proposals + 1] = {
            id = record.id,
            choices = copy_array(record.choices),
            deadline = record.deadline,
            quorum = record.quorum,
            opened_at = record.opened_at,
            electorate = sorted_keys(record.electorate),
            votes = votes,
            revisions = revisions,
            status = record.status,
            result = result,
        }
    end
    return { version = 1, saved_at = now, proposals = proposals }
end

function Ballot.load(data, options)
    local self = Ballot.new(options)
    if type(data) ~= "table" or type(data.proposals) ~= "table" then
        return self
    end
    for index = 1, #data.proposals do
        local saved = data.proposals[index]
        if type(saved) == "table" and is_identifier(saved.id) and self.proposals[saved.id] == nil
            and type(saved.choices) == "table" and is_finite(saved.deadline) then
            local choice_set, electorate, size = {}, {}, 0
            for _, choice_id in ipairs(saved.choices) do
                choice_set[choice_id] = true
            end
            for _, voter_id in ipairs(saved.electorate or {}) do
                if not electorate[voter_id] then
                    electorate[voter_id] = true
                    size = size + 1
                end
            end
            local votes, revisions = {}, {}
            for _, entry in ipairs(saved.revisions or {}) do
                revisions[entry.voter_id] = entry.revision
            end
            for _, entry in ipairs(saved.votes or {}) do
                if electorate[entry.voter_id] and choice_set[entry.choice_id] then
                    votes[entry.voter_id] = { choice_id = entry.choice_id, revision = entry.revision }
                end
            end
            local result = nil
            if type(saved.result) == "table" then
                result = {
                    proposal_id = saved.id,
                    status = saved.result.status,
                    choice_id = saved.result.choice_id,
                    participants = saved.result.participants,
                    electorate_size = saved.result.electorate_size,
                    quorum = saved.result.quorum,
                    counts = copy_counts(saved.result.counts or {}),
                    closed_at = saved.result.closed_at,
                }
            end
            self.proposals[saved.id] = {
                id = saved.id,
                choices = copy_array(saved.choices),
                choice_set = choice_set,
                deadline = saved.deadline,
                quorum = saved.quorum,
                opened_at = saved.opened_at,
                electorate = electorate,
                electorate_size = size,
                votes = votes,
                revisions = revisions,
                status = result ~= nil and result.status or OPEN,
                result = result,
            }
            self.order[#self.order + 1] = saved.id
        end
    end
    return self
end

return Ballot
