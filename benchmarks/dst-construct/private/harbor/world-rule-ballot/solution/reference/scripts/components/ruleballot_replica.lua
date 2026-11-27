-- Read-only replica. The server writes one compact aggregate string; clients
-- decode it on the dirty event. Individual votes are never replicated.

local function decode_state(encoded)
    if type(encoded) ~= "string" or encoded == "" then
        return nil
    end
    local fields = {}
    for field in string.gmatch(encoded .. "|", "([^|]*)|") do
        fields[#fields + 1] = field
    end
    local counts = {}
    for choice_id, count in string.gmatch(fields[7] or "", "([^=,]+)=(%d+)") do
        counts[#counts + 1] = { choice_id = choice_id, count = tonumber(count) }
    end
    return {
        proposal_id = fields[1],
        status = fields[2],
        choice_id = fields[3] ~= "" and fields[3] or nil,
        deadline = tonumber(fields[4]),
        participants = tonumber(fields[5]),
        electorate_size = tonumber(fields[6]),
        counts = counts,
    }
end

local RuleBallotReplica = Class(function(self, inst)
    self.inst = inst
    self._state = net_string(inst.GUID, "ruleballot.state", "ruleballotdirty")
    self.public_state = nil

    if not inst.ismastersim then
        inst:ListenForEvent("ruleballotdirty", function()
            self.public_state = decode_state(self._state:value())
            inst:PushEvent("ruleballotchanged", self.public_state)
        end)
    end
end)

function RuleBallotReplica:SetState(encoded)
    if self.inst.ismastersim then
        self._state:set(encoded)
        self.public_state = decode_state(encoded)
    end
end

function RuleBallotReplica:GetState()
    if self.public_state == nil then
        self.public_state = decode_state(self._state:value())
    end
    return self.public_state
end

return RuleBallotReplica
