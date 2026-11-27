local cases = {}

local function case(name, body)
    local ok, message = pcall(body)
    cases[#cases + 1] = { name = name, passed = ok, message = ok and "ok" or tostring(message) }
end

local function equal(left, right, message)
    if left ~= right then error((message or "values differ") .. ": " .. tostring(left) .. " ~= " .. tostring(right), 2) end
end

local Registry = load_submission("lua/rhenium_prop_registry/registry.lua")

local function fresh(state, storage)
    local value, error_code = Registry.new({ max_props = 2, cleanup_delay = 5, state = state, storage = storage })
    assert(value, error_code)
    return value
end

case("first registration increments quota", function()
    local registry = fresh()
    local ok, code, data = registry:register("r1", "A", "prop:1", 1)
    assert(ok); equal(code, "registered"); equal(data.count, 1)
    equal(registry:snapshot(0).owners[1].count, 1)
end)

case("third prop is rejected without replacing state", function()
    local registry = fresh()
    assert(registry:register("r1", "A", "prop:1", 1))
    assert(registry:register("r2", "A", "prop:2", 1))
    local ok, code = registry:register("r3", "A", "prop:3", 1)
    assert(not ok); equal(code, "quota_exceeded")
    equal(#registry:snapshot(0).entities, 2)
end)

case("register retries are exact and request conflicts fail", function()
    local registry = fresh()
    local ok1, code1, data1 = registry:register("r1", "A", "prop:1", 1)
    local ok2, code2, data2 = registry:register("r1", "A", "prop:1", 1)
    assert(ok1 and ok2); equal(code1, code2); equal(data1.count, data2.count)
    equal(#registry:snapshot(0).entities, 1)
    local ok3, code3 = registry:register("r1", "A", "prop:2", 1)
    assert(not ok3); equal(code3, "request_conflict")
end)

case("remove retries release quota exactly once", function()
    local registry = fresh()
    assert(registry:register("r1", "A", "prop:1", 1))
    local ok1, code1, data1 = registry:remove("x1", "prop:1", 1)
    local ok2, code2, data2 = registry:remove("x1", "prop:1", 1)
    assert(ok1 and ok2); equal(code1, "removed"); equal(code2, code1)
    equal(data1.count, 0); equal(data2.count, 0)
    local ok3, code3 = registry:remove("x2", "prop:1", 1)
    assert(not ok3); equal(code3, "not_found")
end)

case("revision replacement rejects stale authority", function()
    local registry = fresh()
    assert(registry:register("r1", "A", "prop:shared", 1))
    assert(registry:register("r2", "B", "prop:shared", 2))
    local allowed, code = registry:can_modify("A", "prop:shared", 1, "delete")
    assert(not allowed); equal(code, "stale_revision")
    assert(registry:can_modify("B", "prop:shared", 2, "delete"))
    equal(registry:snapshot(0).owners[1].player_id, "B")
end)

case("operations and ownership are enforced", function()
    local registry = fresh()
    assert(registry:register("r1", "A", "prop:1", 1))
    for _, operation in ipairs({ "physgun", "tool", "property_remover", "delete" }) do
        assert(registry:can_modify("A", "prop:1", 1, operation))
        local allowed, code = registry:can_modify("B", "prop:1", 1, operation)
        assert(not allowed); equal(code, "not_owner")
    end
    local allowed, code = registry:can_modify("A", "prop:1", 1, "unknown")
    assert(not allowed); equal(code, "invalid_operation")
end)

case("disconnect waits strictly below five seconds and cleans at boundary", function()
    local registry = fresh()
    assert(registry:register("r1", "A", "prop:1", 1))
    assert(registry:disconnect("A", 10))
    registry:tick(14.999)
    equal(#registry:snapshot(14.999).entities, 1)
    local ok, _, data = registry:tick(15)
    assert(ok); equal(#data.removed, 1); equal(#registry:snapshot(15).entities, 0)
end)

case("reconnect before boundary cancels cleanup", function()
    local registry = fresh()
    assert(registry:register("r1", "A", "prop:1", 1))
    registry:disconnect("A", 0)
    local ok, code = registry:reconnect("A", 4.999)
    assert(ok); equal(code, "canceled")
    registry:tick(100)
    equal(#registry:snapshot(100).entities, 1)
end)

case("time reversal is clamped", function()
    local registry = fresh()
    assert(registry:register("r1", "A", "prop:1", 1))
    registry:tick(20)
    local _, _, disconnected = registry:disconnect("A", 10)
    equal(disconnected.cleanup_at, 25)
    registry:tick(24.999)
    equal(#registry:snapshot(1).entities, 1)
    registry:tick(25)
    equal(#registry:snapshot(0).entities, 0)
end)

case("snapshot is deterministic and detached", function()
    local registry = fresh()
    assert(registry:register("r2", "B", "z", 1))
    assert(registry:register("r1", "A", "a", 1))
    local first = registry:snapshot(0)
    equal(first.entities[1].entity_id, "a"); equal(first.entities[2].entity_id, "z")
    equal(first.owners[1].player_id, "A"); equal(first.owners[2].player_id, "B")
    first.entities[1].owner_id = "tampered"
    equal(registry:snapshot(0).entities[1].owner_id, "A")
end)

case("save load round trip preserves request idempotency", function()
    local written = nil
    local storage = { save = function(_, value) written = value; return true end }
    local registry = fresh(nil, storage)
    assert(registry:register("r1", "A", "prop:1", 1))
    local state = assert(registry:save(3))
    assert(written ~= nil)
    local restored = fresh(state)
    local ok, code, data = restored:register("r1", "A", "prop:1", 1)
    assert(ok); equal(code, "registered"); equal(data.count, 1)
    equal(#restored:snapshot(3).entities, 1)
end)

case("shutdown is idempotent and freezes mutations", function()
    local registry = fresh()
    assert(registry:shutdown()); assert(registry:shutdown())
    local ok, code = registry:register("r1", "A", "prop:1", 1)
    assert(not ok); equal(code, "shutdown")
end)

case("only the exact public two prop five second options are accepted", function()
    for _, options in ipairs({
        { max_props = 1, cleanup_delay = 5 },
        { max_props = 3, cleanup_delay = 5 },
        { max_props = 2, cleanup_delay = 4.999 },
        { max_props = 2, cleanup_delay = 6 },
    }) do
        local value, code = Registry.new(options)
        assert(value == nil); equal(code, "invalid_options")
    end
    assert(Registry.new({ max_props = 2, cleanup_delay = 5 }))
end)

case("malformed saved state is rejected completely", function()
    local registry = fresh()
    assert(registry:register("r1", "A", "prop:1", 1))
    registry:disconnect("A", 1)
    local state = assert(registry:save(1))
    local variants = {}
    local function variant(change)
        local value = assert(registry:save(1))
        change(value)
        variants[#variants + 1] = value
    end
    variant(function(value) value.entities[2] = value.entities[1] end)
    variant(function(value) value.latest_revisions[2] = value.latest_revisions[1] end)
    variant(function(value) value.latest_revisions[1].revision = 0 end)
    variant(function(value) value.pending_cleanup[2] = value.pending_cleanup[1] end)
    variant(function(value) value.pending_cleanup[1].cleanup_at = value.last_now end)
    variant(function(value) value.requests[1].arguments = { "A" } end)
    variant(function(value) value.requests.extra = {} end)
    for _, value in ipairs(variants) do
        local loaded, code = Registry.new({ max_props = 2, cleanup_delay = 5, state = value })
        assert(loaded == nil); equal(code, "invalid_state")
    end
    state.max_props = 3
    local loaded, code = Registry.new({ max_props = 2, cleanup_delay = 5, state = state })
    assert(loaded == nil); equal(code, "state_configuration_mismatch")
end)

return { cases = cases }
