-- Read-only replica. The server publishes one compact string with the open
-- queue and the active leases; request history never leaves the server.
--   queue entry: target,effective_severity,x,z
--   lease entry: lease_id,target,helper,expires_at
--   state:       <queue entries joined by ;>|<lease entries joined by ;>

local function split(text, separator)
    local parts = {}
    if text == nil or text == "" then
        return parts
    end
    for part in string.gmatch(text .. separator, "([^" .. separator .. "]*)" .. separator) do
        parts[#parts + 1] = part
    end
    return parts
end

local function decode_state(encoded)
    local state = { queue = {}, leases = {} }
    if type(encoded) ~= "string" or encoded == "" then
        return state
    end
    local sections = split(encoded, "|")
    for _, entry in ipairs(split(sections[1], ";")) do
        local fields = split(entry, ",")
        if fields[1] ~= nil and fields[1] ~= "" then
            state.queue[#state.queue + 1] = {
                target_id = fields[1],
                effective_severity = tonumber(fields[2]),
                x = tonumber(fields[3]),
                z = tonumber(fields[4]),
            }
        end
    end
    for _, entry in ipairs(split(sections[2], ";")) do
        local fields = split(entry, ",")
        if fields[1] ~= nil and fields[1] ~= "" then
            state.leases[#state.leases + 1] = {
                lease_id = fields[1],
                target_id = fields[2],
                helper_id = fields[3],
                expires_at = tonumber(fields[4]),
            }
        end
    end
    return state
end

local RescueDispatchReplica = Class(function(self, inst)
    self.inst = inst
    self._state = net_string(inst.GUID, "rescuedispatch.state", "rescuedispatchdirty")
    self.public_state = nil

    if not inst.ismastersim then
        inst:ListenForEvent("rescuedispatchdirty", function()
            self.public_state = decode_state(self._state:value())
            inst:PushEvent("rescuedispatchchanged", self.public_state)
        end)
    end
end)

function RescueDispatchReplica:SetState(encoded)
    if self.inst.ismastersim and self._state:value() ~= encoded then
        self._state:set(encoded)
        self.public_state = decode_state(encoded)
    end
end

function RescueDispatchReplica:GetState()
    if self.public_state == nil then
        self.public_state = decode_state(self._state:value())
    end
    return self.public_state
end

return RescueDispatchReplica
