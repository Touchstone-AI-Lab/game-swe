-- World component for the waystone network (master simulation only).
-- Bindings are kept as an array of records and the world itself listens to
-- each bound entity, so every callback can be removed from one place.

local Network = require("waystones/network")

local CONFIG = {
    network = { max_nodes_per_owner = 4, max_link_length = 60, cost_per_unit = 0.25, ticket_ttl = 10, cooldown = 30 },
    currency = "goldnugget",
    travel_radius = 4,
    sweep_period = 2,
}

local function nope(code, fields)
    local out = { ok = false, code = code }
    for key, value in pairs(fields or {}) do
        out[key] = value
    end
    return out
end

local function usable_entity(entity)
    if type(entity) ~= "table" or entity.Transform == nil or type(entity.IsValid) ~= "function" then
        return false
    end
    return entity:IsValid()
end

local function userid_of(who)
    local id = type(who) == "table" and who.userid or nil
    if type(id) == "string" and id:len() > 0 then
        return id
    end
    return nil
end

-- wallet: the three real-inventory operations the fare needs
local wallet = {}

function wallet.can_pay(player, amount)
    local enough = player.components.inventory:Has(CONFIG.currency, amount)
    return enough == true
end

function wallet.withdraw(player, amount)
    player.components.inventory:ConsumeByName(CONFIG.currency, amount)
end

function wallet.deposit(player, amount)
    local left = amount
    while left > 0 do
        local coin = SpawnPrefab(CONFIG.currency)
        if coin == nil then
            break
        end
        local batch = 1
        local stack = coin.components.stackable
        if stack ~= nil then
            batch = math.min(left, stack.maxsize or left)
            stack:SetStackSize(batch)
        end
        player.components.inventory:GiveItem(coin)
        left = left - batch
    end
end

local function place(player, x, y, z)
    if player.Physics == nil then
        player.Transform:SetPosition(x, y, z)
        return
    end
    player.Physics:Teleport(x, y, z)
end

local WaystoneNetwork = Class(function(self, inst)
    self.inst = inst
    self.core = Network.new(CONFIG.network)
    self.bindings = {}
    self.shift = 0
    self.high_water = 0
    self.sweeper = inst:DoPeriodicTask(CONFIG.sweep_period, function()
        self.core:tick(self:Clock())
    end)
end)

function WaystoneNetwork:Clock()
    local candidate = GetTime() + self.shift
    if candidate > self.high_water then
        self.high_water = candidate
    end
    return self.high_water
end

function WaystoneNetwork:FindBinding(key, value)
    for index, record in ipairs(self.bindings) do
        if record[key] == value then
            return record, index
        end
    end
    return nil
end

function WaystoneNetwork:Forget(record)
    local _, index = self:FindBinding("entity", record.entity)
    if index ~= nil then
        table.remove(self.bindings, index)
        self.inst:RemoveEventCallback("onremove", record.callback, record.entity)
    end
end

function WaystoneNetwork:Remember(entity, node_id)
    local record = { entity = entity, node_id = node_id }
    record.callback = function()
        self:Forget(record)
        self.core:remove_node(node_id, self:Clock())
    end
    self.inst:ListenForEvent("onremove", record.callback, entity)
    table.insert(self.bindings, record)
end

function WaystoneNetwork:Register(entity, node_id, owner_player)
    if not usable_entity(entity) then
        return nope("invalid_entity")
    end
    local owner_id = userid_of(owner_player)
    if owner_id == nil then
        return nope("invalid_player")
    end
    if self:FindBinding("entity", entity) ~= nil then
        return nope("already_registered")
    end
    if self:FindBinding("node_id", node_id) ~= nil then
        return nope("duplicate_node")
    end
    local stored_owner = self.core:owner_of(node_id)
    if stored_owner ~= nil then
        if stored_owner ~= owner_id then
            return nope("owner_mismatch")
        end
        self:Remember(entity, node_id)
        return { ok = true, rebound = true, node_id = node_id }
    end
    local x, _, z = entity.Transform:GetWorldPosition()
    local added = self.core:add_node(node_id, owner_id, x, z, self:Clock())
    if added.ok ~= true then
        return added
    end
    self:Remember(entity, node_id)
    return { ok = true, rebound = false, node_id = node_id }
end

function WaystoneNetwork:Link(node_a, node_b)
    return self.core:link(node_a, node_b, self:Clock())
end

function WaystoneNetwork:Route(from_id, to_id)
    return self.core:route(from_id, to_id, self:Clock())
end

-- Checks that must hold between reserve and the first real effect. Returns a
-- failure table or nil plus the destination entity.
function WaystoneNetwork:Preflight(player, ticket)
    local origin = self:FindBinding("node_id", ticket.from_id)
    local target = self:FindBinding("node_id", ticket.to_id)
    if origin == nil or target == nil or not usable_entity(origin.entity) or not usable_entity(target.entity) then
        return nope("unbound_node")
    end
    local px, _, pz = player.Transform:GetWorldPosition()
    local ox, _, oz = origin.entity.Transform:GetWorldPosition()
    local gap = (px - ox) ^ 2 + (pz - oz) ^ 2
    if gap > CONFIG.travel_radius ^ 2 then
        return nope("too_far")
    end
    if not wallet.can_pay(player, ticket.price) then
        return nope("insufficient_funds", { price = ticket.price })
    end
    return nil, target.entity
end

function WaystoneNetwork:Travel(player, request_id, from_id, to_id)
    local traveler_id = userid_of(player)
    local equipped = traveler_id ~= nil and player.Transform ~= nil and player.components ~= nil
        and player.components.inventory ~= nil
    if not equipped then
        return nope("invalid_player")
    end
    local booking = self.core:reserve(request_id, traveler_id, from_id, to_id, self:Clock())
    if booking.ok ~= true then
        return booking
    end
    local ticket = booking.ticket
    if booking.duplicate then
        if ticket.status ~= "committed" then
            return nope("ticket_closed", { status = ticket.status })
        end
        return { ok = true, duplicate = true, ticket = ticket }
    end
    local problem, target = self:Preflight(player, ticket)
    if problem ~= nil then
        self.core:abort(ticket.ticket_id, self:Clock())
        return problem
    end
    local home = { player.Transform:GetWorldPosition() }
    wallet.withdraw(player, ticket.price)
    place(player, target.Transform:GetWorldPosition())
    local sealed = self.core:commit(ticket.ticket_id, self:Clock())
    if sealed.ok == true then
        return { ok = true, duplicate = false, ticket = sealed.ticket, price = ticket.price,
            cooldown_until = sealed.cooldown_until }
    end
    place(player, home[1], home[2], home[3])
    wallet.deposit(player, ticket.price)
    return sealed
end

function WaystoneNetwork:DropAllBindings()
    while #self.bindings > 0 do
        self:Forget(self.bindings[#self.bindings])
    end
end

function WaystoneNetwork:OnSave()
    local saved = self.core:save(self:Clock())
    return { schema = 1, core = saved.data }
end

function WaystoneNetwork:OnLoad(data)
    if type(data) ~= "table" or data.schema ~= 1 then
        return
    end
    self:DropAllBindings()
    self.core = Network.load(data.core, CONFIG.network)
    local restored = self.core.clock_value()
    self.high_water = restored
    self.shift = math.max(0, restored - GetTime())
end

function WaystoneNetwork:OnRemoveFromEntity()
    if self.sweeper ~= nil then
        self.sweeper:Cancel()
        self.sweeper = nil
    end
    self:DropAllBindings()
end

return WaystoneNetwork
