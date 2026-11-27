local mod = RegisterMod("Construct Config Navigation Reference", 1)

local CATEGORIES = { "menu", "general", "controls" }
local SUBCATEGORIES = {
    { id = "menu/main", category = 1, options = { "open_at_start", "menu_scale" } },
    { id = "menu/demo", category = 1, options = { "demo_mode", "demo_rate" } },
    { id = "general/hud", category = 2, options = { "show_hud", "hud_offset" } },
    { id = "controls/keybinds", category = 3, options = { "open_menu", "reset_config" } },
}
local OPTION_KINDS = {
    open_at_start = "boolean",
    menu_scale = "slider",
    demo_mode = "boolean",
    demo_rate = "slider",
    show_hud = "boolean",
    hud_offset = "slider",
    open_menu = "keybind",
    reset_config = "keybind",
}
local DEFAULTS = {
    open_at_start = false,
    menu_scale = 5.0,
    demo_mode = false,
    demo_rate = 5.0,
    show_hud = true,
    hud_offset = 5.0,
    open_menu = "KEY_F2",
    reset_config = "KEY_F3",
}
local SLIDER_MIN = 0.0
local SLIDER_MAX = 10.0
local SLIDER_STEP = 0.5
local FIRST_REPEAT_FRAME = 12
local REPEAT_INTERVAL = 5
local ANALOG_PRESS = 0.5
local ANALOG_RELEASE = 0.25
local DRAW_X = 24
local DRAW_Y = 24
local ROW_HEIGHT = 16

-- Menu directions in action priority order, then the two face actions.
local DIRECTIONS = { "up", "down", "left", "right" }
local ACTIONS = { "up", "down", "left", "right", "confirm", "back" }
local ACTION_ENUM_NAMES = {
    up = "ACTION_MENUUP",
    down = "ACTION_MENUDOWN",
    left = "ACTION_MENULEFT",
    right = "ACTION_MENURIGHT",
    confirm = "ACTION_MENUCONFIRM",
    back = "ACTION_MENUBACK",
}
-- Symbolic binding names of the menu directions; KEY_F1..KEY_F12 are the others.
local DIRECTION_SYMBOLS = {
    up = "ACTION_MENUUP",
    down = "ACTION_MENUDOWN",
    left = "ACTION_MENULEFT",
    right = "ACTION_MENURIGHT",
}
local DIRECTION_OF_SYMBOL = {
    ACTION_MENUUP = "up",
    ACTION_MENUDOWN = "down",
    ACTION_MENULEFT = "left",
    ACTION_MENURIGHT = "right",
}

local function defaultConfig()
    local config = {}
    for optionId, value in pairs(DEFAULTS) do
        config[optionId] = value
    end
    return config
end

local state = {
    open = false,
    pane = "category",
    categoryIndex = 1,
    subcategoryIndex = 1,
    optionIndex = 1,
    capture = false,
    captureOption = nil,
    repeatDirection = nil,
    repeatFrames = 0,
    config = defaultConfig(),
    lastDraws = {},
    renderErrorCount = 0,
    inputErrorCount = 0,
}

-- Input memory between frames: the held state of every action, the analog hysteresis
-- state of every direction, and directions whose current press was consumed (by a
-- binding, by keybind capture, or while the menu was closed) until they are released.
local previousHeld = {}
local analogHeld = {}
local consumed = {}

local function wrap(index, count)
    return (index - 1) % count + 1
end

local function clamp(value, low, high)
    if value < low then
        return low
    end
    if value > high then
        return high
    end
    return value
end

local function currentSubcategory()
    return SUBCATEGORIES[state.subcategoryIndex]
end

local function currentOptionId()
    return currentSubcategory().options[state.optionIndex]
end

local function inputTable(frameInput, name)
    local value = type(frameInput) == "table" and frameInput[name] or nil
    if type(value) == "table" then
        return value
    end
    return {}
end

-- Resolve one frame of input into held and newly pressed actions. A direction is held
-- while its digital action is pressed or its analog value keeps the hysteresis latched.
local function readInput(frameInput)
    local triggered = inputTable(frameInput, "triggered")
    local held = inputTable(frameInput, "held")
    local analog = inputTable(frameInput, "analog")
    local keys = inputTable(frameInput, "keys")
    local isHeld = {}
    local newPress = {}
    for _, action in ipairs(ACTIONS) do
        local pressed = (held[action] or triggered[action]) and true or false
        if DIRECTION_SYMBOLS[action] then
            local value = tonumber(analog[action]) or 0
            if value >= ANALOG_PRESS then
                analogHeld[action] = true
            elseif value < ANALOG_RELEASE then
                analogHeld[action] = false
            end
            pressed = pressed or analogHeld[action] == true
        end
        isHeld[action] = pressed
        newPress[action] = pressed and (triggered[action] and true or not previousHeld[action])
        if not pressed or newPress[action] then
            consumed[action] = nil
        end
    end
    return isHeld, newPress, keys
end

local function consumeHeldDirections(isHeld)
    for _, direction in ipairs(DIRECTIONS) do
        if isHeld[direction] then
            consumed[direction] = true
        end
    end
    state.repeatDirection = nil
    state.repeatFrames = 0
end

local function bindingPressed(symbol, newPress, keys)
    if type(symbol) ~= "string" then
        return false, nil
    end
    local direction = DIRECTION_OF_SYMBOL[symbol]
    if direction then
        return newPress[direction] == true, direction
    end
    return keys[symbol] and true or false, nil
end

local function captureSymbol(newPress, keys)
    for _, direction in ipairs(DIRECTIONS) do
        if newPress[direction] then
            return DIRECTION_SYMBOLS[direction]
        end
    end
    for number = 1, 12 do
        local symbol = "KEY_F" .. number
        if keys[symbol] then
            return symbol
        end
    end
    return nil
end

local function endCapture()
    state.capture = false
    state.captureOption = nil
end

-- While capturing, the first direction or F-key becomes the binding and back cancels;
-- the configured bindings and navigation are suspended for the whole frame.
local function stepCapture(isHeld, newPress, keys)
    if newPress.back then
        endCapture()
    else
        local symbol = captureSymbol(newPress, keys)
        if symbol then
            state.config[state.captureOption] = symbol
            endCapture()
        end
    end
    consumeHeldDirections(isHeld)
end

-- open_menu is matched first; an identical reset_config binding never fires with it.
local function stepBindings(newPress, keys)
    local openSymbol = state.config.open_menu
    local resetSymbol = state.config.reset_config
    local openPressed, openDirection = bindingPressed(openSymbol, newPress, keys)
    if openPressed then
        state.open = not state.open
        if openDirection then
            consumed[openDirection] = true
        end
    end
    if resetSymbol ~= openSymbol then
        local resetPressed, resetDirection = bindingPressed(resetSymbol, newPress, keys)
        if resetPressed and state.open then
            state.config = defaultConfig()
            if resetDirection then
                consumed[resetDirection] = true
            end
        end
    end
end

local function selectSubcategory(index)
    if index ~= state.subcategoryIndex then
        state.optionIndex = 1
    end
    state.subcategoryIndex = index
    state.categoryIndex = SUBCATEGORIES[index].category
end

local function firstSubcategoryOf(categoryIndex)
    for index, subcategory in ipairs(SUBCATEGORIES) do
        if subcategory.category == categoryIndex then
            return index
        end
    end
    return 1
end

local function applyDirection(direction)
    if state.pane == "category" then
        if direction == "up" then
            state.categoryIndex = wrap(state.categoryIndex - 1, #CATEGORIES)
        elseif direction == "down" then
            state.categoryIndex = wrap(state.categoryIndex + 1, #CATEGORIES)
        elseif direction == "right" then
            selectSubcategory(firstSubcategoryOf(state.categoryIndex))
            state.pane = "subcategory"
        end
    elseif state.pane == "subcategory" then
        if direction == "up" then
            state.pane = "category"
        elseif direction == "down" then
            state.pane = "options"
        elseif direction == "left" then
            selectSubcategory(wrap(state.subcategoryIndex - 1, #SUBCATEGORIES))
        else
            selectSubcategory(wrap(state.subcategoryIndex + 1, #SUBCATEGORIES))
        end
    else
        local optionCount = #currentSubcategory().options
        if direction == "up" then
            state.optionIndex = wrap(state.optionIndex - 1, optionCount)
        elseif direction == "down" then
            state.optionIndex = wrap(state.optionIndex + 1, optionCount)
        else
            local optionId = currentOptionId()
            if OPTION_KINDS[optionId] == "slider" then
                local delta = direction == "left" and -SLIDER_STEP or SLIDER_STEP
                state.config[optionId] = clamp(state.config[optionId] + delta, SLIDER_MIN, SLIDER_MAX)
            elseif direction == "left" then
                state.pane = "subcategory"
            end
        end
    end
end

local function applyConfirm()
    if state.pane ~= "options" then
        return false
    end
    local optionId = currentOptionId()
    local kind = OPTION_KINDS[optionId]
    if kind == "boolean" then
        state.config[optionId] = not state.config[optionId]
        return true
    end
    if kind == "keybind" then
        state.capture = true
        state.captureOption = optionId
        return true
    end
    return false
end

local function applyBack()
    if state.pane == "options" then
        state.pane = "subcategory"
    elseif state.pane == "subcategory" then
        state.pane = "category"
    else
        state.open = false
    end
end

local function isRepeatFrame(frames)
    return frames == FIRST_REPEAT_FRAME
        or (frames > FIRST_REPEAT_FRAME and (frames - FIRST_REPEAT_FRAME) % REPEAT_INTERVAL == 0)
end

-- One direction action per frame: new presses and the selected direction's scheduled
-- repeat compete in priority order. A new press becomes the selected held direction
-- with a fresh timer (held frame 1).
local function stepDirections(isHeld, newPress)
    local eligible = {}
    for _, direction in ipairs(DIRECTIONS) do
        eligible[direction] = isHeld[direction] and not consumed[direction]
    end
    local selected = state.repeatDirection
    local scheduled = nil
    if selected and eligible[selected] and not newPress[selected] then
        state.repeatFrames = state.repeatFrames + 1
        if isRepeatFrame(state.repeatFrames) then
            scheduled = selected
        end
    end

    local chosen = nil
    for _, direction in ipairs(DIRECTIONS) do
        if eligible[direction] and (newPress[direction] or direction == scheduled) then
            chosen = direction
            break
        end
    end
    if chosen then
        applyDirection(chosen)
    end

    if chosen and newPress[chosen] then
        state.repeatDirection = chosen
        state.repeatFrames = 1
    elseif selected and eligible[selected] then
        if newPress[selected] then
            state.repeatFrames = 1
        end
    else
        -- The selected direction was released or consumed: another held direction, if
        -- any, becomes the selected one and its timer starts over.
        local replacement = nil
        for _, direction in ipairs(DIRECTIONS) do
            if eligible[direction] then
                replacement = direction
                break
            end
        end
        state.repeatDirection = replacement
        state.repeatFrames = replacement and 1 or 0
    end
end

local function step(frameInput)
    local isHeld, newPress, keys = readInput(frameInput)
    if state.capture then
        stepCapture(isHeld, newPress, keys)
    else
        stepBindings(newPress, keys)
        if not state.open then
            consumeHeldDirections(isHeld)
        elseif newPress.back then
            applyBack()
            consumeHeldDirections(isHeld)
        elseif newPress.confirm and applyConfirm() then
            consumeHeldDirections(isHeld)
        else
            stepDirections(isHeld, newPress)
        end
    end
    for _, action in ipairs(ACTIONS) do
        previousHeld[action] = isHeld[action]
    end
end

local function snapshot()
    local config = {}
    for optionId, value in pairs(state.config) do
        config[optionId] = value
    end
    local draws = {}
    for index, record in ipairs(state.lastDraws) do
        draws[index] = {
            pane = record.pane,
            rowId = record.rowId,
            text = record.text,
            selected = record.selected,
            x = record.x,
            y = record.y,
        }
    end
    return {
        open = state.open,
        pane = state.pane,
        categoryIndex = state.categoryIndex,
        subcategoryIndex = state.subcategoryIndex,
        optionIndex = state.optionIndex,
        capture = state.capture,
        repeatDirection = state.repeatDirection,
        repeatFrames = state.repeatFrames,
        config = config,
        lastDraws = draws,
        renderErrorCount = state.renderErrorCount,
    }
end

IsaacConstructNavigation = {
    Step = step,
    Snapshot = snapshot,
}

-- Real input: menu actions of the keyboard (controller 0) and of player one's
-- controller, analog values from the same actions, and F1-F12 from the keyboard.
local function controllerIndices()
    local indices = { 0 }
    local player = Isaac.GetPlayer(0)
    local index = player and player.ControllerIndex
    if type(index) == "number" and index ~= 0 then
        indices[2] = index
    end
    return indices
end

local function pollActions(frameInput)
    local indices = controllerIndices()
    for _, action in ipairs(ACTIONS) do
        local buttonAction = ButtonAction[ACTION_ENUM_NAMES[action]]
        local analogValue = 0
        for _, index in ipairs(indices) do
            if Input.IsActionTriggered(buttonAction, index) then
                frameInput.triggered[action] = true
            end
            if Input.IsActionPressed(buttonAction, index) then
                frameInput.held[action] = true
            end
            if DIRECTION_SYMBOLS[action] then
                local value = Input.GetActionValue(buttonAction, index)
                if type(value) == "number" and value > analogValue then
                    analogValue = value
                end
            end
        end
        if DIRECTION_SYMBOLS[action] then
            frameInput.analog[action] = analogValue
        end
    end
end

local function pollKeys(frameInput)
    for number = 1, 12 do
        local symbol = "KEY_F" .. number
        local key = Keyboard[symbol]
        if key ~= nil and Input.IsButtonTriggered(key, 0) then
            frameInput.keys[symbol] = true
        end
    end
end

local function pollFrameInput()
    local frameInput = { triggered = {}, held = {}, analog = {}, keys = {} }
    if not pcall(pollActions, frameInput) then
        state.inputErrorCount = state.inputErrorCount + 1
        frameInput.triggered, frameInput.held, frameInput.analog = {}, {}, {}
    end
    if not pcall(pollKeys, frameInput) then
        state.inputErrorCount = state.inputErrorCount + 1
        frameInput.keys = {}
    end
    return frameInput
end

local menuFont = nil
local textColor = nil

local function loadFont()
    if menuFont == nil then
        local font = Font()
        font:Load("font/terminus.fnt")
        textColor = KColor(1, 1, 1, 1)
        menuFont = font
    end
    return menuFont, textColor
end

local function valueText(optionId)
    local value = state.config[optionId]
    if OPTION_KINDS[optionId] == "slider" then
        return string.format("%.1f", value)
    end
    return tostring(value)
end

local function activeRows()
    local rows = {}
    if state.pane == "category" then
        for index, categoryId in ipairs(CATEGORIES) do
            rows[index] = { id = categoryId, text = categoryId }
        end
        return rows, state.categoryIndex
    end
    if state.pane == "subcategory" then
        for index, subcategory in ipairs(SUBCATEGORIES) do
            rows[index] = { id = subcategory.id, text = subcategory.id }
        end
        return rows, state.subcategoryIndex
    end
    for index, optionId in ipairs(currentSubcategory().options) do
        rows[index] = { id = optionId, text = optionId .. " = " .. valueText(optionId) }
    end
    return rows, state.optionIndex
end

-- Drawing reads the menu state and records what it drew; it never changes the menu,
-- the configuration, or saved data.
local function renderActivePane()
    local draws = {}
    if state.open then
        local rows, selectedIndex = activeRows()
        local fontReady, font, color = pcall(loadFont)
        for index, row in ipairs(rows) do
            local selected = index == selectedIndex
            local text = (selected and "> " or "  ") .. row.text
            local x = DRAW_X
            local y = DRAW_Y + ROW_HEIGHT * (index - 1)
            local drawn = fontReady and pcall(function()
                font:DrawString(text, x, y, color, 0, false)
            end)
            if drawn then
                draws[#draws + 1] = {
                    pane = state.pane,
                    rowId = row.id,
                    text = text,
                    selected = selected,
                    x = x,
                    y = y,
                }
            else
                state.renderErrorCount = state.renderErrorCount + 1
            end
        end
    end
    state.lastDraws = draws
end

mod:AddCallback(ModCallbacks.MC_POST_RENDER, function()
    step(pollFrameInput())
    renderActivePane()
end)
