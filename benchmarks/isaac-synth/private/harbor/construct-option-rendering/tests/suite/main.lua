local suite = RegisterMod("Construct Option Rendering Verifier", 1)
local game = Game()
local json = require("json")

local EPSILON = 1e-6
local ACTIVE_ALPHA = 1.0
local INACTIVE_ALPHA = 0.4
-- An asynchronous case is checked once this many real MC_POST_RENDER passes have
-- completed after its setup, and fails if they do not happen within the frame budget.
local RENDER_PASSES = 2
local RENDER_WAIT_FRAMES = 90

-- Dyadic components are exact in the engine's single-precision KColor fields.
local NORMAL_RGB = { 0.25, 0.5, 0.75 }
local CUSTOM_A = { 0.875, 0.125, 0.375 }
local CUSTOM_B = { 0.0625, 0.9375, 0.5 }
local CUSTOM_C = { 0.375, 0.75, 0.125 }

local EXPECTED_CASES = {
    "default_color_unchanged", "valid_rgb_replaces_rgb", "alpha_accessor_is_used",
    "focused_selectable_alpha", "unfocused_pane_alpha", "disabled_option_alpha",
    "selected_disabled_alpha", "text_draw_no_error", "slider_draw_no_error",
    "text_and_slider_share_custom_rgb", "non_slider_has_no_sprite_mutation",
    "option_position_unchanged", "cursor_position_unchanged", "strikeout_unchanged",
    "color_follows_option_identity", "row_reorder_keeps_color",
    "removed_option_drops_color", "palette_update_visible_next_frame",
    "clear_restores_text_rgb", "clear_restores_alpha", "clear_restores_slider_color",
    "invalid_rgb_rejected_atomically", "partial_rgb_rejected", "nan_rgb_rejected",
    "infinity_rgb_rejected", "last_valid_color_survives_rejection",
    "custom_color_not_saved", "option_value_not_changed_by_color", "color_state_not_shared",
    "between_categories", "repeated_render_is_idempotent",
    "custom_color_does_not_abort_callback", "normal_color_accessor_missing_fallback",
    "alpha_never_nil", "inactive_slider_alpha",
}

local passed = 0
local failed = 0
local recorded = {}
local finished = false
local started = false
-- Update frames since the run started; the synchronous cases run on the first one so
-- that every mod's MC_POST_GAME_STARTED handler has completed whatever the load order.
local updateFrames = 0
-- Real render passes observed by this mod's MC_POST_RENDER handler.
local renderFrames = 0
local knownIds = {}
local asyncSteps = {}
local asyncIndex = 0
local activeStep = nil

local function log(text)
    Isaac.DebugString(text)
end

local function oneLine(value)
    return (tostring(value):gsub("[\r\n]+", " "))
end

local function describe(value)
    local ok, text = pcall(json.encode, value)
    if ok and type(text) == "string" then
        return text
    end
    return tostring(value)
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

local function near(actual, expected, label)
    if type(actual) ~= "number"
        or actual ~= actual
        or math.abs(actual - expected) > EPSILON then
        error(label .. ": expected " .. tostring(expected)
            .. ", received " .. tostring(actual), 0)
    end
end

local function flag(value)
    return value and true or false
end

local function record(name, ok, detail)
    if recorded[name] then
        return
    end
    recorded[name] = true
    if ok then
        passed = passed + 1
        log("[GCB_CASE] PASS " .. name .. " " .. oneLine(detail or "ok"))
    else
        failed = failed + 1
        log("[GCB_CASE] FAIL " .. name .. " " .. oneLine(detail or "failed"))
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
    for _, name in ipairs(EXPECTED_CASES) do
        if not recorded[name] then
            record(name, false, "case did not run")
        end
    end
    log("[GCB_SUMMARY] passed=" .. tostring(passed)
        .. " failed=" .. tostring(failed)
        .. " total=" .. tostring(passed + failed))
end

local function rgb(color)
    return { color[1], color[2], color[3] }
end

local function api()
    local exported = IsaacConstructPalette
    truthy(type(exported) == "table", "IsaacConstructPalette is not exported")
    return exported
end

local function snapshot()
    local current = api().Snapshot()
    truthy(type(current) == "table", "Snapshot did not return a table")
    truthy(type(current.palette) == "table", "Snapshot.palette is missing")
    truthy(type(current.lastRender) == "table", "Snapshot.lastRender is missing")
    truthy(type(current.renderErrorCount) == "number", "Snapshot.renderErrorCount is missing")
    return current
end

local function renderNow()
    api().RenderNow()
    return snapshot()
end

local function normalText()
    return KColor(NORMAL_RGB[1], NORMAL_RGB[2], NORMAL_RGB[3], 1)
end

local function mockText(alpha)
    return { Red = NORMAL_RGB[1], Green = NORMAL_RGB[2], Blue = NORMAL_RGB[3], Alpha = alpha }
end

local function normalSlider()
    return { R = 0.5, G = 0.625, B = 0.75, A = 0.75, RO = 16, GO = 0, BO = 32 }
end

local function renderState(fields)
    local result = {
        selectable = true,
        selected = false,
        focused = true,
        x = 96,
        y = 64,
    }
    for key, value in pairs(fields or {}) do
        result[key] = value
    end
    if result.normalTextColor == nil then
        result.normalTextColor = normalText()
    end
    return result
end

local function upsert(id, kind, value, fields)
    knownIds[id] = true
    local result = renderState(fields)
    api().UpsertOption(id, kind, value, result)
    return result
end

local function remove(id)
    knownIds[id] = nil
    api().RemoveOption(id)
end

local function setColor(id, color)
    truthy(api().SetOptionColor(id, color) ~= false,
        "SetOptionColor rejected a valid color for " .. id)
end

local function clearColor(id)
    api().ClearOptionColor(id)
end

-- A rejected update may return false/nil or raise; it must not report success.
local function rejectColor(id, color, label)
    local setter = api().SetOptionColor
    local ok, result = pcall(setter, id, color)
    truthy(not ok or result ~= true, label .. " was accepted for " .. id)
end

local function setOrder(ids)
    api().SetOptionOrder(ids)
end

local function setContext(context)
    api().SetRenderContext(context)
end

-- Removes every option earlier cases created (through the public API only) and restores
-- the default menu context, so each case observes only its own stable ids.
local function resetOptions()
    local exported = api()
    for id in pairs(knownIds) do
        pcall(exported.RemoveOption, id)
    end
    knownIds = {}
    exported.SetRenderContext({ category = "general" })
end

local function findIntent(current, id)
    local found = nil
    for _, intent in ipairs(current.lastRender) do
        if type(intent) == "table" and intent.id == id then
            truthy(found == nil, "duplicate render intent for " .. id)
            found = intent
        end
    end
    return found
end

local function intentFor(current, id)
    local found = findIntent(current, id)
    truthy(found, "no render intent for " .. id)
    return found
end

local function orderOf(current, prefix)
    local ids = {}
    for _, intent in ipairs(current.lastRender) do
        if type(intent) == "table"
            and type(intent.id) == "string"
            and intent.id:sub(1, #prefix) == prefix then
            ids[#ids + 1] = intent.id
        end
    end
    return ids
end

local function sequenceEquals(actual, expected, label)
    equal(#actual, #expected, label .. " length")
    for index, value in ipairs(expected) do
        equal(actual[index], value, label .. "[" .. tostring(index) .. "]")
    end
end

local function expectText(intent, color, alpha, label)
    local text = intent.text
    truthy(type(text) == "table", label .. ": text color missing")
    near(text.red, color[1], label .. " text.red")
    near(text.green, color[2], label .. " text.green")
    near(text.blue, color[3], label .. " text.blue")
    near(text.alpha, alpha, label .. " text.alpha")
end

local function expectSlider(intent, rgba, offsets, label)
    local slider = intent.slider
    truthy(type(slider) == "table", label .. ": slider color missing")
    near(slider.red, rgba[1], label .. " slider.red")
    near(slider.green, rgba[2], label .. " slider.green")
    near(slider.blue, rgba[3], label .. " slider.blue")
    near(slider.alpha, rgba[4], label .. " slider.alpha")
    near(slider.ro, offsets[1], label .. " slider.ro")
    near(slider.go, offsets[2], label .. " slider.go")
    near(slider.bo, offsets[3], label .. " slider.bo")
end

local function expectCustomSlider(intent, color, alpha, label)
    expectSlider(intent, { color[1], color[2], color[3], alpha }, { 0, 0, 0 }, label)
end

local function expectNormalSlider(intent, label)
    local normal = normalSlider()
    expectSlider(intent, { normal.R, normal.G, normal.B, normal.A },
        { normal.RO, normal.GO, normal.BO }, label)
end

local function expectPalette(current, id, color, label)
    local entry = current.palette[id]
    truthy(type(entry) == "table", label .. ": palette entry missing")
    near(entry.red, color[1], label .. " palette.red")
    near(entry.green, color[2], label .. " palette.green")
    near(entry.blue, color[3], label .. " palette.blue")
end

local function expectNoPalette(current, id, label)
    local entry = current.palette[id]
    if entry ~= nil then
        error(label .. ": unexpected palette entry " .. describe(entry), 0)
    end
end

local function expectFlags(intent, focused, selected, disabled, label)
    equal(flag(intent.focused), focused, label .. " focused flag")
    equal(flag(intent.selected), selected, label .. " selected flag")
    equal(flag(intent.disabled), disabled, label .. " disabled flag")
end

-- The caller-owned normal text color must never be written by the renderer.
local function expectNormalTextUnchanged(color, label)
    near(color.Red, NORMAL_RGB[1], label .. " Red")
    near(color.Green, NORMAL_RGB[2], label .. " Green")
    near(color.Blue, NORMAL_RGB[3], label .. " Blue")
    near(color.Alpha, 1, label .. " Alpha")
end

local function expectNormalSliderUnchanged(color, label)
    local normal = normalSlider()
    for _, key in ipairs({ "R", "G", "B", "A", "RO", "GO", "BO" }) do
        equal(color[key], normal[key], label .. " " .. key)
    end
end

-- Position, cursor, strikeout, and pane flags of one render intent.
local function sameLayout(actual, expected, label)
    equal(actual.id, expected.id, label .. " id")
    equal(actual.x, expected.x, label .. " x")
    equal(actual.y, expected.y, label .. " y")
    equal(actual.cursorX, expected.cursorX, label .. " cursorX")
    equal(actual.cursorY, expected.cursorY, label .. " cursorY")
    equal(flag(actual.strikeout), flag(expected.strikeout), label .. " strikeout")
    equal(flag(actual.focused), flag(expected.focused), label .. " focused")
    equal(flag(actual.selected), flag(expected.selected), label .. " selected")
    equal(flag(actual.disabled), flag(expected.disabled), label .. " disabled")
end

local function sameIntent(actual, expected, label)
    sameLayout(actual, expected, label)
    truthy(type(actual.text) == "table" and type(expected.text) == "table",
        label .. ": text color missing")
    for _, key in ipairs({ "red", "green", "blue", "alpha" }) do
        equal(actual.text[key], expected.text[key], label .. " text." .. key)
    end
    equal(type(actual.slider), type(expected.slider), label .. " slider presence")
    if type(expected.slider) == "table" then
        for _, key in ipairs({ "red", "green", "blue", "alpha", "ro", "go", "bo" }) do
            equal(actual.slider[key], expected.slider[key], label .. " slider." .. key)
        end
    end
end

local function expectRenderNowSucceeds(label)
    local renderer = api().RenderNow
    local ok, err = pcall(renderer)
    truthy(ok, label .. ": RenderNow raised " .. tostring(err))
    return snapshot()
end

local function countingConstructor(original, counts, name)
    return setmetatable({}, {
        __call = function(_, ...)
            counts[name] = counts[name] + 1
            return original(...)
        end,
        __index = original,
    })
end

-- Counts Font() and Sprite() constructions made while fn runs.
local function withConstructorAudit(fn)
    local counts = { Font = 0, Sprite = 0 }
    local originalFont, originalSprite = Font, Sprite
    Font = countingConstructor(originalFont, counts, "Font")
    Sprite = countingConstructor(originalSprite, counts, "Sprite")
    local ok, err = pcall(fn)
    Font, Sprite = originalFont, originalSprite
    if not ok then
        error(err, 0)
    end
    return counts
end

-- Counts mod-data writes (Mod:SaveData goes through Isaac.SaveModData) while fn runs.
local function withSaveAudit(fn)
    local original = Isaac.SaveModData
    truthy(type(original) == "function", "Isaac.SaveModData is unavailable")
    local writes = 0
    Isaac.SaveModData = function(...)
        writes = writes + 1
        return original(...)
    end
    local ok, err = pcall(fn)
    Isaac.SaveModData = original
    if not ok then
        error(err, 0)
    end
    return writes
end

asyncSteps = {
    {
        name = "palette_update_visible_next_frame",
        setup = function(context)
            resetOptions()
            upsert("next.text", "text", "Text", { y = 40 })
            upsert("next.slider", "slider", 0.5, { normalSliderColor = normalSlider(), y = 56 })
            -- A warm-up render lets a lazy renderer create its font and sprites once.
            renderNow()
            local counts = withConstructorAudit(function()
                setColor("next.text", rgb(CUSTOM_A))
                setColor("next.slider", rgb(CUSTOM_A))
                local current = renderNow()
                expectText(intentFor(current, "next.text"), CUSTOM_A, ACTIVE_ALPHA,
                    "RenderNow after update")
                expectCustomSlider(intentFor(current, "next.slider"), CUSTOM_A, ACTIVE_ALPHA,
                    "RenderNow after update")
            end)
            equal(counts.Font, 0, "Font constructions during a palette update")
            equal(counts.Sprite, 0, "Sprite constructions during a palette update")
            -- Only the real MC_POST_RENDER callback can show this second update.
            setColor("next.text", rgb(CUSTOM_B))
            setColor("next.slider", rgb(CUSTOM_B))
            context.errors = snapshot().renderErrorCount
        end,
        check = function(context)
            run("palette_update_visible_next_frame", function()
                local real = snapshot()
                expectText(intentFor(real, "next.text"), CUSTOM_B, ACTIVE_ALPHA,
                    "next MC_POST_RENDER")
                expectCustomSlider(intentFor(real, "next.slider"), CUSTOM_B, ACTIVE_ALPHA,
                    "next MC_POST_RENDER")
                equal(real.renderErrorCount, context.errors, "render errors")
                local direct = renderNow()
                sameIntent(intentFor(direct, "next.text"), intentFor(real, "next.text"),
                    "RenderNow and MC_POST_RENDER text")
                sameIntent(intentFor(direct, "next.slider"), intentFor(real, "next.slider"),
                    "RenderNow and MC_POST_RENDER slider")
                return "frame=" .. tostring(game:GetFrameCount())
            end)
        end,
    },
    {
        name = "custom_color_does_not_abort_callback",
        setup = function(context)
            resetOptions()
            upsert("abort.text", "text", "Text", { y = 40 })
            upsert("abort.mock", "boolean", false, { normalTextColor = mockText(nil), y = 56 })
            upsert("abort.slider", "slider", 0.5, { y = 72 })
            upsert("abort.locked", "slider", 0.25, {
                selectable = false,
                normalSliderColor = normalSlider(),
                y = 88,
            })
            upsert("abort.idle", "text", "Idle", { focused = false, y = 104 })
            setColor("abort.text", rgb(CUSTOM_A))
            setColor("abort.mock", rgb(CUSTOM_B))
            setColor("abort.slider", rgb(CUSTOM_C))
            setColor("abort.locked", rgb(CUSTOM_A))
            setColor("abort.idle", rgb(CUSTOM_B))
            expectRenderNowSucceeds("colored options")
            context.errors = snapshot().renderErrorCount
            -- Added after the last direct render: only the real callback can draw it.
            upsert("abort.probe", "text", "Probe", { y = 120 })
        end,
        check = function(context)
            run("custom_color_does_not_abort_callback", function()
                local real = snapshot()
                equal(real.renderErrorCount, context.errors, "render errors in MC_POST_RENDER")
                equal(#orderOf(real, "abort."), 6, "options drawn by MC_POST_RENDER")
                expectText(intentFor(real, "abort.text"), CUSTOM_A, ACTIVE_ALPHA, "abort.text")
                expectText(intentFor(real, "abort.mock"), CUSTOM_B, ACTIVE_ALPHA, "abort.mock")
                expectText(intentFor(real, "abort.slider"), CUSTOM_C, ACTIVE_ALPHA, "abort.slider")
                expectCustomSlider(intentFor(real, "abort.slider"), CUSTOM_C, ACTIVE_ALPHA,
                    "abort.slider")
                expectText(intentFor(real, "abort.locked"), CUSTOM_A, INACTIVE_ALPHA,
                    "abort.locked")
                expectCustomSlider(intentFor(real, "abort.locked"), CUSTOM_A, INACTIVE_ALPHA,
                    "abort.locked")
                expectText(intentFor(real, "abort.idle"), CUSTOM_B, INACTIVE_ALPHA, "abort.idle")
                expectText(intentFor(real, "abort.probe"), NORMAL_RGB, ACTIVE_ALPHA,
                    "abort.probe")
                return "frame=" .. tostring(game:GetFrameCount())
            end)
        end,
    },
}

local function beginStep()
    while asyncIndex < #asyncSteps do
        asyncIndex = asyncIndex + 1
        local step = asyncSteps[asyncIndex]
        local context = {}
        local ok, err = pcall(step.setup, context)
        if ok then
            activeStep = {
                step = step,
                context = context,
                renderMark = renderFrames,
                frameMark = updateFrames,
            }
            return true
        end
        record(step.name, false, "setup: " .. tostring(err))
    end
    activeStep = nil
    return false
end

-- One asynchronous step per update frame: check it after the required real render
-- passes, or fail it when the frame budget runs out; then set up the next one.
local function advanceAsync()
    local current = activeStep
    if current ~= nil then
        if renderFrames - current.renderMark >= RENDER_PASSES then
            activeStep = nil
            current.step.check(current.context)
        elseif updateFrames - current.frameMark >= RENDER_WAIT_FRAMES then
            activeStep = nil
            record(current.step.name, false, "no " .. tostring(RENDER_PASSES)
                .. " real MC_POST_RENDER passes within " .. tostring(RENDER_WAIT_FRAMES)
                .. " update frames")
        else
            return
        end
    end
    if not beginStep() then
        finish()
    end
end

local function executeSuite()
    run("default_color_unchanged", function()
        resetOptions()
        local shared = normalText()
        local sharedSlider = normalSlider()
        upsert("def.text", "text", "Label", { normalTextColor = shared, y = 40 })
        upsert("def.bool", "boolean", true, { normalTextColor = shared, y = 56 })
        upsert("def.slider", "slider", 0.5, {
            normalTextColor = shared,
            normalSliderColor = sharedSlider,
            y = 72,
        })
        upsert("def.peer", "text", "Peer", { y = 88 })
        local before = renderNow()
        setColor("def.peer", rgb(CUSTOM_A))
        local after = renderNow()
        for _, id in ipairs({ "def.text", "def.bool", "def.slider" }) do
            local intent = intentFor(after, id)
            expectText(intent, NORMAL_RGB, ACTIVE_ALPHA, id)
            expectNoPalette(after, id, id)
            sameIntent(intent, intentFor(before, id), id .. " after a peer color")
        end
        expectNormalSlider(intentFor(after, "def.slider"), "def.slider")
        expectText(intentFor(after, "def.peer"), CUSTOM_A, ACTIVE_ALPHA, "def.peer")
        expectNormalTextUnchanged(shared, "shared normal KColor")
        expectNormalSliderUnchanged(sharedSlider, "shared normal slider color")
    end)

    run("valid_rgb_replaces_rgb", function()
        resetOptions()
        upsert("rgb.text", "text", "Label", { y = 40 })
        upsert("rgb.bool", "boolean", false, { y = 56 })
        local before = renderNow()
        setColor("rgb.text", rgb(CUSTOM_A))
        setColor("rgb.bool", { 0, 1, 0 })
        local after = renderNow()
        local text = intentFor(after, "rgb.text")
        expectText(text, CUSTOM_A, ACTIVE_ALPHA, "rgb.text")
        expectPalette(after, "rgb.text", CUSTOM_A, "rgb.text")
        sameLayout(text, intentFor(before, "rgb.text"), "rgb.text")
        expectText(intentFor(after, "rgb.bool"), { 0, 1, 0 }, ACTIVE_ALPHA, "lower bound")
        expectPalette(after, "rgb.bool", { 0, 1, 0 }, "lower bound")
        setColor("rgb.bool", { 1, 1, 1 })
        expectText(intentFor(renderNow(), "rgb.bool"), { 1, 1, 1 }, ACTIVE_ALPHA, "upper bound")
    end)

    run("alpha_accessor_is_used", function()
        resetOptions()
        local errors = snapshot().renderErrorCount
        -- A Color-style A field on a mock must be ignored in favor of KColor Alpha.
        local function conflicting()
            local color = mockText(1)
            color.A = 0.25
            return color
        end
        upsert("acc.real", "text", "Real", { normalTextColor = normalText(), y = 40 })
        upsert("acc.mock", "text", "Mock", { normalTextColor = conflicting(), y = 56 })
        upsert("acc.slider", "slider", 0.5, {
            normalTextColor = conflicting(),
            normalSliderColor = normalSlider(),
            y = 72,
        })
        upsert("acc.idle", "text", "Idle", {
            normalTextColor = conflicting(),
            focused = false,
            y = 88,
        })
        local normal = renderNow()
        expectText(intentFor(normal, "acc.real"), NORMAL_RGB, ACTIVE_ALPHA, "real KColor")
        expectText(intentFor(normal, "acc.mock"), NORMAL_RGB, ACTIVE_ALPHA, "mock KColor")
        expectText(intentFor(normal, "acc.slider"), NORMAL_RGB, ACTIVE_ALPHA, "slider text")
        expectText(intentFor(normal, "acc.idle"), NORMAL_RGB, INACTIVE_ALPHA, "unfocused mock")
        for _, id in ipairs({ "acc.real", "acc.mock", "acc.slider", "acc.idle" }) do
            setColor(id, rgb(CUSTOM_B))
        end
        local custom = renderNow()
        expectText(intentFor(custom, "acc.real"), CUSTOM_B, ACTIVE_ALPHA, "custom real KColor")
        expectText(intentFor(custom, "acc.mock"), CUSTOM_B, ACTIVE_ALPHA, "custom mock KColor")
        expectText(intentFor(custom, "acc.slider"), CUSTOM_B, ACTIVE_ALPHA, "custom slider text")
        expectCustomSlider(intentFor(custom, "acc.slider"), CUSTOM_B, ACTIVE_ALPHA,
            "custom slider")
        expectText(intentFor(custom, "acc.idle"), CUSTOM_B, INACTIVE_ALPHA, "custom unfocused")
        equal(custom.renderErrorCount, errors, "render errors")
    end)

    run("focused_selectable_alpha", function()
        resetOptions()
        upsert("fs.plain", "text", "Plain", { y = 40 })
        upsert("fs.cursor", "boolean", true, { selected = true, y = 56 })
        upsert("fs.slider", "slider", 0.25, {
            selected = true,
            normalSliderColor = normalSlider(),
            y = 72,
        })
        local normal = renderNow()
        expectText(intentFor(normal, "fs.plain"), NORMAL_RGB, ACTIVE_ALPHA, "unselected")
        expectText(intentFor(normal, "fs.cursor"), NORMAL_RGB, ACTIVE_ALPHA, "selected")
        expectText(intentFor(normal, "fs.slider"), NORMAL_RGB, ACTIVE_ALPHA, "slider")
        expectFlags(intentFor(normal, "fs.plain"), true, false, false, "unselected")
        expectFlags(intentFor(normal, "fs.cursor"), true, true, false, "selected")
        for _, id in ipairs({ "fs.plain", "fs.cursor", "fs.slider" }) do
            setColor(id, rgb(CUSTOM_C))
        end
        local custom = renderNow()
        expectText(intentFor(custom, "fs.plain"), CUSTOM_C, ACTIVE_ALPHA, "custom unselected")
        expectText(intentFor(custom, "fs.cursor"), CUSTOM_C, ACTIVE_ALPHA, "custom selected")
        expectText(intentFor(custom, "fs.slider"), CUSTOM_C, ACTIVE_ALPHA, "custom slider text")
        expectCustomSlider(intentFor(custom, "fs.slider"), CUSTOM_C, ACTIVE_ALPHA,
            "custom slider")
    end)

    run("unfocused_pane_alpha", function()
        resetOptions()
        upsert("uf.plain", "text", "Plain", { focused = false, y = 40 })
        upsert("uf.cursor", "boolean", false, { focused = false, selected = true, y = 56 })
        local normal = renderNow()
        expectText(intentFor(normal, "uf.plain"), NORMAL_RGB, INACTIVE_ALPHA, "unselected")
        expectText(intentFor(normal, "uf.cursor"), NORMAL_RGB, INACTIVE_ALPHA, "selected")
        expectFlags(intentFor(normal, "uf.plain"), false, false, false, "unselected")
        expectFlags(intentFor(normal, "uf.cursor"), false, true, false, "selected")
        setColor("uf.plain", rgb(CUSTOM_A))
        setColor("uf.cursor", rgb(CUSTOM_B))
        local custom = renderNow()
        expectText(intentFor(custom, "uf.plain"), CUSTOM_A, INACTIVE_ALPHA, "custom unselected")
        expectText(intentFor(custom, "uf.cursor"), CUSTOM_B, INACTIVE_ALPHA, "custom selected")
    end)

    run("disabled_option_alpha", function()
        resetOptions()
        upsert("dis.focused", "text", "Locked", { selectable = false, y = 40 })
        upsert("dis.unfocused", "boolean", true, { selectable = false, focused = false, y = 56 })
        local normal = renderNow()
        expectText(intentFor(normal, "dis.focused"), NORMAL_RGB, INACTIVE_ALPHA, "focused pane")
        expectText(intentFor(normal, "dis.unfocused"), NORMAL_RGB, INACTIVE_ALPHA,
            "unfocused pane")
        expectFlags(intentFor(normal, "dis.focused"), true, false, true, "focused pane")
        expectFlags(intentFor(normal, "dis.unfocused"), false, false, true, "unfocused pane")
        setColor("dis.focused", rgb(CUSTOM_C))
        setColor("dis.unfocused", rgb(CUSTOM_A))
        local custom = renderNow()
        expectText(intentFor(custom, "dis.focused"), CUSTOM_C, INACTIVE_ALPHA,
            "custom focused pane")
        expectText(intentFor(custom, "dis.unfocused"), CUSTOM_A, INACTIVE_ALPHA,
            "custom unfocused pane")
    end)

    run("selected_disabled_alpha", function()
        resetOptions()
        upsert("sd.text", "text", "Locked", { selectable = false, selected = true, y = 40 })
        upsert("sd.slider", "slider", 0.75, {
            selectable = false,
            selected = true,
            normalSliderColor = normalSlider(),
            y = 56,
        })
        local normal = renderNow()
        expectText(intentFor(normal, "sd.text"), NORMAL_RGB, INACTIVE_ALPHA, "selected text")
        expectText(intentFor(normal, "sd.slider"), NORMAL_RGB, INACTIVE_ALPHA, "selected slider")
        expectFlags(intentFor(normal, "sd.text"), true, true, true, "selected text")
        setColor("sd.text", rgb(CUSTOM_B))
        setColor("sd.slider", rgb(CUSTOM_C))
        local custom = renderNow()
        expectText(intentFor(custom, "sd.text"), CUSTOM_B, INACTIVE_ALPHA, "custom text")
        expectText(intentFor(custom, "sd.slider"), CUSTOM_C, INACTIVE_ALPHA, "custom slider text")
        expectCustomSlider(intentFor(custom, "sd.slider"), CUSTOM_C, INACTIVE_ALPHA,
            "custom slider")
    end)

    run("text_draw_no_error", function()
        resetOptions()
        local errors = snapshot().renderErrorCount
        upsert("tdraw.text", "text", "Text", { y = 40 })
        upsert("tdraw.bool", "boolean", false, { normalTextColor = mockText(nil), y = 56 })
        upsert("tdraw.idle", "text", "Idle", { focused = false, selected = true, y = 72 })
        setColor("tdraw.text", rgb(CUSTOM_A))
        setColor("tdraw.bool", rgb(CUSTOM_B))
        setColor("tdraw.idle", rgb(CUSTOM_C))
        local current = expectRenderNowSucceeds("custom text")
        equal(current.renderErrorCount, errors, "render errors")
        expectText(intentFor(current, "tdraw.text"), CUSTOM_A, ACTIVE_ALPHA, "tdraw.text")
        expectText(intentFor(current, "tdraw.bool"), CUSTOM_B, ACTIVE_ALPHA, "tdraw.bool")
        expectText(intentFor(current, "tdraw.idle"), CUSTOM_C, INACTIVE_ALPHA, "tdraw.idle")
    end)

    run("slider_draw_no_error", function()
        resetOptions()
        local errors = snapshot().renderErrorCount
        upsert("sdraw.normal", "slider", 0.5, { normalSliderColor = normalSlider(), y = 40 })
        upsert("sdraw.bare", "slider", 0.5, { y = 56 })
        for _, color in ipairs({ CUSTOM_A, CUSTOM_B, CUSTOM_C }) do
            setColor("sdraw.normal", rgb(color))
            setColor("sdraw.bare", rgb(color))
            local custom = expectRenderNowSucceeds("custom slider")
            expectCustomSlider(intentFor(custom, "sdraw.normal"), color, ACTIVE_ALPHA,
                "sdraw.normal")
            expectCustomSlider(intentFor(custom, "sdraw.bare"), color, ACTIVE_ALPHA,
                "sdraw.bare")
            clearColor("sdraw.normal")
            local cleared = expectRenderNowSucceeds("cleared slider")
            expectNormalSlider(intentFor(cleared, "sdraw.normal"), "cleared sdraw.normal")
        end
        equal(snapshot().renderErrorCount, errors, "render errors")
    end)

    run("text_and_slider_share_custom_rgb", function()
        resetOptions()
        upsert("share.active", "slider", 0.5, { normalSliderColor = normalSlider(), y = 40 })
        upsert("share.idle", "slider", 0.5, {
            normalSliderColor = normalSlider(),
            focused = false,
            y = 56,
        })
        setColor("share.active", rgb(CUSTOM_C))
        setColor("share.idle", rgb(CUSTOM_C))
        local current = renderNow()
        for _, entry in ipairs({
            { id = "share.active", alpha = ACTIVE_ALPHA },
            { id = "share.idle", alpha = INACTIVE_ALPHA },
        }) do
            local intent = intentFor(current, entry.id)
            expectText(intent, CUSTOM_C, entry.alpha, entry.id)
            expectCustomSlider(intent, CUSTOM_C, entry.alpha, entry.id)
            equal(intent.slider.red, intent.text.red, entry.id .. " shared red")
            equal(intent.slider.green, intent.text.green, entry.id .. " shared green")
            equal(intent.slider.blue, intent.text.blue, entry.id .. " shared blue")
            equal(intent.slider.alpha, intent.text.alpha, entry.id .. " shared alpha")
        end
    end)

    run("non_slider_has_no_sprite_mutation", function()
        resetOptions()
        local sharedSlider = normalSlider()
        upsert("nsm.text", "text", "Text", { normalSliderColor = sharedSlider, y = 40 })
        upsert("nsm.bool", "boolean", true, { normalSliderColor = sharedSlider, y = 56 })
        upsert("nsm.slider", "slider", 0.5, { normalSliderColor = sharedSlider, y = 72 })
        local before = renderNow()
        truthy(intentFor(before, "nsm.text").slider == nil, "text option has a slider color")
        setColor("nsm.text", rgb(CUSTOM_A))
        setColor("nsm.bool", rgb(CUSTOM_B))
        local after = renderNow()
        truthy(intentFor(after, "nsm.text").slider == nil, "custom text option changed a slider")
        truthy(intentFor(after, "nsm.bool").slider == nil,
            "custom boolean option changed a slider")
        expectText(intentFor(after, "nsm.text"), CUSTOM_A, ACTIVE_ALPHA, "nsm.text")
        expectText(intentFor(after, "nsm.bool"), CUSTOM_B, ACTIVE_ALPHA, "nsm.bool")
        sameIntent(intentFor(after, "nsm.slider"), intentFor(before, "nsm.slider"),
            "uncolored slider")
        expectNormalSlider(intentFor(after, "nsm.slider"), "uncolored slider")
        expectNormalSliderUnchanged(sharedSlider, "shared normal slider color")
    end)

    run("option_position_unchanged", function()
        resetOptions()
        local options = {
            { id = "pos.text", kind = "text", value = "Text", fields = { x = 100, y = 37 } },
            { id = "pos.bool", kind = "boolean", value = false,
                fields = { x = 48, y = 53, selected = true } },
            { id = "pos.slider", kind = "slider", value = 0.5,
                fields = { x = 132, y = 69, focused = false,
                    normalSliderColor = normalSlider() } },
        }
        for _, option in ipairs(options) do
            upsert(option.id, option.kind, option.value, option.fields)
        end
        local before = renderNow()
        for index, option in ipairs(options) do
            setColor(option.id, rgb(({ CUSTOM_A, CUSTOM_B, CUSTOM_C })[index]))
        end
        local after = renderNow()
        for _, option in ipairs(options) do
            local intent = intentFor(after, option.id)
            equal(intent.x, option.fields.x, option.id .. " x")
            equal(intent.y, option.fields.y, option.id .. " y")
            equal(intentFor(before, option.id).x, option.fields.x, option.id .. " normal x")
            equal(intentFor(before, option.id).y, option.fields.y, option.id .. " normal y")
        end
    end)

    run("cursor_position_unchanged", function()
        resetOptions()
        upsert("cur.selected", "text", "Selected", { selected = true, x = 90, y = 40 })
        upsert("cur.idle", "boolean", true, { selected = true, focused = false, x = 90, y = 56 })
        upsert("cur.plain", "slider", 0.5, { x = 90, y = 72, normalSliderColor = normalSlider() })
        local before = renderNow()
        local selected = intentFor(before, "cur.selected")
        truthy(type(selected.cursorX) == "number" and type(selected.cursorY) == "number",
            "selected option has no cursorX/cursorY")
        setColor("cur.selected", rgb(CUSTOM_A))
        setColor("cur.idle", rgb(CUSTOM_B))
        setColor("cur.plain", rgb(CUSTOM_C))
        local after = renderNow()
        for _, id in ipairs({ "cur.selected", "cur.idle", "cur.plain" }) do
            equal(intentFor(after, id).cursorX, intentFor(before, id).cursorX, id .. " cursorX")
            equal(intentFor(after, id).cursorY, intentFor(before, id).cursorY, id .. " cursorY")
        end
    end)

    run("strikeout_unchanged", function()
        resetOptions()
        local ids = { "strike.off", "strike.on", "strike.text", "strike.locked" }
        upsert("strike.off", "boolean", false, { y = 40 })
        upsert("strike.on", "boolean", true, { y = 56 })
        upsert("strike.text", "text", "Text", { y = 72 })
        upsert("strike.locked", "boolean", false, { selectable = false, y = 88 })
        local before = renderNow()
        for index, id in ipairs(ids) do
            setColor(id, rgb(({ CUSTOM_A, CUSTOM_B, CUSTOM_C, CUSTOM_A })[index]))
        end
        local colored = renderNow()
        for _, id in ipairs(ids) do
            clearColor(id)
        end
        local cleared = renderNow()
        for _, id in ipairs(ids) do
            equal(type(intentFor(before, id).strikeout), "boolean", id .. " strikeout flag type")
            local expected = flag(intentFor(before, id).strikeout)
            equal(flag(intentFor(colored, id).strikeout), expected, id .. " colored strikeout")
            equal(flag(intentFor(cleared, id).strikeout), expected, id .. " cleared strikeout")
        end
    end)

    run("color_follows_option_identity", function()
        resetOptions()
        upsert("ident.a", "text", "A", { y = 40 })
        upsert("ident.b", "text", "B", { y = 56 })
        upsert("ident.c", "text", "C", { y = 72 })
        setColor("ident.b", rgb(CUSTOM_A))
        -- ident.b moves to a new row and ident.a takes the row ident.b left.
        upsert("ident.b", "text", "B", { y = 88, selected = true })
        upsert("ident.a", "text", "A", { y = 56 })
        local moved = renderNow()
        expectText(intentFor(moved, "ident.b"), CUSTOM_A, ACTIVE_ALPHA, "moved option")
        equal(intentFor(moved, "ident.b").y, 88, "moved option row")
        expectText(intentFor(moved, "ident.a"), NORMAL_RGB, ACTIVE_ALPHA, "option in the old row")
        expectText(intentFor(moved, "ident.c"), NORMAL_RGB, ACTIVE_ALPHA, "untouched option")
        expectPalette(moved, "ident.b", CUSTOM_A, "moved option")
        expectNoPalette(moved, "ident.a", "option in the old row")
        setColor("ident.c", rgb(CUSTOM_B))
        local second = renderNow()
        expectText(intentFor(second, "ident.c"), CUSTOM_B, ACTIVE_ALPHA, "second custom color")
        expectText(intentFor(second, "ident.b"), CUSTOM_A, ACTIVE_ALPHA, "first custom color")
        expectText(intentFor(second, "ident.a"), NORMAL_RGB, ACTIVE_ALPHA, "uncolored option")
    end)

    run("row_reorder_keeps_color", function()
        resetOptions()
        upsert("row.a", "text", "A", { y = 40 })
        upsert("row.b", "text", "B", { y = 56 })
        upsert("row.c", "text", "C", { y = 72 })
        setColor("row.a", rgb(CUSTOM_A))
        setOrder({ "row.c", "row.a", "row.b" })
        upsert("row.c", "text", "C", { y = 40 })
        upsert("row.a", "text", "A", { y = 56 })
        upsert("row.b", "text", "B", { y = 72 })
        local first = renderNow()
        sequenceEquals(orderOf(first, "row."), { "row.c", "row.a", "row.b" }, "first order")
        expectText(intentFor(first, "row.a"), CUSTOM_A, ACTIVE_ALPHA, "row.a in row 2")
        expectText(intentFor(first, "row.c"), NORMAL_RGB, ACTIVE_ALPHA, "row.c in row 1")
        expectText(intentFor(first, "row.b"), NORMAL_RGB, ACTIVE_ALPHA, "row.b in row 3")
        setOrder({ "row.b", "row.c", "row.a" })
        upsert("row.b", "text", "B", { y = 40 })
        upsert("row.c", "text", "C", { y = 56 })
        upsert("row.a", "text", "A", { y = 72 })
        local second = renderNow()
        sequenceEquals(orderOf(second, "row."), { "row.b", "row.c", "row.a" }, "second order")
        expectText(intentFor(second, "row.a"), CUSTOM_A, ACTIVE_ALPHA, "row.a in row 3")
        expectText(intentFor(second, "row.b"), NORMAL_RGB, ACTIVE_ALPHA, "row.b in row 1")
        expectText(intentFor(second, "row.c"), NORMAL_RGB, ACTIVE_ALPHA, "row.c in row 2")
        expectPalette(second, "row.a", CUSTOM_A, "row.a")
    end)

    run("removed_option_drops_color", function()
        resetOptions()
        upsert("rm.a", "text", "A", { y = 40 })
        upsert("rm.b", "slider", 0.5, { normalSliderColor = normalSlider(), y = 56 })
        setColor("rm.a", rgb(CUSTOM_A))
        setColor("rm.b", rgb(CUSTOM_B))
        remove("rm.a")
        local removed = renderNow()
        expectNoPalette(removed, "rm.a", "removed option")
        truthy(findIntent(removed, "rm.a") == nil, "removed option was rendered")
        expectText(intentFor(removed, "rm.b"), CUSTOM_B, ACTIVE_ALPHA, "remaining option")
        expectPalette(removed, "rm.b", CUSTOM_B, "remaining option")
        upsert("rm.a", "text", "A", { y = 40 })
        local restored = renderNow()
        expectText(intentFor(restored, "rm.a"), NORMAL_RGB, ACTIVE_ALPHA, "re-added option")
        expectNoPalette(restored, "rm.a", "re-added option")
        remove("rm.b")
        upsert("rm.b", "slider", 0.5, { normalSliderColor = normalSlider(), y = 56 })
        local slider = renderNow()
        expectText(intentFor(slider, "rm.b"), NORMAL_RGB, ACTIVE_ALPHA, "re-added slider")
        expectNormalSlider(intentFor(slider, "rm.b"), "re-added slider")
        expectNoPalette(slider, "rm.b", "re-added slider")
    end)

    run("clear_restores_text_rgb", function()
        resetOptions()
        upsert("ctext.text", "text", "Text", { y = 40 })
        upsert("ctext.bool", "boolean", false, { selected = true, y = 56 })
        local before = renderNow()
        setColor("ctext.text", rgb(CUSTOM_A))
        setColor("ctext.bool", rgb(CUSTOM_B))
        local colored = renderNow()
        expectText(intentFor(colored, "ctext.text"), CUSTOM_A, ACTIVE_ALPHA, "colored text")
        expectText(intentFor(colored, "ctext.bool"), CUSTOM_B, ACTIVE_ALPHA, "colored boolean")
        clearColor("ctext.text")
        clearColor("ctext.bool")
        local cleared = renderNow()
        for _, id in ipairs({ "ctext.text", "ctext.bool" }) do
            expectText(intentFor(cleared, id), NORMAL_RGB, ACTIVE_ALPHA, id)
            sameIntent(intentFor(cleared, id), intentFor(before, id), id .. " after clear")
            expectNoPalette(cleared, id, id)
        end
    end)

    run("clear_restores_alpha", function()
        resetOptions()
        local options = {
            { id = "calpha.active", kind = "text", value = "Active", alpha = ACTIVE_ALPHA,
                fields = { y = 40 } },
            { id = "calpha.idle", kind = "text", value = "Idle", alpha = INACTIVE_ALPHA,
                fields = { focused = false, y = 56 } },
            { id = "calpha.locked", kind = "boolean", value = true, alpha = INACTIVE_ALPHA,
                fields = { selectable = false, selected = true, y = 72 } },
            { id = "calpha.mock", kind = "text", value = "Mock", alpha = ACTIVE_ALPHA,
                fields = { normalTextColor = mockText(nil), y = 88 } },
        }
        for _, option in ipairs(options) do
            upsert(option.id, option.kind, option.value, option.fields)
        end
        local before = renderNow()
        for _, option in ipairs(options) do
            setColor(option.id, rgb(CUSTOM_C))
        end
        local colored = renderNow()
        for _, option in ipairs(options) do
            clearColor(option.id)
        end
        local cleared = renderNow()
        for _, option in ipairs(options) do
            expectText(intentFor(before, option.id), NORMAL_RGB, option.alpha,
                option.id .. " normal")
            expectText(intentFor(colored, option.id), CUSTOM_C, option.alpha,
                option.id .. " colored")
            expectText(intentFor(cleared, option.id), NORMAL_RGB, option.alpha,
                option.id .. " cleared")
            sameIntent(intentFor(cleared, option.id), intentFor(before, option.id),
                option.id .. " after clear")
        end
    end)

    run("clear_restores_slider_color", function()
        resetOptions()
        local other = { R = 1, G = 0.5, B = 0.25, A = 1, RO = 0, GO = 8, BO = 0 }
        upsert("cslider.a", "slider", 0.5, { normalSliderColor = normalSlider(), y = 40 })
        upsert("cslider.b", "slider", 0.25, { normalSliderColor = other, y = 56 })
        local before = renderNow()
        expectNormalSlider(intentFor(before, "cslider.a"), "normal cslider.a")
        expectSlider(intentFor(before, "cslider.b"), { 1, 0.5, 0.25, 1 }, { 0, 8, 0 },
            "normal cslider.b")
        setColor("cslider.a", rgb(CUSTOM_A))
        setColor("cslider.b", rgb(CUSTOM_B))
        local colored = renderNow()
        expectCustomSlider(intentFor(colored, "cslider.a"), CUSTOM_A, ACTIVE_ALPHA,
            "colored cslider.a")
        expectCustomSlider(intentFor(colored, "cslider.b"), CUSTOM_B, ACTIVE_ALPHA,
            "colored cslider.b")
        clearColor("cslider.a")
        clearColor("cslider.b")
        local cleared = renderNow()
        expectNormalSlider(intentFor(cleared, "cslider.a"), "cleared cslider.a")
        expectSlider(intentFor(cleared, "cslider.b"), { 1, 0.5, 0.25, 1 }, { 0, 8, 0 },
            "cleared cslider.b")
        for _, id in ipairs({ "cslider.a", "cslider.b" }) do
            sameIntent(intentFor(cleared, id), intentFor(before, id), id .. " after clear")
        end
    end)

    run("invalid_rgb_rejected_atomically", function()
        resetOptions()
        upsert("inv.text", "text", "Text", { y = 40 })
        upsert("inv.slider", "slider", 0.5, { normalSliderColor = normalSlider(), y = 56 })
        setColor("inv.text", rgb(CUSTOM_A))
        setColor("inv.slider", rgb(CUSTOM_A))
        local attempts = {
            { label = "red above range", value = { 1.5, 0.25, 0.25 } },
            { label = "green below range", value = { 0.25, -0.25, 0.25 } },
            { label = "blue above range", value = { 0.25, 0.25, 1.25 } },
            { label = "boolean component", value = { 0.25, true, 0.25 } },
            { label = "string color", value = "red" },
            { label = "number color", value = 0.5 },
        }
        for _, attempt in ipairs(attempts) do
            rejectColor("inv.text", attempt.value, attempt.label)
            rejectColor("inv.slider", attempt.value, attempt.label)
            local current = renderNow()
            expectPalette(current, "inv.text", CUSTOM_A, attempt.label)
            expectText(intentFor(current, "inv.text"), CUSTOM_A, ACTIVE_ALPHA, attempt.label)
            expectCustomSlider(intentFor(current, "inv.slider"), CUSTOM_A, ACTIVE_ALPHA,
                attempt.label)
        end
    end)

    run("partial_rgb_rejected", function()
        resetOptions()
        upsert("part.colored", "text", "Colored", { y = 40 })
        upsert("part.plain", "text", "Plain", { y = 56 })
        setColor("part.colored", rgb(CUSTOM_B))
        local attempts = {
            { label = "two components", value = { 0.25, 0.5 } },
            { label = "missing green", value = { 0.25, nil, 0.5 } },
            { label = "missing red and green", value = { nil, nil, 0.5 } },
            { label = "empty table", value = {} },
            { label = "nil color", value = nil },
        }
        for _, attempt in ipairs(attempts) do
            rejectColor("part.colored", attempt.value, attempt.label)
            rejectColor("part.plain", attempt.value, attempt.label)
            local current = renderNow()
            expectPalette(current, "part.colored", CUSTOM_B, attempt.label)
            expectText(intentFor(current, "part.colored"), CUSTOM_B, ACTIVE_ALPHA, attempt.label)
            expectNoPalette(current, "part.plain", attempt.label)
            expectText(intentFor(current, "part.plain"), NORMAL_RGB, ACTIVE_ALPHA, attempt.label)
        end
    end)

    run("nan_rgb_rejected", function()
        resetOptions()
        local nan = 0 / 0
        upsert("nan.colored", "text", "Colored", { y = 40 })
        upsert("nan.plain", "text", "Plain", { y = 56 })
        setColor("nan.colored", rgb(CUSTOM_C))
        for index = 1, 3 do
            local value = { 0.5, 0.5, 0.5 }
            value[index] = nan
            local label = "NaN component " .. tostring(index)
            rejectColor("nan.colored", value, label)
            rejectColor("nan.plain", value, label)
            local current = renderNow()
            expectPalette(current, "nan.colored", CUSTOM_C, label)
            expectText(intentFor(current, "nan.colored"), CUSTOM_C, ACTIVE_ALPHA, label)
            expectNoPalette(current, "nan.plain", label)
            expectText(intentFor(current, "nan.plain"), NORMAL_RGB, ACTIVE_ALPHA, label)
        end
    end)

    run("infinity_rgb_rejected", function()
        resetOptions()
        upsert("inf.colored", "text", "Colored", { y = 40 })
        upsert("inf.plain", "text", "Plain", { y = 56 })
        setColor("inf.colored", rgb(CUSTOM_A))
        local attempts = {
            { label = "+inf red", value = { math.huge, 0.5, 0.5 } },
            { label = "-inf green", value = { 0.5, -math.huge, 0.5 } },
            { label = "+inf blue", value = { 0.5, 0.5, math.huge } },
        }
        for _, attempt in ipairs(attempts) do
            rejectColor("inf.colored", attempt.value, attempt.label)
            rejectColor("inf.plain", attempt.value, attempt.label)
            local current = renderNow()
            expectPalette(current, "inf.colored", CUSTOM_A, attempt.label)
            expectText(intentFor(current, "inf.colored"), CUSTOM_A, ACTIVE_ALPHA, attempt.label)
            expectNoPalette(current, "inf.plain", attempt.label)
            expectText(intentFor(current, "inf.plain"), NORMAL_RGB, ACTIVE_ALPHA, attempt.label)
        end
    end)

    run("last_valid_color_survives_rejection", function()
        resetOptions()
        upsert("last.text", "text", "Text", { y = 40 })
        setColor("last.text", rgb(CUSTOM_A))
        local held = rgb(CUSTOM_B)
        setColor("last.text", held)
        rejectColor("last.text", { 2, 0, 0 }, "out-of-range color")
        rejectColor("last.text", { 0 / 0, 0, 0 }, "NaN color")
        rejectColor("last.text", { 0.5, 0.5 }, "partial color")
        -- The caller reuses its table after a successful update.
        held[1] = 7
        held[2] = nil
        local current = renderNow()
        expectPalette(current, "last.text", CUSTOM_B, "last valid color")
        expectText(intentFor(current, "last.text"), CUSTOM_B, ACTIVE_ALPHA, "last valid color")
        clearColor("last.text")
        rejectColor("last.text", { -1, 0, 0 }, "color after clear")
        local cleared = renderNow()
        expectNoPalette(cleared, "last.text", "cleared option")
        expectText(intentFor(cleared, "last.text"), NORMAL_RGB, ACTIVE_ALPHA, "cleared option")
        setColor("last.text", rgb(CUSTOM_C))
        expectText(intentFor(renderNow(), "last.text"), CUSTOM_C, ACTIVE_ALPHA, "new valid color")
    end)

    run("custom_color_not_saved", function()
        resetOptions()
        upsert("save.bool", "boolean", false, { y = 40 })
        upsert("save.slider", "slider", 0.5, { normalSliderColor = normalSlider(), y = 56 })
        local before = renderNow()
        local writes = withSaveAudit(function()
            setColor("save.bool", rgb(CUSTOM_A))
            setColor("save.slider", rgb(CUSTOM_B))
            renderNow()
            clearColor("save.bool")
            setColor("save.bool", rgb(CUSTOM_C))
            renderNow()
        end)
        equal(writes, 0, "mod data writes during palette updates")
        local current = snapshot()
        expectPalette(current, "save.bool", CUSTOM_C, "save.bool")
        for _, id in ipairs({ "save.bool", "save.slider" }) do
            sameLayout(intentFor(current, id), intentFor(before, id), id)
            local value = intentFor(current, id).value
            if value ~= nil then
                equal(value, intentFor(before, id).value, id .. " value")
            end
        end
        remove("save.bool")
        expectNoPalette(renderNow(), "save.bool", "removed option")
        upsert("save.bool", "boolean", false, { y = 40 })
        local restored = renderNow()
        expectNoPalette(restored, "save.bool", "re-added option")
        expectText(intentFor(restored, "save.bool"), NORMAL_RGB, ACTIVE_ALPHA, "re-added option")
    end)

    run("option_value_not_changed_by_color", function()
        resetOptions()
        local options = {
            { id = "value.off", kind = "boolean", value = false },
            { id = "value.on", kind = "boolean", value = true },
            { id = "value.slider", kind = "slider", value = 7.5 },
            { id = "value.text", kind = "text", value = "Hello" },
        }
        for index, option in ipairs(options) do
            upsert(option.id, option.kind, option.value, {
                y = 24 + 16 * index,
                normalSliderColor = option.kind == "slider" and normalSlider() or nil,
            })
        end
        local before = renderNow()
        for index, option in ipairs(options) do
            setColor(option.id, rgb(({ CUSTOM_A, CUSTOM_B, CUSTOM_C, CUSTOM_A })[index]))
        end
        local colored = renderNow()
        for _, option in ipairs(options) do
            local intent = intentFor(colored, option.id)
            sameLayout(intent, intentFor(before, option.id), option.id)
            if intent.value ~= nil then
                equal(intent.value, option.value, option.id .. " value")
            end
            clearColor(option.id)
        end
        local cleared = renderNow()
        for _, option in ipairs(options) do
            sameIntent(intentFor(cleared, option.id), intentFor(before, option.id),
                option.id .. " after clear")
        end
    end)

    run("color_state_not_shared", function()
        resetOptions()
        local sharedText = normalText()
        local sharedSlider = normalSlider()
        upsert("iso.a", "slider", 0.5, {
            normalTextColor = sharedText,
            normalSliderColor = sharedSlider,
            y = 40,
        })
        upsert("iso.b", "slider", 0.5, {
            normalTextColor = sharedText,
            normalSliderColor = sharedSlider,
            y = 56,
        })
        local before = renderNow()
        local input = rgb(CUSTOM_A)
        setColor("iso.a", input)
        input[1], input[2], input[3] = 0.0625, 0.0625, 0.0625
        local colored = renderNow()
        expectText(intentFor(colored, "iso.a"), CUSTOM_A, ACTIVE_ALPHA, "iso.a")
        expectCustomSlider(intentFor(colored, "iso.a"), CUSTOM_A, ACTIVE_ALPHA, "iso.a")
        sameIntent(intentFor(colored, "iso.b"), intentFor(before, "iso.b"),
            "peer sharing the normal colors")
        expectNormalTextUnchanged(sharedText, "shared normal KColor")
        expectNormalSliderUnchanged(sharedSlider, "shared normal slider color")
        -- Snapshots are fresh copies of the palette and render intents.
        expectPalette(colored, "iso.a", CUSTOM_A, "iso.a")
        colored.palette["iso.a"].red = 0
        intentFor(colored, "iso.a").text.red = 0
        intentFor(colored, "iso.a").slider.red = 0
        local fresh = snapshot()
        expectPalette(fresh, "iso.a", CUSTOM_A, "fresh palette")
        expectText(intentFor(fresh, "iso.a"), CUSTOM_A, ACTIVE_ALPHA, "fresh intent")
        expectCustomSlider(intentFor(fresh, "iso.a"), CUSTOM_A, ACTIVE_ALPHA, "fresh intent")
        setColor("iso.b", rgb(CUSTOM_B))
        clearColor("iso.a")
        local swapped = renderNow()
        sameIntent(intentFor(swapped, "iso.a"), intentFor(before, "iso.a"), "cleared iso.a")
        expectText(intentFor(swapped, "iso.b"), CUSTOM_B, ACTIVE_ALPHA, "iso.b")
        expectCustomSlider(intentFor(swapped, "iso.b"), CUSTOM_B, ACTIVE_ALPHA, "iso.b")
        setOrder({ "iso.b", "iso.a" })
        upsert("iso.b", "slider", 0.5, {
            normalTextColor = sharedText,
            normalSliderColor = sharedSlider,
            y = 40,
        })
        upsert("iso.a", "slider", 0.5, {
            normalTextColor = sharedText,
            normalSliderColor = sharedSlider,
            y = 56,
        })
        local reordered = renderNow()
        sequenceEquals(orderOf(reordered, "iso."), { "iso.b", "iso.a" }, "order")
        expectText(intentFor(reordered, "iso.b"), CUSTOM_B, ACTIVE_ALPHA, "reordered iso.b")
        expectText(intentFor(reordered, "iso.a"), NORMAL_RGB, ACTIVE_ALPHA, "reordered iso.a")
        expectNormalSlider(intentFor(reordered, "iso.a"), "reordered iso.a")
    end)

    run("between_categories", function()
        resetOptions()
        setContext({ category = "general" })
        upsert("cat.a", "text", "A", { y = 40 })
        upsert("cat.b", "text", "B", { y = 56 })
        setColor("cat.a", rgb(CUSTOM_A))
        local general = renderNow()
        expectText(intentFor(general, "cat.a"), CUSTOM_A, ACTIVE_ALPHA, "general cat.a")
        expectText(intentFor(general, "cat.b"), NORMAL_RGB, ACTIVE_ALPHA, "general cat.b")
        setContext({ category = "controls" })
        upsert("cat.a", "text", "A", { x = 120, y = 72, selected = true })
        upsert("cat.c", "text", "C", { x = 120, y = 88 })
        local controls = renderNow()
        local moved = intentFor(controls, "cat.a")
        expectText(moved, CUSTOM_A, ACTIVE_ALPHA, "controls cat.a")
        equal(moved.x, 120, "moved x")
        equal(moved.y, 72, "moved y")
        expectText(intentFor(controls, "cat.c"), NORMAL_RGB, ACTIVE_ALPHA, "controls cat.c")
        expectPalette(controls, "cat.a", CUSTOM_A, "controls cat.a")
        expectNoPalette(controls, "cat.c", "controls cat.c")
        setContext({ category = "general" })
        upsert("cat.a", "text", "A", { y = 40 })
        local back = renderNow()
        expectText(intentFor(back, "cat.a"), CUSTOM_A, ACTIVE_ALPHA, "returned cat.a")
        equal(intentFor(back, "cat.a").y, 40, "returned y")
    end)

    run("repeated_render_is_idempotent", function()
        resetOptions()
        local ids = { "idem.idle", "idem.slider", "idem.plain", "idem.locked" }
        upsert("idem.idle", "text", "Idle", { focused = false, y = 40 })
        upsert("idem.slider", "slider", 0.5, {
            focused = false,
            normalSliderColor = normalSlider(),
            y = 56,
        })
        upsert("idem.plain", "text", "Plain", { y = 72 })
        upsert("idem.locked", "boolean", false, { selectable = false, selected = true, y = 88 })
        setColor("idem.idle", rgb(CUSTOM_A))
        setColor("idem.slider", rgb(CUSTOM_B))
        setColor("idem.locked", rgb(CUSTOM_C))
        local errors = snapshot().renderErrorCount
        local first = renderNow()
        local second = renderNow()
        local third = renderNow()
        sequenceEquals(orderOf(second, "idem."), orderOf(first, "idem."), "second order")
        sequenceEquals(orderOf(third, "idem."), orderOf(first, "idem."), "third order")
        for _, id in ipairs(ids) do
            sameIntent(intentFor(second, id), intentFor(first, id), id .. " second render")
            sameIntent(intentFor(third, id), intentFor(first, id), id .. " third render")
        end
        expectText(intentFor(third, "idem.idle"), CUSTOM_A, INACTIVE_ALPHA, "idem.idle")
        expectCustomSlider(intentFor(third, "idem.slider"), CUSTOM_B, INACTIVE_ALPHA,
            "idem.slider")
        expectText(intentFor(third, "idem.plain"), NORMAL_RGB, ACTIVE_ALPHA, "idem.plain")
        expectText(intentFor(third, "idem.locked"), CUSTOM_C, INACTIVE_ALPHA, "idem.locked")
        expectPalette(third, "idem.slider", CUSTOM_B, "idem.slider")
        equal(third.renderErrorCount, errors, "render errors")
    end)

    run("normal_color_accessor_missing_fallback", function()
        resetOptions()
        local errors = snapshot().renderErrorCount
        local colorA = mockText(nil)
        colorA.A = 0.25
        local options = {
            { id = "fb.missing", color = mockText(nil) },
            { id = "fb.nan", color = mockText(0 / 0) },
            { id = "fb.inf", color = mockText(math.huge) },
            { id = "fb.ninf", color = mockText(-math.huge) },
            { id = "fb.colora", color = colorA },
        }
        for index, option in ipairs(options) do
            upsert(option.id, "text", "Mock", {
                normalTextColor = option.color,
                y = 24 + 16 * index,
            })
        end
        upsert("fb.idle", "text", "Idle", {
            normalTextColor = mockText(nil),
            focused = false,
            y = 120,
        })
        upsert("fb.slider", "slider", 0.5, {
            normalTextColor = mockText(nil),
            normalSliderColor = normalSlider(),
            y = 136,
        })
        local normal = renderNow()
        for _, option in ipairs(options) do
            expectText(intentFor(normal, option.id), NORMAL_RGB, ACTIVE_ALPHA, option.id)
        end
        expectText(intentFor(normal, "fb.idle"), NORMAL_RGB, INACTIVE_ALPHA, "fb.idle")
        expectText(intentFor(normal, "fb.slider"), NORMAL_RGB, ACTIVE_ALPHA, "fb.slider")
        expectNormalSlider(intentFor(normal, "fb.slider"), "fb.slider")
        for _, option in ipairs(options) do
            setColor(option.id, rgb(CUSTOM_A))
        end
        setColor("fb.idle", rgb(CUSTOM_B))
        setColor("fb.slider", rgb(CUSTOM_C))
        local custom = renderNow()
        for _, option in ipairs(options) do
            expectText(intentFor(custom, option.id), CUSTOM_A, ACTIVE_ALPHA,
                "custom " .. option.id)
        end
        expectText(intentFor(custom, "fb.idle"), CUSTOM_B, INACTIVE_ALPHA, "custom fb.idle")
        expectCustomSlider(intentFor(custom, "fb.slider"), CUSTOM_C, ACTIVE_ALPHA,
            "custom fb.slider")
        equal(custom.renderErrorCount, errors, "render errors")
    end)

    run("alpha_never_nil", function()
        resetOptions()
        local options = {
            { id = "anil.real", kind = "text", fields = {} },
            { id = "anil.missing", kind = "boolean", fields = { normalTextColor = mockText(nil) } },
            { id = "anil.nan", kind = "text", fields = { normalTextColor = mockText(0 / 0) } },
            { id = "anil.idle", kind = "text", fields = { focused = false } },
            { id = "anil.locked", kind = "boolean", fields = { selectable = false } },
            { id = "anil.slider", kind = "slider",
                fields = { normalTextColor = mockText(nil), normalSliderColor = normalSlider() } },
            { id = "anil.bare", kind = "slider", fields = { focused = false } },
        }
        local values = { text = "Text", boolean = true, slider = 0.5 }
        for index, option in ipairs(options) do
            option.fields.y = 24 + 16 * index
            upsert(option.id, option.kind, values[option.kind], option.fields)
        end
        local function checkAlphas(current, colored, label)
            for _, option in ipairs(options) do
                local intent = intentFor(current, option.id)
                truthy(type(intent.text) == "table", label .. " " .. option.id .. " text missing")
                local alpha = intent.text.alpha
                truthy(type(alpha) == "number" and alpha == alpha and alpha >= 0 and alpha <= 1,
                    label .. " " .. option.id .. " text alpha " .. tostring(alpha))
                local sliderRequired = option.kind == "slider"
                    and (colored or option.fields.normalSliderColor ~= nil)
                if sliderRequired or intent.slider ~= nil then
                    truthy(type(intent.slider) == "table",
                        label .. " " .. option.id .. " slider color missing")
                    local sliderAlpha = intent.slider.alpha
                    truthy(type(sliderAlpha) == "number" and sliderAlpha == sliderAlpha
                        and sliderAlpha >= 0 and sliderAlpha <= 1,
                        label .. " " .. option.id .. " slider alpha " .. tostring(sliderAlpha))
                end
            end
        end
        checkAlphas(renderNow(), false, "normal")
        for _, option in ipairs(options) do
            setColor(option.id, rgb(CUSTOM_B))
        end
        checkAlphas(renderNow(), true, "custom")
    end)

    run("inactive_slider_alpha", function()
        resetOptions()
        upsert("islider.idle", "slider", 0.5, {
            focused = false,
            normalSliderColor = normalSlider(),
            y = 40,
        })
        upsert("islider.locked", "slider", 0.5, {
            selectable = false,
            selected = true,
            normalSliderColor = normalSlider(),
            y = 56,
        })
        upsert("islider.active", "slider", 0.5, { normalSliderColor = normalSlider(), y = 72 })
        local normal = renderNow()
        expectText(intentFor(normal, "islider.idle"), NORMAL_RGB, INACTIVE_ALPHA, "normal idle")
        expectText(intentFor(normal, "islider.locked"), NORMAL_RGB, INACTIVE_ALPHA,
            "normal locked")
        for _, id in ipairs({ "islider.idle", "islider.locked", "islider.active" }) do
            setColor(id, rgb(CUSTOM_B))
        end
        local custom = renderNow()
        expectText(intentFor(custom, "islider.idle"), CUSTOM_B, INACTIVE_ALPHA, "idle text")
        expectCustomSlider(intentFor(custom, "islider.idle"), CUSTOM_B, INACTIVE_ALPHA,
            "idle slider")
        expectText(intentFor(custom, "islider.locked"), CUSTOM_B, INACTIVE_ALPHA, "locked text")
        expectCustomSlider(intentFor(custom, "islider.locked"), CUSTOM_B, INACTIVE_ALPHA,
            "locked slider")
        expectCustomSlider(intentFor(custom, "islider.active"), CUSTOM_B, ACTIVE_ALPHA,
            "active slider")
    end)

    -- The two cases that need real MC_POST_RENDER passes run from the update state
    -- machine; start the first one now.
    if not beginStep() then
        finish()
    end
end

suite:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, function()
    if started then
        return
    end
    started = true
    updateFrames = 0
    log("[GCB_RUNTIME] suite_started")
end)

suite:AddCallback(ModCallbacks.MC_POST_RENDER, function()
    renderFrames = renderFrames + 1
end)

suite:AddCallback(ModCallbacks.MC_POST_UPDATE, function()
    if finished or not started then
        return
    end
    updateFrames = updateFrames + 1
    local body = updateFrames == 1 and executeSuite or advanceAsync
    local ok, err = pcall(body)
    if not ok then
        log("[GCB_FATAL] " .. oneLine(err))
        finish()
    end
end)
