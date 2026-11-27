-- Preparation is restricted to the declared starting deck and first shop, before testing ownership.
local prepared,sealed,preparations=false,false,0
assert(BB_DISPATCHER.register({name='poc.hl.prepare',description='One starting deck/shop preparation',
    schema={stage={type='string',required=true}},
    execute=function(args,respond)
        if args.stage=='deck' then
            assert(not prepared and not sealed and G.STATE==G.STATES.BLIND_SELECT and G.GAME.round==0)
            assert(#G.jokers.cards==0)
            for _,card in ipairs(G.playing_cards) do card:set_base(G.P_CARDS.H_2) end
            G.GAME.dollars=50;prepared=true;preparations=preparations+1
        elseif args.stage=='shop' then
            assert(prepared and not sealed and G.STATE==G.STATES.SHOP and G.GAME.round==1)
            assert(#G.jokers.cards==0)
            for i=#G.shop_jokers.cards,1,-1 do G.shop_jokers.cards[i]:remove() end
            G.shop_jokers:change_size(5-G.shop_jokers.config.card_limit)
            for _,key in ipairs({'j_rhl_spacer','j_rhl_spacer','j_juggler','j_rhl_spacer','j_rhl_spacer'}) do
                local card=create_card('Joker',G.shop_jokers,nil,nil,nil,nil,key,'hlfixture')
                card:set_edition(nil,true,true) -- declared ordinary starting objects, before acquisition/seal
                G.shop_jokers:emplace(card)
                create_shop_card_ui(card,'Joker',G.shop_jokers)
            end
            sealed=true;preparations=preparations+1
        else error('Unknown preparation stage') end
        respond({prepared=prepared,sealed=sealed,preparations=preparations})
    end
}))
-- Everything below is observation; no candidate callback is invoked or replaced.
local function pack(...) return {n=select('#',...),...} end
local frames,changed,dropped,errors=0,0,0,0
local rows,signature,objects={},'',{}
local function name()
    for k,v in pairs(G.STATES) do if v==G.STATE then return k end end
    return tostring(G.STATE)
end
local function info(c)
    return {id=c.sort_id,key=c.config.center.key,added=c.added_to_deck==true,
        cost=c.cost,sell_cost=c.sell_cost,edition=c.edition~=nil,debuff=c.debuff==true,
        removed=c.REMOVED==true or c.removed==true,owned=c.area==G.jokers,
        buy_ready=c.children and c.children.buy_button~=nil}
end
local function cards(area)
    local out={}
    for _,c in ipairs(area and area.cards or {}) do objects[c.sort_id]=c;out[#out+1]=info(c) end
    return out
end
local function snapshot()
    local locks={}
    for k,v in pairs(G.CONTROLLER.locks or {}) do if v then locks[#locks+1]=k end end
    table.sort(locks)
    local ids={}
    for _,c in ipairs(G.hand and G.hand.cards or {}) do ids[#ids+1]=c.sort_id end
    return {frame=frames,state=name(),state_complete=G.STATE_COMPLETE==true,
        locked=G.CONTROLLER.locked==true,locks=locks,paused=G.SETTINGS.paused==true,
        stop_use=G.GAME.STOP_USE or 0,hand_limit=G.hand and G.hand.config.card_limit or 0,
        hand_count=G.hand and #G.hand.cards or 0,hand_ids=ids,
        play_count=G.play and #G.play.cards or 0,jokers=cards(G.jokers),shop=cards(G.shop_jokers),
        dollars=G.GAME.dollars or 0,round=G.GAME.round or 0,
        hands_played=G.GAME.current_round and G.GAME.current_round.hands_played or 0,
        prepared=prepared,sealed=sealed,preparations=preparations}
end
local previous=love.update
love.update=function(...)
    local r=pack(previous(...));frames=frames+1
    local ok=pcall(function()
        local s=snapshot()
        local sig=table.concat({s.state,s.hand_limit,s.hand_count,#s.jokers,#s.shop,s.dollars,
            tostring(s.locked),#s.locks,s.stop_use},':')
        if sig~=signature then
            changed=frames;signature=sig
            if #rows<256 then rows[#rows+1]={frame=frames,state=s.state,limit=s.hand_limit,
                hand_count=s.hand_count,joker_count=#s.jokers,shop_count=#s.shop}
            else dropped=dropped+1 end
        end
    end)
    if not ok then errors=errors+1 end
    return unpack(r,1,r.n)
end
assert(BB_DISPATCHER.register({name='poc.hl.observe',description='Read-only native ownership and actual hand telemetry',schema={},
    execute=function(args,respond)
        local s=snapshot();s.quiet_frames=frames-changed;s.rows=rows;s.dropped=dropped;s.observer_errors=errors
        s.objects={}
        for _,c in pairs(objects) do s.objects[#s.objects+1]=info(c) end
        table.sort(s.objects,function(a,b)return a.id<b.id end)
        respond(s)
    end
}))
