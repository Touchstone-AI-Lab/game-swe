-- This module observes engine-scheduled work; it never drives event callbacks.
local json = require('json')
local unpack_values = unpack
local function pack(...) return {n=select('#', ...), ...} end
local counts = {frames=0, start_enter=0, start_return=0, event_registered=0,
    callback_enter=0, callback_return=0, response_enter=0, response_return=0,
    server_enter=0, server_return=0}
local created = love.timer.getTime()
local renderer, renderer_version, renderer_vendor, renderer_device = love.graphics.getRendererInfo()
local width, height, window_flags = love.window.getMode()
local rows, bytes, dropped, observer_errors = 0, 0, 0, 0
local in_start, sending_start = false, false
local completion, last_signature, last_heartbeat
local function scalar(value)
    local t = type(value)
    if t == 'boolean' or t == 'number' then return {type=t, value=value} end
    return {type=t, value=t == 'string' and value:sub(1, 64) or t}
end
local function name_for(values, value)
    for k, v in pairs(values) do if v == value then return k end end
    return 'unknown'
end
local function event_fields(e)
    local info = debug.getinfo(e.func, 'S')
    return {trigger=e.trigger, blocking=scalar(e.blocking), blockable=scalar(e.blockable),
        complete=scalar(e.complete), created_on_pause=scalar(e.created_on_pause),
        timer=e.timer, start_timer=scalar(e.start_timer), delay=e.delay,
        source=(info.source:match('([^/\\]+)$') or 'unknown'):sub(1, 64),
        line=info.linedefined}
end
local function state()
    local locks, n = {}, 0
    for k, v in pairs(G.CONTROLLER.locks) do
        n = n + 1
        if n <= 24 then locks[tostring(k):sub(1, 48)] = scalar(v) end
    end
    return {state=G.STATE, state_name=name_for(G.STATES, G.STATE),
        stage=G.STAGE, stage_name=name_for(G.STAGES, G.STAGE),
        state_complete=scalar(G.STATE_COMPLETE), locked=scalar(G.CONTROLLER.locked),
        locks=locks, lock_count=n, paused=scalar(G.SETTINGS.paused),
        overlay=scalar(G.OVERLAY_MENU), screenwipe=scalar(G.screenwipe),
        hand_present=G.hand ~= nil, hand_count=G.hand and G.hand.cards and #G.hand.cards or 0,
        blind_on_deck=scalar(G.GAME.blind_on_deck),
        blind_select_options=G.blind_select_opts ~= nil,
        small_option=G.blind_select_opts ~= nil and G.blind_select_opts.small ~= nil,
        start_completion_condition=G.GAME.blind_on_deck ~= nil
            and G.blind_select_opts ~= nil and G.blind_select_opts.small ~= nil
            and G.blind_select_opts.small:get_UIE_by_ID('tag_Small') ~= nil}
end
local function snapshot(tag)
    local s = state()
    local counters = {}
    for k,v in pairs(counts) do counters[k] = v end
    local queue = {}
    for i,e in ipairs(G.E_MANAGER.queues.base) do
        if i <= 12 then queue[i] = event_fields(e) end
    end
    return {version='start-diag-v1', tag=tag, elapsed=love.timer.getTime()-created,
        real_timer=G.TIMERS.REAL, total_timer=G.TIMERS.TOTAL, state=s, counts=counters,
        graphics={fps=love.timer.getFPS(), delta=love.timer.getDelta(),
            renderer=renderer, version=renderer_version, vendor=renderer_vendor, device=renderer_device,
            width=width, height=height, fullscreen=window_flags.fullscreen, vsync=window_flags.vsync},
        completion=completion and event_fields(completion) or false,
        base_queue_count=#G.E_MANAGER.queues.base, base_queue_prefix=queue,
        rows=rows, bytes=bytes, dropped=dropped, observer_errors=observer_errors}
end
local function record(tag, force)
    -- Only observer work is protected; original wrapped functions are not caught.
    local ok = pcall(function()
        local s = state()
        local signature = json.encode(s)
        local now = love.timer.getTime()
        if force or signature ~= last_signature or not last_heartbeat or now-last_heartbeat >= 1 then
            last_signature, last_heartbeat = signature, now
            local line = json.encode(snapshot(tag)) .. '\n'
            if rows < 512 and bytes+#line <= 192*1024 then
                local written = love.filesystem.append('start-diagnostic-v1.jsonl', line)
                if written then rows, bytes = rows+1, bytes+#line else observer_errors=observer_errors+1 end
            else dropped=dropped+1 end
        end
    end)
    if not ok then observer_errors=observer_errors+1 end
end
local add_event = EventManager.add_event
EventManager.add_event = function(self, event, ...)
    local info = debug.getinfo(event.func, 'S')
    if in_start and info.source:find('src/lua/endpoints/start.lua', 1, true) then
        counts.event_registered = counts.event_registered+1
        completion = event
        local callback = event.func
        event.func = function(...)
            counts.callback_enter = counts.callback_enter+1
            record('callback_enter', counts.callback_enter == 1)
            local result = pack(callback(...))
            counts.callback_return = counts.callback_return+1
            record('callback_return', counts.callback_return == 1 or result[1] == true)
            return unpack_values(result, 1, result.n)
        end
        record('completion_registered', true)
    end
    return add_event(self, event, ...)
end
local execute = assert(BB_DISPATCHER.endpoints.start).execute
BB_DISPATCHER.endpoints.start.execute = function(args, respond, ...)
    counts.start_enter = counts.start_enter+1
    in_start = true
    record('start_enter', true)
    local result = pack(execute(args, function(...)
        counts.response_enter = counts.response_enter+1
        sending_start = true
        record('start_response_enter', true)
        local result = pack(respond(...))
        counts.response_return = counts.response_return+1
        sending_start = false
        record('start_response_return', true)
        return unpack_values(result, 1, result.n)
    end, ...))
    counts.start_return = counts.start_return+1
    in_start = false
    record('start_return', true)
    return unpack_values(result, 1, result.n)
end
local send_response = BB_SERVER.send_response
BB_SERVER.send_response = function(...)
    local is_start = sending_start
    if is_start then counts.server_enter=counts.server_enter+1; record('server_enter', true) end
    local result = pack(send_response(...))
    if is_start then
        counts.server_return=counts.server_return+1
        counts.server_success=result[1] == true
        record('server_return', true)
    end
    return unpack_values(result, 1, result.n)
end
local update = love.update
love.update = function(...)
    counts.frames = counts.frames+1
    local result = pack(update(...))
    record('frame', false)
    return unpack_values(result, 1, result.n)
end
assert(BB_DISPATCHER.register({name='poc.start_diagnostic',
    description='Read-only bounded start telemetry snapshot', schema={},
    execute=function(args, respond) respond(snapshot('query')) end}))
