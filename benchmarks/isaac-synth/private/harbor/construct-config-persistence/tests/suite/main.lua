local suite = RegisterMod("Construct Config Persistence Verifier", 1)
local game = Game()
local json = require("json")
local passed = 0
local failed = 0
local recorded = {}
local finished = false
-- Update frames observed since the run started; the suite body runs on the first one so
-- that every mod's MC_POST_GAME_STARTED handler has completed whatever the load order.
local updateFrames = 0
local runStarted = false

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
    -- Keep each marker on one line whatever an error message contains.
    local text = string.gsub(tostring(detail or (ok and "ok" or "failed")), "[\r\n]+", " ")
    if #text > 400 then
        text = string.sub(text, 1, 400) .. "..."
    end
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

-- The registered defaults of the public statement.
local function defaults()
    return {
        menu = { dev = false, demo = false, open = false },
        general = { hud = true, hud_offset = 0.0 },
        controls = { menu_key = "F2", reset_key = "F3" },
    }
end

-- Every field differs from its default, with menu.dev enabled.
local function custom()
    return {
        menu = { dev = true, demo = true, open = true },
        general = { hud = false, hud_offset = 6.5 },
        controls = { menu_key = "F7", reset_key = "F8" },
    }
end

-- Every field differs from its default except menu.dev.
local function alternate()
    return {
        menu = { dev = false, demo = true, open = true },
        general = { hud = false, hud_offset = 9 },
        controls = { menu_key = "F9", reset_key = "F10" },
    }
end

-- The defaults with the given category values replaced.
local function expect(changes)
    local result = defaults()
    for category, values in pairs(changes) do
        for key, value in pairs(values) do
            result[category][key] = value
        end
    end
    return result
end

-- A copy of the category tables of a configuration; other entries are not copied.
local function copyConfig(values)
    local result = {}
    for category, section in pairs(values) do
        if type(section) == "table" then
            local copy = {}
            for key, value in pairs(section) do
                copy[key] = value
            end
            result[category] = copy
        end
    end
    return result
end

-- Deterministic JSON text for test payloads: tables with a [1] entry become arrays,
-- other tables objects with sorted keys. Test strings contain no characters to escape.
local function encodeJson(value)
    local kind = type(value)
    if kind == "boolean" or kind == "number" then
        return tostring(value)
    elseif kind == "string" then
        return '"' .. value .. '"'
    elseif kind == "table" then
        local parts = {}
        if value[1] ~= nil then
            for index = 1, #value do
                parts[index] = encodeJson(value[index])
            end
            return "[" .. table.concat(parts, ",") .. "]"
        end
        local keys = {}
        for key in pairs(value) do
            keys[#keys + 1] = key
        end
        table.sort(keys)
        for index, key in ipairs(keys) do
            parts[index] = '"' .. key .. '":' .. encodeJson(value[key])
        end
        return "{" .. table.concat(parts, ",") .. "}"
    end
    error("cannot encode a " .. kind)
end

local function v2Of(values)
    return {
        schema_version = 2,
        menu = values.menu,
        general = values.general,
        controls = values.controls,
    }
end

local FIELDS = {
    { "menu", "dev" },
    { "menu", "demo" },
    { "menu", "open" },
    { "general", "hud" },
    { "general", "hud_offset" },
    { "controls", "menu_key" },
    { "controls", "reset_key" },
}

-- Compares the seven registered fields by type and value.
local function configEquals(actual, expected, label)
    truthy(type(actual) == "table", label .. ": configuration is not a table")
    for _, path in ipairs(FIELDS) do
        local category, key = path[1], path[2]
        local section = actual[category]
        truthy(type(section) == "table", label .. ": " .. category .. " is not a table")
        local value = section[key]
        local wanted = expected[category][key]
        if type(value) ~= type(wanted) or value ~= wanted then
            error(label .. ": " .. category .. "." .. key .. " expected " .. tostring(wanted)
                .. ", received " .. tostring(value))
        end
    end
end

local function api()
    local config = IsaacConstructConfig
    truthy(type(config) == "table", "IsaacConstructConfig is not exported")
    return config
end

local function snap(config)
    local current = config.Snapshot()
    truthy(type(current) == "table", "Snapshot() did not return a table")
    truthy(type(current.config) == "table", "Snapshot().config is not a table")
    return current
end

-- Makes `values` the live configuration through a complete, valid version 2 payload.
local function setLive(config, values)
    config.LoadRaw(true, encodeJson(v2Of(values)))
    configEquals(snap(config).config, values, "setup")
end

local function resetLive(config)
    setLive(config, defaults())
end

local function hudOffset(current)
    truthy(type(current.config.general) == "table", "config.general is not a table")
    return current.config.general.hud_offset
end

local function decodeSaved(raw)
    truthy(type(raw) == "string", "lastSavedRaw is not a string")
    local ok, decoded = pcall(json.decode, raw)
    truthy(ok and type(decoded) == "table", "lastSavedRaw is not a JSON object")
    return decoded
end

local function sortedKeys(value, label)
    truthy(type(value) == "table", label .. " is not a table")
    local keys = {}
    for key in pairs(value) do
        keys[#keys + 1] = tostring(key)
    end
    table.sort(keys)
    return table.concat(keys, ",")
end

-- Overwrites every configuration field reachable from a value a caller holds. Errors
-- from a read-only value are ignored; only the effect on later snapshots matters.
local function scribble(value)
    if type(value) ~= "table" then
        return
    end
    pcall(function()
        local config = value
        if type(value.config) == "table" then
            config = value.config
        end
        for _, path in ipairs(FIELDS) do
            local section = config[path[1]]
            if type(section) == "table" then
                section[path[2]] = "scribbled"
            end
        end
        value.screenOffset = -1
        value.offsetSyncCount = -1
        value.successDiagnosticCount = -1
    end)
end

local function executeSuite()
    run("defaults_without_data", function()
        local config = api()
        -- The first observation of the run: the game-start callback loaded without any
        -- mod data, and the suite has not called the submission yet.
        local atStart = snap(config)
        truthy(type(atStart.offsetSyncCount) == "number" and atStart.offsetSyncCount >= 1,
            "the game-start callback did not load through LoadRaw")
        configEquals(atStart.config, defaults(), "game start without mod data")
        equal(atStart.screenOffset, 0, "game start screen offset")
        setLive(config, custom())
        config.LoadRaw(true, nil, defaults())
        configEquals(snap(config).config, defaults(), "LoadRaw(true, nil)")
        setLive(config, custom())
        config.LoadRaw(nil, nil, defaults())
        configEquals(snap(config).config, defaults(), "LoadRaw(nil, nil)")
        return "start_loads=" .. tostring(atStart.offsetSyncCount)
            .. " frame=" .. tostring(game:GetFrameCount())
    end)

    run("hasdata_false", function()
        local config = api()
        setLive(config, custom())
        config.LoadRaw(false, nil, defaults())
        configEquals(snap(config).config, defaults(), "LoadRaw(false, nil)")
        -- HasData()==false means there is no saved payload, whatever text accompanies it.
        setLive(config, custom())
        config.LoadRaw(false, encodeJson(v2Of(alternate())), defaults())
        configEquals(snap(config).config, defaults(), "LoadRaw(false, payload)")
    end)

    run("empty_payload", function()
        local config = api()
        for _, raw in ipairs({ "", "   " }) do
            setLive(config, custom())
            config.LoadRaw(true, raw, defaults())
            configEquals(snap(config).config, defaults(), "payload '" .. raw .. "'")
        end
    end)

    run("malformed_json", function()
        local config = api()
        for index, raw in ipairs({
            "{bad json",
            '{"schema_version":2,"menu":{"dev":true',
            "[1,2",
            "}{",
        }) do
            setLive(config, custom())
            config.LoadRaw(true, raw, defaults())
            configEquals(snap(config).config, defaults(), "malformed payload " .. tostring(index))
        end
    end)

    run("decoded_boolean", function()
        local config = api()
        for _, raw in ipairs({ "true", "false" }) do
            -- A rejected payload rebuilds from the defaults plus the supplied pre-load
            -- configuration...
            setLive(config, defaults())
            config.LoadRaw(true, raw, alternate())
            configEquals(snap(config).config, alternate(), raw .. " with currentBeforeLoad")
            -- ...or, when none is supplied, the live configuration.
            setLive(config, alternate())
            config.LoadRaw(true, raw)
            configEquals(snap(config).config, alternate(), raw .. " keeps the live configuration")
        end
    end)

    run("decoded_number", function()
        local config = api()
        local rebuilt = expect({
            menu = { open = true },
            general = { hud_offset = 6 },
            controls = { menu_key = "F9" },
        })
        for _, raw in ipairs({ "42", "0", "-7.5" }) do
            -- Defaults replace whatever the pre-load configuration lacks or holds invalid.
            setLive(config, custom())
            config.LoadRaw(true, raw, {
                menu = { dev = "yes", open = true },
                general = { hud_offset = 6 },
                controls = { menu_key = "F9" },
            })
            configEquals(snap(config).config, rebuilt, raw .. " with a partial currentBeforeLoad")
            setLive(config, alternate())
            config.LoadRaw(true, raw)
            configEquals(snap(config).config, alternate(), raw .. " keeps the live configuration")
        end
    end)

    run("decoded_string", function()
        local config = api()
        for _, raw in ipairs({ '"text"', '"{}"', '""' }) do
            setLive(config, custom())
            config.LoadRaw(true, raw, defaults())
            configEquals(snap(config).config, defaults(), raw .. " with default currentBeforeLoad")
            setLive(config, alternate())
            config.LoadRaw(true, raw)
            configEquals(snap(config).config, alternate(), raw .. " keeps the live configuration")
        end
    end)

    run("v2_menu_override", function()
        local config = api()
        resetLive(config)
        for _, menu in ipairs({
            { dev = true, demo = true, open = true },
            { dev = false, demo = true, open = false },
            { dev = false, demo = false, open = true },
        }) do
            local values = expect({ menu = menu })
            config.LoadRaw(true, encodeJson(v2Of(values)))
            configEquals(snap(config).config, values, "menu " .. encodeJson(menu))
        end
    end)

    run("v2_general_override", function()
        local config = api()
        resetLive(config)
        for _, general in ipairs({
            { hud = false, hud_offset = 7.5 },
            { hud = true, hud_offset = 10 },
            { hud = false, hud_offset = 0 },
            { hud = true, hud_offset = 3 },
        }) do
            local values = expect({ general = general })
            config.LoadRaw(true, encodeJson(v2Of(values)))
            configEquals(snap(config).config, values, "general " .. encodeJson(general))
        end
    end)

    run("v2_controls_override", function()
        local config = api()
        resetLive(config)
        for _, controls in ipairs({
            { menu_key = "F5", reset_key = "F6" },
            { menu_key = "F11", reset_key = "F12" },
            { menu_key = "F2", reset_key = "F9" },
        }) do
            local values = expect({ controls = controls })
            config.LoadRaw(true, encodeJson(v2Of(values)))
            configEquals(snap(config).config, values, "controls " .. encodeJson(controls))
        end
    end)

    run("missing_menu_keys_default", function()
        local config = api()
        local kept = custom()
        for _, menu in ipairs({ {}, { dev = true }, { open = true } }) do
            setLive(config, custom())
            config.LoadRaw(true, encodeJson({
                schema_version = 2,
                menu = menu,
                general = kept.general,
                controls = kept.controls,
            }))
            configEquals(snap(config).config,
                expect({ menu = menu, general = kept.general, controls = kept.controls }),
                "menu " .. encodeJson(menu))
        end
    end)

    run("missing_general_keys_default", function()
        local config = api()
        local kept = custom()
        for _, general in ipairs({ {}, { hud = false }, { hud_offset = 4 } }) do
            setLive(config, custom())
            config.LoadRaw(true, encodeJson({
                schema_version = 2,
                menu = kept.menu,
                general = general,
                controls = kept.controls,
            }))
            configEquals(snap(config).config,
                expect({ menu = kept.menu, general = general, controls = kept.controls }),
                "general " .. encodeJson(general))
        end
    end)

    run("missing_controls_keys_default", function()
        local config = api()
        local kept = custom()
        for _, controls in ipairs({ {}, { menu_key = "F5" }, { reset_key = "F6" } }) do
            setLive(config, custom())
            config.LoadRaw(true, encodeJson({
                schema_version = 2,
                menu = kept.menu,
                general = kept.general,
                controls = controls,
            }))
            configEquals(snap(config).config,
                expect({ menu = kept.menu, general = kept.general, controls = controls }),
                "controls " .. encodeJson(controls))
        end
    end)

    run("unknown_keys_ignored", function()
        local config = api()
        resetLive(config)
        config.LoadRaw(true, encodeJson({
            schema_version = 2,
            theme = "dark",
            extra = { nested = true },
            menu = { dev = false, demo = true, open = false, overlay = true },
            general = { hud = false, hud_offset = 2.5, scale = 3 },
            controls = { menu_key = "F5", reset_key = "F6", jump_key = "F9" },
        }))
        local current = snap(config)
        configEquals(current.config, expect({
            menu = { demo = true },
            general = { hud = false, hud_offset = 2.5 },
            controls = { menu_key = "F5", reset_key = "F6" },
        }), "known keys")
        equal(current.config.theme, nil, "unknown top-level key theme")
        equal(current.config.extra, nil, "unknown top-level key extra")
        equal(current.config.menu.overlay, nil, "unknown menu key")
        equal(current.config.general.scale, nil, "unknown general key")
        equal(current.config.controls.jump_key, nil, "unknown controls key")
        config.SaveNow()
        local saved = decodeSaved(snap(config).lastSavedRaw)
        equal(saved.theme, nil, "saved unknown top-level key theme")
        equal(saved.extra, nil, "saved unknown top-level key extra")
        truthy(type(saved.menu) == "table" and type(saved.general) == "table"
            and type(saved.controls) == "table", "saved categories are not objects")
        equal(saved.menu.overlay, nil, "saved unknown menu key")
        equal(saved.general.scale, nil, "saved unknown general key")
        equal(saved.controls.jump_key, nil, "saved unknown controls key")
    end)

    run("invalid_menu_type_default", function()
        local config = api()
        local kept = custom()
        setLive(config, custom())
        config.LoadRaw(true, encodeJson({
            schema_version = 2,
            menu = { dev = "yes", demo = 1, open = {} },
            general = kept.general,
            controls = kept.controls,
        }))
        configEquals(snap(config).config,
            expect({ general = kept.general, controls = kept.controls }), "invalid menu values")
        local other = alternate()
        for _, menu in ipairs({ "broken", 7, false }) do
            resetLive(config)
            config.LoadRaw(true, encodeJson({
                schema_version = 2,
                menu = menu,
                general = other.general,
                controls = other.controls,
            }))
            configEquals(snap(config).config,
                expect({ general = other.general, controls = other.controls }),
                "menu " .. encodeJson(menu))
        end
    end)

    run("invalid_general_type_default", function()
        local config = api()
        local kept = custom()
        for _, general in ipairs({
            { hud = "off", hud_offset = "5" },
            { hud = 0, hud_offset = -1 },
            { hud = {}, hud_offset = 10.5 },
            { hud = "true", hud_offset = true },
        }) do
            setLive(config, custom())
            config.LoadRaw(true, encodeJson({
                schema_version = 2,
                menu = kept.menu,
                general = general,
                controls = kept.controls,
            }))
            configEquals(snap(config).config,
                expect({ menu = kept.menu, controls = kept.controls }),
                "general " .. encodeJson(general))
        end
        -- JSON 1e999 decodes to an infinite offset, which is not a finite number.
        for _, number in ipairs({ "1e999", "-1e999" }) do
            resetLive(config)
            config.LoadRaw(true, '{"schema_version":2,"general":{"hud":true,"hud_offset":'
                .. number .. "}}")
            local current = snap(config)
            equal(hudOffset(current), 0, "hud_offset " .. number)
            equal(current.screenOffset, 0, "screen offset for hud_offset " .. number)
        end
        -- NaN has no JSON form; it reaches the same validation as a pre-load value.
        resetLive(config)
        config.LoadRaw(true, "{bad json", { general = { hud = true, hud_offset = 0 / 0 } })
        local current = snap(config)
        equal(hudOffset(current), 0, "NaN hud_offset")
        equal(current.screenOffset, 0, "screen offset for a NaN hud_offset")
        local other = alternate()
        for _, general in ipairs({ "corrupt", 3, true }) do
            resetLive(config)
            config.LoadRaw(true, encodeJson({
                schema_version = 2,
                menu = other.menu,
                general = general,
                controls = other.controls,
            }))
            configEquals(snap(config).config,
                expect({ menu = other.menu, controls = other.controls }),
                "general " .. encodeJson(general))
        end
    end)

    run("invalid_controls_type_default", function()
        local config = api()
        local kept = custom()
        for _, controls in ipairs({
            { menu_key = 5, reset_key = false },
            { menu_key = {}, reset_key = { "F4" } },
            { menu_key = true, reset_key = 0 },
        }) do
            setLive(config, custom())
            config.LoadRaw(true, encodeJson({
                schema_version = 2,
                menu = kept.menu,
                general = kept.general,
                controls = controls,
            }))
            configEquals(snap(config).config,
                expect({ menu = kept.menu, general = kept.general }),
                "controls " .. encodeJson(controls))
        end
        local other = alternate()
        for _, controls in ipairs({ "F5", 12, false }) do
            resetLive(config)
            config.LoadRaw(true, encodeJson({
                schema_version = 2,
                menu = other.menu,
                general = other.general,
                controls = controls,
            }))
            configEquals(snap(config).config,
                expect({ menu = other.menu, general = other.general }),
                "controls " .. encodeJson(controls))
        end
    end)

    run("partial_section_merge", function()
        local config = api()
        setLive(config, custom())
        config.LoadRaw(true, encodeJson({
            schema_version = 2,
            menu = { open = true },
            general = { hud_offset = 3 },
            controls = { reset_key = "F11" },
        }))
        configEquals(snap(config).config, expect({
            menu = { open = true },
            general = { hud_offset = 3 },
            controls = { reset_key = "F11" },
        }), "first partial payload")
        setLive(config, custom())
        config.LoadRaw(true, encodeJson({
            schema_version = 2,
            menu = { dev = false, demo = true },
            general = { hud = false },
            controls = { menu_key = "F12" },
        }))
        configEquals(snap(config).config, expect({
            menu = { demo = true },
            general = { hud = false },
            controls = { menu_key = "F12" },
        }), "complementary partial payload")
    end)

    run("valid_section_survives_bad_section", function()
        local config = api()
        local other = alternate()
        resetLive(config)
        config.LoadRaw(true, encodeJson({
            schema_version = 2,
            menu = other.menu,
            general = "corrupt",
            controls = other.controls,
        }))
        configEquals(snap(config).config,
            expect({ menu = other.menu, controls = other.controls }), "malformed general")
        resetLive(config)
        config.LoadRaw(true, encodeJson({
            schema_version = 2,
            menu = 42,
            general = other.general,
        }))
        configEquals(snap(config).config, expect({ general = other.general }),
            "malformed menu and absent controls")
        resetLive(config)
        config.LoadRaw(true, encodeJson({
            schema_version = 2,
            menu = { dev = "x", demo = "y", open = "z" },
            general = other.general,
            controls = { "F1" },
        }))
        configEquals(snap(config).config, expect({ general = other.general }),
            "invalid menu values and array controls")
    end)

    run("full_round_trip", function()
        local config = api()
        resetLive(config)
        config.LoadRaw(true, encodeJson(v2Of(custom())))
        configEquals(snap(config).config, custom(), "loaded payload")
        config.SaveNow()
        local first = snap(config)
        local raw = first.lastSavedRaw
        truthy(type(raw) == "string" and raw ~= "", "SaveNow did not record lastSavedRaw")
        -- Duplicate lifecycle delivery changes neither the payload nor the live settings.
        config.SaveNow()
        local second = snap(config)
        equal(second.lastSavedRaw, raw, "payload of a duplicate save")
        configEquals(second.config, custom(), "live settings after a duplicate save")
        equal(second.screenOffset, first.screenOffset, "screen offset after a duplicate save")
        -- The saved payload restores the same configuration over the defaults.
        resetLive(config)
        config.LoadRaw(true, raw)
        configEquals(snap(config).config, custom(), "reloaded payload")
        config.SaveNow()
        configEquals(decodeSaved(snap(config).lastSavedRaw), custom(), "payload saved after reload")
        configEquals(decodeSaved(raw), custom(), "first saved payload")
    end)

    run("unknown_schema_defaults", function()
        local config = api()
        local other = custom()
        for _, version in ipairs({ 3, 99, 0 }) do
            local raw = encodeJson({
                schema_version = version,
                dev = true,
                demo = true,
                open = true,
                menu = other.menu,
                general = other.general,
                controls = other.controls,
            })
            setLive(config, alternate())
            config.LoadRaw(true, raw, defaults())
            configEquals(snap(config).config, defaults(),
                "schema_version " .. tostring(version) .. " with default currentBeforeLoad")
            resetLive(config)
            config.LoadRaw(true, raw)
            configEquals(snap(config).config, defaults(),
                "schema_version " .. tostring(version) .. " over the default live configuration")
        end
    end)

    run("next_save_is_v2", function()
        local config = api()
        setLive(config, alternate())
        config.LoadRaw(true, '{"schema_version":1,"dev":true,"demo":false,"open":true}')
        config.SaveNow()
        local saved = decodeSaved(snap(config).lastSavedRaw)
        equal(sortedKeys(saved, "saved payload"), "controls,general,menu,schema_version",
            "saved top-level keys")
        equal(saved.schema_version, 2, "saved schema_version")
        configEquals(saved, expect({ menu = { dev = true, open = true } }), "saved values")
        equal(sortedKeys(saved.menu, "saved menu"), "demo,dev,open", "saved menu keys")
        equal(sortedKeys(saved.general, "saved general"), "hud,hud_offset", "saved general keys")
        equal(sortedKeys(saved.controls, "saved controls"), "menu_key,reset_key",
            "saved controls keys")
    end)

    run("flat_v1_dev_migrates", function()
        local config = api()
        setLive(config, alternate())
        config.LoadRaw(true, '{"schema_version":1,"dev":true,"demo":false,"open":false}')
        configEquals(snap(config).config, expect({ menu = { dev = true } }), "legacy dev")
        setLive(config, alternate())
        config.LoadRaw(true, '{"schema_version":1,"dev":true,"demo":true,"open":false}')
        configEquals(snap(config).config, expect({ menu = { dev = true, demo = true } }),
            "legacy dev and demo")
        resetLive(config)
        config.LoadRaw(true, '{"schema_version":1,"dev":"yes","demo":false,"open":false}')
        configEquals(snap(config).config, defaults(), "legacy dev of an invalid type")
    end)

    run("flat_v1_demo_migrates", function()
        local config = api()
        local live = expect({
            menu = { dev = true, open = true },
            general = { hud = false, hud_offset = 5 },
            controls = { menu_key = "F11", reset_key = "F12" },
        })
        setLive(config, live)
        config.LoadRaw(true, '{"schema_version":1,"dev":false,"demo":true,"open":false}')
        configEquals(snap(config).config, expect({ menu = { demo = true } }), "legacy demo")
        setLive(config, live)
        config.LoadRaw(true, '{"schema_version":1,"dev":false,"demo":true,"open":true}')
        configEquals(snap(config).config, expect({ menu = { demo = true, open = true } }),
            "legacy demo and open")
    end)

    run("flat_v1_open_migrates", function()
        local config = api()
        local live = expect({
            menu = { dev = true, demo = true },
            general = { hud = false, hud_offset = 5 },
            controls = { menu_key = "F11", reset_key = "F12" },
        })
        setLive(config, live)
        config.LoadRaw(true, '{"schema_version":1,"dev":false,"demo":false,"open":true}')
        configEquals(snap(config).config, expect({ menu = { open = true } }), "legacy open")
        setLive(config, live)
        config.LoadRaw(true, '{"schema_version":1,"dev":true,"demo":false,"open":true}')
        configEquals(snap(config).config, expect({ menu = { dev = true, open = true } }),
            "legacy dev and open")
    end)

    run("nested_v2_not_misread_as_legacy", function()
        local config = api()
        -- Flat legacy-looking keys beside the categories are unknown version 2 keys.
        resetLive(config)
        config.LoadRaw(true, encodeJson({
            schema_version = 2,
            dev = true,
            demo = true,
            open = true,
            menu = { dev = false, demo = false, open = false },
            general = { hud = false, hud_offset = 2.5 },
            controls = { menu_key = "F4", reset_key = "F5" },
        }))
        configEquals(snap(config).config, expect({
            general = { hud = false, hud_offset = 2.5 },
            controls = { menu_key = "F4", reset_key = "F5" },
        }), "nested categories beside flat keys")
        -- Version 2 without a menu category keeps its other categories.
        resetLive(config)
        config.LoadRaw(true, encodeJson({
            schema_version = 2,
            general = { hud = false, hud_offset = 1.5 },
            controls = { menu_key = "F6", reset_key = "F7" },
        }))
        configEquals(snap(config).config, expect({
            general = { hud = false, hud_offset = 1.5 },
            controls = { menu_key = "F6", reset_key = "F7" },
        }), "version 2 without menu")
        -- The nested save written after a migration reloads as version 2, to the state
        -- that was saved.
        config.LoadRaw(true, '{"schema_version":1,"dev":false,"demo":true,"open":false}')
        local migrated = copyConfig(snap(config).config)
        config.SaveNow()
        local raw = snap(config).lastSavedRaw
        setLive(config, alternate())
        config.LoadRaw(true, raw)
        configEquals(snap(config).config, migrated, "saved migration reloaded")
    end)

    run("migration_is_idempotent", function()
        local config = api()
        local legacy = '{"schema_version":1,"dev":true,"demo":true,"open":false}'
        local migrated = expect({ menu = { dev = true, demo = true } })
        setLive(config, alternate())
        config.LoadRaw(true, legacy)
        configEquals(snap(config).config, migrated, "first migration")
        config.LoadRaw(true, legacy)
        configEquals(snap(config).config, migrated, "second migration")
        config.SaveNow()
        local firstRaw = snap(config).lastSavedRaw
        config.LoadRaw(true, firstRaw)
        configEquals(snap(config).config, migrated, "reload of the migrated save")
        config.SaveNow()
        local secondRaw = snap(config).lastSavedRaw
        local first = decodeSaved(firstRaw)
        local second = decodeSaved(secondRaw)
        equal(first.schema_version, 2, "first saved schema_version")
        equal(second.schema_version, 2, "second saved schema_version")
        configEquals(first, migrated, "first saved values")
        configEquals(second, migrated, "second saved values")
    end)

    run("offset_synced_after_valid_load", function()
        local config = api()
        resetLive(config)
        for _, offset in ipairs({ 7.5, 2, 10, 0, 4.25 }) do
            local before = snap(config)
            config.LoadRaw(true, encodeJson(v2Of(expect({ general = { hud_offset = offset } }))))
            local after = snap(config)
            equal(hudOffset(after), offset, "normalized hud_offset")
            equal(after.screenOffset, offset, "screen offset")
            equal(after.offsetSyncCount, before.offsetSyncCount + 1, "offset synchronizations")
        end
        -- The helper follows the normalized value, not the saved one.
        local before = snap(config)
        config.LoadRaw(true, encodeJson(v2Of(expect({ general = { hud_offset = 12 } }))))
        local after = snap(config)
        equal(hudOffset(after), 0, "normalized out-of-range hud_offset")
        equal(after.screenOffset, 0, "screen offset after an out-of-range hud_offset")
        equal(after.offsetSyncCount, before.offsetSyncCount + 1, "offset synchronizations")
    end)

    run("offset_synced_after_bad_json", function()
        local config = api()
        setLive(config, expect({ general = { hud_offset = 4 } }))
        local before = snap(config)
        config.LoadRaw(true, "{bad json", defaults())
        local after = snap(config)
        equal(hudOffset(after), 0, "normalized hud_offset")
        equal(after.screenOffset, 0, "screen offset")
        equal(after.offsetSyncCount, before.offsetSyncCount + 1, "offset synchronizations")
        setLive(config, expect({ general = { hud_offset = 4 } }))
        before = snap(config)
        config.LoadRaw(true, '{"schema_version":2,"general":{"hud_offset":8')
        after = snap(config)
        equal(after.screenOffset, hudOffset(after), "screen offset without currentBeforeLoad")
        equal(after.offsetSyncCount, before.offsetSyncCount + 1,
            "offset synchronizations without currentBeforeLoad")
    end)

    run("offset_synced_after_boolean", function()
        local config = api()
        for _, raw in ipairs({ "true", "false" }) do
            setLive(config, expect({ general = { hud_offset = 4 } }))
            local before = snap(config)
            config.LoadRaw(true, raw, defaults())
            local after = snap(config)
            equal(hudOffset(after), 0, raw .. " normalized hud_offset")
            equal(after.screenOffset, 0, raw .. " screen offset")
            equal(after.offsetSyncCount, before.offsetSyncCount + 1, raw .. " offset synchronizations")
            setLive(config, expect({ general = { hud_offset = 4 } }))
            before = snap(config)
            config.LoadRaw(true, raw, { general = { hud_offset = 9 } })
            after = snap(config)
            equal(after.screenOffset, hudOffset(after), raw .. " screen offset with a live offset")
            equal(after.offsetSyncCount, before.offsetSyncCount + 1,
                raw .. " offset synchronizations with a live offset")
        end
    end)

    run("offset_synced_when_absent", function()
        local config = api()
        local absent = {
            { "LoadRaw(false, nil)", false },
            { "LoadRaw(true, nil)", true },
            { "LoadRaw(nil, nil)", nil },
        }
        for _, call in ipairs(absent) do
            setLive(config, expect({ general = { hud_offset = 4 } }))
            local before = snap(config)
            config.LoadRaw(call[2], nil, defaults())
            local after = snap(config)
            equal(hudOffset(after), 0, call[1] .. " normalized hud_offset")
            equal(after.screenOffset, 0, call[1] .. " screen offset")
            equal(after.offsetSyncCount, before.offsetSyncCount + 1,
                call[1] .. " offset synchronizations")
            setLive(config, expect({ general = { hud_offset = 4 } }))
            before = snap(config)
            config.LoadRaw(call[2], nil)
            after = snap(config)
            equal(after.screenOffset, hudOffset(after),
                call[1] .. " screen offset without currentBeforeLoad")
            equal(after.offsetSyncCount, before.offsetSyncCount + 1,
                call[1] .. " offset synchronizations without currentBeforeLoad")
        end
    end)

    run("exactly_one_offset_sync_per_call", function()
        local config = api()
        resetLive(config)
        local valid = encodeJson(v2Of(expect({ general = { hud_offset = 5 } })))
        local calls = {
            { "valid version 2", true, valid },
            { "legacy version 1", true, '{"schema_version":1,"dev":false,"demo":true,"open":false}' },
            { "HasData false", false, nil },
            { "no data", true, nil },
            { "empty text", true, "" },
            { "decode error", true, "{bad json" },
            { "decoded boolean", true, "true" },
            { "decoded number", true, "42" },
            { "decoded string", true, '"text"' },
            { "non-table category", true,
                '{"schema_version":2,"menu":"broken","general":{"hud":true,"hud_offset":1.5}}' },
            { "unknown schema", true, '{"schema_version":7}' },
            { "repeated valid version 2", true, valid },
            { "repeated valid version 2 again", true, valid },
        }
        local count = snap(config).offsetSyncCount
        for _, call in ipairs(calls) do
            config.LoadRaw(call[2], call[3])
            local current = snap(config)
            equal(current.offsetSyncCount, count + 1, call[1] .. " offset synchronizations")
            equal(current.screenOffset, hudOffset(current), call[1] .. " screen offset")
            count = current.offsetSyncCount
        end
    end)

    run("debug_only_after_valid_dev_load", function()
        local config = api()
        resetLive(config)
        local base = snap(config).successDiagnosticCount
        truthy(type(base) == "number", "successDiagnosticCount is not a number")
        local development = expect({ menu = { dev = true }, general = { hud_offset = 2.5 } })
        config.LoadRaw(true, encodeJson(v2Of(development)))
        local current = snap(config)
        equal(current.successDiagnosticCount, base + 1, "diagnostics after a merged menu.dev payload")
        configEquals(current.config, development, "configuration after the diagnostic")
        equal(current.screenOffset, 2.5, "screen offset after the diagnostic")
        config.LoadRaw(true, encodeJson(v2Of(expect({ menu = { demo = true } }))))
        equal(snap(config).successDiagnosticCount, base + 1, "diagnostics with menu.dev false")
        config.LoadRaw(true, encodeJson({
            schema_version = 2,
            menu = { dev = "true" },
            general = { hud = true, hud_offset = 0 },
        }))
        equal(snap(config).successDiagnosticCount, base + 1, "diagnostics with an invalid menu.dev")
        config.LoadRaw(true, encodeJson(v2Of(development)))
        equal(snap(config).successDiagnosticCount, base + 2,
            "diagnostics after a second merged menu.dev payload")
    end)

    run("no_debug_after_rejected_load", function()
        local config = api()
        local development = expect({ menu = { dev = true } })
        setLive(config, development)
        local base = snap(config).successDiagnosticCount
        truthy(type(base) == "number", "successDiagnosticCount is not a number")
        local rejected = {
            { "HasData false", false, nil },
            { "no data", true, nil },
            { "empty text", true, "" },
            { "decode error", true, '{"schema_version":2,"menu":{"dev":true' },
            { "decoded boolean", true, "true" },
            { "decoded number", true, "1" },
            { "decoded string", true, '"dev"' },
            { "unknown schema", true, encodeJson({ schema_version = 5, menu = { dev = true } }) },
        }
        for _, call in ipairs(rejected) do
            config.LoadRaw(call[2], call[3], copyConfig(development))
            equal(snap(config).successDiagnosticCount, base,
                call[1] .. " with a menu.dev pre-load configuration")
            config.LoadRaw(call[2], call[3])
            equal(snap(config).successDiagnosticCount, base,
                call[1] .. " after a menu.dev live configuration")
        end
    end)

    run("repeated_load_has_same_normalized_state", function()
        local config = api()
        local loads = {
            { "full version 2", true, encodeJson(v2Of(custom())) },
            { "partial version 2", true, encodeJson({
                schema_version = 2,
                menu = { open = true },
                general = { hud_offset = 3 },
            }) },
            { "legacy version 1", true, '{"schema_version":1,"dev":false,"demo":true,"open":true}' },
            { "invalid values", true, encodeJson({
                schema_version = 2,
                menu = { dev = 1 },
                general = { hud_offset = 11 },
                controls = { menu_key = false },
            }) },
            { "rejected with currentBeforeLoad", true, "{bad json", alternate },
            { "unknown schema", true, '{"schema_version":9}' },
        }
        for _, entry in ipairs(loads) do
            local label, hasData, raw, live = entry[1], entry[2], entry[3], entry[4]
            resetLive(config)
            local supplied = live and live() or nil
            local returned = config.LoadRaw(hasData, raw, supplied)
            local first = snap(config)
            local expected = copyConfig(first.config)
            local expectedOffset = first.screenOffset
            -- Nothing a caller holds may alias the internal state.
            scribble(returned)
            scribble(supplied)
            scribble(first)
            scribble(config.Snapshot())
            configEquals(snap(config).config, expected, label .. " after caller mutation")
            config.LoadRaw(hasData, raw, live and live() or nil)
            local second = snap(config)
            configEquals(second.config, expected, label .. " repeated load")
            equal(second.screenOffset, expectedOffset, label .. " repeated screen offset")
            scribble(config.SaveNow())
            configEquals(snap(config).config, expected, label .. " after mutating a save result")
        end
    end)

    -- Leave the defaults live and saved, so the submission's mod data ends in the state
    -- a run without mod data starts from.
    pcall(function()
        local config = IsaacConstructConfig
        if type(config) == "table" then
            config.LoadRaw(true, encodeJson(v2Of(defaults())))
            config.SaveNow()
        end
    end)
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

suite:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, function()
    log("[GCB_RUNTIME] suite_started")
    updateFrames = 0
    finished = false
    runStarted = true
end)

suite:AddCallback(ModCallbacks.MC_POST_UPDATE, function()
    if finished or not runStarted then
        return
    end
    updateFrames = updateFrames + 1
    if updateFrames == 1 then
        -- Every mod's game-start handler has run by now, whichever order they loaded in.
        -- All cases are synchronous calls of the public API, so the suite ends this frame.
        local ok, err = pcall(executeSuite)
        if not ok then
            log("[GCB_FATAL] " .. tostring(err))
        end
        finish()
    end
end)
