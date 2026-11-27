local Queue = require("raiddispatch.queue")

local RaidDispatchService = {}
RaidDispatchService.__index = RaidDispatchService

local function clock()
    return os.time()
end

local function member_id_of(value)
    if type(value) == "string" and value ~= "" then return value end
    if type(value) ~= "table" then return nil end
    if type(value.get) == "function" then
        local ok, unwrapped = pcall(value.get, value)
        if ok and unwrapped ~= nil then value = unwrapped end
    end
    if type(value.GetPlayerUId) == "function" then
        local ok, member_id = pcall(value.GetPlayerUId, value)
        if ok and member_id ~= nil then return tostring(member_id) end
    end
    return value.member_id or value.player_id
end

function RaidDispatchService.new(options)
    options = type(options) == "table" and options or {}
    local self = setmetatable({}, RaidDispatchService)
    self.options = options.queue_options or { lease_seconds = 30, max_attempts = 3 }
    self.now = options.now or clock
    self.queue = Queue.new(self.options)
    self.players = {}
    return self
end

function RaidDispatchService:Track(controller)
    local member_id = member_id_of(controller)
    if member_id == nil then return { ok = false, code = "invalid_member" } end
    self.players[member_id] = controller
    return { ok = true, member_id = member_id }
end

function RaidDispatchService:Enqueue(request_id, member_or_controller, priority)
    local member_id = member_id_of(member_or_controller)
    if member_id == nil then return { ok = false, code = "invalid_request" } end
    return self.queue:enqueue(request_id, member_id, priority, self.now())
end

function RaidDispatchService:Lease(worker_id)
    return self.queue:lease(worker_id, self.now())
end

function RaidDispatchService:Renew(token)
    return self.queue:renew(token, self.now())
end

function RaidDispatchService:Complete(token, outcome)
    return self.queue:complete(token, outcome, self.now())
end

function RaidDispatchService:Release(token)
    return self.queue:release(token, self.now())
end

function RaidDispatchService:Sweep()
    return self.queue:expire(self.now())
end

function RaidDispatchService:Snapshot()
    return self.queue:snapshot(self.now())
end

function RaidDispatchService:Save()
    return self.queue:save(self.now())
end

function RaidDispatchService:Load(data)
    self.queue = Queue.load(data, self.options)
    return { ok = true }
end

return RaidDispatchService
