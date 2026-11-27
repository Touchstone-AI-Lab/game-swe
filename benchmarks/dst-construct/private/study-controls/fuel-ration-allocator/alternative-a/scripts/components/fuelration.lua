local Allocator = require("fuelration/allocator")

local OPTIONS = { unit_size = 15, depot_capacity = 60, max_units_per_round = 6, reserve_floor = 2 }
local FUEL_UNITS = { log = 3, twigs = 1, cutgrass = 1 }
local ROUND_PERIOD = 30

------------------------------------------------------------------------------
-- helpers that only look at real game objects

local function fueled_of(entity)
    if type(entity) ~= "table" or type(entity.IsValid) ~= "function" or not entity:IsValid() then
        return nil
    end
    return entity.components ~= nil and entity.components.fueled or nil
end

local function to_units(fueled)
    local capacity = math.floor(fueled.maxfuel / OPTIONS.unit_size)
    local level = math.ceil(fueled.currentfuel / OPTIONS.unit_size)
    if level > capacity then
        level = capacity
    end
    return capacity, level
end

local function holding(inventory, prefab)
    local _, found = inventory:Has(prefab, 1)
    return found or 0
end

-- Takes exactly `count` items out of the inventory, stack by stack.
local function take_items(inventory, prefab, count)
    local expected = holding(inventory, prefab) - count
    for item, amount in pairs(inventory:GetItemByName(prefab, count)) do
        local stackable = item.components.stackable
        local removed
        if stackable ~= nil and stackable:StackSize() > amount then
            removed = stackable:Get(amount)
        else
            removed = inventory:RemoveItem(item, true)
        end
        if removed ~= nil then
            removed:Remove()
        end
    end
    return holding(inventory, prefab) == expected
end

local function refuse(code)
    return { ok = false, code = code }
end

------------------------------------------------------------------------------

local FuelRation = Class(function(self, inst)
    self.inst = inst
    self.core = Allocator.new(OPTIONS)
    self.fires = {}          -- array of { id, entity, priority, handler }
    self.auto_rounds = 0
    self.round_task = inst:DoPeriodicTask(ROUND_PERIOD, function(_, component)
        component.auto_rounds = component.auto_rounds + 1
        component:RunRound("auto-" .. string.format("%d", component.auto_rounds))
    end, nil, self)
end)

-- The session clock restarts at zero after a reload; never hand the core a
-- time below its own restored clock.
function FuelRation:_time()
    return math.max(GetTime(), self.core:snapshot(0).clock)
end

function FuelRation:_find(predicate)
    for index, fire in ipairs(self.fires) do
        if predicate(fire) then
            return index, fire
        end
    end
    return nil, nil
end

function FuelRation:_drop(index)
    local fire = table.remove(self.fires, index)
    if fire.entity ~= nil and fire.handler ~= nil then
        fire.entity:RemoveEventCallback("onremove", fire.handler)
    end
    return fire
end

function FuelRation:Track(entity, consumer_id, priority)
    local fueled = fueled_of(entity)
    if fueled == nil then
        return refuse("not_fueled")
    end
    local capacity, level = to_units(fueled)
    if capacity < 1 then
        return refuse("not_fueled")
    end
    if self:_find(function(fire) return fire.entity == entity end) ~= nil then
        return refuse("already_tracked")
    end
    local now = self:_time()
    local outcome = self.core:register(consumer_id, priority, capacity, now)
    if not outcome.ok then
        return outcome
    end
    self.core:report(consumer_id, level, now)
    local fire = { id = consumer_id, entity = entity, priority = priority }
    fire.handler = function()
        self:Untrack(consumer_id)
    end
    entity:ListenForEvent("onremove", fire.handler)
    self.fires[#self.fires + 1] = fire
    return { ok = true, status = "registered", consumer_id = consumer_id, capacity = capacity, level = level }
end

function FuelRation:Untrack(consumer_id)
    local index = self:_find(function(fire) return fire.id == consumer_id end)
    if index == nil then
        return refuse("unknown_consumer")
    end
    self:_drop(index)
    return self.core:unregister(consumer_id, self:_time())
end

local DEPOSIT_CHECKS = {
    function(_, player)
        return (type(player) ~= "table" or type(player.userid) ~= "string" or player.userid == "") and "invalid_player"
    end,
    function(_, player)
        return (player.components == nil or player.components.inventory == nil) and "no_inventory"
    end,
    function(_, _, _, prefab)
        return (type(prefab) ~= "string" or FUEL_UNITS[prefab] == nil) and "not_fuel"
    end,
    function(_, _, _, _, count)
        return (type(count) ~= "number" or count ~= count or count == math.huge or count < 1
            or count % 1 ~= 0) and "invalid_units"
    end,
    function(_, _, request_id)
        return (type(request_id) ~= "string" or #request_id < 1 or #request_id > 64) and "invalid_id"
    end,
}

function FuelRation:Deposit(player, request_id, item_prefab, count)
    for _, check in ipairs(DEPOSIT_CHECKS) do
        local code = check(self, player, request_id, item_prefab, count)
        if code then
            return refuse(code)
        end
    end
    local earlier = self.core:lookup(request_id, player.userid)
    if earlier ~= nil then
        return earlier
    end
    local units = count * FUEL_UNITS[item_prefab]
    if units > self.core:snapshot(0).free then
        return refuse("depot_full")
    end
    local inventory = player.components.inventory
    if not inventory:Has(item_prefab, count) then
        return refuse("insufficient_items")
    end
    if not take_items(inventory, item_prefab, count) then
        return refuse("removal_failed")
    end
    return self.core:deposit(request_id, player.userid, units, self:_time())
end

function FuelRation:_refresh(now)
    for index = #self.fires, 1, -1 do
        local fire = self.fires[index]
        local fueled = fueled_of(fire.entity)
        if fueled == nil then
            self:_drop(index)
            self.core:unregister(fire.id, now)
        else
            local _, level = to_units(fueled)
            self.core:report(fire.id, level, now)
        end
    end
end

function FuelRation:_deliver(round_id, share, now)
    local _, fire = self:_find(function(candidate) return candidate.id == share.consumer_id end)
    local fueled = fire ~= nil and fueled_of(fire.entity) or nil
    if fueled == nil then
        return self.core:abort(round_id, share.consumer_id, now)
    end
    local before = fueled.currentfuel
    fueled:DoDelta(share.units * OPTIONS.unit_size)
    local accepted = math.floor((fueled.currentfuel - before) / OPTIONS.unit_size)
    if accepted < 0 then
        accepted = 0
    elseif accepted > share.units then
        accepted = share.units
    end
    return self.core:commit(round_id, share.consumer_id, accepted, now)
end

function FuelRation:RunRound(round_id)
    local now = self:_time()
    self:_refresh(now)
    local plan = self.core:plan(round_id, now)
    if not plan.ok then
        return plan
    end
    local report = { ok = true, status = "closed", round_id = round_id, shares = {} }
    for _, share in ipairs(plan.shares) do
        local settled = self:_deliver(round_id, share, now)
        report.shares[#report.shares + 1] = {
            consumer_id = share.consumer_id,
            units = share.units,
            delivered = settled.delivered,
            status = settled.status,
        }
    end
    local closed = self.core:close(round_id, now)
    report.total, report.delivered, report.returned = closed.total, closed.delivered, closed.returned
    return report
end

function FuelRation:Snapshot()
    return self.core:snapshot(self:_time())
end

function FuelRation:OnSave()
    return { core = self.core:save(self:_time()), auto_rounds = self.auto_rounds }
end

function FuelRation:OnLoad(data)
    data = type(data) == "table" and data or {}
    self.core = Allocator.load(data.core, OPTIONS)
    if type(data.auto_rounds) == "number" and data.auto_rounds > self.auto_rounds then
        self.auto_rounds = data.auto_rounds
    end
    local now = self:_time()
    local view = self.core:snapshot(now)
    if view.round ~= nil then
        self.core:close(view.round.round_id, now)
    end
    local restored = {}
    for _, row in ipairs(view.consumers) do
        restored[row.consumer_id] = true
        if self:_find(function(fire) return fire.id == row.consumer_id end) == nil then
            self.core:unregister(row.consumer_id, now)
        end
    end
    for _, fire in ipairs(self.fires) do
        local fueled = fueled_of(fire.entity)
        if fueled ~= nil then
            local capacity, level = to_units(fueled)
            if not restored[fire.id] then
                self.core:register(fire.id, fire.priority, capacity, now)
            end
            self.core:report(fire.id, level, now)
        end
    end
end

function FuelRation:OnRemoveFromEntity()
    if self.round_task ~= nil then
        self.round_task:Cancel()
        self.round_task = nil
    end
    while #self.fires > 0 do
        self:_drop(#self.fires)
    end
end

return FuelRation
