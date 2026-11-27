local Ballot = require("ruleballot.ballot")

local RuleBallotService = {}
RuleBallotService.__index = RuleBallotService

local function now_seconds()
    return os.time()
end

local function voter_id_of(controller)
    if type(controller) == "string" and controller ~= "" then return controller end
    if type(controller) ~= "table" then return nil end
    if type(controller.get) == "function" then
        local ok, unwrapped = pcall(controller.get, controller)
        if ok and unwrapped ~= nil then controller = unwrapped end
    end
    if type(controller.GetPlayerUId) == "function" then
        local ok, value = pcall(controller.GetPlayerUId, controller)
        if ok and value ~= nil then return tostring(value) end
    end
    return controller.voter_id or controller.player_id
end

function RuleBallotService.new(options)
    options = type(options) == "table" and options or {}
    local self = setmetatable({}, RuleBallotService)
    self.now = options.now or now_seconds
    self.schedule = options.schedule
    self.ballot = Ballot.new(options.ballot_options or {})
    self.controllers = {}
    self.deadlines = {}
    return self
end

function RuleBallotService:Attach(controller)
    local voter_id = voter_id_of(controller)
    if voter_id == nil then return { ok = false, code = "invalid_voter" } end
    self.controllers[voter_id] = controller
    return { ok = true, voter_id = voter_id }
end

function RuleBallotService:VoterIdOf(controller)
    return voter_id_of(controller)
end

function RuleBallotService:CurrentController()
    return FindFirstOf("PalPlayerController")
end

function RuleBallotService:_schedule(proposal_id, deadline)
    if type(self.schedule) ~= "function" then return end
    local remaining = math.max(0, deadline - self.now())
    self.schedule(remaining * 1000, function()
        -- The guard also makes early or duplicated scheduler callbacks harmless.
        if self.now() >= deadline then self.ballot:close(proposal_id, self.now()) end
    end)
end

function RuleBallotService:Open(proposal, electorate)
    if type(proposal) ~= "table" or type(proposal.deadline_seconds) ~= "number" then
        return { ok = false, code = "invalid_proposal" }
    end
    local now = self.now()
    local absolute = {}
    for key, value in pairs(proposal) do absolute[key] = value end
    absolute.deadline = now + proposal.deadline_seconds
    absolute.deadline_seconds = nil
    local voters = {}
    if type(electorate) == "table" then
        for _, controller in ipairs(electorate) do
            local voter_id = voter_id_of(controller)
            if voter_id ~= nil then voters[#voters + 1] = voter_id end
        end
    end
    local result = self.ballot:open(absolute, voters, now)
    if result.ok then
        self.deadlines[absolute.id] = absolute.deadline
        self:_schedule(absolute.id, absolute.deadline)
    end
    return result
end

function RuleBallotService:Cast(controller, proposal_id, choice_id, revision)
    local voter_id = voter_id_of(controller)
    if voter_id == nil then return { ok = false, code = "not_a_voter" } end
    return self:CastAs(voter_id, proposal_id, choice_id, revision)
end

function RuleBallotService:CastAs(voter_id, proposal_id, choice_id, revision)
    return self.ballot:cast(voter_id, proposal_id, choice_id, revision, self.now())
end

function RuleBallotService:Close(proposal_id)
    local deadline = self.deadlines[proposal_id]
    local now = self.now()
    -- Operator-driven close is authoritative and settles at the frozen deadline.
    if type(deadline) == "number" and now < deadline then now = deadline end
    return self.ballot:close(proposal_id, now)
end

function RuleBallotService:Cancel(proposal_id)
    return self.ballot:cancel(proposal_id, self.now())
end

function RuleBallotService:Snapshot()
    return self.ballot:snapshot(self.now())
end

function RuleBallotService:Save()
    return {
        ballot = self.ballot:save(self.now()),
        deadlines = self.deadlines,
    }
end

function RuleBallotService:Load(data)
    data = type(data) == "table" and data or {}
    self.ballot = Ballot.load(data.ballot, {})
    self.deadlines = type(data.deadlines) == "table" and data.deadlines or {}
    for proposal_id, deadline in pairs(self.deadlines) do
        self:_schedule(proposal_id, deadline)
    end
    return { ok = true }
end

return RuleBallotService
