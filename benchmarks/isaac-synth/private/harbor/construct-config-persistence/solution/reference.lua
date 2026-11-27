local mod = RegisterMod("Construct Config Persistence Reference", 1)
local json = require("json")

local SCHEMA_VERSION = 2
local LEGACY_SCHEMA_VERSION = 1
local HUD_OFFSET_MIN = 0
local HUD_OFFSET_MAX = 10
local SAVE_COMMAND = "constructcfg"

local function isBoolean(value)
    return type(value) == "boolean"
end

local function isString(value)
    return type(value) == "string"
end

local function isHudOffset(value)
    return type(value) == "number"
        and value == value
        and value ~= math.huge
        and value ~= -math.huge
        and value >= HUD_OFFSET_MIN
        and value <= HUD_OFFSET_MAX
end

-- The registered defaults and the validator of every key. The ordered lists fix how a
-- configuration is built, so equal configurations are always built the same way.
local SCHEMA = {
    {
        name = "menu",
        keys = {
            { name = "dev", default = false, valid = isBoolean },
            { name = "demo", default = false, valid = isBoolean },
            { name = "open", default = false, valid = isBoolean },
        },
    },
    {
        name = "general",
        keys = {
            { name = "hud", default = true, valid = isBoolean },
            { name = "hud_offset", default = 0.0, valid = isHudOffset },
        },
    },
    {
        name = "controls",
        keys = {
            { name = "menu_key", default = "F2", valid = isString },
            { name = "reset_key", default = "F3", valid = isString },
        },
    },
}

-- One category rebuilt key by key from `source`. A valid value is kept; a missing key,
-- a wrong type, an offset outside [0,10] or a non-table source takes the default.
-- Unknown keys are never copied.
local function normalizeCategory(category, source)
    local result = {}
    for _, key in ipairs(category.keys) do
        local value = nil
        if type(source) == "table" then
            value = source[key.name]
        end
        if key.valid(value) then
            result[key.name] = value
        else
            result[key.name] = key.default
        end
    end
    return result
end

-- A complete configuration merged by category and key over the defaults. `source` may
-- be a version 2 payload, a live configuration or nothing at all; the result never
-- shares a table with it.
local function buildConfig(source)
    local config = {}
    for _, category in ipairs(SCHEMA) do
        local section = nil
        if type(source) == "table" then
            section = source[category.name]
        end
        config[category.name] = normalizeCategory(category, section)
    end
    return config
end

-- Version 1 stored the three menu flags flat at the top level. Only those migrate;
-- general and controls keep their defaults.
local function migrateLegacy(decoded)
    return buildConfig({
        menu = { dev = decoded.dev, demo = decoded.demo, open = decoded.open },
    })
end

-- The configuration a saved payload describes, or nil when there is nothing to merge:
-- no data, empty text, a decode error, a decoded non-table value or an unknown schema
-- version. A rejected value is never indexed.
local function decodePayload(hasData, rawData)
    if not hasData or type(rawData) ~= "string" or rawData == "" then
        return nil
    end
    local ok, decoded = pcall(json.decode, rawData)
    if not ok or type(decoded) ~= "table" then
        return nil
    end
    if decoded.schema_version == SCHEMA_VERSION then
        return buildConfig(decoded)
    elseif decoded.schema_version == LEGACY_SCHEMA_VERSION then
        return migrateLegacy(decoded)
    end
    return nil
end

local state = {
    config = buildConfig(nil),
    screenOffset = 0.0,
    offsetSyncCount = 0,
    successDiagnosticCount = 0,
    lastSavedRaw = nil,
}

-- The live screen-offset helper follows the normalized general.hud_offset once per load.
local function syncScreenOffset()
    state.screenOffset = state.config.general.hud_offset
    state.offsetSyncCount = state.offsetSyncCount + 1
end

-- The development success diagnostic only counts and logs; a failure to log is ignored.
local function emitSuccessDiagnostic()
    state.successDiagnosticCount = state.successDiagnosticCount + 1
    pcall(function()
        Isaac.DebugString("[ConstructConfig] saved configuration merged with menu.dev enabled")
    end)
end

local function loadRaw(hasData, rawData, currentBeforeLoad)
    local live = state.config
    if currentBeforeLoad ~= nil then
        live = currentBeforeLoad
    end
    local merged = decodePayload(hasData, rawData)
    -- An absent or rejected payload rebuilds from the defaults plus the pre-load live
    -- configuration, through the same per-key validation as a saved category.
    state.config = merged or buildConfig(live)
    syncScreenOffset()
    if merged ~= nil and state.config.menu.dev == true then
        emitSuccessDiagnostic()
    end
    return merged ~= nil
end

-- The one save routine. It writes the normalized configuration as version 2 and never
-- changes the live settings, so a repeated call writes the same payload.
local function saveNow()
    local config = buildConfig(state.config)
    local payload = {
        schema_version = SCHEMA_VERSION,
        menu = config.menu,
        general = config.general,
        controls = config.controls,
    }
    local encoded, rawData = pcall(json.encode, payload)
    if not encoded or type(rawData) ~= "string" then
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
    return {
        config = buildConfig(state.config),
        screenOffset = state.screenOffset,
        offsetSyncCount = state.offsetSyncCount,
        successDiagnosticCount = state.successDiagnosticCount,
        lastSavedRaw = state.lastSavedRaw,
    }
end

IsaacConstructConfig = {
    LoadRaw = loadRaw,
    SaveNow = saveNow,
    Snapshot = snapshot,
}

mod:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, function()
    local hasData = mod:HasData()
    loadRaw(hasData, hasData and mod:LoadData() or nil)
end)

local function saveOnLifecycle()
    saveNow()
end
mod:AddCallback(ModCallbacks.MC_PRE_GAME_EXIT, saveOnLifecycle)
mod:AddCallback(ModCallbacks.MC_POST_GAME_END, saveOnLifecycle)

mod:AddCallback(ModCallbacks.MC_EXECUTE_CMD, function(_, command)
    if command == SAVE_COMMAND then
        saveNow()
    end
end)
