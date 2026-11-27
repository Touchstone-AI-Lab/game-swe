-- Owned process graphics configuration only. No gameplay or readiness writes.
local json=require('json')
local previous=love.update
local pending=true
local function pack(...) return {n=select('#',...),...} end
love.update=function(...)
    local result=pack(previous(...))
    if pending and G.STATE==G.STATES.MENU and not G.OVERLAY_MENU then
        assert(not G.SETTINGS.QUEUED_CHANGE or next(G.SETTINGS.QUEUED_CHANGE)==nil,
            'Unexpected pending window settings')
        G.SETTINGS.WINDOW.screenmode='Windowed'
        G.SETTINGS.QUEUED_CHANGE={screenres={w=800,h=600},vsync=0}
        G.FUNCS.apply_window_changes()
        local w,h,flags=love.window.getMode()
        assert(w==800 and h==600 and not flags.fullscreen and love.window.isVisible(),
            'Visible window configuration did not take effect')
        local name,version,vendor,device=love.graphics.getRendererInfo()
        assert(love.filesystem.write('window-profile-v2.json',json.encode({
            schema='visible-window-profile-v2',width=w,height=h,fullscreen=flags.fullscreen,
            visible=love.window.isVisible(),vsync=love.window.getVSync(),
            renderer={name=name,version=version,vendor=vendor,device=device}})))
        pending=false
    end
    return unpack(result,1,result.n)
end
