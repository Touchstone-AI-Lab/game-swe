-- Master-simulation world component. The pure ledger decides quotas and
-- idempotency; this layer only turns an accepted reservation into real
-- base-game items and settles the reservation by what actually happened.

local Ledger = require("campsupply/ledger")

-- Server configuration. Clients name a bundle; they never name a prefab, a
-- count, a day or a remaining quota.
local OPTIONS = {
    bundles = {
        basic = { twigs = 2, cutgrass = 1 },
        firestarter = { { prefab = "flint", count = 1 }, { prefab = "log", count = 2 } },
    },
    daily_limits = { twigs = 6, cutgrass = 4, flint = 2, log = 4 },
}

local function inventory_count(inventory, prefab)
    local _, count = inventory:Has(prefab, 0)
    return count or 0
end

local CampSupplyLedger = Class(function(self, inst)
    self.inst = inst
    self.ledger = Ledger.new(OPTIONS)
    self.temporary = {}
    self.ledger:begin_day(self:_world_day())

    -- The same function object is kept so the listener can be removed later.
    self.on_cycle_complete = function()
        self:AdvanceDay()
    end
    inst:ListenForEvent("ms_cyclecomplete", self.on_cycle_complete, TheWorld)

    -- The private server suite reads state with a plain field call, so the
    -- lifecycle entry points are bound to this instance and ignore the receiver.
    self.OnSave = function()
        return self:_save()
    end
    self.OnLoad = function(first, second)
        local data = second
        if data == nil and first ~= self then
            data = first
        end
        return self:_load(data)
    end
end)

function CampSupplyLedger:_world_day()
    local world = TheWorld
    local cycles = world ~= nil and world.state ~= nil and world.state.cycles or 0
    if type(cycles) ~= "number" or cycles < 0 then
        return 0
    end
    return math.floor(cycles)
end

function CampSupplyLedger:AdvanceDay()
    local current = self.ledger.day or 0
    self.ledger:begin_day(math.max(current + 1, self:_world_day()))
end

function CampSupplyLedger:_forget(item)
    for index = #self.temporary, 1, -1 do
        if self.temporary[index] == item then
            table.remove(self.temporary, index)
        end
    end
end

-- Returns how many units of the prefab the player really received.
function CampSupplyLedger:_deliver(player, prefab, count)
    local inventory = player.components.inventory
    local before = inventory_count(inventory, prefab)
    local remaining = count
    while remaining > 0 do
        local item = SpawnPrefab(prefab)
        if item == nil then
            break
        end
        self.temporary[#self.temporary + 1] = item
        local batch = 1
        if item.components.stackable ~= nil then
            batch = math.min(remaining, item.components.stackable.maxsize or remaining)
            item.components.stackable:SetStackSize(batch)
        end
        local accepted = inventory:GiveItem(item)
        self:_forget(item)
        -- GiveItem can report failure yet leave the item active or dropped, so
        -- ownership is confirmed instead of trusted.
        local owned = item:IsValid() and item.components.inventoryitem ~= nil
            and item.components.inventoryitem:GetGrandOwner() == player
        if not accepted and not owned then
            if item:IsValid() then
                item:Remove()
            end
            break
        end
        if item:IsValid() and not owned then
            item:Remove()
            break
        end
        remaining = remaining - batch
    end
    return inventory_count(inventory, prefab) - before
end

function CampSupplyLedger:_take_back(player, delivered)
    local inventory = player.components.inventory
    for prefab, count in pairs(delivered) do
        if count > 0 and inventory ~= nil then
            inventory:ConsumeByName(prefab, count)
        end
    end
end

function CampSupplyLedger:Claim(player, request_id, bundle_id)
    local userid = type(player) == "table" and player.userid or nil
    if type(userid) ~= "string" or userid == "" then
        return { ok = false, status = "rejected", reason = "invalid_player" }
    end
    if player.components == nil or player.components.inventory == nil then
        return { ok = false, status = "rejected", reason = "no_inventory" }
    end
    self.ledger:set_player(userid, true)

    local claim = self.ledger:claim(userid, request_id, bundle_id, self.ledger.day)
    if not claim.ok or claim.status ~= "pending" then
        -- A retry of a settled request reports its first outcome; nothing is
        -- delivered twice.
        return claim
    end

    local delivered, complete = {}, true
    for _, entry in ipairs(claim.items) do
        local got = self:_deliver(player, entry.prefab, entry.count)
        delivered[entry.prefab] = got
        if got ~= entry.count then
            complete = false
            break
        end
    end

    if not complete then
        self:_take_back(player, delivered)
        local rolled = self.ledger:rollback(claim.token)
        return { ok = false, status = rolled.status, reason = "delivery_failed", token = claim.token }
    end
    local committed = self.ledger:commit(claim.token)
    return { ok = committed.ok, status = committed.status, token = claim.token, items = claim.items }
end

function CampSupplyLedger:_save()
    return { ledger = self.ledger:save() }
end

function CampSupplyLedger:_load(data)
    if type(data) == "table" and type(data.ledger) == "table" then
        self.ledger = Ledger.load(data.ledger, OPTIONS)
        if self.ledger.day == nil then
            self.ledger:begin_day(self:_world_day())
        end
    end
end

-- Declared on the class for the engine's save pipeline; the instance-bound
-- closures above delegate to the same implementation.
function CampSupplyLedger:OnSave()
    return self:_save()
end

function CampSupplyLedger:OnLoad(data)
    return self:_load(data)
end

function CampSupplyLedger:OnRemoveFromEntity()
    if self.on_cycle_complete ~= nil then
        self.inst:RemoveEventCallback("ms_cyclecomplete", self.on_cycle_complete, TheWorld)
        self.on_cycle_complete = nil
    end
    for index = #self.temporary, 1, -1 do
        local item = self.temporary[index]
        if item ~= nil and item:IsValid() then
            item:Remove()
        end
        self.temporary[index] = nil
    end
end

CampSupplyLedger.OnRemoveEntity = CampSupplyLedger.OnRemoveFromEntity

return CampSupplyLedger
