-- Read-only view of the public ballot state. The server writes one compact
-- JSON document of aggregates into the world's net_string; this class only
-- decodes it. It has no setter for votes because votes are never replicated.

local STATE_EVENT = "ruleballotdirty"

local function decode(text)
    if type(text) ~= "string" or text == "" then
        return nil
    end
    local ok, value = pcall(json.decode, text)
    if ok and type(value) == "table" then
        return value
    end
    return nil
end

local RuleBallotView = Class(function(self, inst)
    self.inst = inst
    if inst._ballot_state == nil then
        -- Entities that did not go through the world post-init still get the
        -- variable here, before any master-only branch.
        inst._ballot_state = net_string(inst.GUID, "ruleballot.state", STATE_EVENT)
    end
    self.netvar = inst._ballot_state
    self.cached_text = nil
    self.cached_view = nil
end)

function RuleBallotView:Publish(text)
    if not self.inst.ismastersim or type(text) ~= "string" then
        return false
    end
    if text ~= self.netvar:value() then
        self.netvar:set(text)
    end
    return true
end

function RuleBallotView:Refresh()
    local text = self.netvar:value()
    if text ~= self.cached_text then
        self.cached_text = text
        self.cached_view = decode(text)
        self.inst:PushEvent("ruleballot_viewchanged", { view = self.cached_view })
    end
    return self.cached_view
end

function RuleBallotView:GetView()
    return self:Refresh()
end

function RuleBallotView:GetCount(choice_id)
    local view = self:Refresh()
    for _, row in ipairs(view ~= nil and view.counts or {}) do
        if row.choice_id == choice_id then
            return row.count
        end
    end
    return 0
end

function RuleBallotView:IsOpen()
    local view = self:Refresh()
    return view ~= nil and view.status == "open"
end

return RuleBallotView
