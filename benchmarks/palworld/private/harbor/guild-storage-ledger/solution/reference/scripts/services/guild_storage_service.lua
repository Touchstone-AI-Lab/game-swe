local Ledger = require("guildledger.ledger")

local GuildStorageService = {}
GuildStorageService.__index = GuildStorageService

local function default_inventory()
    return {
        add = function(_member_id, _item_id, _count) return true end,
        remove = function(_member_id, _item_id, _count) return true end,
    }
end

local function member_id_of(controller)
    if type(controller) == "string" and controller ~= "" then
        return controller
    end
    if type(controller) ~= "table" then
        return nil
    end
    if type(controller.GetPlayerUId) == "function" then
        local ok, value = pcall(controller.GetPlayerUId, controller)
        if ok and value ~= nil then return tostring(value) end
    end
    return controller.member_id or controller.player_id or controller.userid
end

function GuildStorageService.new(options)
    options = type(options) == "table" and options or {}
    local ledger_options = options.ledger_options or {
        quota = 2,
        bundles = { basic = { wood = 2, stone = 1 } },
    }
    local self = setmetatable({}, GuildStorageService)
    self.ledger_options = ledger_options
    self.ledger = Ledger.new(ledger_options)
    self.inventory = options.inventory or default_inventory()
    self.storage = options.storage
    self.controllers = {}
    self.current_cycle = nil
    return self
end

function GuildStorageService:Track(controller)
    local member_id = member_id_of(controller)
    if member_id == nil then return { ok = false, code = "invalid_member" } end
    self.controllers[member_id] = controller
    self.ledger:set_member(member_id, true)
    return { ok = true, member_id = member_id }
end

function GuildStorageService:MemberIdOf(controller)
    return member_id_of(controller)
end

function GuildStorageService:CurrentController()
    return FindFirstOf("PalPlayerController")
end

function GuildStorageService:BeginCycle(cycle)
    local result = self.ledger:begin_cycle(cycle)
    if result.ok then self.current_cycle = cycle end
    return result
end

function GuildStorageService:Claim(controller_or_member, request_id, bundle_id)
    local member_id = member_id_of(controller_or_member)
    if member_id == nil then return { ok = false, code = "invalid_member" } end
    if self.current_cycle == nil then
        local started = self:BeginCycle(0)
        if not started.ok then return started end
    end
    if self.controllers[member_id] == nil then
        self.ledger:set_member(member_id, true)
    end
    local claim = self.ledger:claim(member_id, request_id, bundle_id, self.current_cycle)
    if not claim.ok or claim.duplicate then return claim end

    local delivered = {}
    local item_ids = {}
    for item_id in pairs(claim.items) do item_ids[#item_ids + 1] = item_id end
    table.sort(item_ids)
    for _, item_id in ipairs(item_ids) do
        local count = claim.items[item_id]
        local ok = self.inventory.add(member_id, item_id, count)
        if not ok then
            for index = #delivered, 1, -1 do
                local entry = delivered[index]
                self.inventory.remove(member_id, entry.item_id, entry.count)
            end
            self.ledger:rollback(claim.token)
            return { ok = false, code = "delivery_failed" }
        end
        delivered[#delivered + 1] = { item_id = item_id, count = count }
    end
    self.ledger:commit(claim.token)
    claim.state = "committed"
    return claim
end

function GuildStorageService:Save()
    local data = self.ledger:save()
    if self.storage and type(self.storage.save) == "function" then
        self.storage.save(data)
    end
    return data
end

function GuildStorageService:Load(data)
    self.ledger = Ledger.load(data, self.ledger_options)
    self.current_cycle = self.ledger:snapshot().cycle
    return { ok = true }
end

return GuildStorageService
