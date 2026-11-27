local suite = RegisterMod("Construct HUD Compositor Verifier", 1)
local game = Game()
local json = require("json")

local HINT_TEXT = "Press F2 to open configuration"
local WARNING_TEXT = "Restart to apply settings"
local EPS = 1e-6
local COLOR_EPS = 1e-5
-- Every acceptance case, in exam order. A case the run never reaches is reported as a
-- failure by finish(), so each name is logged exactly once.
local CASES = {
    "hint_frame_0", "hint_frame_839", "hint_frame_840", "hint_frame_899",
    "hint_frame_900_hidden", "game_start_restarts_hint", "floor_change_keeps_hint_timer",
    "warning_hidden_initially", "warning_visible_when_pending",
    "warning_survives_room_change", "warning_survives_floor_change",
    "warning_cleared_by_reset", "reset_is_idempotent", "hint_only_bottom_slot",
    "warning_only_bottom_slot", "both_messages_stack",
    "hint_returns_to_bottom_after_clear", "warning_stays_bottom_when_hint_expires",
    "fractional_offset_0_5_width_floor", "fractional_offset_9_5_width_floor",
    "integer_corner_width_unchanged", "fractional_corner_no_render_error",
    "hint_y_bottom_slot", "warning_y_bottom_slot", "stacked_hint_y",
    "hint_text_unchanged", "warning_text_unchanged", "hint_color_and_alpha",
    "warning_color_constant", "right_alignment_mode_preserved",
    "live_offset_applies_next_frame", "screen_resize_recomputes_corner",
    "warning_reset_same_frame", "offset_command_validates_and_unknown_is_noop",
    "new_run_clears_warning",
}

local passed = 0
local failed = 0
local recorded = {}
local finished = false
local started = false
local steps = nil
local stepIndex = 1
local stepAge = 0
-- Update frames since the suite started, and since the latest MC_POST_GAME_STARTED.
local updateCount = 0
local updatesSinceStart = 0
local gameStarts = 0
local newRooms = 0
local newLevels = 0
-- The timer model. Both this suite and the submission restart counting inside the same
-- MC_POST_GAME_STARTED dispatch, so the elapsed frame the submission draws next is the
-- number of real MC_POST_RENDER callbacks plus the RenderFrame() calls made by this suite
-- since that game start, whichever mod's callbacks run first.
local renderCount = 0
local renderCalls = 0
-- Room corner seen by this suite's own MC_POST_RENDER in the latest rendered frame.
local lastRenderCorner = nil
-- Snapshots taken by this suite's MC_POST_RENDER in the first frames after a game start.
local captures = {}
local captureRemaining = 0
-- Every MC_EXECUTE_CMD delivery this suite observed, to tell a missing engine dispatch apart
-- from a submission that ignored the command.
local commandsSeen = {}
local notes = {}
local alignmentLog = { checked = 0, violations = {} }
local cornerLog = { checks = 0, failures = {}, contexts = {}, distinct = {}, distinctCount = 0 }

local function log(text)
    Isaac.DebugString(text)
end

-- One log line per detail, and no verifier marker can be smuggled in through a message the
-- submission controls (such as an error string).
local function sanitize(value)
    local text = tostring(value):gsub("[\r\n]+", " ")
    text = text:gsub("%[GCB_", "[gcb_")
    if #text > 400 then
        text = text:sub(1, 400) .. "..."
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
        log("[GCB_CASE] PASS " .. name .. " " .. sanitize(detail or "ok"))
    else
        failed = failed + 1
        local text = tostring(detail or "failed")
        if notes.renderStarved then
            -- A handler of another mod that returns a value or raises can keep later mods'
            -- MC_POST_RENDER handlers from running, which breaks the render-frame model.
            text = "[suite MC_POST_RENDER starved] " .. text
        end
        log("[GCB_CASE] FAIL " .. name .. " " .. sanitize(text))
    end
end

local function run(name, fn)
    local ok, result = pcall(fn)
    record(name, ok, result)
end

local function num(value)
    if type(value) == "number" then
        return string.format("%.4f", value)
    end
    return tostring(value)
end

local function equal(actual, expected, label)
    if actual ~= expected then
        error((label or "value") .. ": expected " .. tostring(expected)
            .. ", received " .. tostring(actual))
    end
end

local function near(actual, expected, label, tolerance)
    if type(actual) ~= "number" or actual ~= actual
        or math.abs(actual - expected) > (tolerance or EPS) then
        error((label or "value") .. ": expected " .. num(expected)
            .. ", received " .. num(actual))
    end
end

local function truthy(value, label)
    if not value then
        error(label or "expected truthy value")
    end
end

local function isNear(actual, expected, tolerance)
    return type(actual) == "number" and actual == actual
        and math.abs(actual - expected) <= (tolerance or EPS)
end

local function integerValue(value, label)
    if type(value) ~= "number" or value ~= value or value == math.huge
        or value == -math.huge or value % 1 ~= 0 then
        error((label or "value") .. " is not an integer: " .. tostring(value))
    end
end

local function trunc(value)
    if value >= 0 then
        return math.floor(value)
    end
    return math.ceil(value)
end

local function hintAlpha(elapsed)
    local alpha = (900 - elapsed) / 61
    if alpha < 0 then
        return 0
    end
    if alpha > 1 then
        return 1
    end
    return alpha
end

local function describe(draws)
    local ok, text = pcall(json.encode, draws)
    if ok and type(text) == "string" then
        return text
    end
    return "<" .. tostring(draws) .. ">"
end

local function hud()
    local api = IsaacConstructHUD
    if type(api) ~= "table" then
        error("IsaacConstructHUD is not exported")
    end
    return api
end

-- A copy of one Snapshot(), taken before the submission can change it again.
local function snapshot()
    local current = hud().Snapshot()
    if type(current) ~= "table" then
        error("Snapshot() did not return a table")
    end
    if type(current.lastDraws) ~= "table" then
        error("Snapshot().lastDraws is not a table")
    end
    local draws = {}
    for index, entry in ipairs(current.lastDraws) do
        if type(entry) ~= "table" then
            error("lastDraws[" .. index .. "] is not a table")
        end
        draws[index] = {
            text = entry.text,
            x = entry.x,
            y = entry.y,
            boxWidth = entry.boxWidth,
            center = entry.center,
            red = entry.red,
            green = entry.green,
            blue = entry.blue,
            alpha = entry.alpha,
        }
    end
    return {
        lastDraws = draws,
        elapsedFrames = current.elapsedFrames,
        warningPending = current.warningPending,
        bottomRightX = current.bottomRightX,
        bottomRightY = current.bottomRightY,
        hudOffset = current.hudOffset,
    }
end

-- The raw room bottom-right screen point, before the HUD offset is subtracted.
local function rawCorner()
    local corner = Isaac.WorldToScreen(game:GetRoom():GetBottomRightPos())
    return corner.X, corner.Y
end

local function expectedNext()
    return renderCount + renderCalls
end

-- One RenderFrame() call; returns the elapsed frame that call draws.
local function renderFrame()
    local api = hud()
    local drawn = expectedNext()
    renderCalls = renderCalls + 1
    api.RenderFrame()
    return drawn
end

-- Snapshot().elapsedFrames may report either the next frame to draw or the frame drawn last;
-- both readings are accepted. Once the hint has expired a capped counter is accepted too.
local function elapsedConsistent(value, label)
    local nextFrame = expectedNext()
    if type(value) ~= "number" or value ~= value then
        error(label .. ": elapsedFrames is not a number: " .. tostring(value))
    end
    if nextFrame - 1 >= 900 then
        truthy(value >= 899, label .. ": elapsedFrames " .. tostring(value)
            .. " after the timer expired (rendered frames " .. nextFrame .. ")")
        return
    end
    truthy(value == nextFrame or (nextFrame > 0 and value == nextFrame - 1),
        label .. ": elapsedFrames " .. tostring(value) .. ", expected " .. nextFrame
            .. " rendered frames since the game start")
end

local function checkOffsetValue(value, label)
    truthy(type(value) == "number" and value == value and value >= 0 and value <= 10,
        (label or "hudOffset") .. " outside [0,10]: " .. tostring(value))
end

local function layout(cx, cy, offset)
    local brX = cx - offset
    local brY = cy - offset
    return {
        brX = brX,
        brY = brY,
        width = trunc(brX),
        lower = brY - 28,
        upper = brY - 48,
    }
end

-- Messages of one frame by exact text.
local function classify(current)
    local result = { hint = nil, warning = nil, count = 0, unknown = {} }
    for _, entry in ipairs(current.lastDraws) do
        result.count = result.count + 1
        if entry.text == HINT_TEXT then
            truthy(result.hint == nil, "hint drawn twice in one frame")
            result.hint = entry
        elseif entry.text == WARNING_TEXT then
            truthy(result.warning == nil, "warning drawn twice in one frame")
            result.warning = entry
        else
            result.unknown[#result.unknown + 1] = tostring(entry.text)
        end
    end
    return result
end

local function noteAlignment(c, context)
    for _, entry in ipairs({ c.hint or false, c.warning or false }) do
        if entry then
            alignmentLog.checked = alignmentLog.checked + 1
            if entry.x ~= 0 or entry.center ~= false then
                alignmentLog.violations[#alignmentLog.violations + 1] = context
                    .. ": " .. tostring(entry.text) .. " x=" .. tostring(entry.x)
                    .. " center=" .. tostring(entry.center)
            end
        end
    end
end

-- Records whether one frame used the corner Isaac.WorldToScreen reported at that moment.
local function noteCorner(context, current, cx, cy, offset, c)
    cornerLog.checks = cornerLog.checks + 1
    cornerLog.contexts[context] = true
    local key = string.format("%.3f,%.3f", cx, cy)
    if not cornerLog.distinct[key] then
        cornerLog.distinct[key] = true
        cornerLog.distinctCount = cornerLog.distinctCount + 1
    end
    local problems = {}
    local bx, by = current.bottomRightX, current.bottomRightY
    if type(bx) ~= "number" or type(by) ~= "number" then
        problems[#problems + 1] = "bottomRightX/Y missing"
    elseif not ((isNear(bx, cx - offset) and isNear(by, cy - offset))
        or (isNear(bx, cx) and isNear(by, cy))) then
        problems[#problems + 1] = "bottomRight=" .. num(bx) .. "," .. num(by)
            .. " corner=" .. num(cx) .. "," .. num(cy) .. " offset=" .. num(offset)
    end
    local width = trunc(cx - offset)
    for _, entry in ipairs({ c.hint or false, c.warning or false }) do
        if entry and entry.boxWidth ~= width then
            problems[#problems + 1] = tostring(entry.text) .. " boxWidth="
                .. tostring(entry.boxWidth) .. " expected " .. width
        end
    end
    if #problems > 0 then
        cornerLog.failures[#cornerLog.failures + 1] = context .. ": "
            .. table.concat(problems, "; ")
    end
end

-- Sets the warning (unless nil) and offset through the public setters and confirms them.
local function setState(warning, offset)
    local api = hud()
    if warning ~= nil then
        api.SetWarning(warning)
    end
    if offset ~= nil then
        api.SetOffset(offset)
    end
    local current = snapshot()
    if warning ~= nil then
        equal(current.warningPending, warning, "warningPending after SetWarning")
    end
    if offset ~= nil then
        near(current.hudOffset, offset, "hudOffset after SetOffset")
    end
    return current
end

-- One RenderFrame() without touching the setters, measured against the corner of this same
-- moment; offset is the value the suite expects the submission to use.
local function renderAt(offset, context)
    local cx, cy = rawCorner()
    local drawn = renderFrame()
    local current = snapshot()
    local c = classify(current)
    noteAlignment(c, context)
    noteCorner(context, current, cx, cy, offset, c)
    return {
        c = c,
        L = layout(cx, cy, offset),
        snap = current,
        E = drawn,
        cx = cx,
        cy = cy,
        offset = offset,
    }
end

-- Sets the state through the public setters, then renders one frame.
local function frame(warning, offset, context)
    setState(warning, offset)
    return renderAt(offset, context)
end

-- The latest real MC_POST_RENDER frame, measured against the corner this suite saw in it.
local function realFrame(offset, context)
    local corner = lastRenderCorner
    truthy(corner, "no real render observed")
    local current = snapshot()
    local c = classify(current)
    noteAlignment(c, context)
    noteCorner(context, current, corner.x, corner.y, offset, c)
    return {
        c = c,
        L = layout(corner.x, corner.y, offset),
        snap = current,
        cx = corner.x,
        cy = corner.y,
        offset = offset,
    }
end

local function requireHintVisible(f)
    truthy(f.E == nil or f.E < 900, "suite timing: frame " .. tostring(f.E)
        .. " is past the hint window")
end

local function expectHint(f, slot, label)
    local hint = f.c.hint
    truthy(hint, (label or "frame") .. ": hint not drawn " .. describe(f.snap.lastDraws))
    near(hint.y, slot == "upper" and f.L.upper or f.L.lower, (label or "hint") .. " y")
    integerValue(hint.boxWidth, (label or "hint") .. " boxWidth")
    equal(hint.boxWidth, f.L.width, (label or "hint") .. " boxWidth")
    return hint
end

local function expectWarning(f, label)
    local warning = f.c.warning
    truthy(warning, (label or "frame") .. ": warning not drawn " .. describe(f.snap.lastDraws))
    near(warning.y, f.L.lower, (label or "warning") .. " y")
    integerValue(warning.boxWidth, (label or "warning") .. " boxWidth")
    equal(warning.boxWidth, f.L.width, (label or "warning") .. " boxWidth")
    return warning
end

local function expectColor(entry, red, green, blue, alpha, label)
    near(entry.red, red, label .. " red", COLOR_EPS)
    near(entry.green, green, label .. " green", COLOR_EPS)
    near(entry.blue, blue, label .. " blue", COLOR_EPS)
    near(entry.alpha, alpha, label .. " alpha", COLOR_EPS)
end

local function exec(line)
    local ok, err = pcall(Isaac.ExecuteCommand, line)
    if not ok then
        notes.execErrors = (notes.execErrors or 0) + 1
        notes.lastExecError = tostring(err)
    end
end

-- The first capture after the latest game start whose Snapshot holds the hint: the frame-0
-- draw, seen in this suite's first or second render callback depending on callback order.
local function firstHintCapture()
    for index, capture in ipairs(captures) do
        if capture.ok and type(capture.snap) == "table" then
            local okClass, c = pcall(classify, capture.snap)
            if okClass and c.hint then
                return capture, index, c
            end
        end
    end
    return nil
end

-- allowWarning lets a still-pending warning share the frame (the hint then takes the upper
-- slot), so a restart check does not also grade the warning transition.
local function checkFrameZero(capture, index, c, label, allowWarning)
    truthy(index <= 2, label .. ": first hint draw appeared in render callback " .. index)
    local snap = capture.snap
    checkOffsetValue(snap.hudOffset, label .. " hudOffset")
    equal(#c.unknown, 0, label .. ": unknown messages")
    truthy(allowWarning or c.warning == nil, label .. ": warning drawn in the frame-0 draw")
    -- A capture taken before the submission's callback in that render shows the draw of
    -- the previous render, so either render's corner may be the one the draw used.
    local matched, lastError = false, label .. ": corner unavailable in that render"
    for _, corner in ipairs(capture.corners) do
        if corner then
            local ok, err = pcall(function()
                local L = layout(corner.x, corner.y, snap.hudOffset)
                near(c.hint.y, c.warning and L.upper or L.lower, label .. " hint y")
                equal(c.hint.boxWidth, L.width, label .. " hint boxWidth")
            end)
            if ok then
                matched = true
                break
            end
            lastError = err
        end
    end
    if not matched then
        error(lastError)
    end
    expectColor(c.hint, 1, 1, 1, 1, label .. " hint")
    truthy(snap.elapsedFrames == 0 or snap.elapsedFrames == 1,
        label .. ": elapsedFrames " .. tostring(snap.elapsedFrames) .. " at the frame-0 draw")
    return "render_callback=" .. index .. " elapsed=" .. tostring(snap.elapsedFrames)
        .. " y=" .. num(c.hint.y) .. " width=" .. tostring(c.hint.boxWidth)
end

local function fractionalWidthCase(offset)
    local solo = frame(false, offset, "start-room")
    requireHintVisible(solo)
    truthy(solo.c.warning == nil, "warning drawn without a pending warning")
    local hint = expectHint(solo, "lower", "hint")
    local stacked = frame(true, offset, "start-room")
    local warning = expectWarning(stacked, "stacked warning")
    local upper = expectHint(stacked, "upper", "stacked hint")
    equal(upper.boxWidth, warning.boxWidth, "hint and warning box widths")
    return "offset=" .. num(offset) .. " brX=" .. num(solo.L.brX)
        .. " width=" .. tostring(hint.boxWidth) .. " y=" .. num(hint.y)
end

-- First update frame after the first game start: every mod's game-start handler has run,
-- whatever the load order, and the hint window is still open.
local function phaseOne()
    -- The state at this update is what a render callback of the next frame would capture
    -- before the submission draws, so it extends the capture sequence when every render
    -- since the game start has been captured.
    if #captures == renderCount then
        local okSnap, snap = pcall(snapshot)
        local okCorner, cx, cy = pcall(rawCorner)
        captures[#captures + 1] = {
            ok = okSnap,
            snap = snap,
            corners = { lastRenderCorner or false, okCorner and { x = cx, y = cy } or false },
            render = renderCount + 1,
        }
    end

    run("hint_frame_0", function()
        local capture, index, c = firstHintCapture()
        if capture then
            return checkFrameZero(capture, index, c, "frame 0", false)
        end
        -- No real render ran before this first update, so the next draw is frame 0.
        truthy(expectedNext() == 0, "no draw in the first " .. #captures
            .. " render callbacks after the game start held the hint")
        local current = snapshot()
        checkOffsetValue(current.hudOffset)
        local f = renderAt(current.hudOffset, "start-room")
        equal(f.E, 0, "frame drawn")
        truthy(f.c.warning == nil, "warning drawn at frame 0")
        expectColor(expectHint(f, "lower", "frame 0 hint"), 1, 1, 1, 1, "frame 0 hint")
        return "first update rendered frame 0"
    end)

    run("warning_hidden_initially", function()
        local current = snapshot()
        equal(current.warningPending, false, "warningPending at the start of a run")
        for index, capture in ipairs(captures) do
            truthy(capture.ok, "Snapshot() failed in render callback " .. index .. ": "
                .. tostring(capture.snap))
            truthy(classify(capture.snap).warning == nil,
                "warning drawn in render callback " .. index)
        end
        truthy(classify(current).warning == nil, "warning drawn in the latest real render")
        return "warningPending=false captures=" .. #captures
    end)

    run("hint_only_bottom_slot", function()
        local f = frame(false, 0, "start-room")
        requireHintVisible(f)
        equal(f.c.count, 1, "messages drawn " .. describe(f.snap.lastDraws))
        truthy(f.c.warning == nil, "warning drawn without a pending warning")
        local hint = expectHint(f, "lower", "hint")
        return "E=" .. f.E .. " brY=" .. num(f.L.brY) .. " y=" .. num(hint.y)
            .. " width=" .. tostring(hint.boxWidth)
    end)

    run("hint_y_bottom_slot", function()
        local seen = {}
        for _, offset in ipairs({ 0, 4.25, 10 }) do
            local f = frame(false, offset, "start-room")
            requireHintVisible(f)
            truthy(f.c.warning == nil, "warning drawn without a pending warning")
            truthy(f.c.hint, "hint not drawn at offset " .. num(offset))
            near(f.c.hint.y, f.L.lower, "hint y at offset " .. num(offset))
            seen[#seen + 1] = num(f.c.hint.y)
        end
        return "y=" .. table.concat(seen, ",")
    end)

    run("hint_text_unchanged", function()
        local solo = frame(false, 0, "start-room")
        requireHintVisible(solo)
        equal(#solo.c.unknown, 0, "unexpected message text " .. describe(solo.snap.lastDraws))
        truthy(solo.c.hint, "no message with the exact hint text "
            .. describe(solo.snap.lastDraws))
        local stacked = frame(true, 0, "start-room")
        equal(#stacked.c.unknown, 0, "unexpected message text while stacked "
            .. describe(stacked.snap.lastDraws))
        truthy(stacked.c.hint, "exact hint text missing while stacked "
            .. describe(stacked.snap.lastDraws))
        return "text=" .. HINT_TEXT
    end)

    run("both_messages_stack", function()
        local f = frame(true, 0, "start-room")
        requireHintVisible(f)
        equal(f.c.count, 2, "messages drawn " .. describe(f.snap.lastDraws))
        local warning = expectWarning(f, "warning")
        local hint = expectHint(f, "upper", "hint")
        truthy(hint.y < warning.y, "hint is not above the warning")
        return "hint_y=" .. num(hint.y) .. " warning_y=" .. num(warning.y)
    end)

    run("stacked_hint_y", function()
        local seen = {}
        for _, offset in ipairs({ 0, 7.75 }) do
            local f = frame(true, offset, "start-room")
            requireHintVisible(f)
            truthy(f.c.warning, "warning not drawn at offset " .. num(offset))
            truthy(f.c.hint, "hint not drawn at offset " .. num(offset))
            near(f.c.hint.y, f.L.upper, "stacked hint y at offset " .. num(offset))
            seen[#seen + 1] = num(f.c.hint.y)
        end
        return "y=" .. table.concat(seen, ",")
    end)

    run("warning_text_unchanged", function()
        local f = frame(true, 0, "start-room")
        equal(#f.c.unknown, 0, "unexpected message text " .. describe(f.snap.lastDraws))
        truthy(f.c.warning, "no message with the exact warning text "
            .. describe(f.snap.lastDraws))
        return "text=" .. WARNING_TEXT
    end)

    run("warning_reset_same_frame", function()
        local stacked = frame(true, 0, "start-room")
        requireHintVisible(stacked)
        expectWarning(stacked, "stacked warning")
        expectHint(stacked, "upper", "stacked hint")
        local cleared = frame(false, 0, "start-room")
        equal(cleared.c.count, 1, "messages on the render after the clear "
            .. describe(cleared.snap.lastDraws))
        truthy(cleared.c.warning == nil, "warning still drawn on the render after the clear")
        expectHint(cleared, "lower", "hint after the clear")
        -- Set and cleared with no render in between: nothing of the warning is drawn.
        hud().SetWarning(true)
        local same = frame(false, 0, "start-room")
        truthy(same.c.warning == nil, "warning drawn after it was set and cleared before a render")
        expectHint(same, "lower", "hint after set and clear")
        return "hint back at y=" .. num(cleared.c.hint.y) .. " on the next render"
    end)

    run("fractional_offset_0_5_width_floor", function()
        return fractionalWidthCase(0.5)
    end)

    run("fractional_offset_9_5_width_floor", function()
        return fractionalWidthCase(9.5)
    end)

    run("integer_corner_width_unchanged", function()
        local cx = rawCorner()
        local fraction = cx - math.floor(cx)
        local widths = {}
        for _, extra in ipairs({ 0, 4 }) do
            local f = frame(true, fraction + extra, "start-room")
            requireHintVisible(f)
            truthy(f.L.brX % 1 == 0, "suite: brX " .. num(f.L.brX) .. " is not integral")
            local warning = expectWarning(f, "warning")
            local hint = expectHint(f, "upper", "hint")
            equal(warning.boxWidth, f.L.brX, "warning box width at integral brX")
            equal(hint.boxWidth, f.L.brX, "hint box width at integral brX")
            widths[#widths + 1] = tostring(hint.boxWidth)
        end
        return "corner_x=" .. num(cx) .. " widths=" .. table.concat(widths, ",")
    end)

    -- A guaranteed fractional brX (fraction .7 whatever the corner): RenderFrame must not
    -- raise, and the state stays in place so the real MC_POST_RENDER frames before the next
    -- update draw it too. The case is recorded on that next update.
    local frac = {}
    notes.frac = frac
    local ok, err = pcall(function()
        local cx = rawCorner()
        frac.offset = (cx - math.floor(cx)) + 0.3
        local f = frame(true, frac.offset, "start-room")
        requireHintVisible(f)
        truthy(f.L.brX % 1 ~= 0, "suite: brX " .. num(f.L.brX) .. " is integral")
        expectWarning(f, "warning")
        local hint = expectHint(f, "upper", "hint")
        frac.detail = "offset=" .. num(frac.offset) .. " brX=" .. num(f.L.brX)
            .. " width=" .. tostring(hint.boxWidth)
    end)
    if not ok then
        frac.error = tostring(err)
    end
    frac.renderAt = renderCount
end

local function fractionalFollowUp(age)
    local frac = notes.frac or {}
    if frac.renderAt and renderCount <= frac.renderAt and age < 20 then
        return false
    end
    run("fractional_corner_no_render_error", function()
        if frac.error then
            error(frac.error)
        end
        truthy(frac.offset and frac.renderAt, "fractional setup did not run")
        truthy(renderCount > frac.renderAt, "no real render after the fractional setup")
        local f = realFrame(frac.offset, "fractional-real")
        near(f.snap.hudOffset, frac.offset, "hudOffset during the real renders")
        elapsedConsistent(f.snap.elapsedFrames, "real renders at a fractional corner")
        expectWarning(f, "real-render warning")
        expectHint(f, "upper", "real-render hint")
        return tostring(frac.detail) .. " real_renders=" .. (renderCount - frac.renderAt)
            .. " real_brX=" .. num(f.L.brX)
    end)
    pcall(setState, false, 0)
    return true
end

-- One console-command step: setup through the public setters, the command lines through
-- Isaac.ExecuteCommand, then verify once this suite's own MC_EXECUTE_CMD observer has seen
-- every line and a real render has followed the last one (or after 12 update frames).
local function commandStep(lines, setup, verify)
    local ctx = { lines = lines }
    return {
        budget = 13,
        fn = function(age)
            if age == 1 then
                if setup then
                    local ok, err = pcall(setup)
                    if not ok then
                        ctx.setupError = tostring(err)
                    end
                end
                ctx.first = #commandsSeen + 1
                ctx.expected = #commandsSeen + #lines
                for _, line in ipairs(lines) do
                    exec(line)
                end
                return false
            end
            local seen = #commandsSeen >= ctx.expected
            if (seen and renderCount > commandsSeen[ctx.expected].render) or age >= 12 then
                ctx.dispatched = seen
                ctx.observed = #commandsSeen - ctx.first + 1
                verify(ctx)
                return true
            end
            return false
        end,
    }
end

-- Whether this suite's own MC_EXECUTE_CMD observer saw the lines. It is a diagnostic only:
-- the verdict comes from the submission's observable state, since a handler that returns a
-- value may keep later mods' handlers from running.
local function dispatchInfo(ctx)
    local text = "MC_EXECUTE_CMD observed " .. tostring(ctx.observed) .. "/" .. #ctx.lines
    if (notes.execErrors or 0) > 0 then
        text = text .. ", ExecuteCommand errors=" .. notes.execErrors .. " "
            .. tostring(notes.lastExecError)
    end
    return text
end

-- The body of one command case: a setup failure fails it, and the dispatch diagnostic rides
-- along with the verdict either way.
local function commandCase(ctx, fn)
    return function()
        if ctx.setupError then
            error("setup: " .. ctx.setupError)
        end
        local ok, result = pcall(fn)
        if not ok then
            error(tostring(result) .. " [" .. dispatchInfo(ctx) .. "]")
        end
        return tostring(result) .. " [" .. dispatchInfo(ctx) .. "]"
    end
end

local function offsetCheck(label, ctx, fn)
    local ok, err = pcall(function()
        if ctx.setupError then
            error("setup: " .. ctx.setupError)
        end
        fn()
    end)
    if not ok then
        notes.offsetErrors[#notes.offsetErrors + 1] = label .. ": " .. tostring(err)
            .. " [" .. dispatchInfo(ctx) .. "]"
    end
end

local function hudOffsetIs(expected, label)
    local current = snapshot()
    near(current.hudOffset, expected, label)
    return current
end

local function commandSteps()
    notes.offsetErrors = {}
    local list = {}

    list[#list + 1] = commandStep({ "constructwarn", "constructwarn" }, function()
        setState(false, 0)
    end, function(ctx)
        run("warning_visible_when_pending", commandCase(ctx, function()
            local real = realFrame(0, "command-real")
            equal(real.snap.warningPending, true, "warningPending after constructwarn")
            expectWarning(real, "real-render warning")
            expectHint(real, "upper", "real-render hint")
            local f = renderAt(0, "command")
            requireHintVisible(f)
            equal(f.c.count, 2, "messages after repeated constructwarn "
                .. describe(f.snap.lastDraws))
            local warning = expectWarning(f, "warning")
            expectHint(f, "upper", "hint")
            return "warning y=" .. num(warning.y) .. " after two constructwarn commands"
        end))
    end)

    list[#list + 1] = commandStep({ "constructreset" }, function()
        local stacked = frame(true, 0, "command")
        requireHintVisible(stacked)
        expectWarning(stacked, "stacked warning before the reset")
        expectHint(stacked, "upper", "stacked hint before the reset")
    end, function(ctx)
        run("hint_returns_to_bottom_after_clear", commandCase(ctx, function()
            local real = realFrame(0, "command-real")
            equal(real.snap.warningPending, false, "warningPending after constructreset")
            truthy(real.c.warning == nil, "real render still draws the warning after the clear")
            expectHint(real, "lower", "real-render hint")
            local f = renderAt(0, "command")
            requireHintVisible(f)
            equal(f.c.count, 1, "messages after the clear " .. describe(f.snap.lastDraws))
            local hint = expectHint(f, "lower", "hint")
            return "hint y=" .. num(hint.y) .. " brY=" .. num(f.L.brY)
        end))
    end)

    list[#list + 1] = commandStep({ "constructreset" }, function()
        setState(true, 0)
    end, function(ctx)
        run("warning_cleared_by_reset", commandCase(ctx, function()
            local current = snapshot()
            equal(current.warningPending, false, "warningPending after SetWarning(true) then constructreset")
            local f = renderAt(0, "command")
            truthy(f.c.warning == nil, "warning drawn after constructreset "
                .. describe(f.snap.lastDraws))
            return "warningPending=false draws=" .. f.c.count
        end))
    end)

    list[#list + 1] = commandStep({ "constructreset", "constructreset" }, function()
        setState(true, 0)
    end, function(ctx)
        run("reset_is_idempotent", commandCase(ctx, function()
            equal(snapshot().warningPending, false, "warningPending after two constructreset")
            local first = renderAt(0, "command")
            requireHintVisible(first)
            equal(first.c.count, 1, "messages after two resets " .. describe(first.snap.lastDraws))
            local hint = expectHint(first, "lower", "hint after two resets")
            hud().SetWarning(false)
            equal(snapshot().warningPending, false, "warningPending after a further SetWarning(false)")
            local second = renderAt(0, "command")
            equal(second.c.count, 1, "messages after a further reset "
                .. describe(second.snap.lastDraws))
            local again = expectHint(second, "lower", "hint after a further reset")
            equal(again.boxWidth, hint.boxWidth, "hint width after a repeated reset")
            near(again.y, hint.y, "hint y after a repeated reset")
            return "warningPending=false hint y=" .. num(again.y)
        end))
    end)

    list[#list + 1] = commandStep({ "constructoffset 6.5" }, function()
        local f = frame(false, 1, "command")
        requireHintVisible(f)
        expectHint(f, "lower", "hint at offset 1")
    end, function(ctx)
        run("live_offset_applies_next_frame", commandCase(ctx, function()
            hudOffsetIs(6.5, "hudOffset after constructoffset 6.5")
            local real = realFrame(6.5, "command-real")
            local realHint = expectHint(real, "lower", "real-render hint at offset 6.5")
            local f = renderAt(6.5, "command")
            requireHintVisible(f)
            local hint = expectHint(f, "lower", "hint at offset 6.5")
            return "real width=" .. tostring(realHint.boxWidth) .. " y=" .. num(realHint.y)
                .. " next width=" .. tostring(hint.boxWidth) .. " y=" .. num(hint.y)
        end))
        pcall(setState, nil, 0)
    end)

    -- Malformed offsets and unknown commands leave the warning and the offset unchanged.
    list[#list + 1] = commandStep({
        "constructoffset abc", "constructoffset", "constructoffset 1e999",
        "constructoffset nan", "constructoffset 7x", "constructoffsets 5",
        "constructwarning", "constructresetx 1", "gcbunknowncommand 2", "construct",
    }, function()
        setState(false, 3)
    end, function(ctx)
        offsetCheck("malformed and unknown commands", ctx, function()
            local current = hudOffsetIs(3, "hudOffset after malformed constructoffset input")
            equal(current.warningPending, false, "warningPending after unknown commands")
            local f = renderAt(3, "command")
            requireHintVisible(f)
            truthy(f.c.warning == nil, "warning drawn after unknown commands")
            expectHint(f, "lower", "hint at offset 3")
        end)
    end)

    list[#list + 1] = commandStep({ "constructresetnow", "constructwarnx", "constructoffsetx 1" },
        function()
            setState(true, 3)
        end, function(ctx)
            offsetCheck("unknown commands with a pending warning", ctx, function()
                local current = hudOffsetIs(3, "hudOffset after unknown commands")
                equal(current.warningPending, true, "warningPending after unknown commands")
            end)
            pcall(setState, false, nil)
        end)

    list[#list + 1] = commandStep({ "constructoffset 42" }, nil, function(ctx)
        offsetCheck("constructoffset 42", ctx, function()
            hudOffsetIs(10, "hudOffset after constructoffset 42")
        end)
    end)

    list[#list + 1] = commandStep({ "constructoffset -4" }, nil, function(ctx)
        offsetCheck("constructoffset -4", ctx, function()
            hudOffsetIs(0, "hudOffset after constructoffset -4")
        end)
    end)

    list[#list + 1] = commandStep({ "constructoffset 2.25" }, nil, function(ctx)
        run("offset_command_validates_and_unknown_is_noop", commandCase(ctx, function()
            hudOffsetIs(2.25, "hudOffset after constructoffset 2.25")
            local f = renderAt(2.25, "command")
            requireHintVisible(f)
            expectHint(f, "lower", "hint at offset 2.25")
            -- SetOffset shares the command's transition: non-finite input is ignored and
            -- finite input is clamped to [0,10].
            local api = hud()
            api.SetOffset(0 / 0)
            hudOffsetIs(2.25, "hudOffset after SetOffset(NaN)")
            api.SetOffset(math.huge)
            hudOffsetIs(2.25, "hudOffset after SetOffset(math.huge)")
            api.SetOffset(-1)
            hudOffsetIs(0, "hudOffset after SetOffset(-1)")
            api.SetOffset(11)
            hudOffsetIs(10, "hudOffset after SetOffset(11)")
            api.SetOffset(0)
            if #notes.offsetErrors > 0 then
                error(notes.offsetErrors[1] .. " (" .. #notes.offsetErrors .. " offset checks failed)")
            end
            return "malformed/unknown ignored; 42->10, -4->0, 2.25 applied; width="
                .. tostring(f.c.hint.boxWidth)
        end))
        pcall(setState, false, 0)
    end)

    return list
end

-- Screen shake moves the rendered room when the engine applies it through the render
-- offset; every frame must use the corner Isaac.WorldToScreen reports at that moment.
local function shakeStep(age)
    if age == 1 then
        pcall(setState, false, 0)
        notes.shakeStarted = pcall(function()
            game:ShakeScreen(40)
        end)
    end
    local okReal, errReal = pcall(realFrame, 0, "shake-real")
    if not okReal then
        cornerLog.failures[#cornerLog.failures + 1] = "shake-real: " .. tostring(errReal)
    end
    local okRender, errRender = pcall(renderAt, 0, "shake")
    if not okRender then
        cornerLog.failures[#cornerLog.failures + 1] = "shake: " .. tostring(errRender)
    end
    return age >= 8
end

-- Renders every elapsed frame from the current one through 907 inside one update, so no
-- real render interleaves: the warning is clear before 870 and pending from 870 on, the
-- offset is 0 until 906, a guaranteed fractional value at 906 and 5.5 at 907.
local function fadeSweep()
    local sweep = { frames = {}, errors = {}, start = expectedNext() }
    local ok, err = pcall(setState, false, 0)
    if not ok then
        sweep.fatal = "setup: " .. tostring(err)
        return sweep
    end
    if expectedNext() > 839 then
        sweep.fatal = "suite timing: " .. expectedNext() .. " frames rendered before the fade sweep"
        return sweep
    end
    local okCorner, cornerX = pcall(rawCorner)
    local fractionalOffset = okCorner and ((cornerX - math.floor(cornerX)) + 0.3) or 0.3
    local offset = 0
    local warning = false
    while expectedNext() <= 907 and #sweep.errors < 3 do
        local target = expectedNext()
        local okFrame, errFrame = pcall(function()
            if target == 870 then
                hud().SetWarning(true)
                warning = true
            elseif target == 906 then
                offset = fractionalOffset
                hud().SetOffset(offset)
            elseif target == 907 then
                offset = 5.5
                hud().SetOffset(offset)
            end
            local cx, cy = rawCorner()
            renderFrame()
            sweep.frames[target] = {
                snap = snapshot(),
                cx = cx,
                cy = cy,
                offset = offset,
                warning = warning,
            }
        end)
        if not okFrame then
            sweep.errors[#sweep.errors + 1] = "E=" .. target .. ": " .. tostring(errFrame)
        end
    end
    pcall(setState, nil, 0)
    return sweep
end

local function sweepFrame(sweep, elapsed)
    if sweep.fatal then
        error(sweep.fatal)
    end
    local entry = sweep.frames[elapsed]
    if not entry then
        error("frame " .. elapsed .. " was not rendered: " .. tostring(sweep.errors[1] or "sweep stopped"))
    end
    local c = classify(entry.snap)
    noteAlignment(c, "fade")
    return {
        c = c,
        L = layout(entry.cx, entry.cy, entry.offset),
        snap = entry.snap,
        E = elapsed,
        offset = entry.offset,
        warning = entry.warning,
    }
end

local function sweepCases(sweep)
    run("hint_frame_839", function()
        local f = sweepFrame(sweep, 839)
        equal(f.c.count, 1, "messages at frame 839 " .. describe(f.snap.lastDraws))
        local hint = expectHint(f, "lower", "hint")
        expectColor(hint, 1, 1, 1, 1, "hint")
        return "alpha=" .. num(hint.alpha) .. " y=" .. num(hint.y)
    end)

    run("hint_frame_840", function()
        local f = sweepFrame(sweep, 840)
        equal(f.c.count, 1, "messages at frame 840 " .. describe(f.snap.lastDraws))
        local hint = expectHint(f, "lower", "hint")
        expectColor(hint, 1, 1, 1, 60 / 61, "hint")
        return "alpha=" .. num(hint.alpha)
    end)

    run("hint_frame_899", function()
        local f = sweepFrame(sweep, 899)
        equal(f.c.count, 2, "messages at frame 899 " .. describe(f.snap.lastDraws))
        expectWarning(f, "warning")
        local hint = expectHint(f, "upper", "hint")
        expectColor(hint, 1, 1, 1, 1 / 61, "hint")
        return "alpha=" .. num(hint.alpha) .. " y=" .. num(hint.y)
    end)

    run("hint_frame_900_hidden", function()
        for elapsed = 900, 905 do
            local f = sweepFrame(sweep, elapsed)
            truthy(f.c.hint == nil, "hint drawn at frame " .. elapsed .. " "
                .. describe(f.snap.lastDraws))
            equal(f.c.count, 1, "messages at frame " .. elapsed .. " "
                .. describe(f.snap.lastDraws))
            expectWarning(f, "warning at frame " .. elapsed)
        end
        return "no hint in frames 900-905"
    end)

    run("warning_stays_bottom_when_hint_expires", function()
        local widths = {}
        for elapsed = 898, 901 do
            local f = sweepFrame(sweep, elapsed)
            local warning = expectWarning(f, "warning at frame " .. elapsed)
            if elapsed <= 899 then
                expectHint(f, "upper", "hint at frame " .. elapsed)
            else
                truthy(f.c.hint == nil, "hint drawn at frame " .. elapsed)
            end
            widths[#widths + 1] = warning.boxWidth
        end
        truthy(widths[1] == widths[2] and widths[2] == widths[3] and widths[3] == widths[4],
            "warning width changed across the expiry: " .. table.concat(widths, ","))
        return "warning stayed at the lower slot across frames 898-901"
    end)

    run("warning_only_bottom_slot", function()
        local seen = {}
        for _, elapsed in ipairs({ 901, 906, 907 }) do
            local f = sweepFrame(sweep, elapsed)
            equal(f.c.count, 1, "messages at frame " .. elapsed .. " "
                .. describe(f.snap.lastDraws))
            local warning = expectWarning(f, "warning at frame " .. elapsed)
            seen[#seen + 1] = "offset " .. num(f.offset) .. " y=" .. num(warning.y)
                .. " width=" .. tostring(warning.boxWidth)
        end
        return table.concat(seen, "; ")
    end)

    run("warning_y_bottom_slot", function()
        local stacked, alone = 0, 0
        for elapsed = 870, 907 do
            local f = sweepFrame(sweep, elapsed)
            truthy(f.c.warning, "warning not drawn at frame " .. elapsed)
            near(f.c.warning.y, f.L.lower, "warning y at frame " .. elapsed)
            if f.c.hint then
                stacked = stacked + 1
            else
                alone = alone + 1
            end
        end
        truthy(stacked > 0 and alone > 0, "suite: stacked=" .. stacked .. " alone=" .. alone)
        return "stacked_frames=" .. stacked .. " alone_frames=" .. alone
    end)

    run("hint_color_and_alpha", function()
        if sweep.fatal then
            error(sweep.fatal)
        end
        local checked = 0
        for elapsed = sweep.start, 905 do
            local f = sweepFrame(sweep, elapsed)
            if elapsed <= 899 then
                truthy(f.c.hint, "hint not drawn at frame " .. elapsed)
                expectColor(f.c.hint, 1, 1, 1, hintAlpha(elapsed), "hint at frame " .. elapsed)
                checked = checked + 1
            else
                truthy(f.c.hint == nil, "hint drawn at frame " .. elapsed)
            end
        end
        return "frames " .. sweep.start .. "-899 checked=" .. checked
    end)

    run("warning_color_constant", function()
        for elapsed = 870, 907 do
            local f = sweepFrame(sweep, elapsed)
            truthy(f.c.warning, "warning not drawn at frame " .. elapsed)
            expectColor(f.c.warning, 1, 0.35, 0.25, 1, "warning at frame " .. elapsed)
        end
        return "KColor(1,0.35,0.25,1) in frames 870-907"
    end)

    run("right_alignment_mode_preserved", function()
        if sweep.fatal then
            error(sweep.fatal)
        end
        for elapsed = sweep.start, 907 do
            local f = sweepFrame(sweep, elapsed)
            for _, entry in ipairs({ f.c.hint or false, f.c.warning or false }) do
                if entry then
                    equal(entry.x, 0, tostring(entry.text) .. " x at frame " .. elapsed)
                    equal(entry.center, false, tostring(entry.text) .. " center at frame " .. elapsed)
                    integerValue(entry.boxWidth, tostring(entry.text) .. " boxWidth")
                    truthy(entry.boxWidth > 0, "non-positive box width at frame " .. elapsed)
                end
            end
            if f.c.hint and f.c.warning then
                equal(f.c.hint.boxWidth, f.c.warning.boxWidth, "box widths at frame " .. elapsed)
            end
        end
        if #alignmentLog.violations > 0 then
            error(alignmentLog.violations[1] .. " (" .. #alignmentLog.violations .. " violations)")
        end
        return "x=0 center=false in " .. alignmentLog.checked .. " draws"
    end)
end

-- Renders until the hint window has closed (the fade sweep normally already did), so the
-- timer checks around transitions start from an expired hint.
local function expireHint()
    local errors = 0
    while expectedNext() <= 900 and errors < 3 do
        if not pcall(renderFrame) then
            errors = errors + 1
        end
    end
    return expectedNext() - 1 >= 900
end

-- Engine state that tells a transition happened even if another mod's callback kept this
-- suite's MC_POST_NEW_ROOM / MC_POST_NEW_LEVEL handler from running.
local function levelMarker()
    local ok, marker = pcall(function()
        local level = game:GetLevel()
        return tostring(level:GetStage()) .. ":" .. tostring(level:GetCurrentRoomIndex())
    end)
    return ok and marker or "unknown"
end

-- A console transition with the warning pending: issue it, wait for this suite's own
-- engine callback counter (or the level marker) to move, let the new room settle, verify.
local function transitionStep(command, budget, counter, verify, cases)
    local ctx = {}
    return {
        budget = budget,
        fn = function(age)
            if age == 1 then
                ctx.before = counter()
                ctx.marker = levelMarker()
                ctx.newLevels = newLevels
                ctx.expired = expireHint()
                local ok, err = pcall(setState, true, 0)
                if not ok then
                    ctx.setupError = tostring(err)
                end
                exec(command)
                return false
            end
            if not ctx.arrivedAt then
                local marker = levelMarker()
                if counter() > ctx.before
                    or (marker ~= "unknown" and ctx.marker ~= "unknown" and marker ~= ctx.marker) then
                    ctx.arrivedAt = age
                end
                return false
            end
            if age < ctx.arrivedAt + 4 then
                return false
            end
            verify(ctx)
            return true
        end,
        timeout = function()
            for _, name in ipairs(cases) do
                record(name, false, "\"" .. command .. "\" produced no engine transition within "
                    .. budget .. " update frames")
            end
        end,
    }
end

local function requireSetup(ctx)
    if ctx.setupError then
        error("setup: " .. ctx.setupError)
    end
end

local function roomStep()
    return transitionStep("goto s.secret.1", 120, function()
        return newRooms
    end, function(ctx)
        run("warning_survives_room_change", function()
            requireSetup(ctx)
            local real = realFrame(0, "secret-room-real")
            equal(real.snap.warningPending, true, "warningPending after the room change")
            expectWarning(real, "real-render warning")
            local f = renderAt(0, "secret-room")
            local warning = expectWarning(f, "warning")
            return "warning y=" .. num(warning.y) .. " new_level_callbacks="
                .. (newLevels - ctx.newLevels)
        end)
    end, { "warning_survives_room_change" })
end

local function floorStep()
    return transitionStep("stage 2", 150, function()
        return newLevels
    end, function(ctx)
        run("warning_survives_floor_change", function()
            requireSetup(ctx)
            local real = realFrame(0, "floor-real")
            equal(real.snap.warningPending, true, "warningPending after the floor change")
            expectWarning(real, "real-render warning")
            local f = renderAt(0, "floor")
            local warning = expectWarning(f, "warning")
            return "warning y=" .. num(warning.y) .. " on the new floor"
        end)
        run("floor_change_keeps_hint_timer", function()
            truthy(ctx.expired, "suite timing: the hint had not expired before the floor change")
            local real = realFrame(0, "floor-real")
            elapsedConsistent(real.snap.elapsedFrames, "after the floor change")
            truthy(real.c.hint == nil, "real render drew the hint again after the floor change")
            local f = renderAt(0, "floor")
            truthy(f.c.hint == nil, "RenderFrame drew the hint again after the floor change")
            return "rendered_frames=" .. expectedNext() .. " elapsedFrames="
                .. tostring(f.snap.elapsedFrames)
        end)
    end, { "warning_survives_floor_change", "floor_change_keeps_hint_timer" })
end

-- A new run through the restart console command, with the warning pending and the hint
-- expired beforehand.
local function restartStep()
    local ctx = {}
    local cases = { "new_run_clears_warning", "game_start_restarts_hint" }
    return {
        budget = 200,
        fn = function(age)
            if age == 1 then
                ctx.gameStarts = gameStarts
                ctx.expired = expireHint()
                local ok, err = pcall(setState, true, 0)
                if not ok then
                    ctx.setupError = tostring(err)
                end
                local okType, playerType = pcall(function()
                    return Isaac.GetPlayer(0):GetPlayerType()
                end)
                exec(okType and ("restart " .. tostring(playerType)) or "restart")
                return false
            end
            if gameStarts <= ctx.gameStarts or updatesSinceStart < 4 then
                return false
            end
            run("new_run_clears_warning", function()
                requireSetup(ctx)
                local current = snapshot()
                equal(current.warningPending, false, "warningPending after a non-continued game start")
                checkOffsetValue(current.hudOffset)
                local real = realFrame(current.hudOffset, "new-run-real")
                truthy(real.c.warning == nil, "real render still draws the warning in the new run")
                local f = renderAt(current.hudOffset, "new-run")
                truthy(f.c.warning == nil, "RenderFrame drew the warning in the new run")
                return "warningPending=false draws=" .. f.c.count
            end)
            run("game_start_restarts_hint", function()
                truthy(ctx.expired, "suite timing: the hint had not expired before the restart")
                local capture, index, c = firstHintCapture()
                truthy(capture, "no render after the new game start drew the hint ("
                    .. #captures .. " captured)")
                local detail = checkFrameZero(capture, index, c, "restarted frame 0", true)
                local current = snapshot()
                elapsedConsistent(current.elapsedFrames, "after the restart")
                checkOffsetValue(current.hudOffset)
                local f = renderAt(current.hudOffset, "new-run")
                requireHintVisible(f)
                truthy(f.c.hint, "RenderFrame did not draw the hint in the new run")
                expectColor(f.c.hint, 1, 1, 1, hintAlpha(f.E), "hint")
                return detail .. " next_frame=" .. f.E
            end)
            return true
        end,
        timeout = function()
            for _, name in ipairs(cases) do
                record(name, false, "restart delivered no MC_POST_GAME_STARTED within 200 update frames")
            end
        end,
    }
end

local function finish()
    if finished then
        return
    end
    finished = true
    for _, name in ipairs(CASES) do
        if not recorded[name] then
            record(name, false, "not reached")
        end
    end
    log("[GCB_SUMMARY] passed=" .. tostring(passed)
        .. " failed=" .. tostring(failed)
        .. " total=" .. tostring(passed + failed))
end

local function finalStep()
    run("screen_resize_recomputes_corner", function()
        if #cornerLog.failures > 0 then
            error(cornerLog.failures[1] .. " (" .. #cornerLog.failures .. " frames failed)")
        end
        truthy(cornerLog.contexts["start-room"], "no start-room corner observation")
        truthy(cornerLog.contexts["shake"], "no corner observation during the screen shake")
        truthy(cornerLog.checks >= 10, "only " .. cornerLog.checks .. " corner observations")
        local contexts = {}
        for name in pairs(cornerLog.contexts) do
            contexts[#contexts + 1] = name
        end
        table.sort(contexts)
        return "checks=" .. cornerLog.checks .. " distinct_corners=" .. cornerLog.distinctCount
            .. " shake=" .. tostring(notes.shakeStarted) .. " contexts=" .. table.concat(contexts, ",")
    end)
    finish()
    return true
end

local function buildSteps()
    local list = {
        { budget = 1, fn = function()
            phaseOne()
            return true
        end },
        { budget = 21, fn = fractionalFollowUp },
    }
    for _, step in ipairs(commandSteps()) do
        list[#list + 1] = step
    end
    list[#list + 1] = { budget = 8, fn = shakeStep }
    list[#list + 1] = { budget = 1, fn = function()
        sweepCases(fadeSweep())
        return true
    end }
    list[#list + 1] = roomStep()
    list[#list + 1] = floorStep()
    list[#list + 1] = restartStep()
    list[#list + 1] = { budget = 1, fn = finalStep }
    return list
end

local function advance()
    if updateCount > 900 then
        finish()
        return
    end
    if updatesSinceStart >= 5 and renderCount == 0 then
        notes.renderStarved = true
    end
    if steps == nil then
        steps = buildSteps()
    end
    local step = steps[stepIndex]
    if not step then
        finish()
        return
    end
    stepAge = stepAge + 1
    local done = step.fn(stepAge)
    if not done and stepAge >= step.budget then
        if step.timeout then
            step.timeout()
        end
        done = true
    end
    if done then
        stepIndex = stepIndex + 1
        stepAge = 0
    end
end

suite:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, function()
    renderCount = 0
    renderCalls = 0
    updatesSinceStart = 0
    gameStarts = gameStarts + 1
    captures = {}
    captureRemaining = 6
    if not started then
        started = true
        log("[GCB_RUNTIME] suite_started")
    end
end)

suite:AddCallback(ModCallbacks.MC_POST_RENDER, function()
    if not started or finished then
        return
    end
    renderCount = renderCount + 1
    local previous = lastRenderCorner
    local okCorner, cx, cy = pcall(rawCorner)
    if okCorner then
        lastRenderCorner = { x = cx, y = cy, render = renderCount }
    else
        lastRenderCorner = nil
    end
    if captureRemaining > 0 then
        captureRemaining = captureRemaining - 1
        local okSnap, snap = pcall(snapshot)
        captures[#captures + 1] = {
            ok = okSnap,
            snap = snap,
            corners = { lastRenderCorner or false, previous or false },
            render = renderCount,
        }
    end
end)

suite:AddCallback(ModCallbacks.MC_POST_NEW_ROOM, function()
    if started then
        newRooms = newRooms + 1
    end
end)

suite:AddCallback(ModCallbacks.MC_POST_NEW_LEVEL, function()
    if started then
        newLevels = newLevels + 1
    end
end)

suite:AddCallback(ModCallbacks.MC_EXECUTE_CMD, function(_, command, parameters)
    commandsSeen[#commandsSeen + 1] = {
        command = tostring(command),
        parameters = tostring(parameters),
        update = updateCount,
        render = renderCount,
    }
end)

suite:AddCallback(ModCallbacks.MC_POST_UPDATE, function()
    if not started or finished then
        return
    end
    updateCount = updateCount + 1
    updatesSinceStart = updatesSinceStart + 1
    local ok, err = pcall(advance)
    if not ok then
        log("[GCB_FATAL] " .. sanitize(err))
        finish()
    end
end)
