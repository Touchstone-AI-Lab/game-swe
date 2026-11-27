-- Master-simulation world component. It owns the authoritative ballot state,
-- derives voter identity from player entities, schedules settlement on the
-- real engine clock and publishes only aggregate state to clients.

local Ballot = require("ruleballot/ballot")

-- The only rules a passed ballot may apply. Clients can never supply code,
-- commands or configuration keys: a proposal is matched by identifier here.
local RULES = {
    ["rhenium-lights"] = function(world, choice_id)
        world.rhenium_lights_enabled = choice_id == "on"
    end,
    ["rhenium-pvp-hint"] = function(world, choice_id)
        world.rhenium_pvp_hint = choice_id
    end,
}

local function encode_state(snapshot)
    if snapshot.proposal_id == nil then
        return ""
    end
    local parts = {}
    for index = 1, #snapshot.counts do
        local entry = snapshot.counts[index]
        parts[#parts + 1] = entry.choice_id .. "=" .. tostring(entry.count)
    end
    return table.concat({
        snapshot.proposal_id,
        snapshot.status,
        tostring(snapshot.choice_id or ""),
        string.format("%.3f", snapshot.deadline),
        tostring(snapshot.participants),
        tostring(snapshot.electorate_size),
        table.concat(parts, ","),
    }, "|")
end

local RuleBallot = Class(function(self, inst)
    self.inst = inst
    self.ballot = Ballot.new({})
    self.tasks = {}
end)

function RuleBallot:_now()
    return GetTime()
end

function RuleBallot:_publish()
    local encoded = encode_state(self.ballot:snapshot(self:_now()))
    local replica = self.inst.replica ~= nil and self.inst.replica.ruleballot or nil
    if replica ~= nil and replica.SetState ~= nil then
        replica:SetState(encoded)
    elseif self.inst._ballot_state ~= nil then
        self.inst._ballot_state:set(encoded)
    end
end

function RuleBallot:_cancel_task(proposal_id)
    local task = self.tasks[proposal_id]
    if task ~= nil then
        task:Cancel()
        self.tasks[proposal_id] = nil
    end
end

function RuleBallot:_schedule(proposal_id, deadline)
    self:_cancel_task(proposal_id)
    local delay = math.max(0, deadline - self:_now())
    self.tasks[proposal_id] = self.inst:DoTaskInTime(delay, function()
        self.tasks[proposal_id] = nil
        self:Close(proposal_id)
    end)
end

function RuleBallot:_settle(result)
    if result.status == "passed" and result.choice_id ~= nil then
        local rule = RULES[result.proposal_id]
        if rule ~= nil then
            rule(self.inst, result.choice_id)
        end
    end
    if TheNet ~= nil then
        local outcome = result.status == "passed" and ("passed: " .. tostring(result.choice_id))
            or result.status
        TheNet:Announce("Ballot " .. result.proposal_id .. " " .. outcome)
    end
end

-- Server-side entry only; the RPC handler never reaches this method.
function RuleBallot:Open(proposal, player_entities)
    local electorate = {}
    if type(player_entities) == "table" then
        for _, player in ipairs(player_entities) do
            if type(player) == "table" and type(player.userid) == "string" and player.userid ~= "" then
                electorate[#electorate + 1] = player.userid
            end
        end
    end
    local opened = self.ballot:open(proposal, electorate, self:_now())
    if opened.ok then
        self:_schedule(opened.proposal_id, opened.deadline)
        self:_publish()
    end
    return opened
end

function RuleBallot:Cast(player, proposal_id, choice_id, revision)
    local voter_id = type(player) == "table" and player.userid or nil
    if type(voter_id) ~= "string" or voter_id == "" then
        return { ok = false, reason = "not_in_electorate" }
    end
    local cast = self.ballot:cast(voter_id, proposal_id, choice_id, revision, self:_now())
    if cast.ok then
        self:_publish()
    end
    return cast
end

function RuleBallot:Close(proposal_id)
    local was_open = self.ballot:is_open(proposal_id)
    local result = self.ballot:close(proposal_id, self:_now())
    if result.ok and was_open then
        self:_cancel_task(proposal_id)
        self:_settle(result)
        self:_publish()
    end
    return result
end

function RuleBallot:Cancel(proposal_id)
    local was_open = self.ballot:is_open(proposal_id)
    local result = self.ballot:cancel(proposal_id, self:_now())
    if result.ok and was_open then
        self:_cancel_task(proposal_id)
        self:_settle(result)
        self:_publish()
    end
    return result
end

function RuleBallot:GetPublicState()
    return self.ballot:snapshot(self:_now())
end

function RuleBallot:OnSave()
    local now = self:_now()
    return { ballot = self.ballot:save(now), saved_at = now }
end

function RuleBallot:OnLoad(data)
    for proposal_id in pairs(self.tasks) do
        self:_cancel_task(proposal_id)
    end
    if type(data) ~= "table" or type(data.ballot) ~= "table" then
        return
    end
    self.ballot = Ballot.load(data.ballot, {})
    -- The engine clock restarts with the process, so pending deadlines keep
    -- their remaining time instead of their stale absolute value.
    if type(data.saved_at) == "number" then
        self.ballot:rebase(self:_now() - data.saved_at)
    end
    for _, pending in ipairs(self.ballot:open_proposals()) do
        self:_schedule(pending.id, pending.deadline)
    end
    self:_publish()
end

function RuleBallot:OnRemoveFromEntity()
    for proposal_id in pairs(self.tasks) do
        self:_cancel_task(proposal_id)
    end
end

RuleBallot.OnRemoveEntity = RuleBallot.OnRemoveFromEntity

return RuleBallot
