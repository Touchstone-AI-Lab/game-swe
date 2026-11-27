local loaded, Dispatch = pcall(load_submission, "scripts/rescuedispatch/dispatch.lua")
if not loaded or type(Dispatch) ~= "table" then Dispatch = {} end
local cases = {}
local function expect(v, m) if not v then error(m or "expectation failed", 0) end end
local function run(name, body) local ok, msg = pcall(body); cases[#cases + 1] = { name=name, passed=ok, message=ok and "ok" or tostring(msg) } end
local options = { lease_ttl = 10, aging_interval = 20 }
local function fresh()
    expect(type(Dispatch.new) == "function", "module must export Dispatch.new")
    local d = Dispatch.new(options)
    for _, id in ipairs({"a", "b", "h1", "h2"}) do
        expect(d:update_player({ id=id, revision=1, connected=true, alive=true, health_percent=.5 }, 0) ~= false)
    end
    return d
end

run("priority ordering is severity then time then id", function()
    local d = fresh()
    expect(d:request("ra", "a", 2, 1).ok)
    expect(d:request("rb", "b", 4, 2).ok)
    local lease = d:volunteer("vh", "h1", 3)
    expect(lease.ok and lease.target_id == "b")
end)

run("one helper and target own at most one lease", function()
    local d = fresh(); d:request("ra", "a", 3, 1); d:request("rb", "b", 2, 1)
    local first = d:volunteer("v1", "h1", 2)
    expect(first.ok)
    expect(d:volunteer("v2", "h1", 2).ok == false, "helper received two leases")
    local second = d:volunteer("v3", "h2", 2)
    expect(second.ok and second.target_id ~= first.target_id)
end)

run("lease expiry requeues unresolved target", function()
    local d = fresh(); d:request("ra", "a", 3, 0)
    local lease = d:volunteer("v1", "h1", 1)
    d:tick(lease.expires_at)
    local next_lease = d:volunteer("v2", "h2", lease.expires_at)
    expect(next_lease.ok and next_lease.target_id == "a" and next_lease.lease_id ~= lease.lease_id)
    expect(d:heartbeat(lease.lease_id, "h1", lease.expires_at).ok == false, "expired lease revived")
end)

run("request and volunteer retries are stable", function()
    local d = fresh()
    local first = d:request("same", "a", 3, 0)
    local retry = d:request("same", "b", 5, 1)
    expect(retry.target_id == first.target_id)
    local lease = d:volunteer("vol", "h1", 2)
    local again = d:volunteer("vol", "h1", 3)
    expect(again.lease_id == lease.lease_id)
end)

run("disconnect releases helper and recovery closes target", function()
    local d = fresh(); d:request("ra", "a", 3, 0)
    local lease = d:volunteer("v1", "h1", 1); expect(lease.ok)
    d:update_player({ id="h1", revision=2, connected=false, alive=true, health_percent=.5 }, 2)
    expect(d:volunteer("v2", "h2", 3).target_id == "a")
    d:update_player({ id="a", revision=2, connected=true, alive=true, health_percent=1 }, 4)
    local snap = d:snapshot(4)
    expect(#snap.queue == 0 and #snap.leases == 0)
end)

run("save load preserves active lease and defensive snapshot", function()
    local d = fresh(); d:request("ra", "a", 3, 0)
    local lease = d:volunteer("v1", "h1", 1)
    local snap = d:snapshot(2); snap.queue = {}; snap.leases = {}
    expect(type(Dispatch.load) == "function")
    local restored = Dispatch.load(d:save(2), options)
    expect(restored:heartbeat(lease.lease_id, "h1", 2).ok)
    expect(#restored:snapshot(2).leases == 1, "snapshot mutated state")
end)

return { cases = cases }
