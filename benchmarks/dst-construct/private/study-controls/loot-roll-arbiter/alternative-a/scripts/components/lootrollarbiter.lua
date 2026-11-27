-- World component that owns the loot roll arbiter on the master simulation.
--
-- The pure arbiter decides who wins; this component supplies the server
-- clock, turns an award into a real inventory item, keeps one deadline task
-- per unsettled roll, publishes a choice-free summary through the world net
-- variable and persists everything through OnSave / OnLoad.

local Arbiter = require("lootroll/arbiter")

local ALLOWED_ITEMS = {
    "goldnugget",
    "gears",
    "redgem",
    "bluegem",
    "purplegem",
    "deerclops_eyeball",
    "bearger_fur",
    "dragon_scales",
    "goose_feather",
    "minotaurhorn",
}

local RETRY_DELAY = 1 / 30

local function make_options(now)
    local items = {}
    for i = 1, #ALLOWED_ITEMS do
        items[i] = ALLOWED_ITEMS[i]
    end
    return {
        window = 30,
        allowed_items = items,
        max_wins_per_window = 2,
        fairness_window = 600,
        max_rounds = 3,
        now = now,
    }
end

local function valid_userid(entity)
    if type(entity) ~= "table" then
        return nil
    end
    local userid = entity.userid
    if type(userid) == "string" and userid ~= "" then
        return userid
    end
    return nil
end

-- Server generated seed covering the whole 0 .. 4294967295 range.
local function random_seed()
    return math.random(0, 65535) * 65536 + math.random(0, 65535)
end

-- Gives one `prefab` to `player` and verifies that it really ended up in the
-- player's inventory. Returns true on success. On failure nothing is left in
-- the world: either nothing was spawned or the spawned item was removed.
local function deliver_item(player, prefab)
    if player == nil or player.components == nil then
        return false
    end
    local inventory = player.components.inventory
    if inventory == nil then
        return false
    end
    local item = SpawnPrefab(prefab)
    if item == nil then
        return false
    end
    local accepted = inventory:GiveItem(item)
    if accepted then
        if not item:IsValid() then
            -- The item was merged into a stack the player already carried.
            return true
        end
        local inventoryitem = item.components.inventoryitem
        if inventoryitem ~= nil and inventoryitem:GetGrandOwner() == player then
            return true
        end
    end
    if item:IsValid() then
        item:Remove()
    end
    return false
end

local LootRollArbiter = Class(function(self, inst)
    self.inst = inst
    self.arbiter = Arbiter.new(make_options(nil))

    -- Roll ids look like "lr-<generation>-<serial>". The serial never goes
    -- backwards and is persisted; the generation grows on every OnLoad.
    self.generation = 1
    self.serial = 0

    -- Unsettled rolls: roll id -> { deadline = , task = , entities = {} }.
    self.pending = {}

    self._on_player_left = function(_, player)
        self:ForgetPlayer(player)
    end
    inst:ListenForEvent("ms_playerleft", self._on_player_left)
end)

---------------------------------------------------------------------------
-- Internal helpers
---------------------------------------------------------------------------

function LootRollArbiter:CancelTask(roll_id)
    local entry = self.pending[roll_id]
    if entry ~= nil and entry.task ~= nil then
        entry.task:Cancel()
        entry.task = nil
    end
end

function LootRollArbiter:ScheduleDeadline(roll_id, minimum_delay)
    local entry = self.pending[roll_id]
    if entry == nil then
        return
    end
    self:CancelTask(roll_id)
    local delay = math.max(minimum_delay or 0, entry.deadline - GetTime())
    entry.task = self.inst:DoTaskInTime(delay, function()
        self:OnDeadline(roll_id)
    end)
end

function LootRollArbiter:OnDeadline(roll_id)
    local entry = self.pending[roll_id]
    if entry == nil then
        return
    end
    entry.task = nil
    local result = self:Resolve(roll_id)
    if not result.ok and result.code == "not_ready" then
        -- The task fired a hair before the deadline; try again next frame.
        self:ScheduleDeadline(roll_id, RETRY_DELAY)
    end
end

-- Drops every cached entity of a departing player. Frozen eligibility lists
-- live inside the arbiter and are never touched here.
function LootRollArbiter:ForgetPlayer(player)
    if player == nil then
        return
    end
    local userid = valid_userid(player)
    for _, entry in pairs(self.pending) do
        if userid ~= nil then
            entry.entities[userid] = nil
        end
        for cached_id, cached in pairs(entry.entities) do
            if cached == player then
                entry.entities[cached_id] = nil
            end
        end
    end
end

function LootRollArbiter:FindPlayer(roll_id, userid)
    local entry = self.pending[roll_id]
    if entry ~= nil then
        local cached = entry.entities[userid]
        if cached ~= nil then
            if cached:IsValid() then
                return cached
            end
            entry.entities[userid] = nil
        end
    end
    if AllPlayers ~= nil then
        for _, player in ipairs(AllPlayers) do
            if player.userid == userid then
                return player
            end
        end
    end
    return nil
end

-- Encodes every open roll as "roll_id|item|chosen|total" joined by ";".
-- Neither choices nor player ids ever enter this string.
function LootRollArbiter:PublishState()
    local netvar = self.inst._lootroll_state
    if netvar == nil then
        return
    end
    local parts = {}
    local snapshot = self.arbiter:snapshot(GetTime())
    if snapshot.ok then
        for i = 1, #snapshot.rolls do
            local roll = snapshot.rolls[i]
            if roll.status == "open" then
                parts[#parts + 1] = string.format("%s|%s|%d|%d", roll.roll_id, roll.item, roll.chosen, roll.total)
            end
        end
    end
    netvar:set(table.concat(parts, ";"))
end

function LootRollArbiter:AnnounceResult(result, winner_entity)
    if TheNet == nil then
        return
    end
    local message
    if result.status == "delivered" then
        local name = result.winner
        if winner_entity ~= nil and type(winner_entity.name) == "string" and winner_entity.name ~= "" then
            name = winner_entity.name
        end
        message = string.format("[Loot Roll] %s: %s was awarded to %s.", result.roll_id, result.item, name)
    elseif result.status == "canceled" then
        message = string.format("[Loot Roll] %s: the roll for %s was canceled.", result.roll_id, result.item)
    else
        message = string.format("[Loot Roll] %s: nobody claimed %s.", result.roll_id, result.item)
    end
    TheNet:Announce(message)
end

-- Called once when a tracked roll reaches a final status.
function LootRollArbiter:Finish(roll_id, result, winner_entity)
    self:CancelTask(roll_id)
    self.pending[roll_id] = nil
    self:AnnounceResult(result, winner_entity)
    self:PublishState()
end

---------------------------------------------------------------------------
-- Public interface
---------------------------------------------------------------------------

-- Server side only. Returns the arbiter's open() result table.
function LootRollArbiter:Open(item_prefab, player_entities, seed)
    local ids, entities = {}, {}
    if type(player_entities) == "table" then
        for i = 1, #player_entities do
            local entity = player_entities[i]
            local userid = valid_userid(entity)
            if userid ~= nil then
                ids[#ids + 1] = userid
                if entities[userid] == nil then
                    entities[userid] = entity
                end
            end
        end
    end
    if seed == nil then
        seed = random_seed()
    end

    local result
    repeat
        local candidate = string.format("lr-%d-%d", self.generation, self.serial + 1)
        result = self.arbiter:open(candidate, item_prefab, ids, seed, GetTime())
        if result.ok or result.code == "duplicate_roll" then
            -- The serial is consumed by a success, or skipped for good when
            -- the arbiter already knows that id.
            self.serial = self.serial + 1
        end
    until result.ok or result.code ~= "duplicate_roll"

    if not result.ok then
        return result
    end
    self.pending[result.roll_id] = {
        deadline = result.deadline,
        task = nil,
        entities = entities,
    }
    self:ScheduleDeadline(result.roll_id)
    self:PublishState()
    return result
end

-- The identity comes from player.userid only. Returns the arbiter's choose()
-- result; a completing choice resolves and delivers the roll immediately.
function LootRollArbiter:Choose(player, roll_id, choice, revision)
    local userid = valid_userid(player)
    if userid == nil then
        return { ok = false, code = "not_eligible" }
    end
    local result = self.arbiter:choose(roll_id, userid, choice, revision, GetTime())
    if result.ok then
        self:PublishState()
        if result.complete == true then
            self:Resolve(roll_id)
        end
    end
    return result
end

-- Resolves the roll and drives delivery until it is delivered or unclaimed.
-- A roll that already reached a final status returns its stored result and
-- never spawns anything again.
function LootRollArbiter:Resolve(roll_id)
    local result = self.arbiter:resolve(roll_id, GetTime())
    if not result.ok then
        return result
    end
    local winner_entity = nil
    while result.status == "awarded" do
        local candidate = self:FindPlayer(roll_id, result.winner)
        local delivered = deliver_item(candidate, result.item)
        local marked = self.arbiter:mark_delivered(roll_id, delivered, GetTime())
        if not marked.ok then
            break
        end
        if delivered then
            winner_entity = candidate
        end
        result = marked
    end
    if self.pending[roll_id] ~= nil and result.status ~= "awarded" then
        self:Finish(roll_id, result, winner_entity)
    end
    return result
end

-- Server side only. Cancels an open roll; no item is ever produced for it.
function LootRollArbiter:Cancel(roll_id)
    local result = self.arbiter:cancel(roll_id, GetTime())
    if not result.ok then
        return result
    end
    self:Finish(roll_id, result, nil)
    return result
end

function LootRollArbiter:OnSave()
    return {
        arbiter = self.arbiter:save(GetTime()),
        generation = self.generation,
        serial = self.serial,
    }
end

function LootRollArbiter:OnLoad(data)
    for roll_id in pairs(self.pending) do
        self:CancelTask(roll_id)
    end
    self.pending = {}

    local now = GetTime()
    local saved = type(data) == "table" and data or {}
    self.arbiter = Arbiter.load(saved.arbiter, make_options(now))
    if type(saved.serial) == "number" then
        self.serial = math.max(self.serial, math.floor(saved.serial))
    end
    if type(saved.generation) == "number" then
        self.generation = math.max(self.generation, math.floor(saved.generation))
    end
    self.generation = self.generation + 1

    -- Re-arm a deadline task for every roll that is not settled yet. Loading
    -- never delivers anything by itself; delivery only happens from a task
    -- or from an explicit Choose / Resolve call.
    local snapshot = self.arbiter:snapshot(now)
    if snapshot.ok then
        for i = 1, #snapshot.rolls do
            local roll = snapshot.rolls[i]
            if roll.status == "open" or roll.status == "awarded" then
                self.pending[roll.roll_id] = {
                    deadline = roll.deadline,
                    task = nil,
                    entities = {},
                }
                self:ScheduleDeadline(roll.roll_id)
            end
        end
    end
    self:PublishState()
end

function LootRollArbiter:OnRemoveFromEntity()
    for roll_id in pairs(self.pending) do
        self:CancelTask(roll_id)
    end
    self.inst:RemoveEventCallback("ms_playerleft", self._on_player_left)
end

return LootRollArbiter
