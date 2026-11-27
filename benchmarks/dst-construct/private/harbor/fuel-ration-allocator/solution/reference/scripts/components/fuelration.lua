-- Master-simulation world component. The pure allocator owns every number;
-- this layer moves real items out of inventories and real fuel into fires,
-- and settles each share by what the `fueled` component actually accepted.

local Allocator = require("fuelration/allocator")

local OPTIONS = {
    unit_size = 15,
    depot_capacity = 60,
    max_units_per_round = 6,
    reserve_floor = 2,
}
-- Server whitelist: prefab -> fuel units per item. Clients never send units.
local FUEL_UNITS = { log = 3, twigs = 1, cutgrass = 1 }
local ROUND_PERIOD = 30

local function reject(code)
    return { ok = false, code = code }
end

local function is_count(value)
    return type(value) == "number" and value == value and value ~= math.huge
        and value == math.floor(value) and value >= 1
end

local function held(inventory, prefab)
    local _, found = inventory:Has(prefab, 1)
    return found or 0
end

local FuelRation = Class(function(self, inst)
    self.inst = inst
    self.allocator = Allocator.new(OPTIONS)
    self.tracked = {}      -- consumer_id -> { entity, priority, onremove }
    self.by_entity = {}    -- entity -> consumer_id
    self.time_offset = 0
    self.round_counter = 0
    self.task = inst:DoPeriodicTask(ROUND_PERIOD, function()
        self:RunAutomaticRound()
    end)
end)

-- GetTime() restarts with every server session, the allocator clock does not:
-- the offset keeps the time handed to the core at or above the restored clock.
function FuelRation:Now()
    local now = self.time_offset + GetTime()
    local clock = self.allocator:snapshot(0).clock
    if now < clock then
        self.time_offset = self.time_offset + (clock - now)
        now = clock
    end
    return now
end

-- capacity rounds down and level rounds up, so capacity - level never asks for
-- more fuel than the real component can take.
local function measure(fueled)
    local capacity = math.floor(fueled.maxfuel / OPTIONS.unit_size)
    local level = math.min(capacity, math.ceil(fueled.currentfuel / OPTIONS.unit_size))
    return capacity, level
end

local function usable(entity)
    return type(entity) == "table" and entity.IsValid ~= nil and entity:IsValid()
        and entity.components ~= nil and entity.components.fueled ~= nil
end

function FuelRation:Track(entity, consumer_id, priority)
    if not usable(entity) then
        return reject("not_fueled")
    end
    local capacity, level = measure(entity.components.fueled)
    if capacity < 1 then
        return reject("not_fueled")
    end
    if self.by_entity[entity] ~= nil then
        return reject("already_tracked")
    end
    local now = self:Now()
    local registered = self.allocator:register(consumer_id, priority, capacity, now)
    if not registered.ok then
        return registered
    end
    self.allocator:report(consumer_id, level, now)

    local record = { entity = entity, priority = priority }
    record.onremove = function()
        self:Untrack(consumer_id)
    end
    self.inst:ListenForEvent("onremove", record.onremove, entity)
    self.tracked[consumer_id] = record
    self.by_entity[entity] = consumer_id
    return { ok = true, status = "registered", consumer_id = consumer_id, capacity = capacity, level = level }
end

function FuelRation:_forget(consumer_id)
    local record = self.tracked[consumer_id]
    if record == nil then
        return false
    end
    self.inst:RemoveEventCallback("onremove", record.onremove, record.entity)
    self.by_entity[record.entity] = nil
    self.tracked[consumer_id] = nil
    return true
end

function FuelRation:Untrack(consumer_id)
    if not self:_forget(consumer_id) then
        return reject("unknown_consumer")
    end
    return self.allocator:unregister(consumer_id, self:Now())
end

function FuelRation:Deposit(player, request_id, item_prefab, count)
    local userid = type(player) == "table" and player.userid or nil
    if type(userid) ~= "string" or userid == "" then
        return reject("invalid_player")
    end
    local inventory = player.components ~= nil and player.components.inventory or nil
    if inventory == nil then
        return reject("no_inventory")
    end
    local per_item = type(item_prefab) == "string" and FUEL_UNITS[item_prefab] or nil
    if per_item == nil then
        return reject("not_fuel")
    end
    if not is_count(count) then
        return reject("invalid_units")
    end
    if type(request_id) ~= "string" or request_id == "" or #request_id > 64 then
        return reject("invalid_id")
    end
    -- A retry must replay the first outcome without touching the inventory again.
    local recorded = self.allocator:lookup(request_id, userid)
    if recorded ~= nil then
        return recorded
    end
    local units = count * per_item
    if self.allocator:snapshot(0).free < units then
        return reject("depot_full")
    end
    if not inventory:Has(item_prefab, count) then
        return reject("insufficient_items")
    end
    local before = held(inventory, item_prefab)
    inventory:ConsumeByName(item_prefab, count)
    if before - held(inventory, item_prefab) ~= count then
        return reject("removal_failed")
    end
    -- Only now, with the items really gone, is the depot credited.
    return self.allocator:deposit(request_id, userid, units, self:Now())
end

function FuelRation:_report_levels(now)
    local ids = {}
    for consumer_id in pairs(self.tracked) do
        ids[#ids + 1] = consumer_id
    end
    table.sort(ids)
    for _, consumer_id in ipairs(ids) do
        local entity = self.tracked[consumer_id].entity
        if usable(entity) then
            local _, level = measure(entity.components.fueled)
            self.allocator:report(consumer_id, level, now)
        else
            self:Untrack(consumer_id)
        end
    end
end

function FuelRation:RunRound(round_id)
    local now = self:Now()
    self:_report_levels(now)
    local plan = self.allocator:plan(round_id, now)
    if not plan.ok then
        return plan
    end
    local shares = {}
    for index, share in ipairs(plan.shares) do
        local record = self.tracked[share.consumer_id]
        local settled
        if record ~= nil and usable(record.entity) then
            local fueled = record.entity.components.fueled
            local before = fueled.currentfuel
            fueled:DoDelta(share.units * OPTIONS.unit_size)
            -- Commit what the real component accepted, not what was planned.
            local gained = (fueled.currentfuel - before) / OPTIONS.unit_size
            local delivered = math.max(0, math.min(share.units, math.floor(gained)))
            settled = self.allocator:commit(round_id, share.consumer_id, delivered, now)
        else
            settled = self.allocator:abort(round_id, share.consumer_id, now)
        end
        shares[index] = {
            consumer_id = share.consumer_id,
            units = share.units,
            delivered = settled.delivered or 0,
            status = settled.status,
        }
    end
    local closed = self.allocator:close(round_id, now)
    return {
        ok = closed.ok,
        status = closed.status,
        round_id = round_id,
        shares = shares,
        total = closed.total,
        delivered = closed.delivered,
        returned = closed.returned,
    }
end

function FuelRation:RunAutomaticRound()
    self.round_counter = self.round_counter + 1
    return self:RunRound(string.format("auto-%d", self.round_counter))
end

function FuelRation:Snapshot()
    return self.allocator:snapshot(self:Now())
end

function FuelRation:OnSave()
    return { allocator = self.allocator:save(self:Now()), round_counter = self.round_counter }
end

function FuelRation:OnLoad(data)
    if type(data) ~= "table" then
        return
    end
    self.allocator = Allocator.load(data.allocator, OPTIONS)
    if type(data.round_counter) == "number" then
        self.round_counter = math.max(self.round_counter, math.floor(data.round_counter))
    end
    self.time_offset = 0
    local now = self:Now()
    local snapshot = self.allocator:snapshot(now)
    -- A round cannot survive a reload: no fuel is in flight, so return it all.
    if snapshot.round ~= nil then
        self.allocator:close(snapshot.round.round_id, now)
    end
    -- Entities are session objects. Consumers without a live tracked entity go,
    -- tracked entities the restored state does not know are registered again.
    local known = {}
    for _, row in ipairs(snapshot.consumers) do
        if self.tracked[row.consumer_id] == nil then
            self.allocator:unregister(row.consumer_id, now)
        else
            known[row.consumer_id] = true
        end
    end
    for consumer_id, record in pairs(self.tracked) do
        if usable(record.entity) then
            local capacity, level = measure(record.entity.components.fueled)
            if not known[consumer_id] then
                self.allocator:register(consumer_id, record.priority, capacity, now)
            end
            self.allocator:report(consumer_id, level, now)
        end
    end
end

function FuelRation:OnRemoveFromEntity()
    if self.task ~= nil then
        self.task:Cancel()
        self.task = nil
    end
    local ids = {}
    for consumer_id in pairs(self.tracked) do
        ids[#ids + 1] = consumer_id
    end
    for _, consumer_id in ipairs(ids) do
        self:_forget(consumer_id)
    end
end

FuelRation.OnRemoveEntity = FuelRation.OnRemoveFromEntity

return FuelRation
