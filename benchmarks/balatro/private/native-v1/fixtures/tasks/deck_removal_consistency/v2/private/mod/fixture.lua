-- Initial fixture and bounded passive observation only.
local prepared=false
local stage=0
local mode=nil
assert(BB_DISPATCHER.register({name='poc.dr2.prepare',description='Initial deck and mixed ordinary hand only',
    schema={stage={type='string',required=true},mode={type='string',required=true}},execute=function(args,respond)
        if args.stage=='deck'then
            assert(stage==0 and G.STATE==G.STATES.BLIND_SELECT and G.GAME.round==0 and #G.jokers.cards==0)
            assert(args.mode=='single' or args.mode=='four' or args.mode=='repeat');mode=args.mode
            assert(G.GAME.pseudorandom.seed=='BATCHTASK2')
            for i=#G.playing_cards,17,-1 do G.playing_cards[i]:remove()end
            for _,c in ipairs(G.playing_cards)do c:set_base(G.P_CARDS.H_2)end
            assert(#G.consumeables.cards==0)
            if mode=='repeat'then G.consumeables:change_size(1)end
            for i=1,(mode=='repeat' and 2 or 1)do SMODS.add_card({key='c_dr2_clean_cut',area=G.consumeables})end
            SMODS.add_card({key='c_pluto',area=G.consumeables});stage=1
        elseif args.stage=='hand'then
            assert(args.mode==mode)
            assert(stage==1 and G.STATE==G.STATES.SELECTING_HAND and G.GAME.round==1 and #G.hand.cards==8)
            for _,v in ipairs({{2,'D_3'},{3,'S_4'},{6,'C_5'},{8,'D_3'}})do
                G.hand.cards[v[1]]:set_base(G.P_CARDS[v[2]])
            end
            stage=2;prepared=true
        else error('Unknown preparation phase')end
        respond({stage=stage,sealed=prepared})
    end}))
-- Bounded read-only snapshots. No removal, draw or callback is performed here.
local frames,changed,errors,dropped=0,0,0,0
local rows,objects,signature={},{},''
local function pack(...)return {n=select('#',...),...}end
local function info(c)
    objects[c.sort_id]=c
    return {id=c.sort_id,rank=c.base.id,suit=c.base.suit,center=c.config.center.key,
        removed=c.REMOVED==true or c.removed==true}
end
local function list(cards)
    local out={};for _,c in ipairs(cards or {})do out[#out+1]=info(c)end;return out
end
local function snapshot()
    local state='unknown';for k,v in pairs(G.STATES)do if G.STATE==v then state=k end end
    return {frame=frames,state=state,prepared=prepared,
        registered=list(G.playing_cards),hand=list(G.hand and G.hand.cards),deck=list(G.deck and G.deck.cards),
        discard=list(G.discard and G.discard.cards),play=list(G.play and G.play.cards),
        deck_limit=G.deck and G.deck.config.card_limit or 0}
end
local original=love.update
love.update=function(...)
    local r=pack(original(...));frames=frames+1
    local ok=pcall(function()
        local s=snapshot();local parts={s.state,s.deck_limit}
        for _,name in ipairs({'registered','hand','deck','discard','play'})do
            parts[#parts+1]=name
            for _,c in ipairs(s[name])do parts[#parts+1]=c.id..'/'..tostring(c.removed)end
        end
        local sig=table.concat(parts,':')
        if sig~=signature then
            signature=sig;changed=frames
            if #rows<256 then rows[#rows+1]=s else dropped=dropped+1 end
        end
    end)
    if not ok then errors=errors+1 end
    return unpack(r,1,r.n)
end
assert(BB_DISPATCHER.register({name='poc.dr2.observe',description='Read-only registered and area membership',schema={},
    execute=function(args,respond)
        local s=snapshot();s.quiet_frames=frames-changed;s.observer_errors=errors;s.dropped=dropped;s.rows=rows;s.objects={}
        for _,c in pairs(objects)do s.objects[#s.objects+1]=info(c)end
        table.sort(s.objects,function(a,b)return a.id<b.id end);respond(s)
    end}))
