local Core = require("epoch.core")
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
function Service:Mount(...)
    return self.core:mount(...)
end

function Service:Schedule(...)
    return self.core:schedule(...)
end

function Service:Poll(...)
    return self.core:poll(...)
end

function Service:Ack(...)
    return self.core:ack(...)
end

function Service:Cancel(...)
    return self.core:cancel(...)
end

return Service
