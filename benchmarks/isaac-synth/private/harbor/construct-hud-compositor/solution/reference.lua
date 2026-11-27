local mod = RegisterMod("Construct HUD Compositor Reference", 1)
local game = Game()

local HINT_TEXT = "Press F2 to open configuration"
local WARNING_TEXT = "Restart to apply settings"
-- The hint is drawn for elapsed frames 0..899 and hidden from frame 900 on.
local HINT_FRAMES = 900
-- alpha = clamp((900 - elapsedFrames) / 61, 0, 1): 1.0 through frame 839, then a linear fade.
local FADE_FRAMES = 61
-- A message in the lower slot is drawn at brY - 28; the hint moves to brY - 48 while a
-- warning occupies the lower slot.
local LOWER_SLOT = 28
local UPPER_SLOT = 48
local OFFSET_MIN = 0
local OFFSET_MAX = 10
local FONT_PATH = "font/terminus.fnt"

-- Timer, compositor and render state only; this mod keeps no save data and never touches
-- seed effects.
--
-- elapsedFrames counts the compositor frames rendered since the last MC_POST_GAME_STARTED.
-- A frame is drawn with the value it has *before* the frame, then the counter advances by
-- one: the first frame after a game start draws elapsed frame 0 and leaves elapsedFrames
-- at 1. Snapshot().elapsedFrames is therefore the elapsed frame the next render draws, and
-- the records in Snapshot().lastDraws were drawn at elapsedFrames - 1.
local state = {
    elapsedFrames = 0,
    warningPending = false,
    hudOffset = 0,
    bottomRightX = nil,
    bottomRightY = nil,
    lastDraws = {},
}

local font = Font()
local fontLoadAttempts = 0

local function loadFont()
    fontLoadAttempts = fontLoadAttempts + 1
    pcall(function()
        font:Load(FONT_PATH)
    end)
end
loadFont()

local function ensureFont()
    local ok, loaded = pcall(function()
        return font:IsLoaded()
    end)
    if (not ok or not loaded) and fontLoadAttempts < 3 then
        loadFont()
    end
end

local function isFiniteNumber(value)
    return type(value) == "number"
        and value == value
        and value ~= math.huge
        and value ~= -math.huge
end

-- Font:DrawString takes an integer box width; a fractional number raises in this build.
local function truncTowardZero(value)
    if not isFiniteNumber(value) then
        return 0
    end
    local whole
    if value >= 0 then
        whole = math.floor(value)
    else
        whole = math.ceil(value)
    end
    return math.tointeger(whole) or whole
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

local function hintAlpha(elapsed)
    return clamp((HINT_FRAMES - elapsed) / FADE_FRAMES, 0, 1)
end

-- The one warning transition: constructwarn, constructreset, SetWarning and a
-- non-continued game start all go through here.
local function setWarning(pending)
    if type(pending) ~= "boolean" then
        return false
    end
    state.warningPending = pending
    return true
end

-- The one offset transition: constructoffset and SetOffset accept only a finite number and
-- clamp it to [0,10]; anything else leaves the live offset unchanged.
local function setOffset(value)
    if not isFiniteNumber(value) then
        return false
    end
    state.hudOffset = clamp(value, OFFSET_MIN, OFFSET_MAX)
    return true
end

local function startTimer()
    state.elapsedFrames = 0
end

local function drawMessage(draws, text, y, boxWidth, red, green, blue, alpha)
    draws[#draws + 1] = {
        text = text,
        x = 0,
        y = y,
        boxWidth = boxWidth,
        center = false,
        red = red,
        green = green,
        blue = blue,
        alpha = alpha,
    }
    -- X=0 with the integer room width as the box and Center=false keeps the text right
    -- aligned against the room's right edge. A failing draw must not stop the compositor
    -- from advancing its timer.
    pcall(function()
        font:DrawString(text, 0, y, KColor(red, green, blue, alpha), boxWidth, false)
    end)
end

-- The compositor. MC_POST_RENDER and RenderFrame() both call it, so the real render path and
-- the public control path issue the same Font:DrawString calls from the same state.
local function renderFrame()
    local elapsed = state.elapsedFrames
    -- Recomputed on every frame from the current room and render coordinates.
    local corner = Isaac.WorldToScreen(game:GetRoom():GetBottomRightPos())
    local brX = corner.X - state.hudOffset
    local brY = corner.Y - state.hudOffset
    local boxWidth = truncTowardZero(brX)
    local warningVisible = state.warningPending
    local hintVisible = elapsed >= 0 and elapsed < HINT_FRAMES

    ensureFont()
    local draws = {}
    if hintVisible then
        local hintY = warningVisible and (brY - UPPER_SLOT) or (brY - LOWER_SLOT)
        drawMessage(draws, HINT_TEXT, hintY, boxWidth, 1, 1, 1, hintAlpha(elapsed))
    end
    if warningVisible then
        drawMessage(draws, WARNING_TEXT, brY - LOWER_SLOT, boxWidth, 1, 0.35, 0.25, 1)
    end

    state.lastDraws = draws
    state.bottomRightX = brX
    state.bottomRightY = brY
    state.elapsedFrames = elapsed + 1
    return true
end

local function snapshot()
    local draws = {}
    for index, draw in ipairs(state.lastDraws) do
        draws[index] = {
            text = draw.text,
            x = draw.x,
            y = draw.y,
            boxWidth = draw.boxWidth,
            center = draw.center,
            red = draw.red,
            green = draw.green,
            blue = draw.blue,
            alpha = draw.alpha,
        }
    end
    return {
        lastDraws = draws,
        elapsedFrames = state.elapsedFrames,
        warningPending = state.warningPending,
        bottomRightX = state.bottomRightX,
        bottomRightY = state.bottomRightY,
        hudOffset = state.hudOffset,
    }
end

local function trim(text)
    return (text:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function executeCommand(command, parameters)
    if type(command) ~= "string" then
        return false
    end
    local name, rest = command:match("^%s*(%S+)%s*(.-)%s*$")
    if not name then
        return false
    end
    -- The engine passes the first word and the rest of the line separately; accept a whole
    -- line in the first argument as well.
    if type(parameters) == "string" and trim(parameters) ~= "" then
        rest = rest ~= "" and (rest .. " " .. trim(parameters)) or trim(parameters)
    end
    if name == "constructwarn" then
        return setWarning(true)
    elseif name == "constructreset" then
        return setWarning(false)
    elseif name == "constructoffset" then
        if rest == "" or rest:find("%s") then
            return false
        end
        -- tonumber yields nil for malformed text; setOffset also rejects NaN and infinity.
        return setOffset(tonumber(rest))
    end
    return false
end

IsaacConstructHUD = {
    SetWarning = setWarning,
    SetOffset = setOffset,
    RenderFrame = renderFrame,
    Snapshot = snapshot,
}

mod:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, function(_, isContinued)
    startTimer()
    if not isContinued then
        setWarning(false)
    end
end)

-- Room and floor transitions (MC_POST_NEW_ROOM, MC_POST_NEW_LEVEL) deliberately have no
-- handler: they restart neither the hint timer nor the pending warning.

mod:AddCallback(ModCallbacks.MC_POST_RENDER, function()
    renderFrame()
end)

mod:AddCallback(ModCallbacks.MC_EXECUTE_CMD, function(_, command, parameters)
    executeCommand(command, parameters)
end)
