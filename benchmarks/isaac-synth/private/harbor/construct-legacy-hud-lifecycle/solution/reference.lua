local mod = RegisterMod("Construct Legacy HUD Lifecycle Reference", 1)
local game = Game()
local json = require("json")

local SCHEMA_VERSION = 2
local LEGACY_SCHEMA_VERSION = 1
local SAVE_COMMAND = "constructlegacy"
local MIN_OFFSET = 0
local MAX_OFFSET = 10

local function isFinite(value)
    return type(value) == "number"
        and value == value
        and value ~= math.huge
        and value ~= -math.huge
end

local function isBoolean(value)
    return type(value) == "boolean"
end

local function isKeyName(value)
    return type(value) == "string"
end

local function isOffset(value)
    return isFinite(value) and value >= MIN_OFFSET and value <= MAX_OFFSET
end

-- Known keys of every category with the check a stored value must pass to replace the
-- default. Anything else in stored data is ignored.
local CATEGORIES = {
    menu = { dev = isBoolean, demo = isBoolean, open = isBoolean },
    general = { hud = isBoolean, hud_offset = isOffset },
    controls = { menu_key = isKeyName, reset_key = isKeyName },
}

-- The HUD-offset default for one Options value: its finite numeric HUDOffset clamped to
-- [0,10], and 0 for anything else.
local function resolveOffset(optionsValue)
    if type(optionsValue) ~= "table" then
        return 0
    end
    local ok, offset = pcall(function()
        return optionsValue.HUDOffset
    end)
    if not ok or not isFinite(offset) then
        return 0
    end
    return math.min(math.max(offset, MIN_OFFSET), MAX_OFFSET)
end

local function defaultConfig(offset)
    return {
        schema_version = SCHEMA_VERSION,
        menu = { dev = false, demo = false, open = false },
        general = { hud = true, hud_offset = offset },
        controls = { menu_key = "F2", reset_key = "F3" },
    }
end

-- Copies the valid known keys of `stored` over one default category.
local function mergeCategory(target, stored, fields)
    if type(stored) ~= "table" then
        return
    end
    for key, valid in pairs(fields) do
        local value = stored[key]
        if valid(value) then
            target[key] = value
        end
    end
end

-- The normalized version-2 object for one decoded value, built over fresh defaults.
local function normalize(decoded, offset)
    local config = defaultConfig(offset)
    if type(decoded) ~= "table" then
        return config
    end
    if decoded.schema_version == LEGACY_SCHEMA_VERSION then
        -- Version 1 kept only the menu's own settings, flat at the top level.
        mergeCategory(config.menu, decoded, CATEGORIES.menu)
        return config
    end
    for category, fields in pairs(CATEGORIES) do
        mergeCategory(config[category], decoded[category], fields)
    end
    return config
end

-- The decoded stored value, or nil when there is no usable data.
local function decodeStored(hasData, rawData)
    if not hasData or type(rawData) ~= "string" or rawData == "" then
        return nil
    end
    local ok, decoded = pcall(json.decode, rawData)
    if not ok then
        return nil
    end
    return decoded
end

-- A fresh copy of the normalized object holding exactly its known keys. Snapshots and
-- the save path both serialize through it.
local function copyConfig(config)
    local copy = { schema_version = SCHEMA_VERSION }
    for category, fields in pairs(CATEGORIES) do
        local section = {}
        for key in pairs(fields) do
            section[key] = config[category][key]
        end
        copy[category] = section
    end
    return copy
end

-- The live screen-offset helper the menu renders with; every load sets it exactly once.
local screenOffset = {
    value = 0,
}

function screenOffset.set(value)
    screenOffset.value = value
end

function screenOffset.origin()
    return 48 + screenOffset.value * 2, 40 + screenOffset.value * 1.2
end

local state = {
    config = defaultConfig(resolveOffset(Options)),
    menuOpen = false,
    seedEffectInitiallyPresent = false,
    ownsSeedEffect = false,
    lastSavedRaw = nil,
}
screenOffset.set(state.config.general.hud_offset)

local function hudSeeds()
    return game:GetSeeds(), SeedEffect.SEED_NO_HUD
end

-- Opening hides the HUD with SEED_NO_HUD and records whether the effect was already
-- present; an already open menu keeps its recorded ownership.
local function openTransition()
    if not state.menuOpen then
        local seeds, effect = hudSeeds()
        local present = seeds:HasSeedEffect(effect)
        local added = false
        if not present then
            seeds:AddSeedEffect(effect)
            added = seeds:HasSeedEffect(effect)
        end
        state.seedEffectInitiallyPresent = present
        state.ownsSeedEffect = added
        state.menuOpen = true
    end
    state.config.menu.open = true
end

-- Closing removes SEED_NO_HUD only when this mod added it.
local function closeTransition()
    if state.menuOpen and state.ownsSeedEffect then
        local seeds, effect = hudSeeds()
        seeds:RemoveSeedEffect(effect)
    end
    state.ownsSeedEffect = false
    state.menuOpen = false
    state.config.menu.open = false
end

-- The one load path of the game-start callback and LoadRaw: normalize over fresh
-- defaults, synchronize the offset helper once, then apply the desired menu state
-- through the same transitions as OpenMenu and CloseMenu.
local function loadTransition(hasData, rawData, offset)
    local config = normalize(decodeStored(hasData, rawData), offset)
    state.config = config
    screenOffset.set(config.general.hud_offset)
    if config.menu.open then
        openTransition()
    else
        closeTransition()
    end
    return true
end

-- The one serialization path of the save command, the exit callbacks and SaveNow.
local function saveNow()
    local ok, rawData = pcall(json.encode, copyConfig(state.config))
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
    return {
        config = copyConfig(state.config),
        hudOffset = screenOffset.value,
        menuOpen = state.menuOpen,
        seedEffectInitiallyPresent = state.seedEffectInitiallyPresent,
        ownsSeedEffect = state.ownsSeedEffect,
        lastSavedRaw = state.lastSavedRaw,
    }
end

local api = {
    OpenMenu = function()
        openTransition()
        return state.menuOpen
    end,
    CloseMenu = function()
        closeTransition()
        return state.menuOpen
    end,
    ResolveOffset = resolveOffset,
    LoadRaw = function(hasData, rawData)
        return loadTransition(hasData, rawData, resolveOffset(Options))
    end,
    SaveNow = saveNow,
    Snapshot = snapshot,
}
IsaacConstructLegacyHUD = api

-- A continued run loads its saved settings; a new run starts from rebuilt defaults.
mod:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, function(_, isContinued)
    local hasData = false
    local rawData = nil
    if isContinued then
        hasData = mod:HasData()
        if hasData then
            rawData = mod:LoadData()
        end
    end
    loadTransition(hasData, rawData, resolveOffset(Options))
end)

mod:AddCallback(ModCallbacks.MC_POST_RENDER, function()
    if not state.menuOpen then
        return
    end
    local x, y = screenOffset.origin()
    local config = state.config
    Isaac.RenderText("Construct Legacy HUD", x, y, 1, 1, 1, 1)
    Isaac.RenderText("dev " .. tostring(config.menu.dev)
        .. "  demo " .. tostring(config.menu.demo), x, y + 12, 1, 1, 1, 0.8)
    Isaac.RenderText("hud " .. tostring(config.general.hud)
        .. "  offset " .. string.format("%.1f", config.general.hud_offset), x, y + 24, 1, 1, 1, 0.8)
    Isaac.RenderText("menu " .. config.controls.menu_key
        .. "  reset " .. config.controls.reset_key, x, y + 36, 1, 1, 1, 0.8)
end)

-- Leaving a run saves, then gives back an effect this mod added so that a continued run
-- does not start with it; the saved configuration keeps the desired menu state.
local function leaveRun()
    saveNow()
    if state.menuOpen and state.ownsSeedEffect then
        local seeds, effect = hudSeeds()
        seeds:RemoveSeedEffect(effect)
    end
    state.menuOpen = false
    state.ownsSeedEffect = false
end
mod:AddCallback(ModCallbacks.MC_PRE_GAME_EXIT, leaveRun)
mod:AddCallback(ModCallbacks.MC_POST_GAME_END, leaveRun)

mod:AddCallback(ModCallbacks.MC_EXECUTE_CMD, function(_, command)
    if command == SAVE_COMMAND then
        saveNow()
    end
end)
