local mod = RegisterMod("Construct Option Rendering Reference", 1)

-- Normal text alpha: the supplied normal KColor's Alpha (1.0 for the canonical baseline)
-- for a selectable option in the focused pane, and exactly 0.4 for an option in an
-- unfocused pane or a disabled option, whether or not it is selected.
local INACTIVE_ALPHA = 0.4
local FALLBACK_ALPHA = 1.0
local CURSOR_OFFSET_X = 12
local KINDS = { boolean = true, slider = true, text = true }
-- Built-in game fonts; the first one that loads is the mod-owned option font.
local FONT_PATHS = {
    "font/terminus.fnt",
    "font/pftempestasevencondensed.fnt",
    "font/teammeatfont10.fnt",
}

local state = {
    options = {},
    order = {},
    palette = {},
    context = {},
    lastRender = {},
    renderErrorCount = 0,
}
local font = nil
local fontAttempted = false

local function isFinite(value)
    return type(value) == "number"
        and value == value
        and value ~= math.huge
        and value ~= -math.huge
end

local function finiteOr(value, fallback)
    if isFinite(value) then
        return value
    end
    return fallback
end

-- Reads one field of a KColor/Color userdata or of a plain table. A missing accessor
-- yields nil instead of raising inside the render callback.
local function field(source, key)
    if source == nil then
        return nil
    end
    local ok, value = pcall(function()
        return source[key]
    end)
    if ok then
        return value
    end
    return nil
end

local function copyFlat(source)
    if source == nil then
        return nil
    end
    local copy = {}
    for key, value in pairs(source) do
        copy[key] = value
    end
    return copy
end

local function validId(id)
    return type(id) == "string" and id ~= ""
end

-- A custom color is a dense array of exactly three finite numbers in [0,1].
local function parseRgb(rgb)
    if type(rgb) ~= "table" then
        return nil
    end
    local count = 0
    for key in pairs(rgb) do
        if key ~= 1 and key ~= 2 and key ~= 3 then
            return nil
        end
        count = count + 1
    end
    if count ~= 3 then
        return nil
    end
    for index = 1, 3 do
        local value = rgb[index]
        if not isFinite(value) or value < 0 or value > 1 then
            return nil
        end
    end
    return { red = rgb[1], green = rgb[2], blue = rgb[3] }
end

local function fontLoaded(candidate)
    local ok, loaded = pcall(function()
        return candidate:IsLoaded()
    end)
    if ok then
        return loaded == true
    end
    return true
end

-- The font is created and loaded once; palette updates never reconstruct it.
local function ensureFont()
    if fontAttempted then
        return font
    end
    fontAttempted = true
    local ok, created = pcall(Font)
    if not ok or created == nil then
        return nil
    end
    for _, path in ipairs(FONT_PATHS) do
        local loadOk = pcall(function()
            created:Load(path)
        end)
        if loadOk and fontLoaded(created) then
            font = created
            return font
        end
    end
    return nil
end

local function newSliderSprite()
    local ok, sprite = pcall(Sprite)
    if ok then
        return sprite
    end
    return nil
end

local function normalTextAlpha(option)
    if option.selectable and option.focused then
        return finiteOr(field(option.normalTextColor, "Alpha"), FALLBACK_ALPHA)
    end
    return INACTIVE_ALPHA
end

local function textColor(option, custom)
    local alpha = normalTextAlpha(option)
    if custom then
        return { red = custom.red, green = custom.green, blue = custom.blue, alpha = alpha }
    end
    local normal = option.normalTextColor
    return {
        red = finiteOr(field(normal, "Red"), 1),
        green = finiteOr(field(normal, "Green"), 1),
        blue = finiteOr(field(normal, "Blue"), 1),
        alpha = alpha,
    }
end

local function sliderColor(option, custom, alpha)
    if custom then
        return {
            red = custom.red,
            green = custom.green,
            blue = custom.blue,
            alpha = alpha,
            ro = 0,
            go = 0,
            bo = 0,
        }
    end
    local normal = option.normalSliderColor
    return {
        red = finiteOr(field(normal, "R"), 1),
        green = finiteOr(field(normal, "G"), 1),
        blue = finiteOr(field(normal, "B"), 1),
        alpha = finiteOr(field(normal, "A"), alpha),
        ro = finiteOr(field(normal, "RO"), 0),
        go = finiteOr(field(normal, "GO"), 0),
        bo = finiteOr(field(normal, "BO"), 0),
    }
end

-- Afterbirth+ Color offsets are integers.
local function colorOffset(value)
    return math.floor(value + 0.5)
end

local function applySliderColor(sprite, color)
    if sprite == nil then
        return
    end
    sprite.Color = Color(color.red, color.green, color.blue, color.alpha,
        colorOffset(color.ro), colorOffset(color.go), colorOffset(color.bo))
end

local function displayText(option)
    if option.kind == "boolean" then
        return option.id .. ": " .. (option.value and "On" or "Off")
    end
    return option.id .. ": " .. tostring(option.value)
end

local function drawOption(option, intent)
    local target = ensureFont()
    if target == nil then
        return
    end
    local text = intent.text
    local color = KColor(text.red, text.green, text.blue, text.alpha)
    local label = displayText(option)
    target:DrawString(label, intent.x, intent.y, color, 0, false)
    if intent.selected then
        target:DrawString(">", intent.cursorX, intent.cursorY, color, 0, false)
    end
    if intent.strikeout then
        target:DrawString(string.rep("-", #label), intent.x, intent.y, color, 0, false)
    end
end

local function renderOption(option)
    local custom = state.palette[option.id]
    local text = textColor(option, custom)
    local intent = {
        id = option.id,
        kind = option.kind,
        value = option.value,
        category = state.context.category,
        x = option.x,
        y = option.y,
        cursorX = option.x - CURSOR_OFFSET_X,
        cursorY = option.y,
        strikeout = option.kind == "boolean" and option.value == false,
        text = text,
        focused = option.focused,
        selected = option.selected,
        disabled = not option.selectable,
    }
    if option.kind == "slider" then
        intent.slider = sliderColor(option, custom, text.alpha)
    end
    local ok = pcall(function()
        if intent.slider then
            applySliderColor(option.sprite, intent.slider)
        end
        drawOption(option, intent)
    end)
    if not ok then
        state.renderErrorCount = state.renderErrorCount + 1
    end
    return intent
end

local function render()
    local intents = {}
    for _, id in ipairs(state.order) do
        local option = state.options[id]
        if option then
            intents[#intents + 1] = renderOption(option)
        end
    end
    state.lastRender = intents
    return #intents
end

-- The one renderer shared by MC_POST_RENDER and RenderNow; it never raises.
local function renderFrame()
    local ok, count = pcall(render)
    if not ok then
        state.renderErrorCount = state.renderErrorCount + 1
        return 0
    end
    return count
end

local function upsertOption(id, kind, value, renderState)
    if not validId(id)
        or not KINDS[kind]
        or type(renderState) ~= "table"
        or not isFinite(renderState.x)
        or not isFinite(renderState.y) then
        return false
    end
    local option = state.options[id]
    if option == nil then
        option = { id = id }
        state.options[id] = option
        state.order[#state.order + 1] = id
    end
    option.kind = kind
    option.value = value
    option.selectable = renderState.selectable ~= false
    option.selected = renderState.selected == true
    option.focused = renderState.focused == true
    option.x = renderState.x
    option.y = renderState.y
    option.normalTextColor = renderState.normalTextColor
    option.normalSliderColor = renderState.normalSliderColor
    if kind == "slider" then
        option.sprite = option.sprite or newSliderSprite()
    else
        option.sprite = nil
    end
    return true
end

local function removeOption(id)
    if not validId(id) or state.options[id] == nil then
        return false
    end
    state.options[id] = nil
    state.palette[id] = nil
    for index = #state.order, 1, -1 do
        if state.order[index] == id then
            table.remove(state.order, index)
        end
    end
    return true
end

local function setOptionOrder(ids)
    if type(ids) ~= "table" then
        return false
    end
    local order = {}
    local seen = {}
    for _, id in ipairs(ids) do
        if state.options[id] ~= nil and not seen[id] then
            seen[id] = true
            order[#order + 1] = id
        end
    end
    for _, id in ipairs(state.order) do
        if not seen[id] then
            seen[id] = true
            order[#order + 1] = id
        end
    end
    state.order = order
    return true
end

local function setOptionColor(id, rgb)
    if not validId(id) or state.options[id] == nil then
        return false
    end
    local color = parseRgb(rgb)
    if color == nil then
        return false
    end
    state.palette[id] = color
    return true
end

local function clearOptionColor(id)
    if not validId(id) then
        return false
    end
    state.palette[id] = nil
    return true
end

local function setRenderContext(context)
    if context ~= nil and type(context) ~= "table" then
        return false
    end
    local copy = {}
    for key, value in pairs(context or {}) do
        local valueType = type(value)
        if valueType == "string" or valueType == "number" or valueType == "boolean" then
            copy[key] = value
        end
    end
    state.context = copy
    return true
end

local function snapshot()
    local palette = {}
    for id, color in pairs(state.palette) do
        palette[id] = { red = color.red, green = color.green, blue = color.blue }
    end
    local lastRender = {}
    for index, intent in ipairs(state.lastRender) do
        local copy = copyFlat(intent)
        copy.text = copyFlat(intent.text)
        copy.slider = copyFlat(intent.slider)
        lastRender[index] = copy
    end
    local order = {}
    for index, id in ipairs(state.order) do
        order[index] = id
    end
    return {
        palette = palette,
        lastRender = lastRender,
        renderErrorCount = state.renderErrorCount,
        order = order,
        context = copyFlat(state.context),
    }
end

IsaacConstructPalette = {
    UpsertOption = upsertOption,
    RemoveOption = removeOption,
    SetOptionOrder = setOptionOrder,
    SetOptionColor = setOptionColor,
    ClearOptionColor = clearOptionColor,
    SetRenderContext = setRenderContext,
    RenderNow = renderFrame,
    Snapshot = snapshot,
}

mod:AddCallback(ModCallbacks.MC_POST_RENDER, function()
    renderFrame()
end)
