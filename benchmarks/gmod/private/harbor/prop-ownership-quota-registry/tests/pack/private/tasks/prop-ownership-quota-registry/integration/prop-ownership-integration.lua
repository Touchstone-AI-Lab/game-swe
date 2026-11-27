local cases = {}
local function case(name, body)
    local ok, message = pcall(body)
    cases[#cases + 1] = { name = name, passed = ok, message = ok and "ok" or tostring(message) }
end
local function equal(left, right) if left ~= right then error(tostring(left) .. " ~= " .. tostring(right), 2) end end

local hooks = {}
local timers = {}
local now = 0
local hook_api = {
    Add = function(event, name, callback) hooks[event .. "/" .. name] = callback end,
    Remove = function(event, name) hooks[event .. "/" .. name] = nil end,
}
local timer_api = {
    Create = function(name, delay, repetitions, callback)
        timers[name] = { delay = delay, repetitions = repetitions, callback = callback }
    end,
    Remove = function(name) timers[name] = nil end,
    Exists = function(name) return timers[name] ~= nil end,
}
local function is_valid(value) return type(value) == "table" and value.valid ~= false end
local function player(name)
    return { valid = true, name = name, IsPlayer = function() return true end }
end
local function entity(index)
    local value = { valid = true, index = index, removed = 0 }
    function value:GetClass() return "prop_physics" end
    function value:EntIndex() return self.index end
    function value:Remove() self.removed = self.removed + 1; self.valid = false end
    return value
end

local bindings
local function include(path)
    assert(path == "rhenium_prop_registry/registry.lua")
    return load_submission("lua/rhenium_prop_registry/registry.lua", bindings)
end
bindings = {
    hook = hook_api, timer = timer_api, CurTime = function() return now end,
    IsValid = is_valid, isstring = function(v) return type(v) == "string" end,
    isnumber = function(v) return type(v) == "number" end, include = include,
}
local Server = load_submission("lua/rhenium_prop_registry/server.lua", bindings)

case("adapter installs required hooks and timer", function()
    Server.Install({ max_props = 2, cleanup_delay = 5 })
    for _, event in ipairs({ "PhysgunPickup", "CanTool", "CanProperty", "EntityRemoved", "PlayerDisconnected", "PlayerInitialSpawn" }) do
        assert(hooks[event .. "/" .. Server.HookPrefix .. "." .. event])
    end
    assert(timers[Server.TimerName])
end)

local a, b = player("A"), player("B")
local first = entity(10)
case("entity bindings reject malformed logical identity and revision", function()
    local ok, code = Server.BindEntity(first, "bad id", 1)
    assert(not ok); equal(code, "invalid_entity")
    ok, code = Server.BindEntity(first, "prop:trusted", 0)
    assert(not ok); equal(code, "invalid_entity")
    ok, code = Server.BindEntity(first, "prop:trusted", 1.5)
    assert(not ok); equal(code, "invalid_entity")
end)

case("trusted player binding owns the prop", function()
    assert(Server.BindPlayer(a, "A")); assert(Server.BindPlayer(b, "B"))
    assert(Server.BindEntity(first, "prop:trusted", 1))
    assert(Server.RegisterProp(a, first, "register:1"))
    local snapshot = Server.Snapshot()
    equal(snapshot.entities[1].owner_id, "A")
end)

case("benchmark identity is independent of EntIndex", function()
    local collision = entity(10)
    assert(Server.BindEntity(collision, "prop:collision", 1))
    assert(Server.RegisterProp(b, collision, "register:collision"))
    local snapshot = Server.Snapshot()
    equal(#snapshot.entities, 2)
    local ids = { [snapshot.entities[1].entity_id] = true, [snapshot.entities[2].entity_id] = true }
    assert(ids["prop:trusted"] and ids["prop:collision"])
end)

case("all modification entry points reject non-owner", function()
    local prefix = Server.HookPrefix
    assert(hooks["PhysgunPickup/" .. prefix .. ".PhysgunPickup"](b, first) == false)
    assert(hooks["CanTool/" .. prefix .. ".CanTool"](b, { Entity = first }, "remover") == false)
    assert(hooks["CanProperty/" .. prefix .. ".CanProperty"](b, "remover", first) == false)
    local ok = Server.HandleDeleteRequest(b, first, "delete:b", "A")
    assert(ok == false); assert(first.valid)
end)

case("client owner payload cannot override server player", function()
    local ok = Server.HandleDeleteRequest(b, first, "delete:forged", "A")
    assert(ok == false); assert(first.valid)
end)

case("quota rejects and removes third prop", function()
    local second, third = entity(11), entity(12)
    assert(Server.BindEntity(second, "prop:2", 1)); assert(Server.RegisterProp(a, second, "register:2"))
    assert(Server.BindEntity(third, "prop:3", 1))
    local ok, code = Server.RegisterProp(a, third, "register:3")
    assert(not ok); equal(code, "quota_exceeded"); assert(not third.valid)
end)

case("entity removal releases once and revision blocks EntIndex reuse", function()
    local prefix = Server.HookPrefix
    hooks["EntityRemoved/" .. prefix .. ".EntityRemoved"](first)
    hooks["EntityRemoved/" .. prefix .. ".EntityRemoved"](first)
    first.valid = false
    local after_removal = Server.Snapshot()
    local stale = false
    for _, item in ipairs(after_removal.entities) do
        if item.entity_id == "prop:trusted" then stale = true end
    end
    assert(not stale)
    local replacement = entity(10)
    assert(Server.BindEntity(replacement, "prop:trusted", 2))
    assert(Server.RegisterProp(b, replacement, "register:new-generation"))
    assert(hooks["PhysgunPickup/" .. prefix .. ".PhysgunPickup"](a, replacement) == false)
    assert(hooks["PhysgunPickup/" .. prefix .. ".PhysgunPickup"](b, replacement) == true)
end)

case("disconnect cleanup and reconnect use real hooks", function()
    local prefix = Server.HookPrefix
    hooks["PlayerDisconnected/" .. prefix .. ".PlayerDisconnected"](b)
    now = 4.999; timers[Server.TimerName].callback()
    local before_reconnect = Server.Snapshot()
    local present_before = false
    for _, item in ipairs(before_reconnect.entities) do
        if item.entity_id == "prop:trusted" and item.revision == 2 then present_before = true end
    end
    assert(present_before)
    hooks["PlayerInitialSpawn/" .. prefix .. ".PlayerInitialSpawn"](b)
    now = 10; timers[Server.TimerName].callback()
    local after_reconnect = Server.Snapshot()
    local present_after = false
    for _, item in ipairs(after_reconnect.entities) do
        if item.entity_id == "prop:trusted" and item.revision == 2 then present_after = true end
    end
    assert(present_after)
end)

case("shutdown removes hooks and timer", function()
    assert(Server.Shutdown()); assert(Server.Shutdown())
    for key in pairs(hooks) do
        if string.find(key, "RheniumPropRegistry", 1, true) then error("hook leaked") end
    end
    assert(not timers[Server.TimerName])
end)

return { cases = cases }
