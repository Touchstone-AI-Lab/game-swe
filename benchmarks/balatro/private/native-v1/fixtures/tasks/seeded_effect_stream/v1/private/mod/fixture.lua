-- Initial scene only; all observation below is read-only and bounded.
local stage,frames,lucky_id=0,0,false
local draws,dropped={},0
local function pack(...)return {n=select('#',...),...}end
local random=pseudorandom
pseudorandom=function(seed,...)
    local r=pack(random(seed,...))
    if seed=='lucky_mult' or seed=='lucky_money' or seed=='ses_private_v1' then
        if #draws<128 then draws[#draws+1]={frame=frames,key=seed,value=r[1]}
        else dropped=dropped+1 end
    end
    return unpack(r,1,r.n)
end
assert(BB_DISPATCHER.register({name='poc.stream.prepare',description='Initial ordinary target and native Lucky card only',
    schema={stage={type='string',required=true}},execute=function(args,respond)
        if args.stage=='deck' then
            assert(stage==0 and G.STATE==G.STATES.BLIND_SELECT and G.GAME.round==0 and #G.jokers.cards==0)
            for _,c in ipairs(G.playing_cards)do c:set_base(G.P_CARDS.H_2)end
            local c=create_card('Joker',G.jokers,nil,nil,nil,nil,'j_ses_private_stream','streamfixture')
            c:set_edition(nil,true,true);c:add_to_deck();G.jokers:emplace(c);stage=1
        elseif args.stage=='lucky' then
            assert(stage==1 and G.STATE==G.STATES.SELECTING_HAND and G.GAME.round==1)
            local c=G.hand.cards[#G.hand.cards];c:set_ability(G.P_CENTERS.m_lucky);lucky_id=c.sort_id;stage=2
        else error('Unknown initial stage')end
        respond({stage=stage,sealed=stage==2})
    end}))
local update=love.update
love.update=function(...)frames=frames+1;return update(...)end
local function cards(area)
    local rows={};for _,c in ipairs(area and area.cards or {})do
        rows[#rows+1]={id=c.sort_id,key=c.config.center.key,edition=c.edition~=nil,added=c.added_to_deck==true}
    end
    return rows
end
assert(BB_DISPATCHER.register({name='poc.stream.observe',description='Read-only money, objects, calls and readiness; never samples RNG',schema={},
    execute=function(args,respond)
        local state='unknown';for k,v in pairs(G.STATES)do if G.STATE==v then state=k end end
        local locks={};for k,v in pairs(G.CONTROLLER.locks or {})do if v then locks[#locks+1]=k end end
        respond({frame=frames,state=state,state_complete=G.STATE_COMPLETE==true,locked=G.CONTROLLER.locked==true,
            locks=locks,paused=G.SETTINGS.paused==true,stop_use=G.GAME.STOP_USE or 0,
            play_count=G.play and #G.play.cards or 0,stage=stage,lucky_id=lucky_id,
            hand=cards(G.hand),discard=cards(G.discard),jokers=cards(G.jokers),playing_count=#G.playing_cards,
            draws=draws,dropped=dropped,chips=G.GAME.chips or 0,dollars=G.GAME.dollars or 0,
            hands=G.GAME.current_round and G.GAME.current_round.hands_played or 0,
            discards=G.GAME.current_round and G.GAME.current_round.discards_used or 0})
    end}))
