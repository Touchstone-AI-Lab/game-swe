assert(BB_DISPATCHER, 'BalatroBot must load first')
-- BalatroBot skips the tutorial, but a brand-new profile has no progress table.
-- Prepare only the isolated fresh settings; never copy daily user settings.
G.SETTINGS.tutorial_progress = G.SETTINGS.tutorial_progress or {completed_parts={}}
G.SETTINGS.tutorial_complete = true
-- Steamodded 26.829.0 run-selection no longer guarantees viewed_back.
-- BalatroBot v1.5.2 start() dereferences it after setup_run(). Supply the
-- ordinary Back instance only when absent; leave both dependencies untouched.
local previous_setup_run = G.FUNCS.setup_run
G.FUNCS.setup_run = function(...)
    local result = previous_setup_run(...)
    if not G.GAME.viewed_back then G.GAME.viewed_back = Back(G.P_CENTERS.b_red) end
    return result
end
assert(BB_DISPATCHER.register({
    name = 'poc.runtime', description = 'Read-only runtime identity', schema = {},
    execute = function(args, respond)
        local mods = {}
        for _, m in ipairs(SMODS.mod_list) do
            if m.can_load then mods[#mods+1] = {id=m.id, version=m.version or 'unknown'} end
        end
        respond({save_dir=love.filesystem.getSaveDirectory(), mod_dir=require('lovely').mod_dir,
            steamodded=SMODS.version, game_version=G.VERSION, mods=mods,
            nonce=os.getenv('POC_NONCE'), steam_active=G.STEAM ~= nil,
            love_version=love._version, visible=love.window.isVisible()})
    end
}))
local quit_requested = false
assert(BB_DISPATCHER.register({
    name = 'poc.quit', description = 'Request ordinary LÖVE quit after RPC response', schema = {},
    execute = function(args, respond)
        quit_requested = true
        respond({accepted=true})
    end
}))
local previous_update = love.update
love.update = function(dt)
    if quit_requested then love.event.quit(); return end
    previous_update(dt)
end
