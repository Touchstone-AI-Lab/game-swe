-- Unit-only doubles: no game is loaded and no engine evidence is produced.
local function pack(...)return {n=select('#',...),...}end
local count, applied, writes=0,0,0
local expected_error={}
local config
package.preload.json=function() return {encode=function(v)config=v;return 'unit' end}end
G={STATE=2,STATES={MENU=11},SETTINGS={WINDOW={},GAMESPEED=1},FUNCS={}}
G.FUNCS.apply_window_changes=function()
    applied=applied+1
    assert(G.SETTINGS.WINDOW.screenmode=='Windowed')
    assert(G.SETTINGS.QUEUED_CHANGE.screenres.w==1280)
    G.SETTINGS.QUEUED_CHANGE={}
end
love={update=function(...)
    count=count+1
    if select(1,...)==expected_error then error(expected_error) end
    assert(select('#',...)==3 and select(2,...)==nil)
    return nil,'original',nil
end,window={getMode=function()return 1280,720,{fullscreen=false}end,
    isVisible=function()return true end,getVSync=function()return 0 end},
    graphics={getRendererInfo=function()return 'OpenGL','unit','unit','unit' end},
    filesystem={write=function(name,contents)
        assert(name=='window-profile-v1.json' and contents=='unit');writes=writes+1;return true
    end}}
dofile(DIAGNOSTIC_PATH)
local r=pack(love.update('input',nil,'tail'))
assert(count==1 and applied==0 and r.n==3 and r[1]==nil and r[2]=='original' and r[3]==nil)
G.STATE=11
r=pack(love.update('input',nil,'tail'))
assert(count==2 and applied==1 and writes==1 and r.n==3)
assert(G.STATE==11 and G.SETTINGS.GAMESPEED==1 and config.visible and not config.fullscreen)
love.update('input',nil,'tail');assert(count==3 and applied==1 and writes==1)
local ok,err=pcall(love.update,expected_error)
assert(not ok and err==expected_error and count==4 and applied==1)
return true
