-- Master-simulation world component. It binds real waystone entities to the
-- pure route network, charges fares from the real inventory and moves the
-- traveler with the real transform/physics API.

local Network = require("waystones/network")

local OPTIONS = { max_nodes_per_owner = 4, max_link_length = 60, cost_per_unit = 0.25, ticket_ttl = 10, cooldown = 30 }
local CURRENCY = "goldnugget"
local TRAVEL_RADIUS = 4
local TICK_PERIOD = 1

local function fail(code, extra)
    local result = extra or {}
    result.ok = false
    result.code = code
    return result
end

local function user_id(player)
    if type(player) ~= "table" or type(player.userid) ~= "string" or player.userid == "" then
        return nil
    end
    return player.userid
end

local function is_live_entity(entity)
    return type(entity) == "table" and entity.Transform ~= nil and entity.IsValid ~= nil and entity:IsValid()
end

local function move_to(player, x, y, z)
    if player.Physics ~= nil then
        player.Physics:Teleport(x, y, z)
    else
        player.Transform:SetPosition(x, y, z)
    end
end

local function refund(inventory, amount)
    while amount > 0 do
        local item = SpawnPrefab(CURRENCY)
        if item == nil then
            return
        end
        local size = 1
        if item.components.stackable ~= nil then
            size = math.min(amount, item.components.stackable.maxsize or amount)
            item.components.stackable:SetStackSize(size)
        end
        amount = amount - size
        inventory:GiveItem(item)
    end
end

local WaystoneNetwork = Class(function(self, inst)
    self.inst = inst
    self.network = Network.new(OPTIONS)
    self.time_offset = 0
    self.last_now = 0
    self.bound = {}     -- node_id -> { entity, on_remove }
    self.node_of = {}   -- entity -> node_id
    self.tick_task = inst:DoPeriodicTask(TICK_PERIOD, function()
        self:Tick()
    end, TICK_PERIOD)
end)

function WaystoneNetwork:_Now()
    self.last_now = math.max(self.last_now, GetTime() + self.time_offset)
    return self.last_now
end

function WaystoneNetwork:_Unbind(node_id)
    local binding = self.bound[node_id]
    if binding == nil then
        return
    end
    self.bound[node_id] = nil
    self.node_of[binding.entity] = nil
    binding.entity:RemoveEventCallback("onremove", binding.on_remove)
end

function WaystoneNetwork:_Bind(entity, node_id)
    local binding = { entity = entity }
    binding.on_remove = function()
        self:_Unbind(node_id)
        self.network:remove_node(node_id, self:_Now())
    end
    entity:ListenForEvent("onremove", binding.on_remove)
    self.bound[node_id] = binding
    self.node_of[entity] = node_id
end

function WaystoneNetwork:_Owner(node_id)
    local view = self.network:snapshot(self:_Now())
    for _, node in ipairs(view.nodes or {}) do
        if node.id == node_id then
            return node.owner_id
        end
    end
    return nil
end

function WaystoneNetwork:Register(entity, node_id, owner_player)
    if not self.inst.ismastersim or not is_live_entity(entity) then
        return fail("invalid_entity")
    end
    local owner_id = user_id(owner_player)
    if owner_id == nil then
        return fail("invalid_player")
    end
    if self.node_of[entity] ~= nil then
        return fail("already_registered")
    end
    if type(node_id) == "string" and self.bound[node_id] ~= nil then
        return fail("duplicate_node")
    end
    local persisted_owner = type(node_id) == "string" and self:_Owner(node_id) or nil
    if persisted_owner ~= nil then
        if persisted_owner ~= owner_id then
            return fail("owner_mismatch")
        end
        self:_Bind(entity, node_id)
        return { ok = true, rebound = true, node_id = node_id }
    end
    -- Coordinates always come from the real entity, never from a caller.
    local x, _, z = entity.Transform:GetWorldPosition()
    local result = self.network:add_node(node_id, owner_id, x, z, self:_Now())
    if result.ok then
        self:_Bind(entity, node_id)
        result.rebound = false
    end
    return result
end

function WaystoneNetwork:Link(node_a, node_b)
    return self.network:link(node_a, node_b, self:_Now())
end

function WaystoneNetwork:Route(from_id, to_id)
    return self.network:route(from_id, to_id, self:_Now())
end

function WaystoneNetwork:Tick()
    return self.network:tick(self:_Now())
end

function WaystoneNetwork:_Abort(ticket, code, extra)
    self.network:abort(ticket.ticket_id, self:_Now())
    return fail(code, extra)
end

function WaystoneNetwork:Travel(player, request_id, from_id, to_id)
    local traveler_id = user_id(player)
    if not self.inst.ismastersim or traveler_id == nil or player.Transform == nil
        or player.components == nil or player.components.inventory == nil then
        return fail("invalid_player")
    end
    local reserved = self.network:reserve(request_id, traveler_id, from_id, to_id, self:_Now())
    if not reserved.ok then
        return reserved
    end
    local ticket = reserved.ticket
    if reserved.duplicate then
        if ticket.status == "committed" then
            return { ok = true, duplicate = true, ticket = ticket, price = ticket.price }
        end
        return fail("ticket_closed", { status = ticket.status })
    end

    local origin, destination = self.bound[from_id], self.bound[to_id]
    if origin == nil or destination == nil or not is_live_entity(origin.entity)
        or not is_live_entity(destination.entity) then
        return self:_Abort(ticket, "unbound_node")
    end
    local px, py, pz = player.Transform:GetWorldPosition()
    local ox, _, oz = origin.entity.Transform:GetWorldPosition()
    if (px - ox) * (px - ox) + (pz - oz) * (pz - oz) > TRAVEL_RADIUS * TRAVEL_RADIUS then
        return self:_Abort(ticket, "too_far")
    end
    local inventory = player.components.inventory
    if not inventory:Has(CURRENCY, ticket.price) then
        return self:_Abort(ticket, "insufficient_funds", { price = ticket.price })
    end

    inventory:ConsumeByName(CURRENCY, ticket.price)
    local dx, dy, dz = destination.entity.Transform:GetWorldPosition()
    move_to(player, dx, dy, dz)
    local committed = self.network:commit(ticket.ticket_id, self:_Now())
    if not committed.ok then
        -- The route changed underneath the trip: undo every real effect.
        move_to(player, px, py, pz)
        refund(inventory, ticket.price)
        self.network:abort(ticket.ticket_id, self:_Now())
        return committed
    end
    return { ok = true, duplicate = false, ticket = committed.ticket, price = ticket.price,
        cooldown_until = committed.cooldown_until }
end

function WaystoneNetwork:_ReleaseBindings()
    local node_ids = {}
    for node_id in pairs(self.bound) do
        node_ids[#node_ids + 1] = node_id
    end
    for index = 1, #node_ids do
        self:_Unbind(node_ids[index])
    end
end

function WaystoneNetwork:OnSave()
    local saved = self.network:save(self:_Now())
    return { version = 1, network = saved.ok and saved.data or nil }
end

-- GetTime() restarts with the process, so the restored clock is kept ahead of
-- it: cooldown and ticket boundaries survive a restart. Entities bind again
-- through Register once they respawn.
function WaystoneNetwork:OnLoad(data)
    if type(data) ~= "table" or data.version ~= 1 then
        return
    end
    self:_ReleaseBindings()
    self.network = Network.load(data.network, OPTIONS)
    self.last_now = self.network.clock
    self.time_offset = math.max(0, self.network.clock - GetTime())
end

function WaystoneNetwork:OnRemoveFromEntity()
    if self.tick_task ~= nil then
        self.tick_task:Cancel()
        self.tick_task = nil
    end
    self:_ReleaseBindings()
end

function WaystoneNetwork:GetDebugString()
    local view = self.network:snapshot(self:_Now())
    return string.format("nodes=%d links=%d tickets=%d", #view.nodes, #view.links, #view.tickets)
end

return WaystoneNetwork
