-- Read-only bounded renderer observations; never changes graphics or game state.
local json=require('json')
local update=love.update
local started,last,rows=love.timer.getTime(),0,0
local function pack(...) return {n=select('#',...),...} end
love.update=function(...)
    local result=pack(update(...))
    local now=love.timer.getTime()
    if rows<30 and now-last>=1 then
        local w,h,flags=love.window.getMode()
        local name,version,vendor,device=love.graphics.getRendererInfo()
        local line=json.encode({elapsed=now-started,fps=love.timer.getFPS(),width=w,height=h,
            vsync=love.window.getVSync(),display=flags.display,fullscreen=flags.fullscreen,
            highdpi=flags.highdpi,msaa=flags.msaa,refreshrate=flags.refreshrate,
            renderer={name=name,version=version,vendor=vendor,device=device},state=G.STATE})..'\n'
        if love.filesystem.append('render-diagnostic-v1.jsonl',line) then rows=rows+1 end
        last=now
    end
    return unpack(result,1,result.n)
end
