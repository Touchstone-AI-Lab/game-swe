local mod = RegisterMod("Construct Callback Transaction Reference", 1)
local game = Game()
local json = require("json")

local SCHEMA_VERSION = 1
local STAGE_PREPARED = "prepared"
local STAGE_APPLIED = "applied"
local FAULT_POINTS = {
    update_before_publish = true,
    room_before_publish = true,
    encode_before_save = true,
    save_data_before_write = true,
}
local SAVED_FIELDS = {
    schema_version = true,
    run_seed = true,
    committed_count = true,
}

-- The published ledger. applied_count and the journal are derived from `pending` (nil or
-- {seq, stage}) when a snapshot is taken, so they can never disagree with it.
local ledger = {
    runSeed = nil,
    committed_count = 0,
    pending = nil,
    lastSavedRaw = nil,
}
-- One-shot test control. It is not ledger state, so a rollback never restores it.
local armedFault = nil
local transitionRunning = false

local function isInteger(value)
    return type(value) == "number"
        and value == value
        and value ~= math.huge
        and value ~= -math.huge
        and value % 1 == 0
end

local function copyPending(pending)
    if pending == nil then
        return nil
    end
    return { seq = pending.seq, stage = pending.stage }
end

local function copyLedger(source)
    return {
        runSeed = source.runSeed,
        committed_count = source.committed_count,
        pending = copyPending(source.pending),
        lastSavedRaw = source.lastSavedRaw,
    }
end

-- Raises at a named injection point when that point is armed. The fault is consumed
-- first, so it stays cleared although the transition that hit it rolls back.
local function reachFaultPoint(pointName)
    if armedFault == pointName then
        armedFault = nil
        error("injected fault at " .. pointName, 0)
    end
end

-- Runs one transition atomically. `build` receives a private copy of the ledger and
-- returns the complete next ledger, or nil when the rules make the call a no-op. The
-- result is published only after every step has succeeded; any error keeps the prior
-- ledger, is never thrown into the game, and makes the call return false. A transition
-- started from inside another one is refused, so re-entry cannot stage a second unit.
local function transition(build)
    if transitionRunning then
        return false
    end
    transitionRunning = true
    local prior = ledger
    local ok, nextLedger = pcall(build, copyLedger(prior))
    transitionRunning = false
    if not ok then
        ledger = prior
        return false
    end
    if nextLedger ~= nil then
        ledger = nextLedger
    end
    return true
end

-- The committed count a continued run may restore, or 0 for anything but an exact
-- schema-1 table written for this run seed.
local function restoredCount(rawData, runSeed)
    if type(rawData) ~= "string" then
        return 0
    end
    local ok, decoded = pcall(json.decode, rawData)
    if not ok or type(decoded) ~= "table" then
        return 0
    end
    local fields = 0
    for key in pairs(decoded) do
        if not SAVED_FIELDS[key] then
            return 0
        end
        fields = fields + 1
    end
    if fields ~= 3
        or not isInteger(decoded.schema_version)
        or decoded.schema_version ~= SCHEMA_VERSION
        or not isInteger(decoded.run_seed)
        or decoded.run_seed ~= runSeed
        or not isInteger(decoded.committed_count)
        or decoded.committed_count < 0 then
        return 0
    end
    return math.floor(decoded.committed_count)
end

local function useItem()
    return transition(function(nextLedger)
        if nextLedger.pending ~= nil then
            -- Ignored until the pending transaction commits or rolls back.
            return nil
        end
        nextLedger.pending = {
            seq = nextLedger.committed_count + 1,
            stage = STAGE_PREPARED,
        }
        return nextLedger
    end)
end

local function update()
    return transition(function(nextLedger)
        local pending = nextLedger.pending
        if pending == nil or pending.stage ~= STAGE_PREPARED then
            return nil
        end
        -- Staging is the stage change itself: applied_count derives one unit from it.
        pending.stage = STAGE_APPLIED
        reachFaultPoint("update_before_publish")
        return nextLedger
    end)
end

local function newRoom()
    return transition(function(nextLedger)
        local pending = nextLedger.pending
        if pending == nil or pending.stage ~= STAGE_APPLIED then
            return nil
        end
        nextLedger.committed_count = pending.seq
        nextLedger.pending = nil
        reachFaultPoint("room_before_publish")
        return nextLedger
    end)
end

local function loadRaw(hasData, rawData, runSeed)
    if not isInteger(runSeed) then
        return false
    end
    return transition(function()
        local seed = math.floor(runSeed)
        return {
            runSeed = seed,
            committed_count = hasData and restoredCount(rawData, seed) or 0,
            pending = nil,
            lastSavedRaw = nil,
        }
    end)
end

local function saveNow()
    return transition(function(nextLedger)
        if not isInteger(nextLedger.runSeed) then
            error("no run to save", 0)
        end
        -- Only committed progress is persisted: the pending transaction is discarded and
        -- its staged unit, if any, rolls back with it.
        nextLedger.pending = nil
        local payload = {
            schema_version = SCHEMA_VERSION,
            run_seed = nextLedger.runSeed,
            committed_count = nextLedger.committed_count,
        }
        reachFaultPoint("encode_before_save")
        local rawData = json.encode(payload)
        if type(rawData) ~= "string" then
            error("save payload did not encode to text", 0)
        end
        reachFaultPoint("save_data_before_write")
        mod:SaveData(rawData)
        nextLedger.lastSavedRaw = rawData
        return nextLedger
    end)
end

local function armFault(pointName)
    if type(pointName) ~= "string" or not FAULT_POINTS[pointName] then
        return false
    end
    armedFault = pointName
    return true
end

local function snapshot()
    local pending = ledger.pending
    local appliedCount = ledger.committed_count
    local journal = {}
    if pending ~= nil then
        journal[1] = copyPending(pending)
        if pending.stage == STAGE_APPLIED then
            appliedCount = appliedCount + 1
        end
    end
    return {
        runSeed = ledger.runSeed,
        committed_count = ledger.committed_count,
        applied_count = appliedCount,
        pending = copyPending(pending),
        journal = journal,
        lastSavedRaw = ledger.lastSavedRaw,
        armedFault = armedFault,
    }
end

local api = {
    UseItem = useItem,
    Update = update,
    NewRoom = newRoom,
    LoadRaw = loadRaw,
    SaveNow = saveNow,
    ArmFault = armFault,
    Snapshot = snapshot,
}
IsaacConstructTransaction = api

-- Engine callbacks call the exported transition methods; none of them returns a value to
-- the game or lets an error escape.
mod:AddCallback(ModCallbacks.MC_USE_ITEM, function()
    api.UseItem()
end)

mod:AddCallback(ModCallbacks.MC_POST_UPDATE, function()
    api.Update()
end)

mod:AddCallback(ModCallbacks.MC_POST_NEW_ROOM, function()
    api.NewRoom()
end)

mod:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, function(_, isContinued)
    local seedRead, runSeed = pcall(function()
        return game:GetSeeds():GetStartSeed()
    end)
    if not seedRead then
        return
    end
    local hasData, rawData = false, nil
    if isContinued then
        local dataRead = pcall(function()
            hasData = mod:HasData()
            if hasData then
                rawData = mod:LoadData()
            end
        end)
        if not dataRead then
            hasData, rawData = false, nil
        end
    end
    -- A non-continued start is LoadRaw(false, nil, seed): count, pending and journal reset.
    api.LoadRaw(hasData, rawData, runSeed)
end)

local function saveCallback()
    api.SaveNow()
end
mod:AddCallback(ModCallbacks.MC_PRE_GAME_EXIT, saveCallback)
mod:AddCallback(ModCallbacks.MC_POST_GAME_END, saveCallback)

mod:AddCallback(ModCallbacks.MC_EXECUTE_CMD, function(_, command)
    if command == "constructtxn" then
        api.SaveNow()
    end
end)
