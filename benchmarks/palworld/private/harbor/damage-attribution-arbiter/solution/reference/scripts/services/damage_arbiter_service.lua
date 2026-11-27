local Arbiter = require("combat.arbiter")

local DamageArbiterService = {}
DamageArbiterService.__index = DamageArbiterService

local function clock()
    return os.time()
end

function DamageArbiterService.new(options)
    options = type(options) == "table" and options or {}
    local self = setmetatable({}, DamageArbiterService)
    self.options = options.arbiter_options or { claim_seconds = 15 }
    self.now = options.now or clock
    self.arbiter = Arbiter.new(self.options)
    self.observed = {}
    return self
end

function DamageArbiterService:Track(object)
    if type(object) ~= "table" then return { ok = false, code = "invalid_object" } end
    if type(object.get) == "function" then
        local ok, unwrapped = pcall(object.get, object)
        if ok and unwrapped ~= nil then object = unwrapped end
    end
    if type(object.IsValid) == "function" and not object:IsValid() then
        return { ok = false, code = "invalid_object" }
    end
    self.observed[tostring(object)] = object
    return { ok = true }
end

function DamageArbiterService:Observe(report)
    return self.arbiter:observe(report)
end

function DamageArbiterService:Claim(attacker_id, target_id)
    return self.arbiter:claim(attacker_id, target_id, self.now())
end

function DamageArbiterService:Renew(token)
    return self.arbiter:renew(token, self.now())
end

function DamageArbiterService:Release(token)
    return self.arbiter:release(token, self.now())
end

function DamageArbiterService:Resolve(target_id)
    return self.arbiter:resolve(target_id, self.now())
end

function DamageArbiterService:Sweep()
    return self.arbiter:sweep(self.now())
end

function DamageArbiterService:Snapshot()
    return self.arbiter:snapshot(self.now())
end

function DamageArbiterService:Save()
    return self.arbiter:save(self.now())
end

function DamageArbiterService:Load(data)
    self.arbiter = Arbiter.load(data, self.options)
    return { ok = true }
end

return DamageArbiterService
