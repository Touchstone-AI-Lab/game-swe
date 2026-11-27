local suite = RegisterMod("Construct Room RNG Verifier", 1)
local game = Game()
local json = require("json")
local MODULUS = 2147483647
local passed = 0
local failed = 0
local recorded = {}
local finished = false
local updateAudit = nil
-- Update frames observed since the run started; the suite body runs on the first one so
-- that every mod's MC_POST_GAME_STARTED handler has completed whatever the load order.
local updateFrames = 0
local startSeedAtStart = nil
local spawnSeedAtStart = nil

local function log(text)
    Isaac.DebugString(text)
end

local function equal(actual, expected, label)
    if actual ~= expected then
        error((label or "value") .. ": expected " .. tostring(expected)
            .. ", received " .. tostring(actual))
    end
end

local function truthy(value, label)
    if not value then
        error(label or "expected truthy value")
    end
end

local function record(name, ok, detail)
    if recorded[name] then
        return
    end
    recorded[name] = true
    if ok then
        passed = passed + 1
        log("[GCB_CASE] PASS " .. name .. " " .. tostring(detail or "ok"))
    else
        failed = failed + 1
        log("[GCB_CASE] FAIL " .. name .. " " .. tostring(detail or "failed"))
    end
end

local function run(name, fn)
    local ok, result = pcall(fn)
    record(name, ok, result)
end

local function reset(seed, roomSeed)
    local api = IsaacConstructRoomRng
    truthy(api.StartRun(false, nil, seed), "StartRun failed")
    truthy(api.SelectRoom(seed, roomSeed), "SelectRoom failed")
    return api
end

local function draw(api, count)
    local output = {}
    for index = 1, count do
        output[index] = api.DrawCurrentRoom()
    end
    return output
end

local function room(snapshot, key)
    for _, entry in ipairs(snapshot.rooms) do
        if entry.key == key then
            return entry
        end
    end
    return nil
end

local function sequenceEquals(actual, expected)
    equal(#actual, #expected, "sequence length")
    for index, value in ipairs(expected) do
        equal(actual[index], value, "sequence[" .. tostring(index) .. "]")
    end
end

local function seedA()
    return { 87, 28, 70, 13, 10, 43, 87, 94 }
end

local function seedB()
    return { 80, 44, 35, 20, 37, 69, 21, 59 }
end

local function seedC()
    return { 75, 69, 76, 66, 59, 78, 51, 95 }
end

local function executeSuite()
    local expectedA = seedA()

    run("same_run_room_same_sequence", function()
        local api = reset(42, 1337)
        sequenceEquals(draw(api, 8), expectedA)
    end)

    run("different_room_distinct_stream", function()
        local api = reset(42, 1337)
        local first = draw(api, 8)
        api.SelectRoom(42, 1338)
        local second = draw(api, 8)
        sequenceEquals(first, expectedA)
        sequenceEquals(second, seedB())
    end)

    run("different_run_distinct_stream", function()
        local api = reset(42, 1337)
        local first = draw(api, 8)
        reset(43, 1337)
        local second = draw(api, 8)
        sequenceEquals(first, expectedA)
        sequenceEquals(second, seedC())
    end)

    run("same_room_reload_same_stream", function()
        local api = reset(42, 1337)
        sequenceEquals(draw(api, 3), { 87, 28, 70 })
        truthy(api.SaveNow(), "save failed")
        local raw = api.Snapshot().lastSavedRaw
        truthy(api.StartRun(true, raw, 42), "continue failed")
        truthy(api.SelectRoom(42, 1337), "room restore failed")
        sequenceEquals(draw(api, 5), { 13, 10, 43, 87, 94 })
    end)

    run("save_resume_next_value", function()
        local api = reset(42, 1337)
        draw(api, 4)
        truthy(api.SaveNow(), "save failed")
        local raw = api.Snapshot().lastSavedRaw
        api.StartRun(true, raw, 42)
        api.SelectRoom(42, 1337)
        equal(api.DrawCurrentRoom(), 10, "resumed value")
    end)

    run("save_resume_consumed_count", function()
        local api = reset(42, 1337)
        draw(api, 3)
        api.SaveNow()
        api.StartRun(true, api.Snapshot().lastSavedRaw, 42)
        api.SelectRoom(42, 1337)
        equal(room(api.Snapshot(), "42:1337").drawCount, 3, "draw count")
    end)

    run("new_run_resets_derived_state", function()
        local api = reset(42, 1337)
        draw(api, 2)
        truthy(api.StartRun(false, nil, 42), "new start failed")
        local current = api.Snapshot()
        equal(#current.rooms, 0, "room reset")
        equal(#current.outputSequence, 0, "trace reset")
        equal(current.activeRoomKey, nil, "active room reset")
    end)

    run("room_entry_reseeds_only_room_stream", function()
        local api = reset(42, 1337)
        draw(api, 2)
        api.SelectRoom(42, 1338)
        draw(api, 1)
        local current = api.Snapshot()
        equal(#current.rooms, 2, "room count")
        equal(room(current, "42:1337").drawCount, 2, "first room draws")
        equal(room(current, "42:1338").drawCount, 1, "second room draws")
    end)

    run("update_draw_order_stable", function()
        local api = reset(42, 1337)
        local first = api.DrawCurrentRoom()
        api.SelectRoom(42, 1338)
        local second = api.DrawCurrentRoom()
        api.SelectRoom(42, 1337)
        local third = api.DrawCurrentRoom()
        sequenceEquals(api.Snapshot().outputSequence, { first, second, third })
        sequenceEquals({ first, second }, { 87, 80 })
        equal(third, 28, "revisited room next value")
    end)

    run("room_seed_not_global_rng", function()
        local seeds = Game():GetSeeds()
        local startSeed = seeds:GetStartSeed()
        local api = reset(42, 1337)
        draw(api, 3)
        equal(seeds:GetStartSeed(), startSeed, "game start seed")
        sequenceEquals(draw(reset(42, 1337), 2), { 87, 28 })
    end)

    run("no_global_rng_reseed", function()
        local old = math.randomseed
        local calls = 0
        math.randomseed = function()
            calls = calls + 1
            error("global RNG reseeded")
        end
        local ok, err = pcall(function()
            draw(reset(42, 1337), 2)
        end)
        math.randomseed = old
        truthy(ok, err)
        equal(calls, 0, "math.randomseed calls")
    end)

    run("no_global_rng_consumption", function()
        local old = math.random
        local calls = 0
        math.random = function()
            calls = calls + 1
            error("global RNG consumed")
        end
        local ok, err = pcall(function()
            draw(reset(42, 1337), 2)
        end)
        math.random = old
        truthy(ok, err)
        equal(calls, 0, "math.random calls")
    end)

    run("game_rng_unchanged_by_first_draw", function()
        local expected = RNG()
        expected:SetSeed(12345, 0)
        local expectedValue = expected:Next()
        local probe = RNG()
        probe:SetSeed(12345, 0)
        reset(42, 1337).DrawCurrentRoom()
        equal(probe:Next(), expectedValue, "independent game RNG object")
    end)

    run("duplicate_room_callback_idempotent", function()
        local api = reset(42, 1337)
        api.SelectRoom(42, 1337)
        api.SelectRoom(42, 1337)
        equal(room(api.Snapshot(), "42:1337").drawCount, 0, "duplicate entry draws")
        equal(api.DrawCurrentRoom(), 87, "first value after duplicate entry")
    end)

    run("room_reentry_resumes_saved_stream", function()
        local api = reset(42, 1337)
        draw(api, 3)
        api.SelectRoom(42, 1338)
        draw(api, 2)
        api.SelectRoom(42, 1337)
        equal(api.DrawCurrentRoom(), 13, "room A resumed value")
    end)

    run("visited_room_state_isolated", function()
        local api = reset(42, 1337)
        draw(api, 2)
        api.SelectRoom(42, 1338)
        draw(api, 1)
        local current = api.Snapshot()
        equal(room(current, "42:1337").drawCount, 2, "room A state")
        equal(room(current, "42:1338").drawCount, 1, "room B state")
    end)

    run("unvisited_room_state_deterministic", function()
        local api = reset(42, 1337)
        api.SelectRoom(42, 9001)
        local first = api.DrawCurrentRoom()
        api.StartRun(false, nil, 42)
        api.SelectRoom(42, 9001)
        equal(api.DrawCurrentRoom(), first, "unvisited room seed")
    end)

    run("state_round_trip", function()
        local api = reset(42, 1337)
        draw(api, 4)
        api.SelectRoom(42, 1338)
        draw(api, 2)
        api.SaveNow()
        local decoded = json.decode(api.Snapshot().lastSavedRaw)
        equal(decoded.schema_version, 1, "schema version")
        equal(decoded.run_seed, 42, "run seed")
        equal(#decoded.rooms, 2, "serialized rooms")
    end)

    run("malformed_persisted_state_recovers", function()
        local api = IsaacConstructRoomRng
        truthy(api.StartRun(true, "{bad json", 42), "continue fallback")
        equal(#api.Snapshot().rooms, 0, "malformed rooms")
        api.SelectRoom(42, 1337)
        equal(api.DrawCurrentRoom(), 87, "recovered first value")
    end)

    run("missing_persisted_state_initializes", function()
        local api = IsaacConstructRoomRng
        truthy(api.StartRun(true, nil, 42), "missing-data continue")
        api.SelectRoom(42, 1337)
        equal(api.DrawCurrentRoom(), 87, "missing-data first value")
    end)

    run("run_seed_is_part_of_key", function()
        local api = reset(42, 1337)
        local first = api.Snapshot().activeRoomKey
        api.StartRun(false, nil, 43)
        api.SelectRoom(43, 1337)
        local second = api.Snapshot().activeRoomKey
        equal(first, "42:1337", "first key")
        equal(second, "43:1337", "second key")
        truthy(first ~= second, "run seed key collision")
    end)

    run("room_spawn_seed_is_part_of_key", function()
        local api = reset(42, 1337)
        local first = api.Snapshot().activeRoomKey
        api.SelectRoom(42, 1338)
        local second = api.Snapshot().activeRoomKey
        equal(first, "42:1337", "first key")
        equal(second, "42:1338", "second key")
    end)

    run("value_range_is_inclusive", function()
        local api = reset(42, 1337)
        for _, value in ipairs(draw(api, 500)) do
            truthy(value >= 0 and value <= 100, "value outside [0,100]")
        end
    end)

    run("integer_generation_is_stable", function()
        local api = reset(42, 1337)
        for _, value in ipairs(draw(api, 50)) do
            equal(value % 1, 0, "non-integer value")
        end
    end)

    run("no_callback_order_drift", function()
        local api = reset(42, 1337)
        local before = api.Snapshot().rooms[1].state
        api.SelectRoom(42, 1338)
        api.SelectRoom(42, 1337)
        equal(api.Snapshot().rooms[1].state, before, "room selection consumed state")
        equal(api.DrawCurrentRoom(), 87, "draw after room selection")
    end)

    run("save_callback_does_not_advance", function()
        local api = reset(42, 1337)
        draw(api, 2)
        local before = api.Snapshot()
        truthy(api.SaveNow(), "save failed")
        local after = api.Snapshot()
        equal(room(after, "42:1337").state, room(before, "42:1337").state, "saved state")
        equal(room(after, "42:1337").drawCount, 2, "saved count")
    end)

    run("room_change_does_not_reset_run", function()
        local api = reset(42, 1337)
        draw(api, 2)
        api.SelectRoom(42, 1338)
        equal(api.Snapshot().runSeed, 42, "run seed after room change")
        equal(room(api.Snapshot(), "42:1337").drawCount, 2, "old room count")
    end)

    run("save_after_n_draws_resumes_n_plus_one", function()
        local api = reset(42, 1337)
        draw(api, 7)
        api.SaveNow()
        local raw = api.Snapshot().lastSavedRaw
        api.StartRun(true, raw, 42)
        api.SelectRoom(42, 1337)
        equal(api.DrawCurrentRoom(), 94, "eighth value")
    end)

    run("invalid_room_entry_isolated", function()
        local api = reset(42, 1337)
        draw(api, 2)
        api.SaveNow()
        local payload = json.decode(api.Snapshot().lastSavedRaw)
        payload.rooms[#payload.rooms + 1] = {
            key = "42:9000",
            state = 0,
            drawCount = 3,
        }
        api.StartRun(true, json.encode(payload), 42)
        equal(#api.Snapshot().rooms, 1, "bad peer discarded")
        api.SelectRoom(42, 1337)
        equal(api.DrawCurrentRoom(), 70, "valid peer retained")
        api.SelectRoom(42, 9000)
        equal(api.DrawCurrentRoom(), 44, "invalid peer reinitialized")
    end)

    run("stream_state_does_not_alias", function()
        local api = reset(42, 1337)
        draw(api, 2)
        api.SelectRoom(42, 1338)
        draw(api, 1)
        local current = api.Snapshot()
        local first = room(current, "42:1337")
        local second = room(current, "42:1338")
        truthy(first ~= second, "room entries alias")
        equal(first.drawCount, 2, "room A count")
        equal(second.drawCount, 1, "room B count")
    end)

    run("no_math_random_dependency", function()
        local api = reset(42, 1337)
        local old = math.random
        math.random = function()
            error("math.random dependency")
        end
        local ok, result = pcall(function()
            return api.DrawCurrentRoom()
        end)
        math.random = old
        truthy(ok, result)
        equal(result, 87, "deterministic result")
    end)

    run("room_stream_cached_not_reinitialized", function()
        local api = reset(42, 1337)
        draw(api, 3)
        api.SelectRoom(42, 1338)
        draw(api, 1)
        api.SelectRoom(42, 1337)
        equal(api.DrawCurrentRoom(), 13, "cached stream")
        equal(room(api.Snapshot(), "42:1337").drawCount, 4, "cached count")
    end)

    run("zero_seed_normalizes_to_one", function()
        local api = reset(0, 0)
        equal(api.DrawCurrentRoom(), 94, "normalized zero stream")
        equal(room(api.Snapshot(), "0:0").state, 48271, "first normalized state")
    end)

    -- Leave room 42:1337 freshly selected; the update audit below watches the real
    -- MC_POST_UPDATE callbacks draw from it. A submission that cannot even select the
    -- room fails that case here so every case is still reported exactly once.
    local armed, api = pcall(reset, 42, 1337)
    if armed then
        updateAudit = { api = api, baseline = nil }
    else
        record("repeated_update_advances_once", false, api)
    end
end

local function finish()
    if finished then
        return
    end
    finished = true
    log("[GCB_SUMMARY] passed=" .. tostring(passed)
        .. " failed=" .. tostring(failed)
        .. " total=" .. tostring(passed + failed))
end

-- The first value the specified stream yields for one (startSeed, roomSpawnSeed) key.
local function expectedFirstValue(startSeed, roomSpawnSeed)
    local state = ((startSeed % (MODULUS - 1)) * 65599
        + (roomSpawnSeed % (MODULUS - 1))) % (MODULUS - 1)
    if state == 0 then
        state = 1
    end
    return ((state * 48271) % MODULUS) % 101
end

suite:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, function()
    log("[GCB_RUNTIME] suite_started")
    updateFrames = 0
    finished = false
    startSeedAtStart = game:GetSeeds():GetStartSeed()
    local currentRoom = game:GetRoom()
    spawnSeedAtStart = currentRoom and currentRoom:GetSpawnSeed() or nil
end)

suite:AddCallback(ModCallbacks.MC_POST_UPDATE, function()
    if finished or startSeedAtStart == nil then
        return
    end
    updateFrames = updateFrames + 1
    if updateFrames == 1 then
        -- Every mod's game-start handler has run by now, whichever order they loaded in.
        -- The submission's own update handler may already have fired once this frame.
        run("game_start_callback_resets_once", function()
            local api = IsaacConstructRoomRng
            truthy(api, "IsaacConstructRoomRng is not exported")
            truthy(spawnSeedAtStart, "initial room missing")
            local current = api.Snapshot()
            equal(current.runSeed, startSeedAtStart, "callback run seed")
            equal(current.activeRoomKey,
                tostring(startSeedAtStart) .. ":" .. tostring(spawnSeedAtStart),
                "callback room selected")
            truthy(#current.outputSequence <= 1, "startup consumed more than one update value")
            if #current.outputSequence == 1 then
                equal(current.outputSequence[1],
                    expectedFirstValue(startSeedAtStart, spawnSeedAtStart),
                    "first real update value")
            end
        end)
        local ok, err = pcall(executeSuite)
        if not ok then
            log("[GCB_FATAL] " .. tostring(err))
            finish()
        end
        return
    end
    local audit = updateAudit
    if not audit then
        finish()
        return
    end
    if audit.baseline == nil then
        -- One full frame boundary later the trace holds one or two values depending on
        -- which mod's update handler runs first; from here on it must grow by exactly one
        -- value per frame.
        local ok, count = pcall(function()
            return #audit.api.Snapshot().outputSequence
        end)
        if ok and type(count) == "number" then
            audit.baseline = count
            return
        end
        updateAudit = nil
        record("repeated_update_advances_once", false, count)
        finish()
        return
    end
    updateAudit = nil
    run("repeated_update_advances_once", function()
        local current = audit.api.Snapshot()
        equal(#current.outputSequence, audit.baseline + 1, "one value per real update callback")
        truthy(audit.baseline >= 1 and audit.baseline <= 2, "unexpected trace length")
        sequenceEquals(current.outputSequence,
            { table.unpack(seedA(), 1, #current.outputSequence) })
    end)
    finish()
end)
