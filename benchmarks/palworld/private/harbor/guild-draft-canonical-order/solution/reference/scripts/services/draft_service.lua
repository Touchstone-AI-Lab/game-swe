local Core = require("draft.core")
local Service = {}
Service.__index = Service
function Service.new()
    return setmetatable({core=Core.new(),active=true},Service)
end
function Service:Reset()
    if not self.active then return {ok=false,code="unmounted"} end
    self.core=Core.new()
    return {ok=true}
end
function Service:Plan(input)
    if not self.active then return {ok=false,code="unmounted"} end
    return self.core:plan(input)
end
function Service:Save()
    return self.core:save()
end
function Service:Snapshot()
    return self.core:snapshot()
end
function Service:Load(data)
    if not self.active then return {ok=false,code="unmounted"} end
    local candidate=Core.load(data)
    self.core=candidate
    return {ok=true}
end
function Service:Unmount()
    if not self.active then return end
    self.active=false
    if self.release then self.release() end
end
return Service
