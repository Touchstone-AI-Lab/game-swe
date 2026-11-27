local mod = RegisterMod("Construct Room RNG Reference", 1)
local game = Game()
local json = require("json")

local MODULUS = 2147483647
local state = {
    runSeed = nil,
    rooms = {},
    activeRoomKey = nil,
    outputSequence = {},
    lastSavedRaw = nil,
    initialized = false,
}
local pendingRoomSpawnSeed = nil

local function isInteger(value)
    return type(value) == "number"
        and value == value
        and value ~= math.huge
        and value ~= -math.huge
        and value % 1 == 0
end

local function copyArray(values)
    local result = {}
    for index, value in ipairs(values) do
        result[index] = value
    end
    return result
end

local function roomKey(startSeed, roomSpawnSeed)
    return tostring(startSeed) .. ":" .. tostring(roomSpawnSeed)
end

local function initialState(startSeed, roomSpawnSeed)
    local value = ((startSeed % (MODULUS - 1)) * 65599
        + (roomSpawnSeed % (MODULUS - 1))) % (MODULUS - 1)
    if value == 0 then
        value = 1
    end
    return value
end

local function validRoomEntry(entry, runSeed)
    if type(entry) ~= "table"
        or type(entry.key) ~= "string"
        or not isInteger(entry.state)
        or entry.state < 1
        or entry.state >= MODULUS
        or not isInteger(entry.drawCount)
        or entry.drawCount < 0 then
        return false
    end

    local savedRunSeed, roomSpawnSeed = entry.key:match("^(-?%d+):(-?%d+)$")
    if not savedRunSeed or not roomSpawnSeed then
        return false
    end
    savedRunSeed = tonumber(savedRunSeed)
    roomSpawnSeed = tonumber(roomSpawnSeed)
    return savedRunSeed == runSeed
        and isInteger(roomSpawnSeed)
        and roomKey(savedRunSeed, roomSpawnSeed) == entry.key
end

local function loadRooms(rawData, runSeed)
    if type(rawData) ~= "string" or rawData == "" then
        return {}
    end
    local ok, decoded = pcall(json.decode, rawData)
    if not ok
        or type(decoded) ~= "table"
        or decoded.schema_version ~= 1
        or decoded.run_seed ~= runSeed
        or type(decoded.rooms) ~= "table" then
        return {}
    end

    local rooms = {}
    for _, entry in ipairs(decoded.rooms) do
        if validRoomEntry(entry, runSeed) and rooms[entry.key] == nil then
            rooms[entry.key] = {
                state = entry.state,
                drawCount = entry.drawCount,
            }
        end
    end
    return rooms
end

local function selectRoom(startSeed, roomSpawnSeed)
    if not state.initialized
        or not isInteger(startSeed)
        or not isInteger(roomSpawnSeed)
        or startSeed ~= state.runSeed then
        return false
    end

    local key = roomKey(startSeed, roomSpawnSeed)
    if state.rooms[key] == nil then
        state.rooms[key] = {
            state = initialState(startSeed, roomSpawnSeed),
            drawCount = 0,
        }
    end
    state.activeRoomKey = key
    return true
end

local function startRun(continued, rawData, runSeed)
    if not isInteger(runSeed) then
        return false
    end
    state.runSeed = runSeed
    state.rooms = continued and loadRooms(rawData, runSeed) or {}
    state.activeRoomKey = nil
    state.outputSequence = {}
    state.lastSavedRaw = nil
    state.initialized = true

    if pendingRoomSpawnSeed ~= nil then
        selectRoom(runSeed, pendingRoomSpawnSeed)
        pendingRoomSpawnSeed = nil
    end
    return true
end

local function drawCurrentRoom()
    local room = state.activeRoomKey and state.rooms[state.activeRoomKey] or nil
    if not room then
        return nil
    end
    room.state = (room.state * 48271) % MODULUS
    room.drawCount = room.drawCount + 1
    local value = room.state % 101
    state.outputSequence[#state.outputSequence + 1] = value
    return value
end

local function saveNow()
    if not isInteger(state.runSeed) then
        return false
    end
    local keys = {}
    for key in pairs(state.rooms) do
        keys[#keys + 1] = key
    end
    table.sort(keys)

    local rooms = {}
    for _, key in ipairs(keys) do
        local room = state.rooms[key]
        rooms[#rooms + 1] = {
            key = key,
            state = room.state,
            drawCount = room.drawCount,
        }
    end
    local payload = {
        schema_version = 1,
        run_seed = state.runSeed,
        rooms = rooms,
    }
    local ok, rawData = pcall(json.encode, payload)
    if not ok or type(rawData) ~= "string" then
        return false
    end
    local saved = pcall(function()
        mod:SaveData(rawData)
    end)
    if not saved then
        return false
    end
    state.lastSavedRaw = rawData
    return true
end

local function snapshot()
    local keys = {}
    for key in pairs(state.rooms) do
        keys[#keys + 1] = key
    end
    table.sort(keys)
    local rooms = {}
    for _, key in ipairs(keys) do
        local room = state.rooms[key]
        rooms[#rooms + 1] = {
            key = key,
            state = room.state,
            drawCount = room.drawCount,
        }
    end
    return {
        runSeed = state.runSeed,
        activeRoomKey = state.activeRoomKey,
        rooms = rooms,
        outputSequence = copyArray(state.outputSequence),
        lastSavedRaw = state.lastSavedRaw,
    }
end

local api = {
    StartRun = startRun,
    SelectRoom = selectRoom,
    DrawCurrentRoom = drawCurrentRoom,
    SaveNow = saveNow,
    Snapshot = snapshot,
}
IsaacConstructRoomRng = api

mod:AddCallback(ModCallbacks.MC_POST_NEW_ROOM, function()
    local room = game:GetRoom()
    if not room then
        return
    end
    pendingRoomSpawnSeed = room:GetSpawnSeed()
    if state.initialized then
        selectRoom(state.runSeed, pendingRoomSpawnSeed)
        pendingRoomSpawnSeed = nil
    end
end)

mod:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, function(_, isContinued)
    local seeds = game:GetSeeds()
    local rawData = mod:HasData() and mod:LoadData() or nil
    startRun(isContinued, rawData, seeds:GetStartSeed())
    if pendingRoomSpawnSeed == nil then
        local room = game:GetRoom()
        if room then
            pendingRoomSpawnSeed = room:GetSpawnSeed()
        end
    end
    if pendingRoomSpawnSeed ~= nil then
        selectRoom(state.runSeed, pendingRoomSpawnSeed)
        pendingRoomSpawnSeed = nil
    end
end)

mod:AddCallback(ModCallbacks.MC_POST_UPDATE, function()
    if state.initialized and state.activeRoomKey then
        drawCurrentRoom()
    end
end)

local function saveAndCloseRun()
    saveNow()
    state.initialized = false
    state.activeRoomKey = nil
end
mod:AddCallback(ModCallbacks.MC_PRE_GAME_EXIT, saveAndCloseRun)
mod:AddCallback(ModCallbacks.MC_POST_GAME_END, saveAndCloseRun)

mod:AddCallback(ModCallbacks.MC_EXECUTE_CMD, function(_, command)
    if command == "constructrng" then
        saveNow()
    end
end)
