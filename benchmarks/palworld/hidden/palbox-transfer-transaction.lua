local loaded, Transaction = pcall(load_submission, "scripts/palboxtransfer/transaction.lua")
if not loaded or type(Transaction) ~= "table" then Transaction = {} end
local cases = {}
local function expect(v, m) if not v then error(m or "expectation failed", 0) end end
local function run(name, body) local ok,msg=pcall(body); cases[#cases+1]={name=name,passed=ok,message=ok and "ok" or tostring(msg)} end

local function adapter(state)
    local calls = {}
    local a = {}
    a.calls = calls
    a.state = state
    a.fail_add = false
    a.fail_restore = false
    function a.snapshot(id)
        calls[#calls + 1] = "snapshot:" .. id
        local copy = {}
        for slot, entry in ipairs(state[id].entries) do
            copy[slot] = { pal_id = entry.pal_id, count = entry.count, level = entry.level, gender = entry.gender }
        end
        return { entries = copy, limit = state[id].limit }
    end
    function a.capacity(id, pal_id)
        calls[#calls + 1] = "capacity:" .. id
        return state[id].limit - #state[id].entries
    end
    function a.remove(id, pal_id, count)
        calls[#calls + 1] = "remove:" .. id
        local taken = {}
        for slot = 1, #state[id].entries do
            local entry = state[id].entries[slot]
            if entry ~= nil and entry.pal_id == pal_id and #taken < count then
                taken[#taken + 1] = entry
                state[id].entries[slot] = false
            end
        end
        if #taken < count then return nil, "insufficient_source" end
        local compacted = {}
        for _, entry in ipairs(state[id].entries) do
            if entry then compacted[#compacted + 1] = entry end
        end
        state[id].entries = compacted
        return taken
    end
    function a.add(id, entries)
        calls[#calls + 1] = "add:" .. id
        if a.fail_add then return nil, "adapter_error" end
        for _, entry in ipairs(entries) do
            state[id].entries[#state[id].entries + 1] = entry
        end
        return entries
    end
    function a.restore(id, snapshot)
        calls[#calls + 1] = "restore:" .. id
        if a.fail_restore then return nil, "adapter_error" end
        local restored = {}
        for slot, entry in ipairs(snapshot.entries) do restored[slot] = entry end
        state[id].entries = restored
        return true
    end
    return a
end

local function world()
    return {
        box = { limit = 4, entries = {
            { pal_id = "lamball", count = 1, level = 7, gender = "female" },
            { pal_id = "cattiva", count = 1, level = 3, gender = "male" },
            { pal_id = "lamball", count = 1, level = 9, gender = "male" },
        } },
        party = { limit = 3, entries = {} },
        full = { limit = 0, entries = {} },
    }
end

local function fresh(state)
    expect(type(Transaction.new) == "function", "module must export Transaction.new")
    local a = adapter(state)
    return Transaction.new(a), a
end

local request = { request_id = "t1", source_id = "box", destination_id = "party", pal_id = "lamball", count = 2 }

run("malformed requests are rejected before any adapter call", function()
    local state = world()
    local transaction, a = fresh(state)
    expect(transaction:transfer({ request_id = "x", source_id = "box", destination_id = "box", pal_id = "lamball", count = 1 }).code == "same_container")
    expect(transaction:transfer({ request_id = "y", source_id = "box", destination_id = "party", pal_id = "lamball", count = 0 }).code == "invalid_request")
    expect(transaction:transfer({ request_id = "z", source_id = "box", destination_id = "party", pal_id = "lamball", count = 1.5 }).code == "invalid_request")
    expect(transaction:transfer({ source_id = "box", destination_id = "party", pal_id = "lamball", count = 1 }).code == "invalid_request")
    expect(#a.calls == 0, "adapter was called for a rejected request")
end)

run("capacity preflight leaves both containers untouched", function()
    local state = world()
    local transaction = fresh(state)
    local result = transaction:transfer({ request_id = "t1", source_id = "box", destination_id = "full", pal_id = "lamball", count = 2 })
    expect(result.ok == false and result.code == "insufficient_capacity", "capacity was not preflighted")
    expect(#state.box.entries == 3 and #state.full.entries == 0, "a container mutated on a capacity failure")
    local missing = transaction:transfer({ request_id = "t2", source_id = "box", destination_id = "party", pal_id = "chikipi", count = 1 })
    expect(missing.ok == false and missing.code == "insufficient_source")
    expect(#state.box.entries == 3, "source mutated on an insufficient-source failure")
end)

run("a committed transfer preserves ordering and metadata", function()
    local state = world()
    local transaction = fresh(state)
    expect(transaction:transfer(request).state == "committed")
    expect(#state.box.entries == 1 and state.box.entries[1].pal_id == "cattiva")
    expect(#state.party.entries == 2, "destination did not receive both entries")
    expect(state.party.entries[1].level == 7 and state.party.entries[1].gender == "female", "slot order or metadata lost")
    expect(state.party.entries[2].level == 9 and state.party.entries[2].gender == "male", "slot order or metadata lost")
end)

run("a failed add compensates in reverse order", function()
    local state = world()
    local transaction, a = fresh(state)
    a.fail_add = true
    local result = transaction:transfer(request)
    expect(result.ok == false and result.code == "adapter_error")
    expect(result.state == "compensated", "failed transfer was not compensated")
    expect(#state.box.entries == 3 and #state.party.entries == 0, "compensation did not restore both containers")
    local order = {}
    for _, call in ipairs(a.calls) do
        if call == "restore:party" or call == "restore:box" then order[#order + 1] = call end
    end
    expect(order[1] == "restore:party" and order[2] == "restore:box", "destination must be restored before the source")
end)

run("failed compensation is reported as unrecoverable", function()
    local state = world()
    local transaction, a = fresh(state)
    a.fail_add = true
    a.fail_restore = true
    local result = transaction:transfer(request)
    expect(result.ok == false, "an unrecoverable transfer reported success")
    expect(result.state == "unrecoverable", "compensation failure was swallowed")
    expect(transaction:status("t1").state == "unrecoverable", "status did not record the unrecoverable phase")
end)

run("request identifiers are deduplicated across every outcome", function()
    local state = world()
    local transaction, a = fresh(state)
    expect(transaction:transfer(request).state == "committed")
    local before = #a.calls
    local retry = transaction:transfer(request)
    expect(retry.ok == true and retry.duplicate == true, "retry did not replay the original outcome")
    expect(#a.calls == before, "a committed request called the adapter again")
    expect(transaction:status("t1").state == "committed")
    expect(transaction:status("never").state == "unknown")
end)

run("recover finishes persisted phases and is idempotent", function()
    local state = world()
    local transaction, a = fresh(state)
    a.fail_add = true
    transaction:transfer(request)
    expect(type(Transaction.load) == "function", "module must export Transaction.load")
    local restored = Transaction.load(adapter(state), transaction:save())
    local first = restored:recover()
    expect(first.ok == true, "recover failed on a persisted transaction")
    local second = restored:recover()
    expect(second.ok == true and second.recovered == 0 and second.compensated == 0, "recover is not idempotent")
    expect(restored:transfer(request).duplicate == true, "deduplication was lost across reload")
end)

return {cases=cases}
