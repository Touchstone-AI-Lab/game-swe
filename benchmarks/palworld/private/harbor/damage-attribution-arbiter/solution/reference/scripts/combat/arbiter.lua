local Arbiter = {}
Arbiter.__index = Arbiter

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

local function options_of(options)
    options = type(options) == "table" and options or {}
    local seconds = options.claim_seconds
    if not finite_number(seconds) or seconds <= 0 then seconds = 15 end
    return { claim_seconds = seconds }
end

local function valid_report(report)
    return type(report) == "table"
        and nonnegative_integer(report.sequence)
        and valid_id(report.attacker_id)
        and valid_id(report.target_id)
        and finite_number(report.amount)
        and report.amount >= 0
        and finite_number(report.tick)
end

local function total_for(target)
    local total = 0
    for _, attacker in pairs(target.attackers) do total = total + attacker.total end
    return total
end

function Arbiter.new(options)
    local self = setmetatable({}, Arbiter)
    self.options = options_of(options)
    self.targets = {}
    self.tokens = {}
    self.token_sequence = 0
    return self
end

function Arbiter.load(data, options)
    local self = Arbiter.new(options)
    if type(data) ~= "table" then return self end
    if type(data.targets) == "table" then self.targets = copy(data.targets) end
    if type(data.tokens) == "table" then self.tokens = copy(data.tokens) end
    if nonnegative_integer(data.token_sequence) then self.token_sequence = data.token_sequence end
    return self
end

function Arbiter:_target(target_id)
    local target = self.targets[target_id]
    if target == nil then
        target = {
            target_id = target_id,
            sequences = {},
            attackers = {},
            claim_token = nil,
            resolution = nil,
        }
        self.targets[target_id] = target
    end
    return target
end

function Arbiter:_expire_target(target, now)
    local token = target.claim_token
    if token == nil then return false end
    local claim = self.tokens[token]
    if claim == nil or claim.state ~= "active" then
        target.claim_token = nil
        return false
    end
    if now < claim.expires_at then return false end
    claim.state = "expired"
    target.claim_token = nil
    return true
end

function Arbiter:observe(report)
    if not valid_report(report) then return rejected("invalid_report") end
    local existing = self.targets[report.target_id]
    if existing ~= nil and existing.resolution ~= nil then return rejected("resolved") end
    local target = existing or self:_target(report.target_id)
    if target.sequences[report.sequence] then
        return {
            ok = true,
            applied = false,
            duplicate = true,
            sequence = report.sequence,
        }
    end

    target.sequences[report.sequence] = true
    local attacker = target.attackers[report.attacker_id]
    if attacker == nil then
        attacker = { total = 0, first_sequence = report.sequence }
        target.attackers[report.attacker_id] = attacker
    elseif report.sequence < attacker.first_sequence then
        attacker.first_sequence = report.sequence
    end
    attacker.total = attacker.total + report.amount
    return {
        ok = true,
        applied = true,
        duplicate = false,
        sequence = report.sequence,
    }
end

function Arbiter:claim(attacker_id, target_id, now)
    if not valid_id(attacker_id) or not valid_id(target_id) or not finite_number(now) then
        return rejected("invalid_claim")
    end
    local target = self.targets[target_id]
    if target == nil then return rejected("unknown_target") end
    if target.resolution ~= nil then return rejected("resolved") end
    self:_expire_target(target, now)
    if target.claim_token ~= nil then return rejected("claimed") end

    self.token_sequence = self.token_sequence + 1
    local token = "damage-claim-" .. tostring(self.token_sequence)
    local expires_at = now + self.options.claim_seconds
    self.tokens[token] = {
        token = token,
        attacker_id = attacker_id,
        target_id = target_id,
        expires_at = expires_at,
        state = "active",
    }
    target.claim_token = token
    return { ok = true, token = token, target_id = target_id, expires_at = expires_at }
end

function Arbiter:renew(token, now)
    if not valid_id(token) or not finite_number(now) then return rejected("unknown_token") end
    local claim = self.tokens[token]
    if claim == nil or claim.state ~= "active" then return rejected("unknown_token") end
    local target = self.targets[claim.target_id]
    if target == nil then return rejected("unknown_token") end
    self:_expire_target(target, now)
    if claim.state ~= "active" then return rejected("unknown_token") end
    claim.expires_at = now + self.options.claim_seconds
    return { ok = true, token = token, expires_at = claim.expires_at }
end

function Arbiter:release(token, now)
    if not valid_id(token) or not finite_number(now) then return rejected("unknown_token") end
    local claim = self.tokens[token]
    if claim == nil or claim.state ~= "active" then return rejected("unknown_token") end
    local target = self.targets[claim.target_id]
    if target == nil then return rejected("unknown_token") end
    self:_expire_target(target, now)
    if claim.state ~= "active" then return rejected("unknown_token") end
    claim.state = "released"
    target.claim_token = nil
    return { ok = true, token = token, state = "released" }
end

function Arbiter:resolve(target_id, now)
    if not valid_id(target_id) or not finite_number(now) then return rejected("unknown_target") end
    local target = self.targets[target_id]
    if target == nil then return rejected("unknown_target") end
    if target.resolution ~= nil then return copy(target.resolution) end
    self:_expire_target(target, now)

    local winner_id = nil
    local winner_total = -1
    local winner_first = math.huge
    for attacker_id, attacker in pairs(target.attackers) do
        if attacker.total > winner_total
            or (attacker.total == winner_total and attacker.first_sequence < winner_first)
            or (attacker.total == winner_total and attacker.first_sequence == winner_first
                and (winner_id == nil or attacker_id < winner_id)) then
            winner_id = attacker_id
            winner_total = attacker.total
            winner_first = attacker.first_sequence
        end
    end
    if winner_id == nil then return rejected("unknown_target") end
    target.resolution = {
        ok = true,
        final = true,
        target_id = target_id,
        attacker_id = winner_id,
        total = winner_total,
        resolved_at = now,
    }
    if target.claim_token ~= nil then
        local claim = self.tokens[target.claim_token]
        if claim ~= nil and claim.state == "active" then claim.state = "resolved" end
        target.claim_token = nil
    end
    return copy(target.resolution)
end

function Arbiter:sweep(now)
    if not finite_number(now) then return rejected("invalid_now") end
    local expired = 0
    for _, target in pairs(self.targets) do
        if self:_expire_target(target, now) then expired = expired + 1 end
    end
    return { ok = true, expired = expired }
end

function Arbiter:snapshot(now)
    if finite_number(now) then self:sweep(now) end
    local identifiers = {}
    for target_id in pairs(self.targets) do identifiers[#identifiers + 1] = target_id end
    table.sort(identifiers)
    local targets = {}
    for _, target_id in ipairs(identifiers) do
        local target = self.targets[target_id]
        local entry = {
            target_id = target_id,
            total = total_for(target),
            resolved = target.resolution ~= nil,
        }
        if target.resolution ~= nil then
            entry.attacker_id = target.resolution.attacker_id
            entry.attributed_total = target.resolution.total
        end
        targets[#targets + 1] = entry
    end
    return { targets = targets }
end

function Arbiter:save(now)
    if finite_number(now) then self:sweep(now) end
    return {
        targets = copy(self.targets),
        tokens = copy(self.tokens),
        token_sequence = self.token_sequence,
    }
end

return Arbiter
