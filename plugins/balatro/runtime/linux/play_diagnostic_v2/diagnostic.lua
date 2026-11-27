local json = require('json')
local function pack(...) return {n=select('#', ...), ...} end
local counts = {frames=0, plays=0, registered=0, entered=0, returned=0, responses=0, sent=0}
local created = love.timer.getTime()
local active, sending = false, false
local rows, bytes, errors, dropped = 0, 0, 0, 0
local last, last_time
local timings={}
local function scalar(value)
    if type(value)=='boolean' or type(value)=='number' then return value end
    return type(value)
end
local function observation()
    local cash = false
    for _,box in ipairs(G.I.UIBOX) do
        if box:get_UIE_by_ID('cash_out_button') then cash=true; break end
    end
    local queue={}
    for i,e in ipairs(G.E_MANAGER.queues.base) do
        if i<=6 then
            local info=debug.getinfo(e.func,'S')
            queue[#queue+1]={trigger=e.trigger,blocking=e.blocking,blockable=e.blockable,
                complete=e.complete,timer=e.timer,time=e.time,delay=e.delay,start_timer=e.start_timer,
                source=(info.source:match('([^/\\]+)$') or '?'),line=info.linedefined}
        end
    end
    local locks={}
    for k,v in pairs(G.CONTROLLER.locks) do locks[tostring(k):sub(1,48)]=scalar(v) end
    return {state=G.STATE,stage=G.STAGE,complete=scalar(G.STATE_COMPLETE),
        locked=scalar(G.CONTROLLER.locked),locks=locks,paused=scalar(G.SETTINGS.paused),
        overlay=scalar(G.OVERLAY_MENU),round_eval=G.round_eval~=nil,
        blind1=G.round_eval and G.round_eval:get_UIE_by_ID('dollar_blind1')~=nil or false,
        cash_out=cash,won=scalar(G.GAME.won),queue=#G.E_MANAGER.queues.base,queue_prefix=queue,real_timer=G.TIMERS.REAL,total_timer=G.TIMERS.TOTAL}
end
local function record(tag)
    local ok=pcall(function()
        local s=observation()
        local signature=tostring(s.state)..tostring(s.complete)..tostring(s.locked)..tostring(s.blind1)..tostring(s.cash_out)
        local now=love.timer.getTime()
        if signature==last and last_time and now-last_time<1 and tag=='frame' then return end
        last,last_time=signature,now
        local line=json.encode({tag=tag,elapsed=now-created,state=s,counts=counts,
            timings=timings,fps=love.timer.getFPS(),focused=love.window.hasFocus(),errors=errors,dropped=dropped})..'\n'
        if rows<512 and bytes+#line<=192*1024 then
            if love.filesystem.append('play-diagnostic-v2.jsonl',line) then
                rows,bytes=rows+1,bytes+#line
            else errors=errors+1 end
        else dropped=dropped+1 end
    end)
    if not ok then errors=errors+1 end
end
local add=EventManager.add_event
EventManager.add_event=function(self,event,...)
    local info=debug.getinfo(event.func,'S')
    if active and info.source:find('src/lua/endpoints/play.lua',1,true) then
        counts.registered=counts.registered+1
        local callback=event.func
        event.func=function(...)
            counts.entered=counts.entered+1
            local result=pack(callback(...))
            counts.returned=counts.returned+1
            if result[1]==true then record('callback_complete') end
            return unpack(result,1,result.n)
        end
        record('registered')
    end
    return add(self,event,...)
end
local execute=assert(BB_DISPATCHER.endpoints.play).execute
BB_DISPATCHER.endpoints.play.execute=function(args,respond,...)
    counts.plays=counts.plays+1
    active=true
    record('play_enter')
    local result=pack(execute(args,function(...)
        counts.responses=counts.responses+1
        sending=true
        record('response_enter')
        local values=pack(respond(...))
        sending=false
        record('response_return')
        return unpack(values,1,values.n)
    end,...))
    active=false
    record('play_return')
    return unpack(result,1,result.n)
end
local send=BB_SERVER.send_response
BB_SERVER.send_response=function(...)
    local current=sending
    local result=pack(send(...))
    if current then counts.sent=counts.sent+1;record('server_return') end
    return unpack(result,1,result.n)
end
local update=love.update
love.update=function(...)
    counts.frames=counts.frames+1
    local result=pack(update(...))
    record('frame')
    return unpack(result,1,result.n)
end

local function observe(owner,key,label)
    local original=assert(owner[key])
    timings[label]={calls=0,seconds=0}
    owner[key]=function(...)
        local started=love.timer.getTime()
        local result=pack(original(...))
        timings[label].calls=timings[label].calls+1
        timings[label].seconds=timings[label].seconds+love.timer.getTime()-started
        return unpack(result,1,result.n)
    end
end
observe(Game,'update','game')
observe(EventManager,'update','events')
observe(love,'draw','draw')
observe(love.graphics,'present','present')
observe(_G,'modulate_sound','sound')
observe(BB_SERVER,'update','server')
