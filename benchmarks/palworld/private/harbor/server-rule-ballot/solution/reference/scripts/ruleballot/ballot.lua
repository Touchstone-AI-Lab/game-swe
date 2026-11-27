local Ballot = {}
Ballot.__index = Ballot

local function valid_id(value)
    return type(value) == "string" and value ~= ""
end

local function nonnegative_integer(value)
    return type(value) == "number" and value >= 0 and value % 1 == 0
end

local function finite_number(value)
    return type(value) == "number" and value == value
        and value ~= math.huge and value ~= -math.huge
end

local function copy(value, seen)
    if type(value) ~= "table" then return value end
    seen = seen or {}
    if seen[value] then return seen[value] end
    local result = {}
    seen[value] = result
    for key, item in pairs(value) do result[copy(key, seen)] = copy(item, seen) end
    return result
end

local function rejected(code)
    return { ok = false, code = code }
end

local function ordered_choices(proposal)
    local choices = {}
    for choice_id in pairs(proposal.choice_set) do choices[#choices + 1] = choice_id end
    table.sort(choices)
    return choices
end

local function counts_for(proposal)
    local totals = {}
    for choice_id in pairs(proposal.choice_set) do totals[choice_id] = 0 end
    for _, vote in pairs(proposal.votes) do
        totals[vote.choice_id] = totals[vote.choice_id] + 1
    end
    local counts = {}
    for _, choice_id in ipairs(ordered_choices(proposal)) do
        counts[#counts + 1] = { choice_id = choice_id, count = totals[choice_id] }
    end
    return counts
end

local function public_result(proposal)
    if proposal.result ~= nil then return copy(proposal.result) end
    return {
        proposal_id = proposal.id,
        status = proposal.state,
        choice_id = nil,
        counts = counts_for(proposal),
    }
end

local function normalize_proposal(proposal, electorate, now)
    if type(proposal) ~= "table" or not valid_id(proposal.id)
        or type(proposal.choices) ~= "table" or not finite_number(proposal.deadline)
        or proposal.deadline <= now or not nonnegative_integer(proposal.quorum)
        or proposal.quorum < 1 or type(electorate) ~= "table" then
        return nil
    end

    local choice_set = {}
    local choice_count = 0
    for _, choice_id in ipairs(proposal.choices) do
        if not valid_id(choice_id) or choice_set[choice_id] then return nil end
        choice_set[choice_id] = true
        choice_count = choice_count + 1
    end
    if choice_count < 2 then return nil end

    local voter_set = {}
    local voter_count = 0
    for _, voter_id in ipairs(electorate) do
        if not valid_id(voter_id) then return nil end
        if not voter_set[voter_id] then
            voter_set[voter_id] = true
            voter_count = voter_count + 1
        end
    end
    if voter_count == 0 or proposal.quorum > voter_count then return nil end

    return {
        id = proposal.id,
        deadline = proposal.deadline,
        quorum = proposal.quorum,
        choice_set = choice_set,
        electorate = voter_set,
        votes = {},
        state = "open",
        result = nil,
    }
end

function Ballot.new(options)
    local self = setmetatable({}, Ballot)
    self.options = type(options) == "table" and copy(options) or {}
    self.proposals = {}
    self.last_proposal_id = nil
    return self
end

function Ballot.load(data, options)
    local self = Ballot.new(options)
    if type(data) ~= "table" then return self end
    if type(data.proposals) == "table" then self.proposals = copy(data.proposals) end
    if valid_id(data.last_proposal_id) then self.last_proposal_id = data.last_proposal_id end
    return self
end

function Ballot:open(proposal, electorate, now)
    if not finite_number(now) then return rejected("invalid_proposal") end
    if type(proposal) == "table" and valid_id(proposal.id)
        and self.proposals[proposal.id] ~= nil then
        return rejected("reused_id")
    end
    local normalized = normalize_proposal(proposal, electorate, now)
    if normalized == nil then return rejected("invalid_proposal") end
    self.proposals[normalized.id] = normalized
    self.last_proposal_id = normalized.id
    return { ok = true, proposal_id = normalized.id }
end

function Ballot:cast(voter_id, proposal_id, choice_id, revision, now)
    local proposal = self.proposals[proposal_id]
    if proposal == nil then return rejected("closed") end
    if proposal.state ~= "open" then return rejected("closed") end
    if not finite_number(now) or now >= proposal.deadline then return rejected("past_deadline") end
    if not proposal.electorate[voter_id] then return rejected("not_a_voter") end
    if not proposal.choice_set[choice_id] then return rejected("unknown_choice") end
    if not nonnegative_integer(revision) then return rejected("stale_revision") end
    local previous = proposal.votes[voter_id]
    if previous ~= nil and revision <= previous.revision then return rejected("stale_revision") end
    proposal.votes[voter_id] = { choice_id = choice_id, revision = revision }
    return { ok = true, revision = revision }
end

function Ballot:close(proposal_id, now)
    local proposal = self.proposals[proposal_id]
    if proposal == nil then return { status = "unknown", choice_id = nil, counts = {} } end
    if proposal.result ~= nil then return copy(proposal.result) end
    if proposal.state == "canceled" then return public_result(proposal) end
    if not finite_number(now) or now < proposal.deadline then
        return { status = "open", choice_id = nil, counts = counts_for(proposal) }
    end

    local counts = counts_for(proposal)
    local participation = 0
    for _ in pairs(proposal.votes) do participation = participation + 1 end
    local status = "no_quorum"
    local winner = nil
    if participation >= proposal.quorum then
        local highest = -1
        local tied = false
        for _, entry in ipairs(counts) do
            if entry.count > highest then
                highest = entry.count
                winner = entry.choice_id
                tied = false
            elseif entry.count == highest then
                tied = true
            end
        end
        if tied then
            status = "tie"
            winner = nil
        else
            status = "passed"
        end
    end
    proposal.state = status
    proposal.result = {
        status = status,
        proposal_id = proposal.id,
        choice_id = winner,
        counts = counts,
    }
    return copy(proposal.result)
end

function Ballot:cancel(proposal_id, _now)
    local proposal = self.proposals[proposal_id]
    if proposal == nil then return { status = "unknown", choice_id = nil, counts = {} } end
    if proposal.result ~= nil then return copy(proposal.result) end
    proposal.state = "canceled"
    proposal.result = {
        status = "canceled",
        proposal_id = proposal.id,
        choice_id = nil,
        counts = counts_for(proposal),
    }
    return copy(proposal.result)
end

function Ballot:snapshot(_now)
    local proposal = self.proposals[self.last_proposal_id]
    if proposal == nil then return { status = "empty", counts = {} } end
    return public_result(proposal)
end

function Ballot:save(_now)
    return {
        proposals = copy(self.proposals),
        last_proposal_id = self.last_proposal_id,
    }
end

return Ballot
