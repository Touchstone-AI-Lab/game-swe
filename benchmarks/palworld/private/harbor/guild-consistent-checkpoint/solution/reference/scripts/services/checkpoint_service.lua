local Core = require("checkpoint.core")
local Service = {}
Service.__index = Service
function Service.new(options)
    local self = setmetatable({}, Service)
    self:Reset(options)
    return self
end
function Service:Reset(options)
    self.core = Core.new(options or {"a", "b", "c"})
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
function Service:Append(...)
    return self.core:append(...)
end

function Service:Cut(...)
    return self.core:cut(...)
end

return Service
