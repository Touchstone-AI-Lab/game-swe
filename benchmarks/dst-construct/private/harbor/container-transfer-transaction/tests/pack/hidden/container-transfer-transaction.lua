local loaded, Transaction = pcall(load_submission, "scripts/containertransfer/transaction.lua")
if not loaded or type(Transaction) ~= "table" then Transaction = {} end
local cases = {}
local function expect(value, message) if not value then error(message or "expectation failed", 0) end end
local function run(name, body)
    local ok, message = pcall(body)
    cases[#cases + 1] = { name = name, passed = ok, message = ok and "ok" or tostring(message) }
end
local function copy_items(items)
    local result = {}
    for i, item in ipairs(items) do
        local row = {}; for key, value in pairs(item) do row[key] = value end
        result[i] = row
    end
    return result
end
local function adapter(options)
    options = options or {}
    local value = {
        stores = {
            a = { { slot = 3, prefab = "twigs", count = 2 }, { slot = 1, prefab = "twigs", count = 3 } },
            b = {},
        },
        calls = {},
    }
    function value:snapshot(id)
        self.calls[#self.calls + 1] = "snapshot:" .. id
        return copy_items(self.stores[id] or {})
    end
    function value:capacity(id, prefab)
        self.calls[#self.calls + 1] = "capacity:" .. id .. ":" .. prefab
        return options.capacity or 20
    end
    function value:remove(id, prefab, count)
        self.calls[#self.calls + 1] = "remove:" .. id
        if options.remove_fail then return nil, "remove-failed" end
        local remaining, removed = count, {}
        table.sort(self.stores[id], function(a, b) return a.slot < b.slot end)
        for _, item in ipairs(self.stores[id]) do
            if item.prefab == prefab and remaining > 0 then
                local take = math.min(item.count, remaining)
                removed[#removed + 1] = { slot = item.slot, prefab = item.prefab, count = take }
                item.count = item.count - take; remaining = remaining - take
            end
        end
        if remaining > 0 then return nil, "insufficient" end
        return removed
    end
    function value:add(id, items)
        self.calls[#self.calls + 1] = "add:" .. id
        if options.add_fail then return false, "add-failed" end
        for _, item in ipairs(items) do self.stores[id][#self.stores[id] + 1] = item end
        return true
    end
    function value:restore(id, snapshot)
        self.calls[#self.calls + 1] = "restore:" .. id
        if options.restore_fail and id == options.restore_fail then return false, "restore-failed" end
        self.stores[id] = copy_items(snapshot); return true
    end
    return value
end
local request = { request_id = "r1", source_id = "a", destination_id = "b", prefab = "twigs", count = 4 }
local function fresh(value)
    expect(type(Transaction.new) == "function", "module must export Transaction.new")
    return Transaction.new(value, nil)
end

run("successful transfer uses deterministic source slots", function()
    local api = adapter(); local tx = fresh(api)
    local result = tx:transfer(request)
    expect(type(result) == "table" and result.ok == true and result.status == "committed")
    expect(api.calls[1] == "snapshot:a" and api.calls[2] == "snapshot:b")
    expect(api.stores.b[1].slot == 1, "source items were not selected by slot")
end)

run("capacity preflight prevents destructive calls", function()
    local api = adapter({ capacity = 2 }); local tx = fresh(api)
    expect(tx:transfer(request).ok == false)
    local merged = table.concat(api.calls, ",")
    expect(not string.find(merged, "remove", 1, true) and not string.find(merged, "add", 1, true))
end)

run("add failure restores destination before source", function()
    local api = adapter({ add_fail = true }); local tx = fresh(api)
    expect(tx:transfer(request).ok == false)
    local destination_restore, source_restore
    for i, call in ipairs(api.calls) do
        if call == "restore:b" then destination_restore = i end
        if call == "restore:a" then source_restore = i end
    end
    expect(destination_restore and source_restore and destination_restore < source_restore)
    expect(#api.stores.a == 2 and #api.stores.b == 0, "compensation did not restore snapshots")
end)

run("committed retry invokes no adapter operations", function()
    local api = adapter(); local tx = fresh(api)
    expect(tx:transfer(request).ok == true)
    local count = #api.calls
    expect(tx:transfer(request).status == "committed")
    expect(#api.calls == count, "retry invoked adapter")
end)

run("malformed request is rejected before adapter", function()
    local api = adapter(); local tx = fresh(api)
    expect(tx:transfer({ request_id = "x", source_id = "a", destination_id = "a", prefab = "twigs", count = -1 }).ok == false)
    expect(#api.calls == 0)
end)

run("save load preserves committed idempotency", function()
    local first_api = adapter(); local tx = fresh(first_api)
    expect(tx:transfer(request).ok == true)
    expect(type(Transaction.load) == "function")
    local next_api = adapter(); local restored = Transaction.load(next_api, tx:save())
    expect(restored:transfer(request).status == "committed")
    expect(#next_api.calls == 0)
end)

return { cases = cases }
