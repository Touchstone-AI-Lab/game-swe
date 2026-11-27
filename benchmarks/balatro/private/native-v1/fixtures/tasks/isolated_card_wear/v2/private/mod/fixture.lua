local stage,frames=0,0
assert(BB_DISPATCHER.register({name='poc.wear2.prepare',description='Initial deck and enhancement construction only',
    schema={stage={type='string',required=true}},execute=function(args,respond)
        if args.stage=='deck' then
            assert(stage==0 and G.STATE==G.STATES.BLIND_SELECT and G.GAME.round==0 and #G.jokers.cards==0)
            for i=#G.playing_cards,9,-1 do G.playing_cards[i]:remove()end
            for _,c in ipairs(G.playing_cards)do c:set_base(G.P_CARDS.H_2)end
            G.GAME.round_resets.blind_choices.Boss='bl_ox';stage=1
        elseif args.stage=='polish' then
            assert(stage==1 and G.STATE==G.STATES.SELECTING_HAND and G.GAME.round==1)
            assert(#G.hand.cards==8 and #G.consumeables.cards==0)
            for _,i in ipairs({1,2,4})do G.hand.cards[i]:set_ability(G.P_CENTERS.m_icw2_polish)end
            G.consumeables:change_size(3-G.consumeables.config.card_limit)
            for count=1,3 do
            local c=create_card('Tarot',G.consumeables,nil,nil,nil,nil,'c_icw2_applicator','wearfixture')
            c:set_edition(nil,true,true);c:add_to_deck();G.consumeables:emplace(c)end;stage=2
        else error('Unknown initial preparation stage')end
        respond({stage=stage,sealed=stage==2})
    end}))
local update=love.update
love.update=function(...)frames=frames+1;return update(...)end
assert(BB_DISPATCHER.register({name='poc.wear2.observe',description='Read-only physical card semantics and actual chips',schema={},
    execute=function(args,respond)
        local cards,hand={},{}
        for _,c in ipairs(G.playing_cards or {})do
            local uses=false
            if c.config.center.key=='m_icw2_polish' then
                uses=c.config.center:loc_vars({},c).vars[1]
                assert(type(uses)=='number','Remaining-use semantic value must be numeric')
            end
            cards[#cards+1]={id=c.sort_id,center=c.config.center.key,uses=uses,
                rank=c.base.id,suit=c.base.suit,edition=c.edition~=nil,debuff=c.debuff==true}
        end
        table.sort(cards,function(a,b)return a.id<b.id end)
        for _,c in ipairs(G.hand and G.hand.cards or {})do hand[#hand+1]=c.sort_id end
        respond({frame=frames,stage=stage,cards=cards,hand=hand,round=G.GAME.round or 0,
            chips=G.GAME.chips or 0,hands=G.GAME.current_round and G.GAME.current_round.hands_played or 0})
    end}))
