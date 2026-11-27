-- Master-simulation world component. It owns the authoritative arbiter,
-- derives identity from player entities, keeps one deadline task per open
-- roll, and turns an award into exactly one real inventory item.

local Arbiter = require("lootroll/arbiter")

local ALLOWED_ITEMS = {
    "goldnugget", "gears", "redgem", "bluegem", "purplegem",
    "deerclops_eyeball", "bearger_fur", "dragon_scales", "goose_feather", "minotaurhorn",
}

local function arbiter_options(now)
    return {
        window = 30,
        allowed_items = ALLOWED_ITEMS,
        max_wins_per_window = 2,
        fairness_window = 600,
        max_rounds = 3,
        now = now,
    }
end

local LootRollArbiter = Class(function(self, inst)
    self.inst = inst
    self.core = Arbiter.new(arbiter_options(nil))
    self.tasks = {}
    self.pending = {}
    self.players = {}
    self.next_roll = 1

    -- A departing player stays in every frozen eligible set; only the cached
    -- entity is forgotten so a later delivery resolves the userid again.
    self._on_player_left = function(_, player)
        if type(player) == "table" and type(player.userid) == "string" then
            self.players[player.userid] = nil
        end
    end
    inst:ListenForEvent("ms_playerleft", self._on_player_left)
end)

function LootRollArbiter:_cancel_task(roll_id)
    local task = self.tasks[roll_id]
    if task ~= nil then
        task:Cancel()
        self.tasks[roll_id] = nil
    end
end

function LootRollArbiter:_schedule(roll_id, deadline)
    self:_cancel_task(roll_id)
    self.pending[roll_id] = true
    local delay = math.max(0, deadline - GetTime())
    self.tasks[roll_id] = self.inst:DoTaskInTime(delay, function()
        self.tasks[roll_id] = nil
        self:Resolve(roll_id)
    end)
end

function LootRollArbiter:_publish()
    local netvar = self.inst._lootroll_state
    if netvar == nil then
        return
    end
    local snapshot = self.core:snapshot(GetTime())
    local parts = {}
    for _, entry in ipairs(snapshot.rolls) do
        if entry.status == "open" then
            parts[#parts + 1] = string.format("%s|%s|%d|%d", entry.roll_id, entry.item, entry.chosen, entry.total)
        end
    end
    netvar:set(table.concat(parts, ";"))
end

function LootRollArbiter:_find_player(userid)
    local cached = self.players[userid]
    if cached ~= nil and cached:IsValid() and cached.userid == userid then
        return cached
    end
    self.players[userid] = nil
    for _, player in ipairs(AllPlayers) do
        if player.userid == userid and player:IsValid() then
            return player
        end
    end
    return nil
end

-- Creates the item only when there is an inventory to receive it, and never
-- trusts GiveItem alone: a full inventory drops the item on the ground.
function LootRollArbiter:_deliver(item_prefab, userid)
    local player = self:_find_player(userid)
    local inventory = player ~= nil and player.components.inventory or nil
    if inventory == nil then
        return false
    end
    local item = SpawnPrefab(item_prefab)
    if item == nil then
        return false
    end
    if item.components.inventoryitem == nil then
        item:Remove()
        return false
    end
    local accepted = inventory:GiveItem(item)
    -- A stackable item merged into an existing stack is consumed by GiveItem.
    local merged = not item:IsValid()
    if accepted and (merged or item.components.inventoryitem:GetGrandOwner() == player) then
        return true
    end
    if not merged then
        item:Remove()
    end
    return false
end

function LootRollArbiter:_announce(result)
    if TheNet == nil then
        return
    end
    if result.status == "delivered" then
        TheNet:Announce(string.format("Loot roll %s: %s wins %s (%s)", result.roll_id, result.winner, result.item, result.tier))
    else
        TheNet:Announce(string.format("Loot roll %s: %s is %s", result.roll_id, result.item, result.status))
    end
end

-- Server-side entry only; the RPC handler never reaches this method.
function LootRollArbiter:Open(item_prefab, player_entities, seed)
    local ids, entities = {}, {}
    if type(player_entities) == "table" then
        for _, player in ipairs(player_entities) do
            if type(player) == "table" and type(player.userid) == "string" and player.userid ~= "" then
                ids[#ids + 1] = player.userid
                entities[player.userid] = player
            end
        end
    end
    if seed == nil then
        seed = math.random(0, 2147483646)
    end
    local roll_id = "roll-" .. string.format("%d", self.next_roll)
    local opened = self.core:open(roll_id, item_prefab, ids, seed, GetTime())
    if opened.ok then
        self.next_roll = self.next_roll + 1
        for userid, player in pairs(entities) do
            self.players[userid] = player
        end
        self:_schedule(roll_id, opened.deadline)
        self:_publish()
    end
    return opened
end

function LootRollArbiter:Choose(player, roll_id, choice, revision)
    local userid = type(player) == "table" and player.userid or nil
    if type(userid) ~= "string" or userid == "" then
        return { ok = false, code = "not_eligible" }
    end
    local chosen = self.core:choose(roll_id, userid, choice, revision, GetTime())
    if chosen.ok then
        if chosen.complete then
            self:Resolve(roll_id)
        else
            self:_publish()
        end
    end
    return chosen
end

function LootRollArbiter:Resolve(roll_id)
    local now = GetTime()
    local result = self.core:resolve(roll_id, now)
    if not result.ok then
        return result
    end
    local first_settlement = self.pending[roll_id] == true
    self.pending[roll_id] = nil
    self:_cancel_task(roll_id)
    -- Each failed attempt is reported once, which moves the award to the next
    -- candidate; a candidate never comes back, so the loop terminates.
    local delivering = false
    while result.ok and result.status == "awarded" do
        delivering = true
        result = self.core:mark_delivered(roll_id, self:_deliver(result.item, result.winner), now)
    end
    if first_settlement or delivering then
        self:_announce(result)
        self:_publish()
    end
    return result
end

function LootRollArbiter:Cancel(roll_id)
    local result = self.core:cancel(roll_id, GetTime())
    if result.ok then
        self.pending[roll_id] = nil
        self:_cancel_task(roll_id)
        self:_announce(result)
        self:_publish()
    end
    return result
end

function LootRollArbiter:GetPublicState()
    return self.core:snapshot(GetTime())
end

function LootRollArbiter:OnSave()
    return { core = self.core:save(GetTime()), next_roll = self.next_roll }
end

function LootRollArbiter:OnLoad(data)
    for roll_id in pairs(self.tasks) do
        self:_cancel_task(roll_id)
    end
    self.pending = {}
    if type(data) ~= "table" or type(data.core) ~= "table" then
        return
    end
    -- The engine clock restarts with the process, so stored deadlines and
    -- ledger times are rebased onto the current clock.
    self.core = Arbiter.load(data.core, arbiter_options(GetTime()))
    if type(data.next_roll) == "number" and data.next_roll > self.next_roll then
        self.next_roll = data.next_roll
    end
    local snapshot = self.core:snapshot(GetTime())
    for _, entry in ipairs(snapshot.rolls) do
        if entry.status == "open" then
            self:_schedule(entry.roll_id, entry.deadline)
        elseif entry.status == "awarded" then
            -- Delivery is synchronous, so this only happens for foreign data.
            self:Resolve(entry.roll_id)
        end
    end
    self:_publish()
end

function LootRollArbiter:OnRemoveFromEntity()
    for roll_id in pairs(self.tasks) do
        self:_cancel_task(roll_id)
    end
    self.pending = {}
    self.inst:RemoveEventCallback("ms_playerleft", self._on_player_left)
end

LootRollArbiter.OnRemoveEntity = LootRollArbiter.OnRemoveFromEntity

return LootRollArbiter
