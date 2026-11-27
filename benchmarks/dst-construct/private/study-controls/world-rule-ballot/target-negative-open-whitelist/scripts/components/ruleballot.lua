-- Server world component for rule ballots.
--
-- Responsibilities kept here and nowhere else: turning player entities into a
-- frozen list of userids, the engine clock, the settlement timer, applying a
-- rule from the mod's own table, the announcement and the public net state.

local Ballot = require("ruleballot/ballot")

-- Proposals an operator can start by name. Durations are seconds of engine
-- time; quorum is a share of the players online when the ballot opens.
local CONFIGURED = {
    ["rule-lights"] = { choices = { "off", "on" }, duration = 120, quorum_share = 0.5 },
    ["rule-respawn"] = { choices = { "abstain", "portal", "touchstone" }, duration = 180, quorum_share = 0.6 },
}

-- What a passed proposal may change: one named flag, one value per option.
-- A proposal or option that is not listed here changes nothing at all.
local EFFECTS = {
    ["rule-lights"] = { flag = "lights", values = { on = true, off = false } },
    ["rule-respawn"] = { flag = "respawn", values = { portal = "portal", touchstone = "touchstone" } },
}

local CORE_OPTIONS = { abstain = "abstain" }

local function quote(text)
    return '"' .. tostring(text):gsub('[%c"\\]', function(char)
        return string.format("\\u%04x", char:byte())
    end) .. '"'
end

-- Aggregates only, fixed key order, so equal states encode to equal strings.
local function encode_public(view)
    if view.proposal_id == nil then
        return ""
    end
    local counts = {}
    for index, row in ipairs(view.counts) do
        counts[index] = "{" .. quote("choice_id") .. ":" .. quote(row.choice_id)
            .. "," .. quote("count") .. ":" .. tostring(row.count) .. "}"
    end
    local fields = {
        quote("proposal_id") .. ":" .. quote(view.proposal_id),
        quote("status") .. ":" .. quote(view.status),
        quote("remaining") .. ":" .. string.format("%d", math.ceil(view.remaining or 0)),
        quote("participants") .. ":" .. tostring(view.participants),
        quote("electorate_size") .. ":" .. tostring(view.electorate_size),
        quote("quorum") .. ":" .. tostring(view.quorum),
        quote("counts") .. ":[" .. table.concat(counts, ",") .. "]",
    }
    if view.choice_id ~= nil then
        fields[#fields + 1] = quote("choice_id") .. ":" .. quote(view.choice_id)
    end
    return "{" .. table.concat(fields, ",") .. "}"
end

local RuleBallot = Class(function(self, inst)
    self.inst = inst
    self.core = Ballot.new(CORE_OPTIONS)
    self.flags = {}
    self.timer = nil
    self.timer_for = nil
end)

local function clock()
    return GetTime()
end

function RuleBallot:StopTimer()
    if self.timer ~= nil then
        self.timer:Cancel()
    end
    self.timer, self.timer_for = nil, nil
end

function RuleBallot:ArmTimer()
    self:StopTimer()
    local pending = self.core:pending()
    if pending == nil then
        return
    end
    local proposal_id = pending.proposal_id
    local delay = pending.deadline - clock()
    self.timer_for = proposal_id
    self.timer = self.inst:DoTaskInTime(delay > 0 and delay or 0, function()
        self.timer, self.timer_for = nil, nil
        self:Close(proposal_id)
    end)
end

function RuleBallot:Broadcast()
    local text = encode_public(self.core:snapshot(clock()))
    local view = self.inst.replica ~= nil and self.inst.replica.ruleballot or nil
    if view ~= nil then
        view:Publish(text)
    elseif self.inst._ballot_state ~= nil then
        self.inst._ballot_state:set(text)
    end
end

function RuleBallot:GetFlag(flag)
    return self.flags[flag]
end

local function finish(self, result)
    -- Reached once per proposal: the caller checked that it was still open.
    local message
    if result.status == "passed" and result.choice_id ~= nil then
        local effect = EFFECTS[result.proposal_id]
        local value = effect ~= nil and effect.values[result.choice_id] or nil
        if value ~= nil then
            self.flags[effect.flag] = value
            self.inst:PushEvent("ruleballot_flagchanged", { flag = effect.flag, value = value })
        end
        message = string.format("Vote '%s' passed: %s.", result.proposal_id, result.choice_id)
    elseif result.status == "tie" then
        message = string.format("Vote '%s' ended in a tie; nothing changes.", result.proposal_id)
    elseif result.status == "no_quorum" then
        message = string.format("Vote '%s' did not reach quorum (%d of %d needed).",
            result.proposal_id, result.participants, result.quorum)
    else
        message = string.format("Vote '%s' was canceled.", result.proposal_id)
    end
    if TheNet ~= nil then
        TheNet:Announce(message)
    end
    if self.timer_for == result.proposal_id then
        self:StopTimer()
    end
    self:Broadcast()
end

local function userids_of(player_entities)
    local ids = {}
    for _, player in ipairs(type(player_entities) == "table" and player_entities or {}) do
        local userid = type(player) == "table" and player.userid or nil
        if type(userid) == "string" and userid ~= "" then
            ids[#ids + 1] = userid
        end
    end
    return ids
end

-- Server code only. The electorate is read from the entities right now and
-- frozen by the core; later joins are not part of it.
function RuleBallot:Open(proposal, player_entities)
    if not self.inst.ismastersim then
        return { ok = false, reason = "not_server" }
    end
    -- "Proposals come from the server's fixed whitelist": an identifier whose
    -- name part is not configured in this mod is refused, whoever asks.
    local name = type(proposal) == "table" and type(proposal.id) == "string"
        and proposal.id:match("^([^#]+)") or nil
    if name == nil or CONFIGURED[name] == nil then
        return { ok = false, reason = "not_configured" }
    end
    local opened = self.core:open(proposal, userids_of(player_entities or AllPlayers), clock())
    if opened.ok then
        self:ArmTimer()
        self:Broadcast()
        if TheNet ~= nil then
            TheNet:Announce(string.format("Vote '%s' is open.", opened.proposal_id))
        end
    end
    return opened
end

function RuleBallot:OpenConfigured(name)
    local entry = CONFIGURED[name]
    if entry == nil then
        return { ok = false, reason = "not_configured" }
    end
    local players = {}
    for _, player in ipairs(AllPlayers or {}) do
        players[#players + 1] = player
    end
    local quorum = math.max(1, math.ceil(#userids_of(players) * entry.quorum_share))
    return self:Open({
        id = string.format("%s#%d", name, TheWorld ~= nil and TheWorld.state ~= nil and TheWorld.state.cycles or 0),
        choices = entry.choices,
        deadline = clock() + entry.duration,
        quorum = quorum,
    }, players)
end

function RuleBallot:Cast(player, proposal_id, choice_id, revision)
    local userid = type(player) == "table" and player.userid or nil
    if type(userid) ~= "string" or userid == "" then
        return { ok = false, reason = "no_identity" }
    end
    local cast = self.core:cast(userid, proposal_id, choice_id, revision, clock())
    if cast.ok then
        self:Broadcast()
    end
    return cast
end

function RuleBallot:Close(proposal_id)
    local was_open = self.core:status(proposal_id) == "open"
    local result = self.core:close(proposal_id, clock())
    if result.ok and was_open then
        finish(self, result)
    end
    return result
end

function RuleBallot:Cancel(proposal_id)
    local was_open = self.core:status(proposal_id) == "open"
    local result = self.core:cancel(proposal_id, clock())
    if result.ok and was_open then
        finish(self, result)
    end
    return result
end

function RuleBallot:GetPublicView()
    return self.core:snapshot(clock())
end

function RuleBallot:OnSave()
    local flags = {}
    for flag, value in pairs(self.flags) do
        flags[flag] = value
    end
    return { core = self.core:save(clock()), flags = flags }
end

function RuleBallot:OnLoad(data)
    self:StopTimer()
    if type(data) ~= "table" then
        return
    end
    if type(data.core) == "table" then
        -- GetTime() starts again with every server process; handing the core
        -- the new "now" keeps the remaining time of an open proposal.
        self.core = Ballot.load(data.core, { abstain = CORE_OPTIONS.abstain, now = clock() })
    end
    self.flags = {}
    for flag, value in pairs(type(data.flags) == "table" and data.flags or {}) do
        self.flags[flag] = value
    end
    self:ArmTimer()
    self:Broadcast()
end

function RuleBallot:OnRemoveFromEntity()
    self:StopTimer()
end

function RuleBallot:OnRemoveEntity()
    self:StopTimer()
end

return RuleBallot
