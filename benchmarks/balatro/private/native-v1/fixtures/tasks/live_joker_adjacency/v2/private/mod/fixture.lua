local prepared,frames=false,0
local objects={}
assert(BB_DISPATCHER.register({name='poc.lja2.prepare',description='Initial native multi-instance scene only',schema={mode={type='string',required=true}},
    execute=function(args,respond)
        assert(not prepared and G.STATE==G.STATES.BLIND_SELECT and G.GAME.round==0 and #G.jokers.cards==0)
        for _,c in ipairs(G.playing_cards)do c:set_base(G.P_CARDS.H_2)end
        G.GAME.dollars=100
        local keys=args.mode=='single' and {'j_credit_card','j_lja2_neighbors','j_four_fingers'} or {'j_credit_card','j_lja2_neighbors','j_lja2_neighbors','j_four_fingers','j_splash'}
        assert(args.mode=='single' or args.mode=='multi')
        for _,key in ipairs(keys)do
            local c=SMODS.add_card({key=key,area=G.jokers});c:set_edition(nil,true,true)
        end
        G.SETTINGS.tutorial_progress=G.SETTINGS.tutorial_progress or {}
        G.SETTINGS.tutorial_progress.forced_shop={'c_pluto','j_lja2_neighbors'}
        prepared=true;respond({prepared=true})
    end}))
local update=love.update
love.update=function(...)frames=frames+1;return update(...)end
local function info(c)
    objects[c.sort_id]=c
    return {id=c.sort_id,key=c.config.center.key,rarity=c.config.center.rarity or false,
        cost=c.cost,sell_cost=c.sell_cost,edition=c.edition~=nil,debuff=c.debuff==true,
        removed=c.REMOVED==true or c.removed==true}
end
local function list(area)
    local out={};for _,c in ipairs(area and area.cards or {})do out[#out+1]=info(c)end;return out
end
assert(BB_DISPATCHER.register({name='poc.lja2.observe',description='Read-only row/shop/physical identities and score',schema={},
    execute=function(args,respond)
        local state='unknown';for k,v in pairs(G.STATES)do if G.STATE==v then state=k end end
        local owned=list(G.jokers);local shop=list(G.shop_jokers);local all={}
        for _,c in pairs(objects)do all[#all+1]=info(c)end
        table.sort(all,function(a,b)return a.id<b.id end)
        local locks={};for k,v in pairs(G.CONTROLLER.locks or {})do if v then locks[#locks+1]=k end end
        respond({frame=frames,state=state,prepared=prepared,owned=owned,shop=shop,objects=all,
            state_complete=G.STATE_COMPLETE==true,locked=G.CONTROLLER.locked==true,locks=locks,
            paused=G.SETTINGS.paused==true,stop_use=G.GAME.STOP_USE or 0,
            play_count=G.play and #G.play.cards or 0,joker_limit=G.jokers and G.jokers.config.card_limit or 0,
            chips=G.GAME.chips or 0,dollars=G.GAME.dollars or 0,round=G.GAME.round or 0,
            hands=G.GAME.current_round and G.GAME.current_round.hands_played or 0})
    end}))
