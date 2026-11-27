-- campsupplyledger: world component (master simulation only).
--
-- Flow of one claim:
--   1. reserve in the pure ledger (quota is held, nothing is handed out yet)
--   2. stage: spawn every stack of the bundle while it still belongs to nobody
--   3. hand over: give the staged stacks one at a time, checking the real owner
--   4. commit when every stack arrived; otherwise undo the hand-over and roll back
-- Staging first means a prefab that cannot be spawned never touches the player.

local Ledger = require("campsupply/ledger")

local SUPPLY_OPTIONS = {
    bundles = {
        basic = { twigs = 2, cutgrass = 1 },
        campfire_kit = { log = 2, cutgrass = 3 },
        tool_kit = { flint = 2, twigs = 2 },
    },
    daily_limits = { twigs = 4, cutgrass = 4, log = 4, flint = 2 },
}

local function held(inventory, prefab)
    local _, amount = inventory:Has(prefab, 1)
    return amount or 0
end

local function discard(item)
    if item ~= nil and item:IsValid() then
        item:Remove()
    end
end

local function belongs_to(item, player)
    local part = item.components.inventoryitem
    return part ~= nil and part:GetGrandOwner() == player
end

-- The world carries exactly one ledger component. It is remembered here so the
-- save entry point still works when a caller invokes it as a plain function
-- (`component.OnSave()`), without the receiver the engine normally passes.
local attached = nil

local CampSupplyLedger = Class(function(self, inst)
    self.inst = inst
    attached = self
    self.book = Ledger.new(SUPPLY_OPTIONS)
    self.staged = {}
    self.watching = {}

    local cycles = inst.state ~= nil and inst.state.cycles or 0
    self.book:begin_day(self:NormalizeDay(cycles))

    self:Watch("ms_cyclecomplete", function()
        self:OnCycleComplete()
    end)
    self:Watch("ms_playerleft", function(_, player)
        if player ~= nil and type(player.userid) == "string" then
            self.book:set_player(player.userid, false)
        end
    end)
end)

-- Every long-lived listener is registered through here so that it can be
-- removed with the identical function object and source.
function CampSupplyLedger:Watch(event, handler)
    self.watching[#self.watching + 1] = { event = event, handler = handler, source = TheWorld or self.inst }
    local entry = self.watching[#self.watching]
    self.inst:ListenForEvent(entry.event, entry.handler, entry.source)
end

function CampSupplyLedger:NormalizeDay(value)
    if type(value) ~= "number" or value ~= value or value < 0 then
        return 0
    end
    return math.floor(value)
end

function CampSupplyLedger:OnCycleComplete()
    local known = self.book:current_day() or 0
    local cycles = self:NormalizeDay(self.inst.state ~= nil and self.inst.state.cycles or 0)
    -- The clock may publish the event before or after the cycle counter moves,
    -- so the ledger day advances by at least one and never runs behind.
    local target = known + 1
    if cycles > target then
        target = cycles
    end
    self.book:begin_day(target)
end

function CampSupplyLedger:Stage(lines)
    local batch = {}
    for _, line in ipairs(lines) do
        local left = line.count
        while left > 0 do
            local item = SpawnPrefab(line.prefab)
            if item == nil or item.components.inventoryitem == nil then
                discard(item)
                return nil, batch
            end
            local size = 1
            if item.components.stackable ~= nil then
                size = math.min(left, item.components.stackable.maxsize or 1)
                item.components.stackable:SetStackSize(size)
            end
            batch[#batch + 1] = { item = item, prefab = line.prefab, size = size }
            self.staged[item] = true
            left = left - size
        end
    end
    return batch
end

function CampSupplyLedger:Unstage(batch)
    for _, slot in ipairs(batch) do
        self.staged[slot.item] = nil
        discard(slot.item)
    end
end

-- Gives the staged stacks in order. Returns true only when every stack is
-- really in the player's possession afterwards.
function CampSupplyLedger:HandOver(player, batch, baseline)
    local inventory = player.components.inventory
    local expected = {}
    for _, slot in ipairs(batch) do
        self.staged[slot.item] = nil
        local accepted = inventory:GiveItem(slot.item)
        expected[slot.prefab] = (expected[slot.prefab] or 0) + slot.size
        local merged = not slot.item:IsValid()
        local owned = not merged and belongs_to(slot.item, player)
        if not accepted or not (merged or owned) then
            return false
        end
        if held(inventory, slot.prefab) - baseline[slot.prefab] ~= expected[slot.prefab] then
            return false
        end
    end
    return true
end

-- Removes whatever this request added: stray entities first (dropped, active
-- or still slotted), then any amount that was merged into an older stack.
function CampSupplyLedger:TakeBack(player, batch, baseline)
    local inventory = player.components.inventory
    for _, slot in ipairs(batch) do
        self.staged[slot.item] = nil
        if slot.item:IsValid() then
            if belongs_to(slot.item, player) then
                inventory:RemoveItem(slot.item, true)
            end
            discard(slot.item)
        end
    end
    for prefab, before in pairs(baseline) do
        local surplus = held(inventory, prefab) - before
        if surplus > 0 then
            inventory:ConsumeByName(prefab, surplus)
        end
    end
end

function CampSupplyLedger:Claim(player, request_id, bundle_id)
    if type(player) ~= "table" or type(player.userid) ~= "string" or player.userid == "" then
        return { ok = false, status = "rejected", reason = "no_identity" }
    end
    local inventory = player.components ~= nil and player.components.inventory or nil
    if inventory == nil then
        return { ok = false, status = "rejected", reason = "no_inventory" }
    end

    local userid = player.userid
    self.book:set_player(userid, true)
    local reservation = self.book:claim(userid, request_id, bundle_id, self.book:current_day())
    if reservation.replayed or reservation.status ~= "pending" then
        -- first-time rejection, or a retry: the stored outcome is the answer
        return reservation
    end

    local baseline = {}
    for _, line in ipairs(reservation.items) do
        baseline[line.prefab] = held(inventory, line.prefab)
    end

    local batch, partial = self:Stage(reservation.items)
    if batch == nil then
        self:Unstage(partial)
        local undone = self.book:rollback(reservation.token)
        return { ok = false, status = undone.status, reason = "spawn_failed", token = reservation.token }
    end

    if not self:HandOver(player, batch, baseline) then
        self:TakeBack(player, batch, baseline)
        local undone = self.book:rollback(reservation.token)
        return { ok = false, status = undone.status, reason = "inventory_refused", token = reservation.token }
    end

    local done = self.book:commit(reservation.token)
    return { ok = done.ok, status = done.status, token = reservation.token, items = reservation.items }
end

function CampSupplyLedger:GetDebugString()
    local view = self.book:snapshot()
    return string.format("day %s, %d players, %d tokens", tostring(view.day), #view.players, #view.tokens)
end

function CampSupplyLedger:OnSave()
    local me = self or attached
    return { book = me.book:save() }
end

function CampSupplyLedger:OnLoad(data)
    if type(self) ~= "table" or self.book == nil then
        -- called without a receiver: the first argument is the saved data
        return attached ~= nil and attached:OnLoad(self) or nil
    end
    if type(data) ~= "table" or type(data.book) ~= "table" then
        return
    end
    self.book = Ledger.load(data.book, SUPPLY_OPTIONS)
    local cycles = self:NormalizeDay(self.inst.state ~= nil and self.inst.state.cycles or 0)
    local known = self.book:current_day()
    if known == nil or cycles > known then
        self.book:begin_day(cycles)
    end
end

function CampSupplyLedger:OnRemoveFromEntity()
    for index = #self.watching, 1, -1 do
        local entry = self.watching[index]
        self.inst:RemoveEventCallback(entry.event, entry.handler, entry.source)
        self.watching[index] = nil
    end
    for item in pairs(self.staged) do
        discard(item)
    end
    self.staged = {}
    if attached == self then
        attached = nil
    end
end

CampSupplyLedger.OnRemoveEntity = CampSupplyLedger.OnRemoveFromEntity

return CampSupplyLedger
