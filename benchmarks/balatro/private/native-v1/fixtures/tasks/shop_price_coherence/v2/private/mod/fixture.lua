local core_cases=assert(SMODS.load_file('core_cases.lua'))()
local stage, sealed,scene = 0, false,'normal'
assert(BB_DISPATCHER.register({name='poc.spc2.prepare',description='Declared initial deck/shop only',
    schema={stage={type='string',required=true},scene={type='string',required=false}},execute=function(args,respond)
        if args.stage=='deck' then
            assert(stage==0 and G.STATE==G.STATES.BLIND_SELECT and G.GAME.round==0)
            for _,c in ipairs(G.playing_cards)do c:set_base(G.P_CARDS.H_2)end
            scene=args.scene or 'normal';assert(scene=='normal' or scene=='funds' or scene=='capacity')
            G.GAME.dollars=150;stage=1
        elseif args.stage=='shop' then
            assert(stage==1 and not sealed and G.STATE==G.STATES.SHOP and G.GAME.round==1)
            assert(#G.jokers.cards==0 and G.GAME.discount_percent==0)
            assert(not SMODS.optional_features.object_weights)
            for _,area in ipairs({G.shop_jokers,G.shop_vouchers})do
                for i=#area.cards,1,-1 do area.cards[i]:remove()end
            end
            G.GAME.shop.joker_max=4
            G.shop_jokers:change_size(4-G.shop_jokers.config.card_limit)
            local keys=scene=='normal' and {'j_sp2_flat','j_sp2_ratio','j_sp2_ratio','j_sp2_coupon'} or {'j_sp2_coupon','j_fibonacci','j_joker','c_pluto'}
            for _,key in ipairs(keys)do
                local c=create_card(G.P_CENTERS[key].set,G.shop_jokers,nil,nil,nil,nil,key,'priceprobe')
                c:set_edition(nil,true,true);c:set_cost()
                G.shop_jokers:emplace(c);create_shop_card_ui(c,c.ability.set,G.shop_jokers)
            end
            G.SETTINGS.tutorial_progress=G.SETTINGS.tutorial_progress or {}
            G.SETTINGS.tutorial_progress.forced_shop={'c_pluto','j_joker','j_sp2_ratio','j_fibonacci','j_sp2_coupon','c_mercury','j_fibonacci','j_sp2_flat','j_greedy_joker','j_fibonacci','j_fibonacci','c_pluto'}
            G.jokers.config.card_limit=12
            if scene~='normal' then
                local c=create_card('Joker',G.jokers,nil,nil,nil,nil,'j_banner','spc2fixture')
                c:set_edition(nil,true,true);c:add_to_deck();G.jokers:emplace(c)
                if scene=='funds' then G.GAME.dollars=4 else G.jokers.config.card_limit=2 end
            end
            stage=2;sealed=true
        else error('Unknown initial stage')end
        respond({stage=stage,sealed=sealed})
    end}))

-- Observer only below this line. Never sets a price or invokes an effect.
local function pack(...)return {n=select('#',...),...}end
local frames,changed,errors,dropped=0,0,0,0
local rows,objects,signature={}, {}, ''
local function quote(c)
    local root=c.children and c.children.price and c.children.price.definition
    local function visit(n,depth)
        if not n or depth>8 then return nil end
        local o=n.config and n.config.object
        local text=o and o.config and o.config.string and o.config.string[1]
        if type(text)=='table' and text.ref_table and text.ref_value then
            return {value=text.ref_table[text.ref_value],same_card=text.ref_table==c,field=text.ref_value}
        end
        for _,child in ipairs(n.nodes or {})do local r=visit(child,depth+1);if r then return r end end
    end
    return visit(root,0) or false
end
local function info(c)
    return {id=c.sort_id,key=c.config.center.key,set=c.ability.set,cost=c.cost,
        base_cost=c.base_cost,extra_cost=c.extra_cost,sell_cost=c.sell_cost,
        quote=quote(c),buy_ready=c.children and c.children.buy_button~=nil,
        edition=c.edition~=nil,debuff=c.debuff==true,added=c.added_to_deck==true,
        removed=c.REMOVED==true or c.removed==true}
end
local function area(a)
    local list={};for _,c in ipairs(a and a.cards or {})do objects[c.sort_id]=c;list[#list+1]=info(c)end
    return list
end
local function snapshot()
    local state='unknown';for k,v in pairs(G.STATES)do if G.STATE==v then state=k end end
    local locks={};for k,v in pairs(G.CONTROLLER.locks or {})do if v then locks[#locks+1]=k end end
    table.sort(locks)
    return {frame=frames,state=state,state_complete=G.STATE_COMPLETE==true,locked=G.CONTROLLER.locked==true,
        locks=locks,paused=G.SETTINGS.paused==true,stop_use=G.GAME.STOP_USE or 0,
        shop=area(G.shop_jokers),vouchers=area(G.shop_vouchers),owned=area(G.jokers),consumables=area(G.consumeables),
        dollars=G.GAME.dollars or 0,discount=G.GAME.discount_percent or 0,
        reroll_cost=G.GAME.current_round and G.GAME.current_round.reroll_cost or 0,
        hands_played=G.GAME.hands_played or 0,chips=G.GAME.chips or 0,play_count=G.play and #G.play.cards or 0,
        stage=stage,sealed=sealed,joker_limit=G.jokers and G.jokers.config.card_limit or 0,round=G.GAME.round,forced_remaining=G.SETTINGS.tutorial_progress and
            #(G.SETTINGS.tutorial_progress.forced_shop or {}) or 0}
end
local previous=love.update
love.update=function(...)
    local r=pack(previous(...));frames=frames+1
    local ok=pcall(function()
        local s=snapshot();local sig={s.state,s.dollars,s.discount,s.reroll_cost,#s.locks,tostring(s.locked),s.stop_use}
        for _,list in ipairs({s.shop,s.vouchers,s.owned})do
            for _,c in ipairs(list)do sig[#sig+1]=c.id..'/'..c.cost..'/'..tostring(c.quote and c.quote.value)end
        end
        local value=table.concat(sig,':')
        if value~=signature then
            signature=value;changed=frames
            if #rows<192 then rows[#rows+1]={frame=frames,state=s.state,dollars=s.dollars,discount=s.discount,
                shop=s.shop,vouchers=s.vouchers,owned=s.owned}
            else dropped=dropped+1 end
        end
    end)
    if not ok then errors=errors+1 end
    return unpack(r,1,r.n)
end
assert(BB_DISPATCHER.register({name='poc.spc2.observe',description='Read-only quote/identity/debit state',schema={},
    execute=function(args,respond)
        local s=snapshot();s.rows=rows;s.quiet_frames=frames-changed;s.observer_errors=errors;s.dropped=dropped
        s.objects={};for _,c in pairs(objects)do s.objects[#s.objects+1]=info(c)end
        table.sort(s.objects,function(a,b)return a.id<b.id end);respond(s)
    end}))

assert(BB_DISPATCHER.register({name='poc.spc2.protocol',description='Independent public-core protocol cases; not gameplay',schema={},
    execute=function(args,respond)
        assert(stage==0 and G.STATE==G.STATES.MENU)
        respond({scope='isolated-core-protocol',cases=core_cases(SPC2_MODEL)})
    end}))
