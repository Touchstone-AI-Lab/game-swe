local suite = RegisterMod("Construct Callback Transaction Verifier", 1)
local game = Game()
local json = require("json")

-- Synthetic run seeds; every case starts from LoadRaw(false, nil, <seed>) so that the
-- real MC_POST_UPDATE calls between frames cannot leak state into it.
local SEED = 4242
local OTHER_SEED = 5151
local WIDE_SEED = 3405691582
local SAVED_KEYS = "committed_count,run_seed,schema_version"
local CASES = {
    "use_item_starts_transaction",
    "duplicate_use_while_pending_ignored",
    "one_pending_transaction_max",
    "pending_sequence_is_committed_plus_one",
    "use_does_not_commit_count",
    "use_without_room_init_safe",
    "second_use_after_commit_starts_next",
    "update_prepared_to_applied",
    "applied_count_increments_once",
    "duplicate_update_is_idempotent",
    "update_noop_without_pending",
    "update_noop_after_applied",
    "update_failure_rolls_back_snapshot",
    "update_failure_does_not_advance_phase",
    "room_before_update_does_not_commit",
    "room_applied_commits_exactly_once",
    "duplicate_room_callback_noop",
    "commit_clears_pending",
    "commit_clears_journal",
    "callback_order_cannot_skip_update",
    "committed_transaction_not_reapplied",
    "save_serializes_exact_schema",
    "save_contains_run_seed",
    "save_after_commit_persists_count",
    "pending_prepared_discarded_on_save",
    "pending_applied_discarded_on_save",
    "continued_load_restores_count",
    "save_callback_does_not_advance_count",
    "continued_wrong_seed_defaults",
    "malformed_save_defaults",
    "missing_save_defaults",
    "new_run_resets_count",
    "new_run_clears_pending_journal",
    "save_failure_restores_memory_snapshot",
    "later_valid_save_recovers",
}

local passed = 0
local failed = 0
local recorded = {}
local finished = false
local started = false
local executed = false
-- Update frames observed since the run started; the suite body runs on the first one so
-- that every mod's MC_POST_GAME_STARTED handler has completed whatever the load order.
local updateFrames = 0
local startSeedAtStart = nil
local startupState = nil
local updateAudit = nil

local function log(text)
    Isaac.DebugString(text)
end

local function equal(actual, expected, label)
    if actual ~= expected then
        error((label or "value") .. ": expected " .. tostring(expected)
            .. ", received " .. tostring(actual), 0)
    end
end

local function truthy(value, label)
    if not value then
        error(label or "expected truthy value", 0)
    end
end

local function record(name, ok, detail)
    if recorded[name] then
        return
    end
    recorded[name] = true
    local text = (tostring(detail or (ok and "ok" or "failed")):gsub("[\r\n]+", " "))
    if ok then
        passed = passed + 1
        log("[GCB_CASE] PASS " .. name .. " " .. text)
    else
        failed = failed + 1
        log("[GCB_CASE] FAIL " .. name .. " " .. text)
    end
end

local function run(name, fn)
    local ok, result = pcall(fn)
    record(name, ok, result)
end

local function finish()
    if finished then
        return
    end
    finished = true
    -- Every case is reported exactly once even if the suite body stopped early.
    for _, name in ipairs(CASES) do
        if not recorded[name] then
            record(name, false, "case did not run")
        end
    end
    log("[GCB_SUMMARY] passed=" .. tostring(passed)
        .. " failed=" .. tostring(failed)
        .. " total=" .. tostring(passed + failed))
end

local function isInteger(value)
    return type(value) == "number"
        and value == value
        and value ~= math.huge
        and value ~= -math.huge
        and value % 1 == 0
end

-- The public contract represents "no pending transaction" and "no armed fault" by
-- absence; false is tolerated as the same thing.
local function absent(value)
    return value == nil or value == false
end

local function deepCopy(value, seen)
    if type(value) ~= "table" then
        return value
    end
    seen = seen or {}
    if seen[value] then
        return seen[value]
    end
    local copy = {}
    seen[value] = copy
    for key, item in pairs(value) do
        copy[deepCopy(key, seen)] = deepCopy(item, seen)
    end
    return copy
end

local function countEntries(value)
    local count = 0
    for _ in pairs(value) do
        count = count + 1
    end
    return count
end

local function describePending(pending)
    if absent(pending) then
        return "none"
    end
    if type(pending) ~= "table" then
        return tostring(pending)
    end
    return "{seq=" .. tostring(pending.seq) .. ",stage=" .. tostring(pending.stage) .. "}"
end

local function describeJournal(journal)
    if type(journal) ~= "table" then
        return tostring(journal)
    end
    local parts = {}
    for index, entry in ipairs(journal) do
        parts[index] = describePending(entry)
    end
    return "[" .. table.concat(parts, ",") .. "] entries=" .. tostring(countEntries(journal))
end

local function transactionApi()
    local api = IsaacConstructTransaction
    truthy(type(api) == "table", "IsaacConstructTransaction is not exported")
    return api
end

-- A private copy of one snapshot, for comparisons after later transitions.
local function capture(api)
    local current = api.Snapshot()
    truthy(type(current) == "table", "Snapshot did not return a table")
    return deepCopy(current)
end

-- Asserts the ledger fields of one snapshot. `expected.stage == nil` means no pending
-- transaction and an empty journal; otherwise pending and the single journal entry both
-- carry `expected.seq` and `expected.stage`.
local function expectState(current, expected, label)
    truthy(type(current) == "table", label .. ": Snapshot did not return a table")
    if expected.runSeed ~= nil then
        equal(current.runSeed, expected.runSeed, label .. ": runSeed")
    end
    equal(current.committed_count, expected.committed, label .. ": committed_count")
    equal(current.applied_count, expected.applied, label .. ": applied_count")
    local journal = current.journal
    truthy(type(journal) == "table", label .. ": journal is not a table")
    if expected.stage == nil then
        truthy(absent(current.pending),
            label .. ": unexpected pending " .. describePending(current.pending))
        equal(countEntries(journal), 0, label .. ": journal entries")
        return
    end
    local pending = current.pending
    truthy(type(pending) == "table", label .. ": pending transaction missing")
    equal(pending.seq, expected.seq, label .. ": pending.seq")
    equal(pending.stage, expected.stage, label .. ": pending.stage")
    equal(countEntries(journal), 1, label .. ": journal entries")
    local entry = journal[1]
    truthy(type(entry) == "table", label .. ": journal[1] is not a table")
    equal(entry.seq, expected.seq, label .. ": journal[1].seq")
    equal(entry.stage, expected.stage, label .. ": journal[1].stage")
end

local function samePending(left, right)
    if absent(left) or absent(right) then
        return absent(left) and absent(right)
    end
    return type(left) == "table" and type(right) == "table"
        and left.seq == right.seq and left.stage == right.stage
end

local function sameJournal(left, right)
    if type(left) ~= "table" or type(right) ~= "table"
        or countEntries(left) ~= countEntries(right) or #left ~= #right then
        return false
    end
    for index = 1, #left do
        if not samePending(left[index], right[index])
            or absent(left[index]) or absent(right[index]) then
            return false
        end
    end
    return true
end

-- Asserts that every snapshot field equals an earlier captured snapshot.
local function sameSnapshot(current, expected, label)
    truthy(type(current) == "table", label .. ": Snapshot did not return a table")
    equal(current.runSeed, expected.runSeed, label .. ": runSeed")
    equal(current.committed_count, expected.committed_count, label .. ": committed_count")
    equal(current.applied_count, expected.applied_count, label .. ": applied_count")
    truthy(samePending(current.pending, expected.pending),
        label .. ": pending " .. describePending(current.pending)
            .. " instead of " .. describePending(expected.pending))
    truthy(sameJournal(current.journal, expected.journal),
        label .. ": journal " .. describeJournal(current.journal)
            .. " instead of " .. describeJournal(expected.journal))
    equal(current.lastSavedRaw, expected.lastSavedRaw, label .. ": lastSavedRaw")
    truthy((absent(current.armedFault) and absent(expected.armedFault))
        or current.armedFault == expected.armedFault,
        label .. ": armedFault " .. tostring(current.armedFault)
            .. " instead of " .. tostring(expected.armedFault))
end

-- A non-continued start for `seed`, verified to be the empty ledger.
local function reset(seed)
    local api = transactionApi()
    api.LoadRaw(false, nil, seed)
    expectState(api.Snapshot(), { runSeed = seed, committed = 0, applied = 0 },
        "non-continued start")
    return api
end

-- One full use/update/room cycle, verified to commit exactly one transaction.
local function commitOne(api)
    local before = api.Snapshot().committed_count
    truthy(isInteger(before), "committed_count is not an integer: " .. tostring(before))
    api.UseItem()
    api.Update()
    api.NewRoom()
    expectState(api.Snapshot(), { committed = before + 1, applied = before + 1 },
        "commit to " .. tostring(before + 1))
end

-- Two committed transactions and a third one applied but not committed.
local function inFlight(seed)
    local api = reset(seed)
    commitOne(api)
    commitOne(api)
    api.UseItem()
    api.Update()
    expectState(api.Snapshot(), { committed = 2, applied = 3, seq = 3, stage = "applied" },
        "in-flight setup")
    return api
end

local function payload(count, seed)
    return '{"schema_version":1,"run_seed":' .. string.format("%d", seed)
        .. ',"committed_count":' .. string.format("%d", count) .. "}"
end

-- Decodes saved text and asserts that it holds exactly the three schema-1 fields.
local function decodeSaved(raw)
    truthy(type(raw) == "string", "saved text is not a string: " .. tostring(raw))
    local ok, decoded = pcall(json.decode, raw)
    truthy(ok and type(decoded) == "table", "saved text is not a JSON object: " .. raw)
    local keys = {}
    for key in pairs(decoded) do
        keys[#keys + 1] = tostring(key)
    end
    table.sort(keys)
    equal(table.concat(keys, ","), SAVED_KEYS, "decoded saved fields")
    local names = {}
    for name in raw:gmatch('"([^"]*)"%s*:') do
        names[#names + 1] = name
    end
    table.sort(names)
    equal(table.concat(names, ","), SAVED_KEYS, "encoded saved keys")
    equal(decoded.schema_version, 1, "schema_version")
    truthy(isInteger(decoded.run_seed), "run_seed is not an integer: " .. tostring(decoded.run_seed))
    truthy(isInteger(decoded.committed_count) and decoded.committed_count >= 0,
        "committed_count is not a non-negative integer: " .. tostring(decoded.committed_count))
    return decoded
end

-- Runs fn(probe) while the engine's mod-data writer is observed and returns the case
-- detail "savedata_probe=on|off". Every mod's SaveData reaches Isaac.SaveModData; the
-- suite's own SaveData call calibrates the hook first, so a build where it cannot be
-- installed only loses this extra evidence (probe.available stays false and the probe
-- checks are skipped). With probe.fail set, the submission's SaveData raises as a real
-- write failure would.
local function withSaveProbe(fn)
    local probe = { available = false, calibrated = false, fail = false, calls = {} }
    function probe.clear()
        probe.calls = {}
    end
    function probe.expectWrote(raw, label)
        if not probe.available then
            return
        end
        truthy(#probe.calls >= 1, label .. ": SaveNow did not reach SaveData")
        equal(probe.calls[#probe.calls], raw, label .. ": text passed to SaveData")
    end
    function probe.expectNoWrite(label)
        if not probe.available then
            return
        end
        equal(#probe.calls, 0, label .. ": SaveData calls")
    end

    local original = nil
    pcall(function()
        original = Isaac.SaveModData
    end)
    local installed = false
    if type(original) == "function" then
        installed = pcall(function()
            Isaac.SaveModData = function(owner, data)
                if owner == suite then
                    probe.calibrated = true
                else
                    probe.calls[#probe.calls + 1] = data
                    if probe.fail then
                        error("verifier simulated SaveData failure", 0)
                    end
                end
                return original(owner, data)
            end
        end)
        if installed then
            local wrote = pcall(function()
                suite:SaveData("probe")
            end)
            probe.available = wrote and probe.calibrated
            probe.calls = {}
        end
    end

    local ok, err = pcall(fn, probe)
    probe.fail = false
    if installed then
        pcall(function()
            Isaac.SaveModData = original
        end)
    end
    local detail = "savedata_probe=" .. (probe.available and "on" or "off")
    if not ok then
        error(tostring(err) .. " (" .. detail .. ")", 0)
    end
    return detail
end

local function executeSuite()
    run("use_item_starts_transaction", function()
        local api = reset(SEED)
        api.UseItem()
        expectState(api.Snapshot(),
            { runSeed = SEED, committed = 0, applied = 0, seq = 1, stage = "prepared" },
            "first use")
    end)

    run("duplicate_use_while_pending_ignored", function()
        local api = reset(SEED)
        api.UseItem()
        api.UseItem()
        api.UseItem()
        expectState(api.Snapshot(), { committed = 0, applied = 0, seq = 1, stage = "prepared" },
            "uses while prepared")
        api.Update()
        api.UseItem()
        expectState(api.Snapshot(), { committed = 0, applied = 1, seq = 1, stage = "applied" },
            "use while applied")
        api.NewRoom()
        expectState(api.Snapshot(), { committed = 1, applied = 1 },
            "commit leaves no queued use behind")
    end)

    run("one_pending_transaction_max", function()
        local api = reset(SEED)
        local steps = {
            { "UseItem", { committed = 0, applied = 0, seq = 1, stage = "prepared" } },
            { "UseItem", { committed = 0, applied = 0, seq = 1, stage = "prepared" } },
            { "Update", { committed = 0, applied = 1, seq = 1, stage = "applied" } },
            { "UseItem", { committed = 0, applied = 1, seq = 1, stage = "applied" } },
            { "Update", { committed = 0, applied = 1, seq = 1, stage = "applied" } },
            { "UseItem", { committed = 0, applied = 1, seq = 1, stage = "applied" } },
            { "NewRoom", { committed = 1, applied = 1 } },
            { "UseItem", { committed = 1, applied = 1, seq = 2, stage = "prepared" } },
            { "UseItem", { committed = 1, applied = 1, seq = 2, stage = "prepared" } },
            { "Update", { committed = 1, applied = 2, seq = 2, stage = "applied" } },
            { "UseItem", { committed = 1, applied = 2, seq = 2, stage = "applied" } },
        }
        for index, step in ipairs(steps) do
            api[step[1]]()
            expectState(api.Snapshot(), step[2], "step " .. tostring(index) .. " " .. step[1])
        end
    end)

    run("pending_sequence_is_committed_plus_one", function()
        local api = reset(SEED)
        for count = 0, 3 do
            api.UseItem()
            expectState(api.Snapshot(),
                { committed = count, applied = count, seq = count + 1, stage = "prepared" },
                "use at committed_count " .. tostring(count))
            api.Update()
            api.NewRoom()
        end
        expectState(api.Snapshot(), { committed = 4, applied = 4 }, "after four commits")
        api.LoadRaw(true, payload(9, SEED), SEED)
        expectState(api.Snapshot(), { runSeed = SEED, committed = 9, applied = 9 },
            "continued with committed_count 9")
        api.UseItem()
        expectState(api.Snapshot(), { committed = 9, applied = 9, seq = 10, stage = "prepared" },
            "use after continue")
    end)

    run("use_does_not_commit_count", function()
        local api = reset(SEED)
        api.UseItem()
        expectState(api.Snapshot(), { committed = 0, applied = 0, seq = 1, stage = "prepared" },
            "use on an empty ledger")
        api.Update()
        api.NewRoom()
        commitOne(api)
        api.UseItem()
        api.UseItem()
        expectState(api.Snapshot(), { committed = 2, applied = 2, seq = 3, stage = "prepared" },
            "use after two commits")
    end)

    run("use_without_room_init_safe", function()
        -- No room callback runs between these starts and the item-use/update handlers.
        local api = reset(SEED)
        api.Update()
        expectState(api.Snapshot(), { committed = 0, applied = 0 }, "update before any use")
        api.UseItem()
        expectState(api.Snapshot(), { committed = 0, applied = 0, seq = 1, stage = "prepared" },
            "use before any room callback")
        api.Update()
        expectState(api.Snapshot(), { committed = 0, applied = 1, seq = 1, stage = "applied" },
            "update before any room callback")
        api.LoadRaw(true, payload(4, SEED), SEED)
        api.UseItem()
        api.Update()
        expectState(api.Snapshot(), { committed = 4, applied = 5, seq = 5, stage = "applied" },
            "use and update right after a continue")
    end)

    run("second_use_after_commit_starts_next", function()
        local api = reset(SEED)
        commitOne(api)
        api.UseItem()
        expectState(api.Snapshot(), { committed = 1, applied = 1, seq = 2, stage = "prepared" },
            "second use")
        api.Update()
        expectState(api.Snapshot(), { committed = 1, applied = 2, seq = 2, stage = "applied" },
            "second update")
        api.NewRoom()
        expectState(api.Snapshot(), { committed = 2, applied = 2 }, "second commit")
    end)

    run("update_prepared_to_applied", function()
        local api = reset(SEED)
        api.UseItem()
        api.Update()
        expectState(api.Snapshot(), { committed = 0, applied = 1, seq = 1, stage = "applied" },
            "first update")
        api.NewRoom()
        commitOne(api)
        api.UseItem()
        api.Update()
        expectState(api.Snapshot(), { committed = 2, applied = 3, seq = 3, stage = "applied" },
            "update after two commits")
    end)

    run("duplicate_update_is_idempotent", function()
        local api = reset(SEED)
        api.UseItem()
        api.Update()
        local once = capture(api)
        expectState(once, { committed = 0, applied = 1, seq = 1, stage = "applied" }, "one update")
        api.Update()
        api.Update()
        sameSnapshot(api.Snapshot(), once, "three updates")
    end)

    run("update_noop_without_pending", function()
        local api = reset(SEED)
        local empty = capture(api)
        api.Update()
        api.Update()
        sameSnapshot(api.Snapshot(), empty, "updates on an empty ledger")
        commitOne(api)
        commitOne(api)
        local committed = capture(api)
        api.Update()
        api.Update()
        sameSnapshot(api.Snapshot(), committed, "updates after two commits")
    end)

    run("update_noop_after_applied", function()
        local api = inFlight(SEED)
        local applied = capture(api)
        for _ = 1, 3 do
            api.Update()
        end
        sameSnapshot(api.Snapshot(), applied, "updates while applied")
        api.NewRoom()
        expectState(api.Snapshot(), { committed = 3, applied = 3 },
            "room commits the single staged unit")
    end)

    run("update_failure_rolls_back_snapshot", function()
        local api = reset(SEED)
        commitOne(api)
        api.UseItem()
        local before = capture(api)
        expectState(before, { committed = 1, applied = 1, seq = 2, stage = "prepared" },
            "before the faulted update")
        api.ArmFault("update_before_publish")
        equal(api.Update(), false, "Update return at update_before_publish")
        -- Includes armedFault: the consumed fault is cleared as before it was armed.
        sameSnapshot(api.Snapshot(), before, "after the faulted update")
    end)

    run("update_failure_does_not_advance_phase", function()
        local api = reset(SEED)
        api.UseItem()
        api.ArmFault("update_before_publish")
        equal(api.Update(), false, "Update return at update_before_publish")
        local current = api.Snapshot()
        expectState(current, { committed = 0, applied = 0, seq = 1, stage = "prepared" },
            "phase after the faulted update")
        truthy(absent(current.armedFault), "consumed fault still armed: " .. tostring(current.armedFault))
        api.NewRoom()
        expectState(api.Snapshot(), { committed = 0, applied = 0, seq = 1, stage = "prepared" },
            "room after the faulted update")
        truthy(not api.ArmFault("update_after_publish"), "unknown fault point accepted")
        truthy(not api.ArmFault("UPDATE_BEFORE_PUBLISH"), "unknown fault point spelling accepted")
        truthy(absent(api.Snapshot().armedFault), "unknown fault point armed")
        api.Update()
        expectState(api.Snapshot(), { committed = 0, applied = 1, seq = 1, stage = "applied" },
            "retried update")
        api.NewRoom()
        expectState(api.Snapshot(), { committed = 1, applied = 1 }, "commit after the retry")
    end)

    run("room_before_update_does_not_commit", function()
        local api = reset(SEED)
        api.UseItem()
        api.NewRoom()
        api.NewRoom()
        expectState(api.Snapshot(), { committed = 0, applied = 0, seq = 1, stage = "prepared" },
            "rooms before the update")
        api.Update()
        expectState(api.Snapshot(), { committed = 0, applied = 1, seq = 1, stage = "applied" },
            "update after early rooms")
        api.NewRoom()
        expectState(api.Snapshot(), { committed = 1, applied = 1 }, "room after the update")
    end)

    run("room_applied_commits_exactly_once", function()
        local api = reset(SEED)
        api.UseItem()
        api.Update()
        local applied = capture(api)
        api.ArmFault("room_before_publish")
        equal(api.NewRoom(), false, "NewRoom return at room_before_publish")
        sameSnapshot(api.Snapshot(), applied, "after the faulted room callback")
        api.NewRoom()
        expectState(api.Snapshot(), { committed = 1, applied = 1 }, "commit")
        api.NewRoom()
        api.Update()
        api.NewRoom()
        expectState(api.Snapshot(), { committed = 1, applied = 1 }, "callbacks after the commit")
    end)

    run("duplicate_room_callback_noop", function()
        local api = reset(SEED)
        local empty = capture(api)
        api.NewRoom()
        api.NewRoom()
        sameSnapshot(api.Snapshot(), empty, "room callbacks on an empty ledger")
        api.UseItem()
        api.Update()
        api.NewRoom()
        local committed = capture(api)
        expectState(committed, { committed = 1, applied = 1 }, "commit")
        api.NewRoom()
        api.NewRoom()
        api.NewRoom()
        sameSnapshot(api.Snapshot(), committed, "repeated room callbacks")
    end)

    run("commit_clears_pending", function()
        local api = inFlight(SEED)
        local applied = api.Snapshot()
        local again = api.Snapshot()
        truthy(type(applied.pending) == "table" and applied.pending ~= again.pending,
            "Snapshot returned the same pending table twice")
        api.NewRoom()
        local current = api.Snapshot()
        truthy(absent(current.pending), "pending survived the commit: " .. describePending(current.pending))
        equal(current.committed_count, 3, "committed_count takes the committed seq")
        equal(current.applied_count, 3, "applied_count after the commit")
        truthy(applied.pending.seq == 3 and applied.pending.stage == "applied",
            "an earlier snapshot changed with the ledger: " .. describePending(applied.pending))
    end)

    run("commit_clears_journal", function()
        local api = reset(SEED)
        api.UseItem()
        local prepared = api.Snapshot()
        expectState(prepared, { committed = 0, applied = 0, seq = 1, stage = "prepared" },
            "journal created with the prepared transaction")
        local again = api.Snapshot()
        truthy(prepared.journal ~= again.journal and prepared.journal[1] ~= again.journal[1],
            "Snapshot returned the same journal twice")
        api.Update()
        expectState(api.Snapshot(), { committed = 0, applied = 1, seq = 1, stage = "applied" },
            "journal advanced to applied")
        api.NewRoom()
        expectState(api.Snapshot(), { committed = 1, applied = 1 }, "journal after the commit")
        truthy(prepared.journal[1].stage == "prepared" and prepared.journal[1].seq == 1,
            "an earlier snapshot's journal changed: " .. describeJournal(prepared.journal))
    end)

    run("callback_order_cannot_skip_update", function()
        local api = reset(SEED)
        api.Update()
        api.UseItem()
        api.NewRoom()
        expectState(api.Snapshot(), { committed = 0, applied = 0, seq = 1, stage = "prepared" },
            "update, use, room")
        api.NewRoom()
        api.NewRoom()
        expectState(api.Snapshot(), { committed = 0, applied = 0, seq = 1, stage = "prepared" },
            "repeated rooms without an update")
        api.Update()
        api.NewRoom()
        expectState(api.Snapshot(), { committed = 1, applied = 1 }, "update, then room")
        api.UseItem()
        api.NewRoom()
        api.Update()
        expectState(api.Snapshot(), { committed = 1, applied = 2, seq = 2, stage = "applied" },
            "use, room, update")
        api.NewRoom()
        expectState(api.Snapshot(), { committed = 2, applied = 2 }, "use, room, update, room")
    end)

    run("committed_transaction_not_reapplied", function()
        local api = reset(SEED)
        commitOne(api)
        local committed = capture(api)
        api.Update()
        api.Update()
        api.NewRoom()
        api.Update()
        sameSnapshot(api.Snapshot(), committed, "callbacks after the commit")
        api.UseItem()
        expectState(api.Snapshot(), { committed = 1, applied = 1, seq = 2, stage = "prepared" },
            "next transaction")
    end)

    run("save_serializes_exact_schema", function()
        local api = reset(SEED)
        commitOne(api)
        return withSaveProbe(function(probe)
            equal(api.SaveNow(), true, "SaveNow return")
            local raw = api.Snapshot().lastSavedRaw
            local decoded = decodeSaved(raw)
            equal(decoded.run_seed, SEED, "run_seed")
            equal(decoded.committed_count, 1, "committed_count")
            probe.expectWrote(raw, "save")
        end)
    end)

    run("save_contains_run_seed", function()
        local seeds = { SEED, OTHER_SEED, WIDE_SEED }
        if isInteger(startSeedAtStart) then
            seeds[#seeds + 1] = startSeedAtStart
        end
        for _, seed in ipairs(seeds) do
            local api = reset(seed)
            equal(api.SaveNow(), true, "SaveNow return for seed " .. tostring(seed))
            local current = api.Snapshot()
            equal(current.runSeed, seed, "snapshot runSeed")
            equal(decodeSaved(current.lastSavedRaw).run_seed, seed, "saved run_seed")
        end
    end)

    run("save_after_commit_persists_count", function()
        local api = reset(SEED)
        commitOne(api)
        commitOne(api)
        commitOne(api)
        local detail = withSaveProbe(function(probe)
            equal(api.SaveNow(), true, "SaveNow return")
            local raw = api.Snapshot().lastSavedRaw
            equal(decodeSaved(raw).committed_count, 3, "saved committed_count")
            probe.expectWrote(raw, "save after three commits")
        end)
        expectState(api.Snapshot(), { committed = 3, applied = 3 }, "after the save")
        return detail
    end)

    run("pending_prepared_discarded_on_save", function()
        local api = reset(SEED)
        commitOne(api)
        api.UseItem()
        equal(api.SaveNow(), true, "SaveNow return")
        local current = api.Snapshot()
        expectState(current, { committed = 1, applied = 1 }, "after saving a prepared transaction")
        equal(decodeSaved(current.lastSavedRaw).committed_count, 1, "saved committed_count")
        api.Update()
        api.NewRoom()
        expectState(api.Snapshot(), { committed = 1, applied = 1 }, "discarded transaction resumed")
        api.UseItem()
        expectState(api.Snapshot(), { committed = 1, applied = 1, seq = 2, stage = "prepared" },
            "next use after the discard")
    end)

    run("pending_applied_discarded_on_save", function()
        local api = inFlight(SEED)
        equal(api.SaveNow(), true, "SaveNow return")
        local current = api.Snapshot()
        expectState(current, { committed = 2, applied = 2 }, "after saving an applied transaction")
        equal(decodeSaved(current.lastSavedRaw).committed_count, 2, "saved committed_count")
        api.NewRoom()
        api.Update()
        expectState(api.Snapshot(), { committed = 2, applied = 2 }, "discarded transaction resumed")
    end)

    run("continued_load_restores_count", function()
        local api = reset(SEED)
        commitOne(api)
        commitOne(api)
        commitOne(api)
        equal(api.SaveNow(), true, "SaveNow return")
        local raw = api.Snapshot().lastSavedRaw
        api.LoadRaw(false, nil, SEED)
        api.UseItem()
        api.Update()
        api.LoadRaw(true, raw, SEED)
        expectState(api.Snapshot(), { runSeed = SEED, committed = 3, applied = 3 },
            "continue from the saved text")
        api.UseItem()
        expectState(api.Snapshot(), { committed = 3, applied = 3, seq = 4, stage = "prepared" },
            "use after the continue")
        local text = string.format("%d", SEED)
        api.LoadRaw(true, '{ "committed_count": 11, "run_seed": ' .. text
            .. ', "schema_version": 1 }', SEED)
        expectState(api.Snapshot(), { runSeed = SEED, committed = 11, applied = 11 },
            "continue from reordered, spaced JSON")
    end)

    run("save_callback_does_not_advance_count", function()
        local api = reset(SEED)
        commitOne(api)
        commitOne(api)
        equal(api.SaveNow(), true, "first save")
        equal(api.SaveNow(), true, "second save")
        local current = api.Snapshot()
        expectState(current, { committed = 2, applied = 2 }, "after two saves")
        equal(decodeSaved(current.lastSavedRaw).committed_count, 2, "count after two saves")
        api.UseItem()
        api.Update()
        equal(api.SaveNow(), true, "save with an applied transaction")
        current = api.Snapshot()
        expectState(current, { committed = 2, applied = 2 }, "save does not commit")
        equal(decodeSaved(current.lastSavedRaw).committed_count, 2,
            "count saved with an applied transaction")
    end)

    run("continued_wrong_seed_defaults", function()
        local api = reset(SEED)
        commitOne(api)
        commitOne(api)
        commitOne(api)
        equal(api.SaveNow(), true, "SaveNow return")
        local raw = api.Snapshot().lastSavedRaw
        api.LoadRaw(true, raw, OTHER_SEED)
        expectState(api.Snapshot(), { runSeed = OTHER_SEED, committed = 0, applied = 0 },
            "own save continued under another seed")
        api.LoadRaw(true, payload(5, SEED), SEED)
        expectState(api.Snapshot(), { runSeed = SEED, committed = 5, applied = 5 },
            "matching continue")
        api.UseItem()
        api.LoadRaw(true, payload(5, SEED + 1), SEED)
        expectState(api.Snapshot(), { runSeed = SEED, committed = 0, applied = 0 },
            "payload written for another seed")
    end)

    run("malformed_save_defaults", function()
        local text = string.format("%d", SEED)
        local samples = {
            "{bad json",
            "[]",
            "[1,2,3]",
            '"text"',
            "42",
            "null",
            "{}",
            '{"schema_version":2,"run_seed":' .. text .. ',"committed_count":3}',
            '{"schema_version":"1","run_seed":' .. text .. ',"committed_count":3}',
            '{"schema_version":1,"run_seed":"' .. text .. '","committed_count":3}',
            '{"schema_version":1,"run_seed":' .. text .. ',"committed_count":"3"}',
            '{"schema_version":1,"run_seed":' .. text .. ',"committed_count":-1}',
            '{"schema_version":1,"run_seed":' .. text .. ',"committed_count":2.5}',
            '{"schema_version":1,"run_seed":' .. text .. "}",
            '{"schema_version":1,"committed_count":3}',
            '{"run_seed":' .. text .. ',"committed_count":3}',
            '{"schema_version":1,"run_seed":' .. text .. ',"committed_count":3,"extra":0}',
            '{"schema_version":1,"run_seed":' .. text
                .. ',"committed_count":3,"pending":{"seq":4,"stage":"applied"}}',
        }
        for index, raw in ipairs(samples) do
            local api = inFlight(SEED)
            api.LoadRaw(true, raw, SEED)
            expectState(api.Snapshot(), { runSeed = SEED, committed = 0, applied = 0 },
                "malformed sample " .. tostring(index) .. " " .. raw)
        end
    end)

    run("missing_save_defaults", function()
        local samples = {
            { hasData = false, raw = nil, label = "no mod data" },
            { hasData = true, raw = nil, label = "HasData without text" },
            { hasData = true, raw = "", label = "empty text" },
        }
        for _, sample in ipairs(samples) do
            local api = inFlight(SEED)
            api.LoadRaw(sample.hasData, sample.raw, SEED)
            expectState(api.Snapshot(), { runSeed = SEED, committed = 0, applied = 0 }, sample.label)
        end
    end)

    run("new_run_resets_count", function()
        -- The game's own non-continued MC_POST_GAME_STARTED ran before the suite.
        truthy(startupState and startupState.ok,
            "Snapshot after the real game start failed: "
                .. tostring(startupState and startupState.value))
        truthy(isInteger(startSeedAtStart), "real start seed unavailable")
        expectState(startupState.value,
            { runSeed = startSeedAtStart, committed = 0, applied = 0 },
            "state after the real game start")
        local api = reset(SEED)
        commitOne(api)
        commitOne(api)
        api.LoadRaw(false, nil, SEED)
        expectState(api.Snapshot(), { runSeed = SEED, committed = 0, applied = 0 },
            "new run with the same seed")
        commitOne(api)
        api.LoadRaw(false, nil, OTHER_SEED)
        expectState(api.Snapshot(), { runSeed = OTHER_SEED, committed = 0, applied = 0 },
            "new run with another seed")
        api.UseItem()
        expectState(api.Snapshot(), { committed = 0, applied = 0, seq = 1, stage = "prepared" },
            "first use of the new run")
    end)

    run("new_run_clears_pending_journal", function()
        local api = inFlight(SEED)
        api.LoadRaw(false, nil, SEED)
        expectState(api.Snapshot(), { runSeed = SEED, committed = 0, applied = 0 },
            "new run after an applied transaction")
        api.UseItem()
        api.LoadRaw(false, nil, SEED)
        expectState(api.Snapshot(), { runSeed = SEED, committed = 0, applied = 0 },
            "new run after a prepared transaction")
        api.NewRoom()
        api.Update()
        expectState(api.Snapshot(), { committed = 0, applied = 0 }, "old transaction resumed")
        api.UseItem()
        expectState(api.Snapshot(), { committed = 0, applied = 0, seq = 1, stage = "prepared" },
            "fresh transaction")
    end)

    run("save_failure_restores_memory_snapshot", function()
        local api = reset(SEED)
        commitOne(api)
        equal(api.SaveNow(), true, "baseline save")
        local savedRaw = api.Snapshot().lastSavedRaw
        truthy(type(savedRaw) == "string", "baseline save text missing")
        api.UseItem()
        api.Update()
        local before = capture(api)
        expectState(before, { committed = 1, applied = 2, seq = 2, stage = "applied" },
            "before the failed saves")
        local detail = withSaveProbe(function(probe)
            for _, point in ipairs({ "encode_before_save", "save_data_before_write" }) do
                probe.clear()
                api.ArmFault(point)
                equal(api.SaveNow(), false, point .. ": SaveNow return")
                local current = api.Snapshot()
                sameSnapshot(current, before, point)
                equal(current.lastSavedRaw, savedRaw, point .. ": lastSavedRaw")
                probe.expectNoWrite(point)
            end
            if probe.available then
                probe.clear()
                probe.fail = true
                local called, result = pcall(api.SaveNow)
                probe.fail = false
                truthy(called, "SaveNow threw when SaveData failed: " .. tostring(result))
                truthy(result ~= true, "SaveNow claimed success when SaveData failed")
                sameSnapshot(api.Snapshot(), before, "failed SaveData write")
            end
        end)
        api = reset(SEED)
        commitOne(api)
        api.UseItem()
        local prepared = capture(api)
        api.ArmFault("encode_before_save")
        equal(api.SaveNow(), false, "SaveNow return with a prepared transaction")
        sameSnapshot(api.Snapshot(), prepared, "failed save of a prepared transaction")
        return detail
    end)

    run("later_valid_save_recovers", function()
        local api = inFlight(SEED)
        return withSaveProbe(function(probe)
            api.ArmFault("save_data_before_write")
            equal(api.SaveNow(), false, "save_data_before_write: SaveNow return")
            api.ArmFault("encode_before_save")
            equal(api.SaveNow(), false, "encode_before_save: SaveNow return")
            expectState(api.Snapshot(), { committed = 2, applied = 3, seq = 3, stage = "applied" },
                "after the failed saves")
            probe.clear()
            equal(api.SaveNow(), true, "later save")
            local current = api.Snapshot()
            expectState(current, { runSeed = SEED, committed = 2, applied = 2 }, "after the later save")
            truthy(absent(current.armedFault), "fault still armed: " .. tostring(current.armedFault))
            local decoded = decodeSaved(current.lastSavedRaw)
            equal(decoded.run_seed, SEED, "saved run_seed")
            equal(decoded.committed_count, 2, "saved committed_count")
            probe.expectWrote(current.lastSavedRaw, "later save")
            api.LoadRaw(true, current.lastSavedRaw, SEED)
            expectState(api.Snapshot(), { runSeed = SEED, committed = 2, applied = 2 },
                "continue from the later save")
        end)
    end)

    -- Leave one prepared transaction for the real MC_POST_UPDATE callbacks to stage over
    -- the next frames. A submission that cannot even start it fails that case here so every
    -- case is still reported exactly once.
    local armed, err = pcall(function()
        local api = reset(SEED)
        api.UseItem()
        expectState(api.Snapshot(), { committed = 0, applied = 0, seq = 1, stage = "prepared" },
            "update audit start")
        updateAudit = { api = api, frames = {} }
    end)
    if not armed then
        record("applied_count_increments_once", false, err)
    end
end

-- Frames 2 and 3: whichever mod's update handler runs first, the transaction prepared on
-- frame 1 has been staged by the submission's real MC_POST_UPDATE callback by the time the
-- suite runs on frame 2, and a further real update must not stage a second unit.
local function auditFrame()
    local audit = updateAudit
    if audit == nil then
        finish()
        return
    end
    local ok, value = pcall(function()
        return capture(audit.api)
    end)
    if not ok then
        updateAudit = nil
        record("applied_count_increments_once", false, "update audit Snapshot failed: " .. tostring(value))
        finish()
        return
    end
    audit.frames[#audit.frames + 1] = value
    if #audit.frames < 2 then
        return
    end
    updateAudit = nil
    run("applied_count_increments_once", function()
        expectState(audit.frames[1],
            { runSeed = SEED, committed = 0, applied = 1, seq = 1, stage = "applied" },
            "one real update frame later")
        expectState(audit.frames[2],
            { runSeed = SEED, committed = 0, applied = 1, seq = 1, stage = "applied" },
            "two real update frames later")
        local api = reset(SEED)
        commitOne(api)
        api.UseItem()
        expectState(api.Snapshot(), { committed = 1, applied = 1, seq = 2, stage = "prepared" },
            "prepared transaction stages nothing")
        for count = 1, 4 do
            api.Update()
            expectState(api.Snapshot(), { committed = 1, applied = 2, seq = 2, stage = "applied" },
                "after direct update " .. tostring(count))
        end
    end)
    finish()
end

suite:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, function()
    if executed then
        return
    end
    if not started then
        log("[GCB_RUNTIME] suite_started")
    end
    started = true
    updateFrames = 0
    local ok, seed = pcall(function()
        return game:GetSeeds():GetStartSeed()
    end)
    startSeedAtStart = ok and seed or nil
end)

suite:AddCallback(ModCallbacks.MC_POST_UPDATE, function()
    if finished or not started then
        return
    end
    updateFrames = updateFrames + 1
    if updateFrames == 1 then
        executed = true
        -- Every mod's game-start handler has run by now, whichever order they loaded in;
        -- the submission's own update handler may already have run once this frame, which
        -- cannot change a ledger with no pending transaction.
        local startupOk, startupValue = pcall(function()
            return capture(transactionApi())
        end)
        startupState = { ok = startupOk, value = startupValue }
        local ok, err = pcall(executeSuite)
        if not ok then
            log("[GCB_FATAL] " .. tostring(err))
            finish()
        end
        return
    end
    auditFrame()
end)
