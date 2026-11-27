-- Master-simulation world component. The pure escrow decides who may trade
-- what and when; this layer proves the offered items really exist in the two
-- base-game inventories and moves the real item entities between them.

local Escrow = require("tradeescrow/escrow")

local OPTIONS = {
    allowed_prefabs = { twigs = true, cutgrass = true, flint = true, log = true, rocks = true },
    max_distinct = 4,
    ttl = 120,
}
local EXPIRY_PERIOD = 1

local function userid_of(player)
    if type(player) ~= "table" then
        return nil
    end
    local userid = player.userid
    if type(userid) ~= "string" or userid == "" then
        return nil
    end
    return userid
end

local function inventory_of(player)
    return type(player) == "table" and player.components ~= nil and player.components.inventory or nil
end

local function held(player, prefab)
    local _, found = inventory_of(player):Has(prefab, 0)
    return found or 0
end

local TradeEscrow = Class(function(self, inst)
    self.inst = inst
    self.escrow = Escrow.new(OPTIONS)
    self.players = {}       -- userid -> last seen player entity
    self.next_trade = 1
    self.clock_offset = 0

    -- The same function object is kept so the listener can be removed later.
    self.on_player_left = function(_, player)
        self:OnPlayerLeft(player)
    end
    inst:ListenForEvent("ms_playerleft", self.on_player_left)
    self.expiry_task = inst:DoPeriodicTask(EXPIRY_PERIOD, function()
        self.escrow:tick(self:Now())
    end)
end)

-- GetTime() restarts from zero with the server, so the saved clock is carried
-- forward as an offset.
function TradeEscrow:Now()
    return self.clock_offset + GetTime()
end

function TradeEscrow:_remember(player)
    local userid = userid_of(player)
    if userid ~= nil and inventory_of(player) ~= nil then
        self.players[userid] = player
        return userid
    end
    return nil
end

function TradeEscrow:_entity(userid)
    local player = self.players[userid]
    if player ~= nil and player:IsValid() and inventory_of(player) ~= nil then
        return player
    end
    for _, candidate in ipairs(AllPlayers) do
        if candidate.userid == userid and candidate:IsValid() and inventory_of(candidate) ~= nil then
            self.players[userid] = candidate
            return candidate
        end
    end
    return nil
end

function TradeEscrow:_view(trade_id)
    for _, view in ipairs(self.escrow:snapshot(self:Now()).trades) do
        if view.trade_id == trade_id then
            return view
        end
    end
    return nil
end

-- Returns this party's revision and the counterparty's revision.
function TradeEscrow:_revisions(trade_id, userid)
    local view = self:_view(trade_id)
    if view == nil then
        return nil, nil
    end
    local own, other
    for _, party in ipairs(view.parties) do
        if party.id == userid then
            own = party.revision
        else
            other = party.revision
        end
    end
    return own, other
end

function TradeEscrow:Open(player_a, player_b)
    local a_id, b_id = self:_remember(player_a), self:_remember(player_b)
    if a_id == nil or b_id == nil then
        return { ok = false, code = "invalid_player" }
    end
    local trade_id = string.format("trade-%d", self.next_trade)
    local opened = self.escrow:open(trade_id, a_id, b_id, self:Now())
    if opened.ok then
        self.next_trade = self.next_trade + 1
    else
        opened.trade_id = nil
    end
    return opened
end

function TradeEscrow:Offer(player, trade_id, items)
    local userid = self:_remember(player)
    if userid == nil then
        return { ok = false, code = "invalid_player" }
    end
    if type(trade_id) ~= "string" or type(items) ~= "table" then
        return { ok = false, code = "invalid_argument" }
    end
    local own = self:_revisions(trade_id, userid)
    return self.escrow:offer(trade_id, userid, items, (own or 0) + 1, self:Now())
end

function TradeEscrow:Confirm(player, trade_id, seen_revision)
    local userid = self:_remember(player)
    if userid == nil then
        return { ok = false, code = "invalid_player" }
    end
    if type(trade_id) ~= "string" then
        return { ok = false, code = "invalid_argument" }
    end
    if seen_revision == nil then
        local _, other = self:_revisions(trade_id, userid)
        seen_revision = other or 0
    end
    local confirmed = self.escrow:confirm(trade_id, userid, seen_revision, self:Now())
    if not confirmed.ok or not confirmed.ready then
        return confirmed
    end
    return self:_settle(trade_id)
end

function TradeEscrow:Cancel(player, trade_id)
    local userid = self:_remember(player)
    if userid == nil then
        return { ok = false, code = "invalid_player" }
    end
    return self.escrow:cancel(trade_id, userid, self:Now())
end

-- ---------------------------------------------------------------------------
-- Settlement against the real inventories
-- ---------------------------------------------------------------------------

-- Takes exactly `count` units of `prefab` out of the inventory as real item
-- entities: whole stacks are removed as they are, a partial stack is split.
local function take(inventory, prefab, count)
    local pieces, taken = {}, 0
    for item, amount in pairs(inventory:GetItemByName(prefab, count)) do
        local stackable = item.components.stackable
        local piece
        if stackable ~= nil and amount < stackable:StackSize() then
            piece = stackable:Get(amount)
            if piece.components.inventoryitem ~= nil then
                piece.components.inventoryitem:OnRemoved()
            end
        else
            piece = inventory:RemoveItem(item, true)
        end
        if piece ~= nil then
            pieces[#pieces + 1] = piece
            taken = taken + amount
        end
    end
    return pieces, taken
end

-- True when the item ended up inside the receiver: merged into one of its
-- stacks (the entity is gone) or owned by it, the active item included.
local function received(item, receiver, accepted)
    if not item:IsValid() then
        return accepted ~= nil and accepted ~= false
    end
    local inventoryitem = item.components.inventoryitem
    return inventoryitem ~= nil and inventoryitem:GetGrandOwner() == receiver
end

-- Brings every (player, prefab) count back to the recorded baseline. Loose
-- pieces (still in hand or dropped on the ground) return to their giver first;
-- any surplus that did reach the other side is moved back afterwards.
function TradeEscrow:_restore(baseline, loose, players)
    for _, entry in ipairs(loose) do
        local item = entry.item
        if item:IsValid() and not received(item, players[entry.to], true) then
            inventory_of(players[entry.from]):GiveItem(item)
        end
    end
    for userid, counts in pairs(baseline) do
        local player = players[userid]
        for prefab, before in pairs(counts) do
            local surplus = held(player, prefab) - before
            if surplus > 0 then
                local pieces = take(inventory_of(player), prefab, surplus)
                for other_id, other in pairs(players) do
                    if other_id ~= userid then
                        for _, piece in ipairs(pieces) do
                            inventory_of(other):GiveItem(piece)
                        end
                    end
                end
            end
        end
    end
end

function TradeEscrow:_settle(trade_id)
    local view = self:_view(trade_id)
    local players = {}
    for _, party in ipairs(view ~= nil and view.parties or {}) do
        players[party.id] = self:_entity(party.id)
    end
    if view == nil or players[view.parties[1].id] == nil or players[view.parties[2].id] == nil then
        return { ok = false, code = "counterparty_unavailable", phase = view ~= nil and view.phase or nil }
    end

    local begun = self.escrow:begin_settle(trade_id, self:Now())
    if not begun.ok then
        return begun
    end
    local function abort(code)
        local finished = self.escrow:finish_settle(trade_id, false, self:Now())
        return { ok = false, code = code, phase = finished.phase }
    end

    -- 1. Both sides must still hold what they offered.
    local baseline = {}
    for _, row in ipairs(begun.plan) do
        if not inventory_of(players[row.from]):Has(row.prefab, row.count) then
            return abort("insufficient_items")
        end
        for _, userid in ipairs({ row.from, row.to }) do
            baseline[userid] = baseline[userid] or {}
            baseline[userid][row.prefab] = held(players[userid], row.prefab)
        end
    end

    -- 2. Take everything out of both inventories before anything is delivered.
    local loose, complete = {}, true
    for _, row in ipairs(begun.plan) do
        local pieces, taken = take(inventory_of(players[row.from]), row.prefab, row.count)
        for _, piece in ipairs(pieces) do
            loose[#loose + 1] = { item = piece, from = row.from, to = row.to }
        end
        if taken ~= row.count then
            complete = false
        end
    end

    -- 3. Deliver; ownership is confirmed instead of trusting the return value.
    if complete then
        for _, entry in ipairs(loose) do
            local accepted = inventory_of(players[entry.to]):GiveItem(entry.item)
            if not received(entry.item, players[entry.to], accepted) then
                complete = false
                break
            end
        end
    end
    if not complete then
        self:_restore(baseline, loose, players)
        return abort("delivery_failed")
    end

    local finished = self.escrow:finish_settle(trade_id, true, self:Now())
    return { ok = finished.ok, code = finished.code, phase = finished.phase }
end

-- ---------------------------------------------------------------------------
-- Lifecycle
-- ---------------------------------------------------------------------------

function TradeEscrow:OnPlayerLeft(player)
    local userid = userid_of(player)
    if userid == nil then
        return
    end
    local now = self:Now()
    for _, view in ipairs(self.escrow:snapshot(now).trades) do
        if view.phase == "open" and (view.parties[1].id == userid or view.parties[2].id == userid) then
            self.escrow:cancel(view.trade_id, userid, now)
        end
    end
    self.players[userid] = nil
end

-- A swap whose progress is unknown is never replayed: it is reopened with both
-- confirmations cleared, and the inventory check runs again on re-confirmation.
function TradeEscrow:Recover()
    local now = self:Now()
    local recovered = {}
    for _, view in ipairs(self.escrow:snapshot(now).trades) do
        if view.phase == "settling" and self.escrow:finish_settle(view.trade_id, false, now).ok then
            recovered[#recovered + 1] = view.trade_id
        end
    end
    return { ok = true, recovered = recovered }
end

function TradeEscrow:OnSave()
    local now = self:Now()
    return { escrow = self.escrow:save(now), next_trade = self.next_trade, clock = now }
end

function TradeEscrow:OnLoad(data)
    if type(data) ~= "table" then
        return
    end
    self.escrow = Escrow.load(data.escrow, OPTIONS)
    if type(data.next_trade) == "number" and data.next_trade > self.next_trade then
        self.next_trade = math.floor(data.next_trade)
    end
    if type(data.clock) == "number" then
        self.clock_offset = math.max(self.clock_offset, data.clock - GetTime())
    end
    self:Recover()
end

function TradeEscrow:OnRemoveFromEntity()
    if self.on_player_left ~= nil then
        self.inst:RemoveEventCallback("ms_playerleft", self.on_player_left)
        self.on_player_left = nil
    end
    if self.expiry_task ~= nil then
        self.expiry_task:Cancel()
        self.expiry_task = nil
    end
    self.players = {}
end

return TradeEscrow
