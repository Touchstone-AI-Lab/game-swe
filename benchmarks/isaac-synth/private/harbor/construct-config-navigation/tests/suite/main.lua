local suite = RegisterMod("Construct Config Navigation Verifier", 1)
local game = Game()
local json = require("json")

local RENDER_CASE = "render_tracks_current_pane_and_selection"
local CATEGORY_IDS = { "menu", "general", "controls" }
local SUBCATEGORY_IDS = { "menu/main", "menu/demo", "general/hud", "controls/keybinds" }
local SUBCATEGORY_CATEGORY = { 1, 1, 2, 3 }
local FIRST_SUBCATEGORY = { 1, 3, 4 }
local OPTION_IDS = {
    "open_at_start", "menu_scale", "demo_mode", "demo_rate",
    "show_hud", "hud_offset", "open_menu", "reset_config",
}
local OPTION_SUBCATEGORY = {
    open_at_start = "menu/main",
    menu_scale = "menu/main",
    demo_mode = "menu/demo",
    demo_rate = "menu/demo",
    show_hud = "general/hud",
    hud_offset = "general/hud",
    open_menu = "controls/keybinds",
    reset_config = "controls/keybinds",
}
local BOOLEAN_IDS = { "open_at_start", "demo_mode", "show_hud" }
local SLIDER_IDS = { "menu_scale", "demo_rate", "hud_offset" }
local DIRECTION_OF_SYMBOL = {
    ACTION_MENUUP = "up",
    ACTION_MENUDOWN = "down",
    ACTION_MENULEFT = "left",
    ACTION_MENURIGHT = "right",
}
local STATE_KEYS = {
    "open", "pane", "categoryIndex", "subcategoryIndex", "optionIndex", "capture",
    "open_at_start", "menu_scale", "demo_mode", "demo_rate",
    "show_hud", "hud_offset", "open_menu", "reset_config",
}
-- The multi-frame render case starts well after a stray launcher key press could still
-- arrive, and every wait inside it has its own update-frame budget.
local RENDER_START_FRAME = 150
local RENDER_WAIT_BUDGET = 60

local passed = 0
local failed = 0
local recorded = {}
local finished = false
local started = false
local updateFrames = 0
local renderFrames = 0
local renderStarted = false
local renderJob = nil
local baselineBooleans = nil
local baselineError = "baseline snapshot was not taken"

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

local function approx(actual, expected, label)
    if type(actual) ~= "number" or math.abs(actual - expected) > 1e-6 then
        error((label or "value") .. ": expected " .. tostring(expected)
            .. ", received " .. tostring(actual))
    end
end

local function oneLine(detail)
    local text = tostring(detail or "")
    text = text:gsub("[\r\n]+", " ")
    if #text > 600 then
        text = text:sub(1, 600) .. "..."
    end
    return text
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

-- Submission access -----------------------------------------------------------------

local function nav()
    local api = IsaacConstructNavigation
    truthy(type(api) == "table", "IsaacConstructNavigation is not exported")
    truthy(type(api.Step) == "function", "IsaacConstructNavigation.Step is missing")
    truthy(type(api.Snapshot) == "function", "IsaacConstructNavigation.Snapshot is missing")
    return api
end

local function snap()
    local current = nav().Snapshot()
    truthy(type(current) == "table", "Snapshot() did not return a table")
    return current
end

local function capturing(current)
    return current.capture ~= nil and current.capture ~= false
end

local function unwrap(entry)
    if type(entry) == "table" and entry.value ~= nil then
        return entry.value
    end
    return entry
end

-- The statement fixes the option IDs but not the config table's layout, so a value is
-- looked up flat, by subcategory ID, or by category and subcategory name.
local function value(current, optionId)
    local config = current.config
    truthy(type(config) == "table", "Snapshot().config is not a table")
    if config[optionId] ~= nil then
        return unwrap(config[optionId])
    end
    local subcategoryId = OPTION_SUBCATEGORY[optionId]
    local categoryId, shortId = subcategoryId:match("^([%w_]+)/([%w_]+)$")
    local containers = {}
    local function add(container)
        if type(container) == "table" then
            containers[#containers + 1] = container
        end
    end
    add(config[subcategoryId])
    if type(config[categoryId]) == "table" then
        add(config[categoryId])
        add(config[categoryId][shortId])
    end
    add(config.keybinds)
    add(config.bindings)
    for _, container in ipairs(containers) do
        if container[optionId] ~= nil then
            return unwrap(container[optionId])
        end
    end
    error("Snapshot().config has no value for " .. optionId)
end

local function menuState(current)
    local result = {
        open = current.open,
        pane = current.pane,
        categoryIndex = current.categoryIndex,
        subcategoryIndex = current.subcategoryIndex,
        optionIndex = current.optionIndex,
        capture = capturing(current),
    }
    for _, optionId in ipairs(OPTION_IDS) do
        result[optionId] = value(current, optionId)
    end
    return result
end

local function expectUnchanged(before, current, label)
    local after = menuState(current)
    for _, key in ipairs(STATE_KEYS) do
        if after[key] ~= before[key] then
            error(label .. ": " .. key .. " changed from " .. tostring(before[key])
                .. " to " .. tostring(after[key]))
        end
    end
end

local EXPECT_FIELDS = {
    { "open", "open" },
    { "pane", "pane" },
    { "cat", "categoryIndex" },
    { "sub", "subcategoryIndex" },
    { "opt", "optionIndex" },
}

local function expect(label, want)
    local current = snap()
    for _, pair in ipairs(EXPECT_FIELDS) do
        if want[pair[1]] ~= nil then
            equal(current[pair[2]], want[pair[1]], label .. " " .. pair[2])
        end
    end
    if want.capture ~= nil then
        equal(capturing(current), want.capture, label .. " capture")
    end
    return current
end

local function validIndices(current)
    local function inRange(index, count)
        return type(index) == "number" and index % 1 == 0 and index >= 1 and index <= count
    end
    return inRange(current.categoryIndex, 3)
        and inRange(current.subcategoryIndex, 4)
        and inRange(current.optionIndex, 2)
end

local function baselineDefault(optionId)
    truthy(baselineBooleans, "initial boolean defaults unavailable: " .. tostring(baselineError))
    return baselineBooleans[optionId]
end

local function expectDefaults(current, label)
    for _, optionId in ipairs(SLIDER_IDS) do
        approx(value(current, optionId), 5.0, label .. " " .. optionId)
    end
    equal(value(current, "open_menu"), "KEY_F2", label .. " open_menu")
    equal(value(current, "reset_config"), "KEY_F3", label .. " reset_config")
    for _, optionId in ipairs(BOOLEAN_IDS) do
        equal(value(current, optionId), baselineDefault(optionId), label .. " " .. optionId)
    end
end

-- Input frames ----------------------------------------------------------------------
-- Every frame carries the full documented shape. A d-pad frame reports the pressed
-- direction as a digital action with a full analog value; a keyboard frame reports only
-- the digital action; an analog frame reports only GetActionValue-style values.

local function blankFrame()
    return {
        triggered = {},
        held = {},
        analog = { up = 0, down = 0, left = 0, right = 0 },
        keys = {},
    }
end

local function send(frameInput)
    nav().Step(frameInput)
end

local function idle()
    send(blankFrame())
end

local function dpadFrame(directions, fresh)
    local frameInput = blankFrame()
    for _, direction in ipairs(directions) do
        if fresh then
            frameInput.triggered[direction] = true
        end
        frameInput.held[direction] = true
        frameInput.analog[direction] = 1.0
    end
    return frameInput
end

local function keyboardFrame(directions, fresh)
    local frameInput = blankFrame()
    for _, direction in ipairs(directions) do
        if fresh then
            frameInput.triggered[direction] = true
        end
        frameInput.held[direction] = true
    end
    return frameInput
end

local function analogFrame(values)
    local frameInput = blankFrame()
    for direction, amount in pairs(values) do
        frameInput.analog[direction] = amount
    end
    return frameInput
end

-- A tap: one pressed frame followed by one released frame.
local function press(direction)
    send(dpadFrame({ direction }, true))
    idle()
end

local function pressKey(symbol)
    local frameInput = blankFrame()
    frameInput.keys[symbol] = true
    send(frameInput)
    idle()
end

local function pressButton(action)
    local frameInput = blankFrame()
    frameInput.triggered[action] = true
    frameInput.held[action] = true
    send(frameInput)
    idle()
end

local function confirm()
    pressButton("confirm")
end

local function back()
    pressButton("back")
end

local function pressBinding(symbol)
    if type(symbol) == "string" and symbol:match("^KEY_F%d+$") then
        pressKey(symbol)
        return
    end
    local direction = DIRECTION_OF_SYMBOL[symbol]
    truthy(direction, "unsupported binding symbol " .. tostring(symbol))
    press(direction)
end

-- Normalization -----------------------------------------------------------------------
-- Tests may only inject input, so every case first drives the menu to one canonical
-- state: open, category pane on `menu`, menu/main and its first option remembered,
-- capture off, and the configuration reset to defaults through reset_config.

local function walkToSubcategory(index)
    local current = snap()
    if current.pane == "options" then
        if current.optionIndex ~= 1 then
            press("up")
        end
        back()
        current = snap()
    end
    if current.pane == "category" then
        press("right")
        current = snap()
    end
    equal(current.pane, "subcategory", "normalize: subcategory pane")
    for _ = 1, 4 do
        if current.subcategoryIndex == index then
            break
        end
        press("left")
        current = snap()
    end
    equal(current.subcategoryIndex, index, "normalize: subcategoryIndex")
    return current
end

-- Only reachable after a failed case left open_menu and reset_config on the same input.
-- The walk to the reset_config row uses back, right and down only, so it also works when
-- the shared binding is up or left.
local function separateBindings(current)
    local symbol = value(current, "open_menu")
    truthy(symbol ~= "ACTION_MENUDOWN" and symbol ~= "ACTION_MENURIGHT",
        "normalize: identical bindings on " .. tostring(symbol) .. " cannot be separated")
    if current.pane == "options" then
        back()
        current = snap()
    end
    if current.pane == "category" then
        press("right")
        current = snap()
    end
    equal(current.pane, "subcategory", "normalize: subcategory pane")
    for _ = 1, 4 do
        if current.subcategoryIndex == 4 then
            break
        end
        press("right")
        current = snap()
    end
    equal(current.subcategoryIndex, 4, "normalize: keybind subcategory")
    press("down")
    current = expect("normalize: keybind options", { pane = "options", sub = 4 })
    if current.optionIndex ~= 2 then
        press("down")
    end
    expect("normalize: reset_config row", { pane = "options", opt = 2 })
    confirm()
    pressKey(symbol == "KEY_F3" and "KEY_F4" or "KEY_F3")
    current = snap()
    truthy(value(current, "open_menu") ~= value(current, "reset_config"),
        "normalize: bindings are still identical")
end

local function normalize()
    local current = snap()
    if capturing(current) then
        back()
        current = snap()
        if capturing(current) then
            -- Back failed to cancel; finish the capture instead (reset restores it below).
            pressKey("KEY_F12")
            current = snap()
        end
        truthy(not capturing(current), "normalize: keybind capture could not be ended")
    end
    if current.open ~= true then
        pressBinding(value(current, "open_menu"))
        current = snap()
        truthy(current.open == true, "normalize: the open_menu binding did not open the menu")
    end
    if value(current, "open_menu") == value(current, "reset_config") then
        separateBindings(current)
        current = snap()
    end
    pressBinding(value(current, "reset_config"))
    current = snap()
    truthy(current.open == true, "normalize: the reset_config binding closed the menu")
    truthy(not capturing(current), "normalize: capture active after reset")
    equal(value(current, "open_menu"), "KEY_F2", "normalize: open_menu after reset")
    equal(value(current, "reset_config"), "KEY_F3", "normalize: reset_config after reset")
    for _, optionId in ipairs(SLIDER_IDS) do
        approx(value(current, optionId), 5.0, "normalize: " .. optionId .. " after reset")
    end
    walkToSubcategory(1)
    press("down")
    current = expect("normalize: menu/main options", { pane = "options", sub = 1 })
    if current.optionIndex ~= 1 then
        press("up")
    end
    expect("normalize: first option", { pane = "options", opt = 1 })
    back()
    press("up")
    current = expect("normalize: canonical state",
        { open = true, pane = "category", cat = 1, sub = 1, opt = 1, capture = false })
    return current
end

-- Navigation from the canonical state ---------------------------------------------------

local function toCategory(categoryIndex)
    for _ = 2, categoryIndex do
        press("down")
    end
    expect("setup category", { pane = "category", cat = categoryIndex })
end

local function toSubcategory(subcategoryIndex)
    local categoryIndex = SUBCATEGORY_CATEGORY[subcategoryIndex]
    toCategory(categoryIndex)
    press("right")
    expect("setup subcategory", { pane = "subcategory", sub = FIRST_SUBCATEGORY[categoryIndex] })
    if subcategoryIndex ~= FIRST_SUBCATEGORY[categoryIndex] then
        press("right")
    end
    expect("setup subcategory", { pane = "subcategory", sub = subcategoryIndex, cat = categoryIndex })
end

-- From the subcategory pane: enter its options and select row `optionIndex`.
local function enterOptions(optionIndex)
    press("down")
    local current = expect("setup options", { pane = "options" })
    if current.optionIndex ~= 1 then
        press("up")
    end
    current = expect("setup options", { pane = "options", opt = 1 })
    if optionIndex == 2 then
        press("down")
        current = expect("setup options", { pane = "options", opt = 2 })
    end
    return current
end

local function toOption(subcategoryIndex, optionIndex)
    toSubcategory(subcategoryIndex)
    return enterOptions(optionIndex)
end

local function rowsOf(ids)
    local rows = {}
    for index, id in ipairs(ids) do
        rows[index] = { id = id, text = id }
    end
    return rows
end

-- Synchronous cases (first update frame) --------------------------------------------------

local function captureBaseline()
    local ok, err = pcall(function()
        local current = snap()
        local booleans = {}
        for _, optionId in ipairs(BOOLEAN_IDS) do
            local initial = value(current, optionId)
            truthy(type(initial) == "boolean", optionId .. " is not a boolean")
            booleans[optionId] = initial
        end
        baselineBooleans = booleans
    end)
    if not ok then
        baselineBooleans = nil
        baselineError = err
    end
end

local function runStateCases()
    run("initial_closed_state", function()
        local current = snap()
        equal(current.open, false, "open")
        equal(current.pane, "category", "pane")
        equal(current.categoryIndex, 1, "categoryIndex")
        equal(current.subcategoryIndex, 1, "subcategoryIndex")
        equal(current.optionIndex, 1, "optionIndex")
        truthy(not capturing(current), "keybind capture active before any input")
        for _, optionId in ipairs(SLIDER_IDS) do
            approx(value(current, optionId), 5.0, optionId)
        end
        equal(value(current, "open_menu"), "KEY_F2", "open_menu")
        equal(value(current, "reset_config"), "KEY_F3", "reset_config")
        for _, optionId in ipairs(BOOLEAN_IDS) do
            equal(type(value(current, optionId)), "boolean", optionId .. " type")
        end
        truthy(type(current.lastDraws) == "table", "lastDraws is not a table")
        equal(#current.lastDraws, 0, "draw records while closed")
        equal(current.renderErrorCount, 0, "renderErrorCount")
        local again = snap()
        truthy(again ~= current
            and again.config ~= current.config
            and again.lastDraws ~= current.lastDraws,
            "Snapshot() does not return a fresh copy")
        return "closed on menu/menu/main/open_at_start with default sliders and F2/F3"
    end)

    run("first_open_state", function()
        pressKey("KEY_F2")
        expect("first open", { open = true, pane = "category", cat = 1, sub = 1, opt = 1, capture = false })
        press("down")
        press("right")
        press("down")
        press("down")
        expect("before closing", { open = true, pane = "options", cat = 2, sub = 3, opt = 2 })
        pressKey("KEY_F2")
        expect("closed", { open = false })
        pressKey("KEY_F2")
        expect("reopened", { open = true, cat = 2, sub = 3, opt = 2 })
        return "first open shows menu, menu/main, open_at_start; reopen keeps general/hud option 2"
    end)
end

local function runCategoryCases()
    run("category_up", function()
        normalize()
        press("down")
        press("down")
        expect("setup", { pane = "category", cat = 3 })
        press("up")
        expect("after up", { open = true, pane = "category", cat = 2 })
        return "controls -> general"
    end)

    run("category_down", function()
        normalize()
        press("down")
        expect("first down", { open = true, pane = "category", cat = 2 })
        press("down")
        expect("second down", { open = true, pane = "category", cat = 3 })
        return "menu -> general -> controls"
    end)

    run("category_wrap_up", function()
        normalize()
        press("up")
        expect("after up", { open = true, pane = "category", cat = 3 })
        return "menu -> controls"
    end)

    run("category_wrap_down", function()
        normalize()
        press("down")
        press("down")
        expect("setup", { pane = "category", cat = 3 })
        press("down")
        expect("after down", { open = true, pane = "category", cat = 1 })
        return "controls -> menu"
    end)

    run("category_right_enters_subcategories", function()
        for categoryIndex, firstSubcategory in ipairs(FIRST_SUBCATEGORY) do
            normalize()
            toCategory(categoryIndex)
            local before = menuState(snap())
            press("left")
            expectUnchanged(before, snap(), "left in the category pane")
            press("right")
            expect(CATEGORY_IDS[categoryIndex] .. " right",
                { open = true, pane = "subcategory", cat = categoryIndex, sub = firstSubcategory })
        end
        return "menu->menu/main general->general/hud controls->controls/keybinds; left is a no-op"
    end)

    run("reset_restores_defaults_and_keeps_menu_open", function()
        normalize()
        toOption(1, 1)
        confirm()
        press("down")
        press("right")
        press("right")
        back()
        press("right")
        enterOptions(1)
        confirm()
        press("down")
        press("left")
        back()
        press("right")
        enterOptions(1)
        confirm()
        press("down")
        press("left")
        press("left")
        press("left")
        back()
        press("right")
        enterOptions(1)
        confirm()
        pressKey("KEY_F7")
        press("down")
        confirm()
        pressKey("KEY_F8")
        local changed = expect("changed",
            { open = true, pane = "options", cat = 3, sub = 4, opt = 2, capture = false })
        for _, optionId in ipairs(BOOLEAN_IDS) do
            equal(value(changed, optionId), not baselineDefault(optionId), "changed " .. optionId)
        end
        approx(value(changed, "menu_scale"), 6.0, "changed menu_scale")
        approx(value(changed, "demo_rate"), 4.5, "changed demo_rate")
        approx(value(changed, "hud_offset"), 3.5, "changed hud_offset")
        equal(value(changed, "open_menu"), "KEY_F7", "changed open_menu")
        equal(value(changed, "reset_config"), "KEY_F8", "changed reset_config")
        pressKey("KEY_F8")
        local after = expect("after reset",
            { open = true, pane = "options", cat = 3, sub = 4, opt = 2, capture = false })
        expectDefaults(after, "after reset")
        return "every option and both keybinds restored; menu stayed open on controls/keybinds option 2"
    end)
end

local function runSubcategoryCases()
    run("subcategory_up_returns", function()
        normalize()
        toSubcategory(3)
        press("up")
        local current = expect("after up", { open = true, pane = "category", cat = 2 })
        truthy(validIndices(current), "indices invalid after returning to the category pane")
        return "general/hud -> category general"
    end)

    run("subcategory_down_enters_options", function()
        normalize()
        press("right")
        expect("setup", { pane = "subcategory", sub = 1 })
        press("down")
        expect("after down", { open = true, pane = "options", cat = 1, sub = 1, opt = 1 })
        return "menu/main -> its options on open_at_start"
    end)

    run("subcategory_left", function()
        normalize()
        toSubcategory(3)
        press("left")
        expect("first left", { open = true, pane = "subcategory", sub = 2, cat = 1 })
        press("left")
        expect("second left", { open = true, pane = "subcategory", sub = 1, cat = 1 })
        return "general/hud -> menu/demo -> menu/main"
    end)

    run("subcategory_right", function()
        normalize()
        press("right")
        expect("setup", { pane = "subcategory", sub = 1 })
        press("right")
        expect("first right", { open = true, pane = "subcategory", sub = 2, cat = 1 })
        press("right")
        expect("second right", { open = true, pane = "subcategory", sub = 3, cat = 2 })
        press("right")
        expect("third right", { open = true, pane = "subcategory", sub = 4, cat = 3 })
        return "menu/main -> menu/demo -> general/hud -> controls/keybinds"
    end)

    run("subcategory_wrap_left", function()
        normalize()
        press("right")
        expect("setup", { pane = "subcategory", sub = 1 })
        press("left")
        expect("after left", { open = true, pane = "subcategory", sub = 4, cat = 3 })
        return "menu/main -> controls/keybinds"
    end)

    run("subcategory_wrap_right", function()
        normalize()
        toSubcategory(4)
        press("right")
        expect("after right", { open = true, pane = "subcategory", sub = 1, cat = 1 })
        return "controls/keybinds -> menu/main"
    end)
end

local function runOptionCases()
    run("options_down", function()
        normalize()
        toOption(1, 1)
        press("down")
        expect("after down", { open = true, pane = "options", sub = 1, opt = 2 })
        return "open_at_start -> menu_scale"
    end)

    run("option_wrap_up", function()
        normalize()
        toOption(3, 1)
        press("up")
        expect("after up", { open = true, pane = "options", sub = 3, opt = 2 })
        return "show_hud -> hud_offset"
    end)

    run("option_wrap_down", function()
        normalize()
        toOption(2, 1)
        press("down")
        expect("first down", { open = true, pane = "options", sub = 2, opt = 2 })
        press("down")
        expect("second down", { open = true, pane = "options", sub = 2, opt = 1 })
        return "demo_mode -> demo_rate -> demo_mode"
    end)

    run("slider_left_step", function()
        normalize()
        local current = toOption(1, 2)
        approx(value(current, "menu_scale"), 5.0, "precondition menu_scale")
        press("left")
        current = expect("first left", { open = true, pane = "options", sub = 1, opt = 2 })
        approx(value(current, "menu_scale"), 4.5, "menu_scale after one left")
        press("left")
        current = expect("second left", { open = true, pane = "options", sub = 1, opt = 2 })
        approx(value(current, "menu_scale"), 4.0, "menu_scale after two lefts")
        approx(value(current, "demo_rate"), 5.0, "demo_rate untouched")
        approx(value(current, "hud_offset"), 5.0, "hud_offset untouched")
        return "menu_scale 5.0 -> 4.5 -> 4.0"
    end)

    run("slider_right_step", function()
        normalize()
        local current = toOption(2, 2)
        approx(value(current, "demo_rate"), 5.0, "precondition demo_rate")
        press("right")
        current = expect("first right", { open = true, pane = "options", sub = 2, opt = 2 })
        approx(value(current, "demo_rate"), 5.5, "demo_rate after one right")
        press("right")
        current = expect("second right", { open = true, pane = "options", sub = 2, opt = 2 })
        approx(value(current, "demo_rate"), 6.0, "demo_rate after two rights")
        approx(value(current, "menu_scale"), 5.0, "menu_scale untouched")
        approx(value(current, "hud_offset"), 5.0, "hud_offset untouched")
        return "demo_rate 5.0 -> 5.5 -> 6.0"
    end)

    run("slider_lower_clamp", function()
        normalize()
        toOption(3, 2)
        for count = 1, 12 do
            press("left")
            local current = expect("left " .. count, { open = true, pane = "options", sub = 3, opt = 2 })
            approx(value(current, "hud_offset"), math.max(0, 5.0 - 0.5 * count),
                "hud_offset after " .. count .. " lefts")
        end
        return "hud_offset reached 0.0 and stayed there; left stayed on the slider"
    end)

    run("slider_upper_clamp", function()
        normalize()
        toOption(1, 2)
        for count = 1, 12 do
            press("right")
            local current = expect("right " .. count, { open = true, pane = "options", sub = 1, opt = 2 })
            approx(value(current, "menu_scale"), math.min(10, 5.0 + 0.5 * count),
                "menu_scale after " .. count .. " rights")
        end
        return "menu_scale reached 10.0 and stayed there"
    end)

    run("keybind_left_returns", function()
        normalize()
        toOption(4, 1)
        local before = menuState(snap())
        press("right")
        expectUnchanged(before, snap(), "right on the open_menu keybind")
        press("left")
        local current = expect("left on open_menu",
            { open = true, pane = "subcategory", sub = 4, cat = 3, capture = false })
        equal(value(current, "open_menu"), "KEY_F2", "open_menu after left")
        enterOptions(2)
        press("left")
        current = expect("left on reset_config",
            { open = true, pane = "subcategory", sub = 4, cat = 3, capture = false })
        equal(value(current, "reset_config"), "KEY_F3", "reset_config after left")
        return "right is a no-op and left returns from both keybind rows"
    end)

    run("open_menu_rebind_takes_effect", function()
        normalize()
        toOption(4, 1)
        confirm()
        expect("capture started", { open = true, pane = "options", opt = 1, capture = true })
        pressKey("KEY_F5")
        local current = expect("F5 captured",
            { open = true, pane = "options", sub = 4, opt = 1, capture = false })
        equal(value(current, "open_menu"), "KEY_F5", "open_menu binding")
        equal(value(current, "reset_config"), "KEY_F3", "reset_config binding")
        pressKey("KEY_F2")
        expect("old F2 binding", { open = true })
        pressKey("KEY_F5")
        expect("F5 closes", { open = false })
        pressKey("KEY_F2")
        expect("F2 while closed", { open = false })
        pressKey("KEY_F5")
        expect("F5 reopens", { open = true, cat = 3, sub = 4, opt = 1 })
        return "open_menu captured as KEY_F5; F5 toggles and F2 no longer does"
    end)
end

-- Hold `direction` for `frames` frames (pressed on frame 1 when `fresh`), recording
-- one option value after every frame.
local function holdTrace(frameOf, direction, frames, optionId, fresh)
    local trace = {}
    for frame = 1, frames do
        send(frameOf({ direction }, fresh and frame == 1))
        trace[frame] = value(snap(), optionId)
    end
    return trace
end

local function expectTrace(trace, first, last, expected, label)
    for frame = first, last do
        approx(trace[frame], expected, label .. " held frame " .. frame)
    end
end

local function runTimingCases()
    run("press_moves_immediately", function()
        normalize()
        send(dpadFrame({ "down" }, true))
        expect("on the press frame", { open = true, pane = "category", cat = 2 })
        idle()
        expect("after release", { open = true, pane = "category", cat = 2 })
        press("right")
        enterOptions(2)
        send(dpadFrame({ "right" }, true))
        approx(value(snap(), "hud_offset"), 5.5, "hud_offset on the press frame")
        idle()
        approx(value(snap(), "hud_offset"), 5.5, "hud_offset after release")
        return "category and slider changed on the press frame"
    end)

    run("repeat_starts_on_frame_12", function()
        normalize()
        toOption(1, 2)
        local trace = holdTrace(dpadFrame, "right", 12, "menu_scale", true)
        idle()
        expectTrace(trace, 1, 11, 5.5, "menu_scale")
        approx(trace[12], 6.0, "menu_scale held frame 12")
        return "press on frame 1, first repeat on held frame 12"
    end)

    run("repeat_every_5_frames", function()
        normalize()
        toOption(1, 2)
        local trace = holdTrace(dpadFrame, "right", 27, "menu_scale", true)
        idle()
        expectTrace(trace, 1, 11, 5.5, "menu_scale")
        expectTrace(trace, 12, 16, 6.0, "menu_scale")
        expectTrace(trace, 17, 21, 6.5, "menu_scale")
        expectTrace(trace, 22, 26, 7.0, "menu_scale")
        approx(trace[27], 7.5, "menu_scale held frame 27")
        return "repeats on held frames 12, 17, 22, 27"
    end)

    run("release_resets_repeat", function()
        normalize()
        toOption(1, 2)
        local trace = holdTrace(dpadFrame, "right", 8, "menu_scale", true)
        expectTrace(trace, 1, 8, 5.5, "first hold")
        idle()
        trace = holdTrace(dpadFrame, "right", 12, "menu_scale", true)
        idle()
        expectTrace(trace, 1, 11, 6.0, "after release")
        approx(trace[12], 6.5, "after release held frame 12")
        -- Switching the held direction restarts the timer as well.
        trace = holdTrace(dpadFrame, "left", 8, "menu_scale", true)
        expectTrace(trace, 1, 8, 6.0, "left hold")
        local switched = holdTrace(dpadFrame, "right", 12, "menu_scale", true)
        idle()
        expectTrace(switched, 1, 11, 6.5, "switched to right")
        approx(switched[12], 7.0, "switched to right held frame 12")
        return "release and a direction switch both restart the 12-frame delay"
    end)
end

local function runActionCases()
    run("face_a_selects", function()
        normalize()
        local current = toOption(1, 1)
        local initial = value(current, "open_at_start")
        truthy(type(initial) == "boolean", "open_at_start is not a boolean")
        confirm()
        current = expect("first confirm",
            { open = true, pane = "options", sub = 1, opt = 1, capture = false })
        equal(value(current, "open_at_start"), not initial, "open_at_start after one confirm")
        confirm()
        current = expect("second confirm",
            { open = true, pane = "options", sub = 1, opt = 1, capture = false })
        equal(value(current, "open_at_start"), initial, "open_at_start after two confirms")
        local before = menuState(current)
        press("right")
        expectUnchanged(before, snap(), "right on a boolean")
        press("left")
        current = expect("left on a boolean", { open = true, pane = "subcategory", sub = 1 })
        equal(value(current, "open_at_start"), initial, "left changed the boolean")
        press("right")
        press("right")
        press("right")
        enterOptions(1)
        confirm()
        expect("confirm on a keybind", { open = true, pane = "options", sub = 4, opt = 1, capture = true })
        pressKey("KEY_F2")
        current = expect("capture finished", { open = true, pane = "options", opt = 1, capture = false })
        equal(value(current, "open_menu"), "KEY_F2", "open_menu recaptured as F2")
        return "confirm toggles open_at_start both ways and enters capture on open_menu"
    end)

    run("face_b_backs_out", function()
        normalize()
        toOption(4, 1)
        confirm()
        expect("capture started", { capture = true })
        back()
        local current = expect("back cancels capture",
            { open = true, pane = "options", sub = 4, opt = 1, capture = false })
        equal(value(current, "open_menu"), "KEY_F2", "binding after cancelled capture")
        back()
        expect("back from options", { open = true, pane = "subcategory", sub = 4 })
        back()
        expect("back from subcategories", { open = true, pane = "category", cat = 3 })
        back()
        expect("back from categories", { open = false })
        pressKey("KEY_F2")
        expect("reopened", { open = true, pane = "category", cat = 3 })
        return "capture -> options -> subcategories -> categories -> closed; reopen kept controls"
    end)

    run("dpad_never_confirms", function()
        normalize()
        local before = menuState(snap())
        for frame = 1, 20 do
            send(dpadFrame({ "left" }, frame == 1))
        end
        idle()
        expectUnchanged(before, snap(), "held left in the category pane")
        for frame = 1, 30 do
            send(dpadFrame({ "up" }, frame == 1))
        end
        idle()
        expect("held up in the category pane", { open = true, pane = "category", capture = false })
        normalize()
        toOption(1, 1)
        before = menuState(snap())
        for frame = 1, 30 do
            send(dpadFrame({ "right" }, frame == 1))
        end
        idle()
        expectUnchanged(before, snap(), "held right on a boolean")
        back()
        press("right")
        press("right")
        press("right")
        enterOptions(1)
        before = menuState(snap())
        for frame = 1, 30 do
            send(dpadFrame({ "right" }, frame == 1))
        end
        idle()
        expectUnchanged(before, snap(), "held right on a keybind")
        return "directions never closed the menu, toggled a boolean, or started capture"
    end)

    run("analog_uses_same_navigation", function()
        normalize()
        local function analog(values)
            send(analogFrame(values))
            return snap()
        end
        local current = analog({ down = 0.6 })
        equal(current.categoryIndex, 2, "0.6 presses on its first frame")
        for frame = 2, 11 do
            current = analog({ down = frame == 5 and 0.25 or 0.3 })
            equal(current.categoryIndex, 2, "analog held frame " .. frame)
        end
        current = analog({ down = 0.3 })
        equal(current.categoryIndex, 3, "analog held frame 12 repeats")
        current = analog({ down = 0.2 })
        equal(current.categoryIndex, 3, "0.2 releases without acting")
        current = analog({ down = 0.4 })
        equal(current.categoryIndex, 3, "0.4 after a release stays released")
        current = analog({ down = 0.5 })
        equal(current.categoryIndex, 1, "0.5 presses again")
        analog({})
        current = analog({ right = 0.9 })
        equal(current.pane, "subcategory", "analog right pane")
        equal(current.subcategoryIndex, 1, "analog right subcategory")
        analog({})
        current = analog({ down = 1.0 })
        equal(current.pane, "options", "analog down pane")
        equal(current.optionIndex, 1, "analog down option")
        analog({})
        current = analog({ down = 0.7 })
        equal(current.optionIndex, 2, "analog option down")
        analog({})
        current = analog({ right = 0.55 })
        approx(value(current, "menu_scale"), 5.5, "analog slider right")
        analog({})
        current = analog({ left = 0.8 })
        approx(value(current, "menu_scale"), 5.0, "analog slider left")
        analog({})
        return "hysteresis 0.5/0.25 with the same press and repeat timing"
    end)

    run("keyboard_uses_same_navigation", function()
        normalize()
        local function key(direction)
            send(keyboardFrame({ direction }, true))
            idle()
            return snap()
        end
        local current = key("down")
        equal(current.categoryIndex, 2, "keyboard category down")
        current = key("right")
        equal(current.pane, "subcategory", "keyboard right pane")
        equal(current.subcategoryIndex, 3, "keyboard right subcategory")
        current = key("down")
        equal(current.pane, "options", "keyboard down pane")
        if current.optionIndex ~= 1 then
            current = key("up")
        end
        equal(current.optionIndex, 1, "keyboard options entry")
        current = key("down")
        equal(current.optionIndex, 2, "keyboard option down")
        local trace = holdTrace(keyboardFrame, "right", 12, "hud_offset", true)
        idle()
        expectTrace(trace, 1, 11, 5.5, "keyboard hud_offset")
        approx(trace[12], 6.0, "keyboard hud_offset held frame 12")
        current = key("left")
        approx(value(current, "hud_offset"), 5.5, "keyboard slider left")
        current = key("up")
        equal(current.optionIndex, 1, "keyboard option up")
        current = key("left")
        equal(current.pane, "subcategory", "keyboard left on a boolean")
        current = key("up")
        equal(current.pane, "category", "keyboard up to categories")
        equal(current.categoryIndex, 2, "keyboard category follows general/hud")
        return "digital-only frames drive every pane with the same repeat timing"
    end)

    run("multi_direction_priority", function()
        normalize()
        press("right")
        expect("setup", { pane = "subcategory", sub = 1 })
        send(dpadFrame({ "up", "down", "left", "right" }, true))
        idle()
        expect("all four pressed", { open = true, pane = "category", cat = 1 })
        send(dpadFrame({ "down", "left", "right" }, true))
        idle()
        expect("down, left, right pressed", { open = true, pane = "category", cat = 2 })
        press("right")
        enterOptions(2)
        send(dpadFrame({ "left", "right" }, true))
        idle()
        approx(value(snap(), "hud_offset"), 4.5, "left and right pressed on a slider")
        back()
        press("up")
        expect("setup repeat", { open = true, pane = "category", cat = 2 })
        for frame = 1, 11 do
            send(dpadFrame({ "down" }, frame == 1))
        end
        expect("held down", { pane = "category", cat = 3 })
        local both = dpadFrame({ "down" }, false)
        both.triggered.right = true
        both.held.right = true
        both.analog.right = 1.0
        send(both)
        idle()
        expect("down repeat beats a new right press", { open = true, pane = "category", cat = 1 })
        return "one action per frame in up, down, left, right order"
    end)

    -- The captured direction is up: reaching and moving inside the keybind options never
    -- needs it (right, down and wrapping down do), whichever pane a reopen restores.
    local function reenterKeybindRow(row)
        local current = snap()
        if current.pane == "category" then
            press("right")
            current = snap()
        end
        if current.pane == "subcategory" then
            press("down")
            current = snap()
        end
        equal(current.pane, "options", "re-enter keybind options pane")
        equal(current.subcategoryIndex, 4, "re-enter keybind subcategory")
        if current.optionIndex ~= row then
            press("down")
        end
        return expect("re-enter keybind row", { open = true, pane = "options", sub = 4, opt = row })
    end

    run("keybind_capture_consumes_dpad_and_open_binding_wins", function()
        normalize()
        toOption(4, 1)
        confirm()
        expect("capture open_menu", { open = true, pane = "options", opt = 1, capture = true })
        send(dpadFrame({ "up" }, true))
        local current = expect("d-pad captured",
            { open = true, pane = "options", sub = 4, opt = 1, capture = false })
        equal(value(current, "open_menu"), "ACTION_MENUUP", "captured open_menu")
        idle()
        expect("after release", { open = true, pane = "options", sub = 4, opt = 1, capture = false })
        press("up")
        expect("bound up closes", { open = false })
        press("up")
        expect("bound up reopens without navigating", { open = true, cat = 3, sub = 4, opt = 1 })
        reenterKeybindRow(1)
        pressKey("KEY_F2")
        expect("F2 is no longer bound", { open = true })
        press("down")
        expect("reset_config row", { pane = "options", opt = 2 })
        confirm()
        expect("capture reset_config", { capture = true })
        pressKey("KEY_F2")
        current = expect("F2 captured during capture",
            { open = true, pane = "options", opt = 2, capture = false })
        equal(value(current, "reset_config"), "KEY_F2", "captured reset_config")
        confirm()
        expect("capture reset_config again", { capture = true })
        send(dpadFrame({ "up" }, true))
        current = expect("identical d-pad bindings",
            { open = true, pane = "options", opt = 2, capture = false })
        equal(value(current, "reset_config"), "ACTION_MENUUP", "captured reset_config")
        idle()
        press("up")
        current = expect("identical binding closes only", { open = false })
        equal(value(current, "reset_config"), "ACTION_MENUUP", "reset ran with the toggle")
        press("up")
        current = expect("identical binding reopens only", { open = true, cat = 3, sub = 4, opt = 2 })
        equal(value(current, "open_menu"), "ACTION_MENUUP", "open_menu after identical presses")
        equal(value(current, "reset_config"), "ACTION_MENUUP", "reset_config after identical presses")
        reenterKeybindRow(1)
        confirm()
        pressKey("KEY_F2")
        current = expect("open_menu restored", { open = true, pane = "options", opt = 1, capture = false })
        equal(value(current, "open_menu"), "KEY_F2", "open_menu restored to F2")
        press("up")
        current = expect("bound up resets without navigating",
            { open = true, pane = "options", sub = 4, opt = 1, capture = false })
        equal(value(current, "open_menu"), "KEY_F2", "open_menu after reset")
        equal(value(current, "reset_config"), "KEY_F3", "reset_config after reset")
        return "captured d-pad up and F2 without acting; open_menu won identical bindings; "
            .. "bound presses never navigated"
    end)
end

-- Render case (real MC_POST_RENDER frames) ---------------------------------------------
-- Each stage injects input on one update frame; the next stage runs only after two
-- more MC_POST_RENDER frames have completed and checks what the submission's own render
-- callback recorded, then sets up the following pane.

local function describeDraws(draws)
    local simplified = {}
    for index, entry in ipairs(type(draws) == "table" and draws or {}) do
        if type(entry) == "table" then
            simplified[index] = {
                pane = tostring(entry.pane),
                rowId = tostring(entry.rowId),
                text = tostring(entry.text),
                selected = tostring(entry.selected),
            }
        else
            simplified[index] = tostring(entry)
        end
    end
    local ok, encoded = pcall(json.encode, simplified)
    return ok and tostring(encoded) or "<unencodable draws>"
end

-- Row text may be recorded with its "> " / "  " marker or as the bare row text, but one
-- frame must use a single form.
local function checkDraws(current, expected, label)
    local draws = current.lastDraws
    truthy(type(draws) == "table", label .. ": lastDraws is not a table")
    if #draws ~= #expected.rows then
        error(label .. ": expected " .. #expected.rows .. " draw records, received "
            .. #draws .. " " .. describeDraws(draws))
    end
    local form = nil
    for index, row in ipairs(expected.rows) do
        local entry = draws[index]
        truthy(type(entry) == "table", label .. ": draw " .. index .. " is not a record")
        local selected = index == expected.selected
        equal(entry.pane, expected.pane, label .. ": draw " .. index .. " pane")
        equal(entry.rowId, row.id, label .. ": draw " .. index .. " rowId")
        equal(entry.selected and true or false, selected, label .. ": draw " .. index .. " selected")
        local marked = (selected and "> " or "  ") .. row.text
        local rowForm = nil
        if entry.text == marked then
            rowForm = "marked"
        elseif entry.text == row.text then
            rowForm = "bare"
        end
        truthy(rowForm, label .. ": draw " .. index .. " text " .. tostring(entry.text)
            .. " (expected " .. marked .. ")")
        form = form or rowForm
        equal(rowForm, form, label .. ": draw " .. index .. " text form")
        if entry.x ~= nil then
            approx(entry.x, 24, label .. ": draw " .. index .. " x")
        end
        if entry.y ~= nil then
            approx(entry.y, 24 + 16 * (index - 1), label .. ": draw " .. index .. " y")
        end
    end
    return form
end

local function checkRendered(job, label)
    local current = snap()
    expectUnchanged(job.before, current, label .. " state after rendering")
    equal(current.renderErrorCount, 0, label .. " renderErrorCount")
    job.forms[#job.forms + 1] = checkDraws(current, job.expected, label) or "none"
end

local renderStages = {
    function(job)
        normalize()
        press("down")
        job.expected = { pane = "category", rows = rowsOf(CATEGORY_IDS), selected = 2 }
        job.before = menuState(snap())
    end,
    function(job)
        checkRendered(job, "category pane")
        press("right")
        job.expected = { pane = "subcategory", rows = rowsOf(SUBCATEGORY_IDS), selected = 3 }
        job.before = menuState(snap())
    end,
    function(job)
        checkRendered(job, "subcategory pane")
        enterOptions(2)
        press("left")
        local current = snap()
        approx(value(current, "hud_offset"), 4.5, "render setup hud_offset")
        job.expected = {
            pane = "options",
            rows = {
                { id = "show_hud", text = "show_hud = " .. tostring(value(current, "show_hud")) },
                { id = "hud_offset", text = "hud_offset = 4.5" },
            },
            selected = 2,
        }
        job.before = menuState(current)
    end,
    function(job)
        checkRendered(job, "general/hud options")
        back()
        press("right")
        enterOptions(1)
        job.expected = {
            pane = "options",
            rows = {
                { id = "open_menu", text = "open_menu = KEY_F2" },
                { id = "reset_config", text = "reset_config = KEY_F3" },
            },
            selected = 1,
        }
        job.before = menuState(snap())
    end,
    function(job)
        checkRendered(job, "controls/keybinds options")
        pressKey("KEY_F3")
        pressKey("KEY_F2")
        local current = expect("render close", { open = false })
        job.expected = { pane = "none", rows = {}, selected = 0 }
        job.before = menuState(current)
    end,
}

local function finish()
    if finished then
        return
    end
    finished = true
    log("[GCB_SUMMARY] passed=" .. tostring(passed)
        .. " failed=" .. tostring(failed)
        .. " total=" .. tostring(passed + failed))
end

local function failRender(detail)
    renderJob = nil
    record(RENDER_CASE, false, detail)
    finish()
end

local function advanceRenderJob()
    local job = renderJob
    if job.waitMark ~= nil then
        if renderFrames - job.waitMark < 2 then
            if updateFrames - job.waitStarted > RENDER_WAIT_BUDGET then
                failRender("no MC_POST_RENDER frames within " .. RENDER_WAIT_BUDGET
                    .. " updates before stage " .. job.stage
                    .. " (game frame " .. tostring(game:GetFrameCount()) .. ")")
            end
            return
        end
        job.waitMark = nil
    end
    if job.stage > #renderStages then
        renderJob = nil
        run("render_tracks_current_pane_and_selection", function()
            checkRendered(job, "closed menu")
            return "category, subcategory, option and keybind panes drawn with one selected row; "
                .. "nothing drawn while closed; text form=" .. tostring(job.forms[1])
        end)
        finish()
        return
    end
    local ok, err = pcall(renderStages[job.stage], job)
    if not ok then
        failRender("stage " .. job.stage .. ": " .. tostring(err))
        return
    end
    job.stage = job.stage + 1
    job.waitMark = renderFrames
    job.waitStarted = updateFrames
end

local function executeSuite()
    captureBaseline()
    runStateCases()
    runCategoryCases()
    runSubcategoryCases()
    runOptionCases()
    runTimingCases()
    runActionCases()
    -- Leave the menu closed at defaults until the render case starts; a submission that
    -- cannot even be normalized fails that case on its first stage instead.
    pcall(function()
        normalize()
        pressKey("KEY_F2")
    end)
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
        local ok, err = pcall(executeSuite)
        if not ok then
            log("[GCB_FATAL] " .. tostring(err))
            finish()
        end
        return
    end
    if updateFrames < RENDER_START_FRAME then
        return
    end
    if not renderStarted then
        renderStarted = true
        renderJob = { stage = 1, waitMark = nil, waitStarted = nil, forms = {} }
    end
    if renderJob == nil then
        finish()
        return
    end
    local ok, err = pcall(advanceRenderJob)
    if not ok then
        log("[GCB_FATAL] " .. tostring(err))
        finish()
    end
end)
