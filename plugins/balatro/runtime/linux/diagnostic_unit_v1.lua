-- Unit-only fake objects. This never loads Balatro or supplies engine evidence.
local function pack(...) return {n=select('#', ...), ...} end
local calls, arguments = {}, {}
local expected_error = {}
local function original(name)
    return function(...)
        calls[name] = (calls[name] or 0)+1
        arguments[name] = pack(...)
        if select(1, ...) == expected_error then error(expected_error) end
        return nil, name, nil
    end
end
package.preload.json = function() return {encode=function() return 'unit' end} end
love = {timer={getTime=function() return 1 end, getFPS=function() return 60 end,
    getDelta=function() return 1/60 end},
    graphics={getRendererInfo=function() return 'unit','unit','unit','unit' end, present=original('present')},
    window={getMode=function() return 800,600,{fullscreen=false,vsync=0} end,
        hasFocus=function() return true end},
    filesystem={append=function() return true end},
    system={getClipboardText=original('clipboard')},
    mouse={getPosition=original('position'),setVisible=original('visible')},
    update=original('update'),draw=original('draw')}
Game = {update=original('game'),update_menu=original('menu'),update_blind_select=original('blind')}
Controller = {update=original('controller')}
nuGC,modulate_sound,update_canvas_juice,set_alerts = original('gc'),original('sound'),original('canvas'),original('alerts')
EventManager = {update=original('event_update')}
local pending
EventManager.add_event = function(self, event, ...)
    calls.add_event = (calls.add_event or 0)+1
    pending = event
    arguments.add_event = pack(...)
    return nil, 'add_event', nil
end
G = {STATES={MENU=1},STAGES={MAIN_MENU=1},STATE=1,STAGE=1,STATE_COMPLETE=false,
    CONTROLLER={locks={},locked=false},SETTINGS={paused=false},GAME={},TIMERS={REAL=0,TOTAL=0},
    E_MANAGER=setmetatable({queues={base={}}},{__index=EventManager})}
BB_SERVER = {send_response=original('send'),update=original('server')}
BB_DISPATCHER = {endpoints={},register=function() return true end}
unit_error,unit_calls,unit_arguments,unit_pack = expected_error,calls,arguments,pack
BB_DISPATCHER.endpoints.start = {execute=assert(loadstring([[
    return function(args, respond, ...)
        unit_calls.execute = (unit_calls.execute or 0)+1
        unit_arguments.execute = {n=select('#',...),...}
        if args == unit_error then error(unit_error) end
        local event = {trigger='condition',timer='REAL',delay=0,complete=false,blocking=false,
            blockable=true,created_on_pause=false,start_timer=false,
            func=function(...)
                unit_calls.callback = (unit_calls.callback or 0)+1
                if select(1,...) == unit_error then error(unit_error) end
                respond('response',nil,'tail')
                return nil,'callback',nil
            end}
        local values = unit_pack(G.E_MANAGER:add_event(event,'base',nil,'tail'))
        assert(values.n==3)
        return nil,'execute',nil
    end
]], '@src/lua/endpoints/start.lua'))()}
dofile(DIAGNOSTIC_PATH)
assert(not pending and not calls.execute and not calls.callback, 'Observer executed unscheduled work')
local values=pack(BB_DISPATCHER.endpoints.start.execute({},BB_SERVER.send_response,'extra',nil,'tail'))
assert(values.n==3 and values[1]==nil and values[2]=='execute' and values[3]==nil)
assert(calls.execute==1 and calls.add_event==1 and not calls.callback)
assert(arguments.execute.n==3 and arguments.execute[1]=='extra' and arguments.execute[3]=='tail')
assert(arguments.add_event.n==3 and arguments.add_event[1]=='base' and arguments.add_event[3]=='tail')
values=pack(pending.func('scheduled',nil,'tail'))
assert(values.n==3 and values[2]=='callback' and calls.callback==1 and calls.send==1)
assert(arguments.send.n==3 and arguments.send[1]=='response' and arguments.send[3]=='tail')
local ok,err=pcall(pending.func,expected_error)
assert(not ok and err==expected_error and calls.callback==2)
ok,err=pcall(BB_DISPATCHER.endpoints.start.execute,expected_error,BB_SERVER.send_response)
assert(not ok and err==expected_error and calls.execute==2 and calls.add_event==1)
for _,item in ipairs({{love,'update'},{love,'draw'},{love.graphics,'present'},
    {Game,'update'},{Controller,'update'},{EventManager,'update'},{BB_SERVER,'update'},
    {love.system,'getClipboardText'},{love.mouse,'getPosition'},{love.mouse,'setVisible'},
    {_G,'nuGC'},{_G,'modulate_sound'},{_G,'update_canvas_juice'},{_G,'set_alerts'},
    {Game,'update_menu'},{Game,'update_blind_select'}}) do
    local values=pack(item[1][item[2]]('argument',nil,'tail'))
    assert(values.n==3 and values[1]==nil and values[3]==nil)
    local name=values[2]
    assert(arguments[name].n==3 and arguments[name][1]=='argument' and arguments[name][3]=='tail')
    local ok,err=pcall(item[1][item[2]],expected_error)
    assert(not ok and err==expected_error)
end
