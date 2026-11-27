local EscrowCore = require("tradeescrow/escrow")

local CONFIG = {
    allowed_prefabs = { twigs = true, cutgrass = true, flint = true, log = true, rocks = true },
    max_distinct = 4,
    ttl = 120,
}

-- ---------------------------------------------------------------------------
-- Inventory helpers (plain functions over base-game components)
-- ---------------------------------------------------------------------------

local function bag(entity)
    return entity ~= nil and entity.components ~= nil and entity.components.inventory or nil
end

local function quantity(entity, prefab)
    local _, total = bag(entity):Has(prefab, 0)
    return total or 0
end

local function stack_size(item)
    return item.components.stackable ~= nil and item.components.stackable:StackSize() or 1
end

-- Lowest slots first so the same request always drains the same stacks.
local function stacks_of(entity, prefab)
    local inventory = bag(entity)
    local found = inventory:FindItems(function(item) return item.prefab == prefab end)
    local slot_of = {}
    for _, item in ipairs(found) do
        slot_of[item] = inventory:GetItemSlot(item) or 1000
    end
    table.sort(found, function(left, right)
        if slot_of[left] ~= slot_of[right] then
            return slot_of[left] < slot_of[right]
        end
        return left.GUID < right.GUID
    end)
    return found
end

-- Hands `amount` units of one stack to `receiver`. Returns how many units
-- verifiably arrived; anything that did not arrive goes straight back.
local function hand_over(giver, receiver, item, amount)
    local piece
    if amount < stack_size(item) then
        piece = item.components.stackable:Get(amount)
    else
        piece = bag(giver):RemoveItem(item, true)
    end
    if piece == nil then
        return 0
    end
    local before = quantity(receiver, piece.prefab)
    local prefab = piece.prefab
    bag(receiver):GiveItem(piece)
    local arrived = quantity(receiver, prefab) - before
    if arrived < amount and piece:IsValid() then
        local owner = piece.components.inventoryitem ~= nil and piece.components.inventoryitem:GetGrandOwner() or nil
        if owner ~= receiver then
            bag(giver):GiveItem(piece)
        end
    end
    return arrived
end

-- Moves exactly `amount` units, stack by stack. Returns the units that arrived.
local function move(giver, receiver, prefab, amount)
    local moved = 0
    for _, item in ipairs(stacks_of(giver, prefab)) do
        if moved >= amount then
            break
        end
        local want = math.min(amount - moved, stack_size(item))
        local arrived = hand_over(giver, receiver, item, want)
        moved = moved + arrived
        if arrived < want then
            break
        end
    end
    return moved
end

-- ---------------------------------------------------------------------------
-- Component
-- ---------------------------------------------------------------------------

local TradeEscrow = Class(function(self, inst)
    self.inst = inst
    self.escrow = EscrowCore.new(CONFIG)
    self.roster = {}
    self.sequence = 0
    self.epoch = 0
    self._departure = function(_, player) self:OnPlayerLeft(player) end
    self.inst:ListenForEvent("ms_playerleft", self._departure)
    self._sweeper = self.inst:DoPeriodicTask(2, function() self.escrow:tick(self:Now()) end)
end)

function TradeEscrow:Now()
    return self.epoch + GetTime()
end

local function identity(player)
    if type(player) == "table" and type(player.userid) == "string" and player.userid ~= "" and bag(player) ~= nil then
        return player.userid
    end
    return nil
end

function TradeEscrow:Enroll(player)
    local userid = identity(player)
    if userid ~= nil then
        self.roster[userid] = player
    end
    return userid
end

function TradeEscrow:Resolve(userid)
    local known = self.roster[userid]
    if known == nil or not known:IsValid() then
        known = nil
        for _, online in ipairs(AllPlayers) do
            if online.userid == userid then
                known = online
            end
        end
        self.roster[userid] = known
    end
    if known ~= nil and known:IsValid() and bag(known) ~= nil then
        return known
    end
    return nil
end

function TradeEscrow:Lookup(trade_id)
    local trades = self.escrow:snapshot(self:Now()).trades
    for index = 1, #trades do
        if trades[index].trade_id == trade_id then
            return trades[index]
        end
    end
    return nil
end

function TradeEscrow:RevisionOf(trade_id, userid, want_other)
    local trade = self:Lookup(trade_id)
    if trade == nil then
        return 0
    end
    for _, party in ipairs(trade.parties) do
        if (party.id == userid) ~= want_other then
            return party.revision
        end
    end
    return 0
end

function TradeEscrow:Open(player_a, player_b)
    local a, b = self:Enroll(player_a), self:Enroll(player_b)
    if not (a and b) then
        return { ok = false, code = "invalid_player" }
    end
    self.sequence = self.sequence + 1
    local outcome = self.escrow:open("escrow#" .. string.format("%06d", self.sequence), a, b, self:Now())
    return { ok = outcome.ok, code = outcome.code, phase = outcome.phase, expires_at = outcome.expires_at,
        trade_id = outcome.ok and outcome.trade_id or nil }
end

function TradeEscrow:Offer(player, trade_id, items)
    local userid = self:Enroll(player)
    if userid == nil then
        return { ok = false, code = "invalid_player" }
    end
    local copy = {}
    if type(items) == "table" then
        for prefab, count in pairs(items) do
            copy[prefab] = count
        end
    else
        copy = items
    end
    return self.escrow:offer(trade_id, userid, copy, self:RevisionOf(trade_id, userid, false) + 1, self:Now())
end

function TradeEscrow:Confirm(player, trade_id, seen_revision)
    local userid = self:Enroll(player)
    if userid == nil then
        return { ok = false, code = "invalid_player" }
    end
    local seen = seen_revision
    if seen == nil then
        seen = self:RevisionOf(trade_id, userid, true)
    end
    local outcome = self.escrow:confirm(trade_id, userid, seen, self:Now())
    if outcome.ok and outcome.ready then
        return self:Settle(trade_id)
    end
    return outcome
end

function TradeEscrow:Cancel(player, trade_id)
    local userid = self:Enroll(player)
    if userid == nil then
        return { ok = false, code = "invalid_player" }
    end
    return self.escrow:cancel(trade_id, userid, self:Now())
end

-- Journalled settlement: each plan row is moved straight from giver to
-- receiver and logged; a failure undoes the journal newest-first.
function TradeEscrow:Settle(trade_id)
    local trade = self:Lookup(trade_id)
    if trade == nil then
        return { ok = false, code = "unknown_trade" }
    end
    local entity = {}
    for _, party in ipairs(trade.parties) do
        entity[party.id] = self:Resolve(party.id)
        if entity[party.id] == nil then
            return { ok = false, code = "counterparty_unavailable", phase = trade.phase }
        end
    end

    local started = self.escrow:begin_settle(trade_id, self:Now())
    if not started.ok then
        return started
    end

    local verdict = nil
    for _, row in ipairs(started.plan) do
        if not bag(entity[row.from]):Has(row.prefab, row.count) then
            verdict = "insufficient_items"
            break
        end
    end

    local journal = {}
    if verdict == nil then
        for _, row in ipairs(started.plan) do
            local arrived = move(entity[row.from], entity[row.to], row.prefab, row.count)
            if arrived > 0 then
                journal[#journal + 1] = { from = row.from, to = row.to, prefab = row.prefab, count = arrived }
            end
            if arrived ~= row.count then
                verdict = "delivery_failed"
                break
            end
        end
    end

    if verdict ~= nil then
        for index = #journal, 1, -1 do
            local entry = journal[index]
            move(entity[entry.to], entity[entry.from], entry.prefab, entry.count)
        end
        local reopened = self.escrow:finish_settle(trade_id, false, self:Now())
        return { ok = false, code = verdict, phase = reopened.phase }
    end

    local done = self.escrow:finish_settle(trade_id, true, self:Now())
    return { ok = done.ok, code = done.code, phase = done.phase }
end

function TradeEscrow:OnPlayerLeft(player)
    local userid = type(player) == "table" and player.userid or nil
    if type(userid) ~= "string" then
        return
    end
    local now = self:Now()
    local trades = self.escrow:snapshot(now).trades
    for _, trade in ipairs(trades) do
        local involved = trade.parties[1].id == userid or trade.parties[2].id == userid
        if involved and trade.phase == "open" then
            self.escrow:cancel(trade.trade_id, userid, now)
        end
    end
    self.roster[userid] = nil
end

function TradeEscrow:Recover()
    local reopened = {}
    local now = self:Now()
    for _, trade in ipairs(self.escrow:snapshot(now).trades) do
        if trade.phase == "settling" then
            local outcome = self.escrow:finish_settle(trade.trade_id, false, now)
            if outcome.ok then
                table.insert(reopened, trade.trade_id)
            end
        end
    end
    table.sort(reopened)
    return { ok = true, recovered = reopened }
end

function TradeEscrow:OnSave()
    local now = self:Now()
    return { core = self.escrow:save(now), sequence = self.sequence, now = now }
end

function TradeEscrow:OnLoad(data)
    if data == nil then
        return
    end
    self.escrow = EscrowCore.load(data.core, CONFIG)
    self.sequence = math.max(self.sequence, tonumber(data.sequence) or 0)
    if type(data.now) == "number" then
        local epoch = data.now - GetTime()
        if epoch > self.epoch then
            self.epoch = epoch
        end
    end
    self:Recover()
end

function TradeEscrow:OnRemoveFromEntity()
    self.inst:RemoveEventCallback("ms_playerleft", self._departure)
    if self._sweeper ~= nil then
        self._sweeper:Cancel()
        self._sweeper = nil
    end
    self.roster = {}
end

return TradeEscrow
