local suite = RegisterMod("Construct Legacy HUD Lifecycle Verifier", 1)
local game = Game()
local json = require("json")

-- Every public acceptance case. `finish` fails a case that a broken run never reached, so
-- the summary always covers all of them exactly once.
local CASES = {
    "version2_saves_all_categories",
    "general_value_round_trip",
    "partial_load_defaults",
    "legacy_flat_menu_migrates",
    "legacy_migration_saves_v2",
    "missing_options_default_zero",
    "offset_clamped_low",
    "offset_clamped_high",
    "seed_absent_initially",
    "menu_open_adds_seed_only_when_absent",
    "preexisting_seed_preserved",
    "menu_close_removes_owned_seed",
    "menu_close_preserves_preexisting_seed",
    "repeated_open_idempotent",
    "repeated_close_idempotent",
    "hud_offset_nil_fallback",
    "hud_offset_non_numeric_fallback",
    "hud_offset_finite_clamp",
    "options_root_absent_safe",
    "unsupported_apis_never_used",
    "load_callback_does_not_throw",
    "render_callback_does_not_throw",
    "load_decoded_table_merges",
    "missing_fields_default",
    "invalid_category_default",
    "unknown_keys_ignored",
    "malformed_json_defaults",
    "non_table_json_defaults",
    "hasdata_false_defaults",
    "missing_data_defaults",
    "save_after_load_is_v2",
    "save_does_not_mutate_live_config",
    "continued_load_restores_config_and_open_effect",
    "new_run_uses_defaults",
    "seed_restored_after_room_change",
}

local SEED_NO_HUD = SeedEffect and SeedEffect.SEED_NO_HUD
local CATEGORY_ORDER = { "menu", "general", "controls" }
local FIELDS = {
    menu = { "dev", "demo", "open" },
    general = { "hud", "hud_offset" },
    controls = { "menu_key", "reset_key" },
}
-- A frame step waits for this many update frames and MC_POST_RENDER callbacks, and fails
-- its case when the wait exceeds its update-frame budget. The whole run has its own budget.
local MIN_UPDATES = 2
local MIN_RENDERS = 3
local STEP_BUDGET = 60
local RUN_BUDGET = 600

local FULL_JSON = '{"schema_version":2,'
    .. '"menu":{"dev":true,"demo":true,"open":false},'
    .. '"general":{"hud":false,"hud_offset":6},'
    .. '"controls":{"menu_key":"F6","reset_key":"F7"}}'
local OPEN_JSON = '{"schema_version":2,'
    .. '"menu":{"dev":true,"demo":false,"open":true},'
    .. '"general":{"hud":false,"hud_offset":5},'
    .. '"controls":{"menu_key":"F4","reset_key":"F5"}}'
local LEGACY_JSON = '{"schema_version":1,"dev":true,"demo":false,"open":false}'
-- Stored inputs that must all be rejected safely: missing, empty, malformed and
-- non-table text, HasData()==false, and category values of the wrong type.
local REJECTED = {
    { true, nil },
    { true, "" },
    { true, "{bad json" },
    { true, '{"schema_version":2,"menu":{"dev":tru' },
    { true, "42" },
    { true, '"text"' },
    { true, "true" },
    { true, "null" },
    { true, "[]" },
    { false, nil },
    { false, "{bad json" },
    { true, '{"schema_version":2,"menu":7,"general":"x","controls":false}' },
    { true, '{"schema_version":1,"dev":"yes","demo":0,"open":"no"}' },
}

local passed = 0
local failed = 0
local recorded = {}
local finished = false
local started = false
-- Update frames observed since the run started; the synchronous cases run on the first
-- one so that every mod's MC_POST_GAME_STARTED handler has completed whatever the load order.
local updateFrames = 0
-- MC_POST_RENDER callbacks observed; the frame-step cases wait for real render frames.
local renderFrames = 0
-- What the production game-start callback left behind, captured on the first update.
local startup = nil
-- The frame-step state machine: the current step, the update frames spent in it, the
-- render count when it began, and observations carried between the steps of one case.
local stage = nil
local stageFrames = 0
local stageRenderBase = 0
local scratch = {}
-- Globals the unsupported-API case replaces temporarily and restores.
local stubs = { installed = {}, calls = {}, repentance = nil }

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

local function near(actual, expected, label)
    if type(actual) ~= "number" or not (math.abs(actual - expected) <= 1e-9) then
        error((label or "value") .. ": expected " .. tostring(expected)
            .. ", received " .. tostring(actual))
    end
end

local function flag(value)
    return value and true or false
end

local function finite(value)
    return type(value) == "number"
        and value == value
        and value ~= math.huge
        and value ~= -math.huge
end

local function record(name, ok, detail)
    if recorded[name] then
        return
    end
    recorded[name] = true
    -- A submission's error object may not even convert to a string; that is its failure,
    -- never a verifier crash.
    local printable, text = pcall(tostring, detail or (ok and "ok" or "failed"))
    if not printable or type(text) ~= "string" then
        text = "unprintable detail"
    end
    text = text:gsub("[\r\n]+", " ")
    if #text > 400 then
        text = text:sub(1, 400)
    end
    if ok then
        passed = passed + 1
        log("[GCB_CASE] PASS " .. name .. " " .. text)
    else
        failed = failed + 1
        log("[GCB_CASE] FAIL " .. name .. " " .. text)
    end
end

local function api()
    local value = IsaacConstructLegacyHUD
    truthy(type(value) == "table", "IsaacConstructLegacyHUD is not exported")
    return value
end

local function seeds()
    truthy(SEED_NO_HUD ~= nil, "SeedEffect.SEED_NO_HUD is unavailable")
    return game:GetSeeds()
end

local function hasSeed()
    return seeds():HasSeedEffect(SEED_NO_HUD) == true
end

-- Sets SEED_NO_HUD directly, as another source of the effect would.
local function forceSeed(present)
    local current = seeds()
    if present and not current:HasSeedEffect(SEED_NO_HUD) then
        current:AddSeedEffect(SEED_NO_HUD)
    elseif not present and current:HasSeedEffect(SEED_NO_HUD) then
        current:RemoveSeedEffect(SEED_NO_HUD)
    end
    equal(current:HasSeedEffect(SEED_NO_HUD) == true, present, "engine SEED_NO_HUD state")
end

-- Puts back every global the unsupported-API case replaced. Safe to call repeatedly.
local function restoreGlobals()
    for index = #stubs.installed, 1, -1 do
        local entry = stubs.installed[index]
        pcall(rawset, entry.container, entry.key, entry.original)
    end
    stubs.installed = {}
    if stubs.repentance ~= nil then
        rawset(_G, "REPENTANCE", stubs.repentance.value)
        stubs.repentance = nil
    end
end

-- Closes the menu through the public API and removes any SEED_NO_HUD left behind, so
-- that one case cannot leak engine state into the next.
local function settle()
    local hud = IsaacConstructLegacyHUD
    if type(hud) == "table" and type(hud.CloseMenu) == "function" then
        pcall(hud.CloseMenu)
    end
    pcall(forceSeed, false)
end

local function run(name, fn)
    local ok, result = pcall(fn)
    settle()
    record(name, ok, result)
end

-- The HUD-offset default the statement specifies for one Options value.
local function specOffset(options)
    if type(options) ~= "table" then
        return 0
    end
    local ok, value = pcall(function()
        return options.HUDOffset
    end)
    if not ok or not finite(value) then
        return 0
    end
    return math.min(math.max(value, 0), 10)
end

local function config(menu, general, controls)
    return { menu = menu, general = general, controls = controls }
end

local function defaults(offset)
    return config({ dev = false, demo = false, open = false },
        { hud = true, hud_offset = offset },
        { menu_key = "F2", reset_key = "F3" })
end

local function fullConfig()
    return config({ dev = true, demo = true, open = false },
        { hud = false, hud_offset = 6 },
        { menu_key = "F6", reset_key = "F7" })
end

local function openConfig()
    return config({ dev = true, demo = false, open = true },
        { hud = false, hud_offset = 5 },
        { menu_key = "F4", reset_key = "F5" })
end

local function keyList(value)
    local keys = {}
    for key in pairs(value) do
        keys[#keys + 1] = tostring(key)
    end
    table.sort(keys)
    return table.concat(keys, ",")
end

-- Checks one normalized version-2 object: exactly the four top-level keys and the
-- expected value of every known field.
local function checkConfig(actual, want, label)
    truthy(type(actual) == "table", label .. ": not a table")
    equal(keyList(actual), "controls,general,menu,schema_version", label .. ": top-level keys")
    equal(actual.schema_version, 2, label .. ": schema_version")
    for _, category in ipairs(CATEGORY_ORDER) do
        local section = actual[category]
        truthy(type(section) == "table", label .. ": " .. category .. " is not a table")
        for _, key in ipairs(FIELDS[category]) do
            local path = label .. ": " .. category .. "." .. key
            if key == "hud_offset" then
                near(section[key], want[category][key], path)
            else
                equal(section[key], want[category][key], path)
            end
        end
    end
end

-- Checks a snapshot's configuration and that the live offset helper follows it.
local function checkLoaded(snap, want, label)
    truthy(type(snap) == "table", label .. ": Snapshot did not return a table")
    checkConfig(snap.config, want, label .. " config")
    near(snap.hudOffset, want.general.hud_offset, label .. " hudOffset")
end

local function checkMenu(snap, open, owns, initially, label)
    truthy(type(snap) == "table", label .. ": Snapshot did not return a table")
    equal(flag(snap.menuOpen), open, label .. ": menuOpen")
    truthy(type(snap.config) == "table" and type(snap.config.menu) == "table",
        label .. ": config.menu missing")
    equal(snap.config.menu.open, open, label .. ": config.menu.open")
    equal(flag(snap.ownsSeedEffect), owns, label .. ": ownsSeedEffect")
    if initially ~= nil then
        equal(flag(snap.seedEffectInitiallyPresent), initially,
            label .. ": seedEffectInitiallyPresent")
    end
end

local function loadStored(hud, hasData, rawData)
    hud.LoadRaw(hasData, rawData)
    return hud.Snapshot()
end

local function decodeSaved(snap, label)
    label = label or "save"
    truthy(type(snap) == "table", label .. ": Snapshot did not return a table")
    local raw = snap.lastSavedRaw
    truthy(type(raw) == "string", label .. ": lastSavedRaw is not a string")
    local ok, decoded = pcall(json.decode, raw)
    truthy(ok and type(decoded) == "table", label .. ": lastSavedRaw is not a JSON object")
    return decoded
end

-- Brings the submission to a closed menu with default settings and SEED_NO_HUD absent.
-- It also passes the real Options through ResolveOffset first, so an implementation that
-- keeps the last resolved offset as its default loads the production default again.
local function baseline()
    local hud = api()
    hud.CloseMenu()
    forceSeed(false)
    pcall(hud.ResolveOffset, Options)
    hud.LoadRaw(false, nil)
    equal(hasSeed(), false, "baseline: SEED_NO_HUD after a default load")
    return hud, specOffset(Options)
end

-- Deep copy of data returned by the submission, so later calls cannot change it.
local function copy(value, depth)
    depth = depth or 0
    if type(value) ~= "table" or depth > 4 then
        return value
    end
    local result = {}
    for key, entry in pairs(value) do
        result[key] = copy(entry, depth + 1)
    end
    return result
end

local function captureStartup()
    local captured = {}
    local okSeed, present = pcall(hasSeed)
    if okSeed then
        captured.effect = present
    else
        captured.seedError = present
    end
    local ok, snap = pcall(function()
        return copy(api().Snapshot())
    end)
    if ok and type(snap) == "table" then
        captured.snapshot = snap
    else
        captured.error = ok and ("Snapshot returned " .. type(snap)) or snap
    end
    return captured
end

local function startupSnapshot()
    truthy(startup ~= nil, "startup state was not captured")
    truthy(type(startup.snapshot) == "table",
        "no Snapshot at the first update: " .. tostring(startup.error))
    return startup.snapshot
end

-- Every observable piece of state as a list of tokens, for comparisons across frames.
local function configTokens(value, tokens, prefix)
    for _, category in ipairs(CATEGORY_ORDER) do
        local section = nil
        if type(value) == "table" then
            section = value[category]
        end
        for _, key in ipairs(FIELDS[category]) do
            local entry = nil
            if type(section) == "table" then
                entry = section[key]
            end
            tokens[#tokens + 1] = prefix .. category .. "." .. key .. "=" .. tostring(entry)
        end
    end
    return tokens
end

local function fingerprint(hud, prefix)
    prefix = prefix or ""
    local snap = hud.Snapshot()
    truthy(type(snap) == "table", "Snapshot did not return a table")
    local tokens = {
        prefix .. "menuOpen=" .. tostring(flag(snap.menuOpen)),
        prefix .. "ownsSeedEffect=" .. tostring(flag(snap.ownsSeedEffect)),
        prefix .. "seedEffectInitiallyPresent=" .. tostring(flag(snap.seedEffectInitiallyPresent)),
        prefix .. "hudOffset=" .. tostring(snap.hudOffset),
        prefix .. "SEED_NO_HUD=" .. tostring(hasSeed()),
    }
    return configTokens(snap.config, tokens, prefix)
end

local function sameTokens(actual, expected, label)
    truthy(type(actual) == "table" and type(expected) == "table", label .. ": missing observations")
    for index = 1, math.max(#actual, #expected) do
        if actual[index] ~= expected[index] then
            error(label .. ": expected " .. tostring(expected[index])
                .. ", received " .. tostring(actual[index]))
        end
    end
end

-- Overwrites the configuration and state fields of a table a public method returned. A
-- method that exposed a live internal table would see its state change.
local function scribble(value)
    if type(value) ~= "table" or value == IsaacConstructLegacyHUD or value == _G then
        return
    end
    for _, target in ipairs({ value, rawget(value, "config") }) do
        if type(target) == "table" then
            for _, category in ipairs(CATEGORY_ORDER) do
                local section = rawget(target, category)
                if type(section) == "table" then
                    for _, key in ipairs(FIELDS[category]) do
                        rawset(section, key, "scribbled")
                    end
                end
            end
            for _, key in ipairs({ "schema_version", "hudOffset", "menuOpen",
                "seedEffectInitiallyPresent", "ownsSeedEffect", "lastSavedRaw" }) do
                if rawget(target, key) ~= nil then
                    rawset(target, key, "scribbled")
                end
            end
        end
    end
end

local function unsupportedStub(label)
    return function()
        stubs.calls[#stubs.calls + 1] = label
        error(label .. " is outside the Afterbirth+ runtime contract", 2)
    end
end

local function installStub(container, key, label)
    if type(container) ~= "table" then
        return
    end
    local okGet, original = pcall(rawget, container, key)
    if okGet and pcall(rawset, container, key, unsupportedStub(label)) then
        stubs.installed[#stubs.installed + 1] = {
            container = container,
            key = key,
            original = original,
        }
    end
end

-- Replaces the APIs the statement puts outside the runtime contract with functions that
-- record the call and raise. Game:GetHUD is reachable only through the Game class
-- metatable; when the binding does not expose it there, that stub is skipped.
local function installStubs()
    restoreGlobals()
    stubs.calls = {}
    installStub(Isaac, "GetScreenWidth", "Isaac.GetScreenWidth")
    installStub(Isaac, "GetScreenHeight", "Isaac.GetScreenHeight")
    local okMeta, meta = pcall(getmetatable, game)
    if okMeta then
        installStub(meta, "GetHUD", "Game:GetHUD")
    end
end

local function setRepentance(value)
    if stubs.repentance == nil then
        stubs.repentance = { value = rawget(_G, "REPENTANCE") }
    end
    rawset(_G, "REPENTANCE", value)
end

-- One scripted pass over the load, open, close and save paths. It returns every
-- observable result, so passes with and without REPENTANCE can be compared.
local function lifecyclePass()
    local hud = baseline()
    local tokens = {}
    local function note(label)
        for _, token in ipairs(fingerprint(hud, label .. ":")) do
            tokens[#tokens + 1] = token
        end
    end
    hud.LoadRaw(false, nil)
    note("default")
    hud.LoadRaw(true, FULL_JSON)
    note("full")
    hud.LoadRaw(true, OPEN_JSON)
    note("open_load")
    hud.CloseMenu()
    note("close")
    hud.OpenMenu()
    note("open")
    hud.SaveNow()
    local okSaved, saved = pcall(decodeSaved, hud.Snapshot())
    if okSaved then
        configTokens(saved, tokens, "saved:")
    else
        tokens[#tokens + 1] = "saved:undecodable"
    end
    hud.CloseMenu()
    note("close_again")
    hud.LoadRaw(true, LEGACY_JSON)
    note("legacy")
    tokens[#tokens + 1] = "resolve=" .. tostring(hud.ResolveOffset(Options))
    return tokens
end

local function executeSuite()
    run("version2_saves_all_categories", function()
        local hud = baseline()
        checkLoaded(loadStored(hud, true, FULL_JSON), fullConfig(), "loaded")
        hud.SaveNow()
        checkConfig(decodeSaved(hud.Snapshot()), fullConfig(), "saved")
    end)

    run("general_value_round_trip", function()
        local hud, offset = baseline()
        local want = defaults(offset)
        want.general = { hud = false, hud_offset = 7.5 }
        checkLoaded(loadStored(hud, true,
            '{"schema_version":2,"general":{"hud":false,"hud_offset":7.5}}'), want, "loaded")
        hud.SaveNow()
        local raw = hud.Snapshot().lastSavedRaw
        truthy(type(raw) == "string", "lastSavedRaw is not a string")
        checkLoaded(loadStored(hud, false, nil), defaults(offset), "defaults")
        checkLoaded(loadStored(hud, true, raw), want, "reloaded")
    end)

    run("partial_load_defaults", function()
        local hud, offset = baseline()
        local want = defaults(offset)
        want.menu.dev = true
        want.controls.reset_key = "F9"
        checkLoaded(loadStored(hud, true,
            '{"schema_version":2,"menu":{"dev":true},"controls":{"reset_key":"F9"}}'),
            want, "partial")
    end)

    run("legacy_flat_menu_migrates", function()
        local hud, offset = baseline()
        local want = defaults(offset)
        want.menu = { dev = true, demo = false, open = false }
        checkLoaded(loadStored(hud, true, LEGACY_JSON), want, "legacy dev")
        want.menu = { dev = false, demo = true, open = false }
        checkLoaded(loadStored(hud, true,
            '{"schema_version":1,"dev":false,"demo":true,"open":false}'), want, "legacy demo")
    end)

    run("legacy_migration_saves_v2", function()
        local hud, offset = baseline()
        local want = defaults(offset)
        want.menu = { dev = true, demo = true, open = false }
        checkLoaded(loadStored(hud, true,
            '{"schema_version":1,"dev":true,"demo":true,"open":false}'), want, "legacy")
        hud.SaveNow()
        checkConfig(decodeSaved(hud.Snapshot()), want, "saved")
    end)

    run("missing_options_default_zero", function()
        local hud = api()
        near(hud.ResolveOffset(nil), 0, "ResolveOffset(nil)")
        near(hud.ResolveOffset({}), 0, "ResolveOffset({})")
        if type(Options) ~= "table" then
            -- This runtime has no usable Options table, so the production start resolved
            -- the default offset to zero.
            local snap = startupSnapshot()
            truthy(type(snap.config) == "table" and type(snap.config.general) == "table",
                "startup config.general missing")
            near(snap.config.general.hud_offset, 0, "startup general.hud_offset")
            near(snap.hudOffset, 0, "startup hudOffset")
            near(hud.ResolveOffset(Options), 0, "ResolveOffset(Options)")
        end
        return "Options=" .. type(Options)
    end)

    run("offset_clamped_low", function()
        local hud = api()
        near(hud.ResolveOffset({ HUDOffset = -5 }), 0, "HUDOffset=-5")
        near(hud.ResolveOffset({ HUDOffset = -0.25 }), 0, "HUDOffset=-0.25")
    end)

    run("offset_clamped_high", function()
        local hud = api()
        near(hud.ResolveOffset({ HUDOffset = 99 }), 10, "HUDOffset=99")
        near(hud.ResolveOffset({ HUDOffset = 10.5 }), 10, "HUDOffset=10.5")
    end)

    run("seed_absent_initially", function()
        truthy(startup ~= nil, "startup state was not captured")
        equal(startup.effect, false, "SEED_NO_HUD at the first update ("
            .. tostring(startup.seedError) .. ")")
        local snap = startupSnapshot()
        equal(flag(snap.menuOpen), false, "startup menuOpen")
        equal(flag(snap.ownsSeedEffect), false, "startup ownsSeedEffect")
        local hud = baseline()
        hud.OpenMenu()
        checkMenu(hud.Snapshot(), true, true, false, "open")
        truthy(hasSeed(), "SEED_NO_HUD absent after open")
        hud.CloseMenu()
        equal(hasSeed(), false, "SEED_NO_HUD after close")
    end)

    run("menu_open_adds_seed_only_when_absent", function()
        local hud = baseline()
        hud.OpenMenu()
        checkMenu(hud.Snapshot(), true, true, false, "open while absent")
        truthy(hasSeed(), "SEED_NO_HUD not added")
        hud.CloseMenu()
        equal(hasSeed(), false, "SEED_NO_HUD after close")
        forceSeed(true)
        hud.OpenMenu()
        checkMenu(hud.Snapshot(), true, false, true, "open while present")
        hud.CloseMenu()
        truthy(hasSeed(), "preexisting SEED_NO_HUD removed")
    end)

    run("preexisting_seed_preserved", function()
        local hud = baseline()
        forceSeed(true)
        hud.OpenMenu()
        checkMenu(hud.Snapshot(), true, false, true, "first open")
        hud.OpenMenu()
        checkMenu(hud.Snapshot(), true, false, true, "repeated open")
        hud.CloseMenu()
        checkMenu(hud.Snapshot(), false, false, nil, "close")
        truthy(hasSeed(), "SEED_NO_HUD removed by close")
        hud.OpenMenu()
        checkMenu(hud.Snapshot(), true, false, true, "second open")
        hud.CloseMenu()
        truthy(hasSeed(), "SEED_NO_HUD removed by second close")
    end)

    run("menu_close_removes_owned_seed", function()
        local hud = baseline()
        hud.OpenMenu()
        truthy(hasSeed(), "SEED_NO_HUD absent after open")
        hud.CloseMenu()
        checkMenu(hud.Snapshot(), false, false, nil, "close")
        equal(hasSeed(), false, "SEED_NO_HUD after close")
    end)

    run("menu_close_preserves_preexisting_seed", function()
        local hud = baseline()
        forceSeed(true)
        hud.OpenMenu()
        hud.CloseMenu()
        checkMenu(hud.Snapshot(), false, false, nil, "close")
        truthy(hasSeed(), "SEED_NO_HUD removed by close")
        hud.CloseMenu()
        truthy(hasSeed(), "SEED_NO_HUD removed by repeated close")
    end)

    run("repeated_open_idempotent", function()
        local hud = baseline()
        hud.OpenMenu()
        hud.OpenMenu()
        hud.OpenMenu()
        checkMenu(hud.Snapshot(), true, true, false, "three opens")
        truthy(hasSeed(), "SEED_NO_HUD absent after opens")
        -- A load whose normalized menu.open is true uses the same idempotent transition.
        hud.LoadRaw(true, '{"schema_version":2,"menu":{"open":true}}')
        checkMenu(hud.Snapshot(), true, true, false, "open load while open")
        hud.CloseMenu()
        equal(hasSeed(), false, "SEED_NO_HUD after close")
    end)

    run("repeated_close_idempotent", function()
        local hud = baseline()
        hud.OpenMenu()
        hud.CloseMenu()
        hud.CloseMenu()
        checkMenu(hud.Snapshot(), false, false, nil, "two closes")
        equal(hasSeed(), false, "SEED_NO_HUD after closes")
        -- Another source hides the HUD while the menu is closed.
        forceSeed(true)
        hud.CloseMenu()
        hud.CloseMenu()
        truthy(hasSeed(), "closing a closed menu removed another source's SEED_NO_HUD")
        hud.LoadRaw(false, nil)
        checkMenu(hud.Snapshot(), false, false, nil, "closed load")
        truthy(hasSeed(), "a closed load removed another source's SEED_NO_HUD")
    end)

    -- The offset cases probe ResolveOffset before `baseline`, which passes the real Options
    -- through it again before any load relies on the resolved default.
    run("hud_offset_nil_fallback", function()
        near(api().ResolveOffset({ HUDOffset = nil }), 0, "HUDOffset=nil")
        local hud, offset = baseline()
        local want = defaults(offset)
        want.general.hud = false
        checkLoaded(loadStored(hud, true, '{"schema_version":2,"general":{"hud":false}}'),
            want, "absent hud_offset")
        want = defaults(offset)
        want.general.hud_offset = 8
        checkLoaded(loadStored(hud, true, '{"schema_version":2,"general":{"hud_offset":8}}'),
            want, "saved 8")
        checkLoaded(loadStored(hud, true, '{"schema_version":2,"general":{}}'),
            defaults(offset), "absent after 8")
        return "default=" .. tostring(offset)
    end)

    run("hud_offset_non_numeric_fallback", function()
        local probe = api()
        near(probe.ResolveOffset({ HUDOffset = "x" }), 0, 'HUDOffset="x"')
        near(probe.ResolveOffset({ HUDOffset = true }), 0, "HUDOffset=true")
        near(probe.ResolveOffset({ HUDOffset = {} }), 0, "HUDOffset={}")
        local hud, offset = baseline()
        checkLoaded(loadStored(hud, true, '{"schema_version":2,"general":{"hud_offset":"x"}}'),
            defaults(offset), 'saved "x"')
        checkLoaded(loadStored(hud, true, '{"schema_version":2,"general":{"hud_offset":true}}'),
            defaults(offset), "saved true")
        checkLoaded(loadStored(hud, true, '{"schema_version":2,"general":{"hud_offset":[3]}}'),
            defaults(offset), "saved [3]")
    end)

    run("hud_offset_finite_clamp", function()
        local probe = api()
        near(probe.ResolveOffset({ HUDOffset = 3.5 }), 3.5, "HUDOffset=3.5")
        near(probe.ResolveOffset({ HUDOffset = 0 }), 0, "HUDOffset=0")
        near(probe.ResolveOffset({ HUDOffset = 10 }), 10, "HUDOffset=10")
        near(probe.ResolveOffset({ HUDOffset = 0 / 0 }), 0, "HUDOffset=NaN")
        near(probe.ResolveOffset({ HUDOffset = math.huge }), 0, "HUDOffset=inf")
        near(probe.ResolveOffset({ HUDOffset = -math.huge }), 0, "HUDOffset=-inf")
        local hud, offset = baseline()
        for _, value in ipairs({ "3.5", "0", "10" }) do
            local want = defaults(offset)
            want.general.hud_offset = tonumber(value)
            checkLoaded(loadStored(hud, true,
                '{"schema_version":2,"general":{"hud_offset":' .. value .. '}}'),
                want, "saved " .. value)
        end
        -- A stored offset outside [0,10] or not finite never survives normalization: the
        -- result is the clamped value or the resolved default, and the helper follows it.
        for _, entry in ipairs({ { "99", 10 }, { "-5", 0 }, { "1e400", 10 }, { "-1e400", 0 } }) do
            local label = "saved " .. entry[1]
            local snap = loadStored(hud, true,
                '{"schema_version":2,"general":{"hud_offset":' .. entry[1] .. '}}')
            truthy(type(snap) == "table" and type(snap.config) == "table"
                and type(snap.config.general) == "table", label .. ": config.general missing")
            local value = snap.config.general.hud_offset
            truthy(finite(value) and (math.abs(value - entry[2]) <= 1e-9
                or math.abs(value - offset) <= 1e-9),
                label .. ": general.hud_offset " .. tostring(value))
            near(snap.hudOffset, value, label .. " hudOffset")
        end
    end)

    run("options_root_absent_safe", function()
        local hud = api()
        near(hud.ResolveOffset(nil), 0, "ResolveOffset(nil)")
        near(hud.ResolveOffset(false), 0, "ResolveOffset(false)")
        near(hud.ResolveOffset(true), 0, "ResolveOffset(true)")
        near(hud.ResolveOffset(Options), specOffset(Options), "ResolveOffset(Options)")
        -- Without an Options root at all, loading, opening, closing and saving stay safe.
        local original = rawget(_G, "Options")
        rawset(_G, "Options", nil)
        local ok, err = pcall(function()
            baseline()
            local snap = loadStored(hud, false, nil)
            local offset = type(snap) == "table" and type(snap.config) == "table"
                and type(snap.config.general) == "table" and snap.config.general.hud_offset
            truthy(finite(offset) and offset >= 0 and offset <= 10,
                "default hud_offset without Options: " .. tostring(offset))
            checkLoaded(snap, defaults(offset), "defaults without Options")
            checkLoaded(loadStored(hud, true, FULL_JSON), fullConfig(), "stored without Options")
            hud.OpenMenu()
            truthy(hasSeed(), "SEED_NO_HUD absent after open without Options")
            hud.CloseMenu()
            equal(hasSeed(), false, "SEED_NO_HUD after close without Options")
            hud.SaveNow()
            checkConfig(decodeSaved(hud.Snapshot()), fullConfig(), "saved without Options")
        end)
        rawset(_G, "Options", original)
        truthy(ok, err)
    end)

    run("load_callback_does_not_throw", function()
        local snap = startupSnapshot()
        checkLoaded(snap, defaults(specOffset(Options)), "startup")
        equal(flag(snap.menuOpen), false, "startup menuOpen")
        local hud, offset = baseline()
        for index, input in ipairs(REJECTED) do
            local label = "rejected input " .. tostring(index)
            local ok, err = pcall(hud.LoadRaw, input[1], input[2])
            truthy(ok, label .. " raised: " .. tostring(err))
            checkLoaded(hud.Snapshot(), defaults(offset), label)
        end
        return "rejected_inputs=" .. tostring(#REJECTED)
    end)

    run("load_decoded_table_merges", function()
        local hud, offset = baseline()
        checkLoaded(loadStored(hud, true, FULL_JSON), fullConfig(), "full")
        -- A later load merges over the defaults, not over the previous configuration.
        local want = defaults(offset)
        want.controls.menu_key = "F8"
        checkLoaded(loadStored(hud, true, '{"schema_version":2,"controls":{"menu_key":"F8"}}'),
            want, "controls only")
    end)

    run("missing_fields_default", function()
        local hud, offset = baseline()
        checkLoaded(loadStored(hud, true, '{"schema_version":2}'), defaults(offset),
            "schema only")
        checkLoaded(loadStored(hud, true,
            '{"schema_version":2,"menu":{},"general":{},"controls":{}}'),
            defaults(offset), "empty categories")
        local want = defaults(offset)
        want.menu.demo = true
        want.general.hud_offset = 2
        want.controls.menu_key = "F4"
        checkLoaded(loadStored(hud, true, '{"schema_version":2,"menu":{"demo":true},'
            .. '"general":{"hud_offset":2},"controls":{"menu_key":"F4"}}'),
            want, "one field per category")
    end)

    run("invalid_category_default", function()
        local hud, offset = baseline()
        checkLoaded(loadStored(hud, true,
            '{"schema_version":2,"menu":"oops","general":5,"controls":true}'),
            defaults(offset), "non-table categories")
        checkLoaded(loadStored(hud, true, '{"schema_version":2,'
            .. '"menu":{"dev":"yes","demo":1,"open":"true"},'
            .. '"general":{"hud":"no","hud_offset":"4"},'
            .. '"controls":{"menu_key":7,"reset_key":false}}'),
            defaults(offset), "invalid value types")
        equal(hasSeed(), false, "SEED_NO_HUD after an invalid menu.open")
        local want = defaults(offset)
        want.menu.dev = true
        want.controls.reset_key = "F10"
        checkLoaded(loadStored(hud, true, '{"schema_version":2,"menu":{"dev":true},'
            .. '"general":"bad","controls":{"reset_key":"F10"}}'),
            want, "valid categories beside an invalid one")
    end)

    run("unknown_keys_ignored", function()
        local hud, offset = baseline()
        local want = defaults(offset)
        want.menu.dev = true
        want.general.hud = false
        want.controls.menu_key = "F4"
        local snap = loadStored(hud, true, '{"schema_version":2,"extra":1,"theme":{"a":1},'
            .. '"menu":{"dev":true,"bogus":true},"general":{"hud":false,"color":"red"},'
            .. '"controls":{"menu_key":"F4","macro":"x"}}')
        checkLoaded(snap, want, "loaded")
        equal(snap.config.menu.bogus, nil, "config.menu.bogus")
        equal(snap.config.general.color, nil, "config.general.color")
        equal(snap.config.controls.macro, nil, "config.controls.macro")
        hud.SaveNow()
        local saved = decodeSaved(hud.Snapshot())
        checkConfig(saved, want, "saved")
        equal(saved.menu.bogus, nil, "saved menu.bogus")
        equal(saved.general.color, nil, "saved general.color")
        equal(saved.controls.macro, nil, "saved controls.macro")
    end)

    run("malformed_json_defaults", function()
        local hud, offset = baseline()
        for _, raw in ipairs({ '{"schema_version":2,"menu":{"dev":tru', "{bad json",
            "not json at all" }) do
            checkLoaded(loadStored(hud, true, FULL_JSON), fullConfig(), "before " .. raw)
            checkLoaded(loadStored(hud, true, raw), defaults(offset), "after " .. raw)
        end
    end)

    run("non_table_json_defaults", function()
        local hud, offset = baseline()
        for _, raw in ipairs({ "42", '"text"', "true", "false", "null" }) do
            checkLoaded(loadStored(hud, true, FULL_JSON), fullConfig(), "before " .. raw)
            checkLoaded(loadStored(hud, true, raw), defaults(offset), "after " .. raw)
        end
    end)

    run("hasdata_false_defaults", function()
        local hud, offset = baseline()
        checkLoaded(loadStored(hud, true, FULL_JSON), fullConfig(), "full")
        checkLoaded(loadStored(hud, false, FULL_JSON), defaults(offset), "stale text")
        checkLoaded(loadStored(hud, true, FULL_JSON), fullConfig(), "full")
        checkLoaded(loadStored(hud, false, nil), defaults(offset), "no text")
        checkLoaded(loadStored(hud, true, FULL_JSON), fullConfig(), "full")
        checkLoaded(loadStored(hud, false, ""), defaults(offset), "empty text")
    end)

    run("missing_data_defaults", function()
        local hud, offset = baseline()
        checkLoaded(loadStored(hud, true, FULL_JSON), fullConfig(), "full")
        checkLoaded(loadStored(hud, true, nil), defaults(offset), "missing text")
        checkLoaded(loadStored(hud, true, FULL_JSON), fullConfig(), "full")
        checkLoaded(loadStored(hud, true, ""), defaults(offset), "empty text")
    end)

    run("save_after_load_is_v2", function()
        local hud, offset = baseline()
        local partial = defaults(offset)
        partial.menu.demo = true
        local legacy = defaults(offset)
        legacy.menu.dev = true
        local inputs = {
            { true, '{"schema_version":2,"menu":{"demo":true}}', partial, "partial" },
            { true, LEGACY_JSON, legacy, "legacy" },
            { true, "{bad json", defaults(offset), "malformed" },
            { false, nil, defaults(offset), "absent" },
        }
        for _, input in ipairs(inputs) do
            local snap = loadStored(hud, input[1], input[2])
            checkLoaded(snap, input[3], input[4] .. " loaded")
            hud.SaveNow()
            checkConfig(decodeSaved(hud.Snapshot(), input[4]), input[3], input[4] .. " saved")
        end
    end)

    run("save_does_not_mutate_live_config", function()
        local hud, offset = baseline()
        local want = defaults(offset)
        want.menu.dev = true
        want.general.hud_offset = 4.25
        want.controls.menu_key = "F5"
        scribble(hud.LoadRaw(true, '{"schema_version":2,"extra":1,"menu":{"dev":true},'
            .. '"general":{"hud_offset":4.25},"controls":{"menu_key":"F5"}}'))
        local before = hud.Snapshot()
        checkLoaded(before, want, "before save")
        scribble(hud.SaveNow())
        local after = hud.Snapshot()
        checkLoaded(after, want, "after save")
        checkMenu(after, false, false, nil, "after save")
        checkConfig(decodeSaved(after), want, "saved")
        -- Every snapshot is a fresh copy.
        truthy(before.config ~= after.config
            and before.config.menu ~= after.config.menu
            and before.config.general ~= after.config.general
            and before.config.controls ~= after.config.controls, "snapshots share tables")
        scribble(after)
        checkLoaded(hud.Snapshot(), want, "after changing a snapshot")
        -- Saving while the menu is open keeps it open and serializes the open state.
        scribble(hud.OpenMenu())
        scribble(hud.SaveNow())
        local opened = hud.Snapshot()
        checkMenu(opened, true, true, false, "save while open")
        truthy(hasSeed(), "SEED_NO_HUD absent after saving while open")
        equal(decodeSaved(opened).menu.open, true, "saved menu.open while open")
        scribble(hud.CloseMenu())
        checkMenu(hud.Snapshot(), false, false, nil, "close")
        want.menu.open = false
        checkLoaded(hud.Snapshot(), want, "after close")
    end)

    run("continued_load_restores_config_and_open_effect", function()
        local hud, offset = baseline()
        local snap = loadStored(hud, true, OPEN_JSON)
        checkLoaded(snap, openConfig(), "continued")
        checkMenu(snap, true, true, false, "continued")
        truthy(hasSeed(), "SEED_NO_HUD absent after continued load")
        hud.CloseMenu()
        equal(hasSeed(), false, "SEED_NO_HUD after close")
        -- Another source already hides the HUD when the run continues.
        forceSeed(true)
        snap = loadStored(hud, true, OPEN_JSON)
        checkLoaded(snap, openConfig(), "continued over a preexisting effect")
        checkMenu(snap, true, false, true, "continued over a preexisting effect")
        hud.CloseMenu()
        truthy(hasSeed(), "preexisting SEED_NO_HUD removed by close")
        -- Legacy data restores the open menu through the same transition.
        forceSeed(false)
        local want = defaults(offset)
        want.menu = { dev = false, demo = true, open = true }
        snap = loadStored(hud, true, '{"schema_version":1,"dev":false,"demo":true,"open":true}')
        checkLoaded(snap, want, "legacy continued")
        checkMenu(snap, true, true, false, "legacy continued")
        truthy(hasSeed(), "SEED_NO_HUD absent after legacy continued load")
    end)

    run("new_run_uses_defaults", function()
        local hud, offset = baseline()
        checkMenu(loadStored(hud, true, OPEN_JSON), true, true, false, "continued")
        local snap = loadStored(hud, false, nil)
        checkLoaded(snap, defaults(offset), "new run")
        checkMenu(snap, false, false, nil, "new run")
        equal(hasSeed(), false, "SEED_NO_HUD after new run")
        forceSeed(true)
        checkMenu(loadStored(hud, true, OPEN_JSON), true, false, true,
            "continued over a preexisting effect")
        snap = loadStored(hud, false, nil)
        checkLoaded(snap, defaults(offset), "new run over a preexisting effect")
        checkMenu(snap, false, false, nil, "new run over a preexisting effect")
        truthy(hasSeed(), "new run removed another source's SEED_NO_HUD")
    end)
end

local function finish()
    if finished then
        return
    end
    finished = true
    restoreGlobals()
    settle()
    for _, name in ipairs(CASES) do
        if not recorded[name] then
            record(name, false, "case was not reached")
        end
    end
    log("[GCB_SUMMARY] passed=" .. tostring(passed)
        .. " failed=" .. tostring(failed)
        .. " total=" .. tostring(passed + failed))
end

local function enterStage(name)
    stage = name
    stageFrames = 0
    stageRenderBase = renderFrames
end

local function waitedEnough()
    return stageFrames >= MIN_UPDATES and renderFrames - stageRenderBase >= MIN_RENDERS
end

local function waitDetail()
    return "updates=" .. tostring(stageFrames)
        .. " renders=" .. tostring(renderFrames - stageRenderBase)
end

-- Fails the frame-step case in progress and names the step to continue with.
local function abandon(name, detail, nextStage)
    restoreGlobals()
    settle()
    record(name, false, detail)
    return nextStage
end

-- Cases that need real engine frames. Each step runs once per update frame and returns
-- the next step's name once it is done; a wait longer than STEP_BUDGET fails its case.
local steps = {}

-- render_callback_does_not_throw: real MC_POST_RENDER frames with the menu open and then
-- closed leave the menu, ownership, effect and configuration as they were.
steps.render_open = function()
    scratch = {}
    local ok, err = pcall(function()
        local hud = baseline()
        hud.OpenMenu()
        checkMenu(hud.Snapshot(), true, true, false, "open")
        truthy(hasSeed(), "SEED_NO_HUD absent after open")
        scratch.opened = fingerprint(hud)
    end)
    if not ok then
        return abandon("render_callback_does_not_throw", err, "unsupported_setup")
    end
    return "render_open_frames"
end

steps.render_open_frames = function()
    if not waitedEnough() then
        if stageFrames >= STEP_BUDGET then
            return abandon("render_callback_does_not_throw",
                "render frames with the menu open did not arrive: " .. waitDetail(),
                "unsupported_setup")
        end
        return nil
    end
    scratch.openWait = waitDetail()
    local ok, err = pcall(function()
        local hud = api()
        sameTokens(fingerprint(hud), scratch.opened, "after render frames with the menu open")
        hud.CloseMenu()
        checkMenu(hud.Snapshot(), false, false, nil, "close")
        equal(hasSeed(), false, "SEED_NO_HUD after close")
        scratch.closed = fingerprint(hud)
    end)
    if not ok then
        return abandon("render_callback_does_not_throw", err, "unsupported_setup")
    end
    return "render_closed_frames"
end

steps.render_closed_frames = function()
    if not waitedEnough() then
        if stageFrames >= STEP_BUDGET then
            return abandon("render_callback_does_not_throw",
                "render frames with the menu closed did not arrive: " .. waitDetail(),
                "unsupported_setup")
        end
        return nil
    end
    local closedWait = waitDetail()
    run("render_callback_does_not_throw", function()
        local hud = api()
        sameTokens(fingerprint(hud), scratch.closed, "after render frames with the menu closed")
        hud.OpenMenu()
        truthy(hasSeed(), "SEED_NO_HUD absent after reopening")
        hud.CloseMenu()
        equal(hasSeed(), false, "SEED_NO_HUD after closing again")
        return "open{" .. tostring(scratch.openWait) .. "} closed{" .. closedWait .. "}"
    end)
    return "unsupported_setup"
end

-- unsupported_apis_never_used: with Isaac.GetScreenWidth, Isaac.GetScreenHeight and (when
-- reachable) Game:GetHUD replaced by recording stubs, the lifecycle runs error-free and
-- identically with REPENTANCE absent and set, and real update and render frames with the
-- menu open and closed call none of them.
steps.unsupported_setup = function()
    scratch = {}
    installStubs()
    scratch.stubbed = #stubs.installed
    setRepentance(nil)
    scratch.plain = { pcall(lifecyclePass) }
    setRepentance(true)
    scratch.flagged = { pcall(lifecyclePass) }
    scratch.open = { pcall(function()
        local hud = baseline()
        hud.OpenMenu()
        truthy(hasSeed(), "SEED_NO_HUD absent after open")
    end) }
    return "unsupported_open_frames"
end

steps.unsupported_open_frames = function()
    if not waitedEnough() then
        if stageFrames >= STEP_BUDGET then
            return abandon("unsupported_apis_never_used",
                "frames with the menu open did not arrive: " .. waitDetail(), "room_open")
        end
        return nil
    end
    scratch.openWait = waitDetail()
    scratch.close = { pcall(function()
        api().CloseMenu()
        equal(hasSeed(), false, "SEED_NO_HUD after close")
    end) }
    return "unsupported_closed_frames"
end

steps.unsupported_closed_frames = function()
    if not waitedEnough() then
        if stageFrames >= STEP_BUDGET then
            return abandon("unsupported_apis_never_used",
                "frames with the menu closed did not arrive: " .. waitDetail(), "room_open")
        end
        return nil
    end
    local closedWait = waitDetail()
    local calls = table.concat(stubs.calls, ",")
    local callCount = #stubs.calls
    restoreGlobals()
    run("unsupported_apis_never_used", function()
        truthy(scratch.plain[1], "lifecycle without REPENTANCE raised: "
            .. tostring(scratch.plain[2]))
        truthy(scratch.flagged[1], "lifecycle with REPENTANCE=true raised: "
            .. tostring(scratch.flagged[2]))
        sameTokens(scratch.flagged[2], scratch.plain[2], "lifecycle with REPENTANCE=true")
        truthy(scratch.open[1], "open under the stubs raised: " .. tostring(scratch.open[2]))
        truthy(scratch.close[1], "close under the stubs raised: " .. tostring(scratch.close[2]))
        equal(callCount, 0, "unsupported API calls [" .. calls .. "]")
        return "stubs=" .. tostring(scratch.stubbed) .. " open{" .. tostring(scratch.openWait)
            .. "} closed{" .. closedWait .. "}"
    end)
    return "room_open"
end

-- seed_restored_after_room_change: across real update and render frames the open menu
-- keeps its effect and ownership, and closing restores SEED_NO_HUD to its state before
-- opening, both when this mod added it and when another source had.
steps.room_open = function()
    scratch = {}
    local ok, err = pcall(function()
        local hud = baseline()
        hud.OpenMenu()
        checkMenu(hud.Snapshot(), true, true, false, "open while absent")
        truthy(hasSeed(), "SEED_NO_HUD absent after open")
        scratch.owned = fingerprint(hud)
    end)
    if not ok then
        return abandon("seed_restored_after_room_change", err, "done")
    end
    return "room_owned_frames"
end

steps.room_owned_frames = function()
    if not waitedEnough() then
        if stageFrames >= STEP_BUDGET then
            return abandon("seed_restored_after_room_change",
                "frames with an owned effect did not arrive: " .. waitDetail(), "done")
        end
        return nil
    end
    scratch.ownedWait = waitDetail()
    local ok, err = pcall(function()
        local hud = api()
        sameTokens(fingerprint(hud), scratch.owned, "owned effect across frames")
        hud.CloseMenu()
        checkMenu(hud.Snapshot(), false, false, nil, "close owned")
        equal(hasSeed(), false, "owned SEED_NO_HUD after close")
        forceSeed(true)
        hud.OpenMenu()
        checkMenu(hud.Snapshot(), true, false, true, "open while present")
        scratch.shared = fingerprint(hud)
    end)
    if not ok then
        return abandon("seed_restored_after_room_change", err, "done")
    end
    return "room_shared_frames"
end

steps.room_shared_frames = function()
    if not waitedEnough() then
        if stageFrames >= STEP_BUDGET then
            return abandon("seed_restored_after_room_change",
                "frames with a preexisting effect did not arrive: " .. waitDetail(), "done")
        end
        return nil
    end
    local sharedWait = waitDetail()
    run("seed_restored_after_room_change", function()
        local hud = api()
        sameTokens(fingerprint(hud), scratch.shared, "preexisting effect across frames")
        hud.CloseMenu()
        checkMenu(hud.Snapshot(), false, false, nil, "close preexisting")
        truthy(hasSeed(), "preexisting SEED_NO_HUD removed by close")
        return "owned{" .. tostring(scratch.ownedWait) .. "} preexisting{" .. sharedWait .. "}"
    end)
    return "done"
end

local function stepFrames()
    local step = steps[stage]
    if step == nil then
        finish()
        return
    end
    stageFrames = stageFrames + 1
    local nextStage = step()
    if nextStage ~= nil then
        enterStage(nextStage)
        if steps[nextStage] == nil then
            finish()
        end
    end
end

suite:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, function()
    if started then
        return
    end
    log("[GCB_RUNTIME] suite_started")
    started = true
    updateFrames = 0
end)

suite:AddCallback(ModCallbacks.MC_POST_RENDER, function()
    renderFrames = renderFrames + 1
end)

suite:AddCallback(ModCallbacks.MC_POST_UPDATE, function()
    if finished or not started then
        return
    end
    updateFrames = updateFrames + 1
    if updateFrames == 1 then
        -- Every mod's game-start handler has run by now, whichever order they loaded in.
        local captured, value = pcall(captureStartup)
        startup = captured and value or { error = value }
        local ok, err = pcall(executeSuite)
        if not ok then
            log("[GCB_FATAL] " .. tostring(err))
            finish()
            return
        end
        enterStage("render_open")
        return
    end
    if updateFrames > RUN_BUDGET then
        finish()
        return
    end
    local ok, err = pcall(stepFrames)
    if not ok then
        log("[GCB_FATAL] " .. tostring(err))
        finish()
    end
end)
