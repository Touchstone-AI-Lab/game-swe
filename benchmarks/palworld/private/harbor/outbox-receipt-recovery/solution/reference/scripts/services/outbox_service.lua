local Core = require("outbox.core")
local Service = {}
Service.__index = Service
function Service.new(options)
    local self = setmetatable({}, Service)
    self:Reset(options)
    return self
end
function Service:Reset(options)
    self.core = Core.new()
    return {ok = true}
end
function Service:Save()
    return self.core:save()
end
function Service:Load(data)
    local restored = Core.load(data)
    self.core = restored
    return {ok = true}
end
function Service:Snapshot()
    return self.core:snapshot()
end
function Service:Submit(...)
    return self.core:submit(...)
end

function Service:Drain(...)
    return self.core:drain(...)
end

function Service:Status(...)
    return self.core:status(...)
end

return Service
