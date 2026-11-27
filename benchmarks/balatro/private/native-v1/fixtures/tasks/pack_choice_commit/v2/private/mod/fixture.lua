local stage=0
assert(BB_DISPATCHER.register({name='poc.pc2.prepare',description='Initial deck/shop only, before any pack action',
    schema={stage={type='string',required=true}},execute=function(args,respond)
        if args.stage=='deck' then
            assert(stage==0 and G.STATE==G.STATES.BLIND_SELECT and G.GAME.round==0)
            for _,c in ipairs(G.playing_cards)do c:set_base(G.P_CARDS.H_2)end
            G.GAME.dollars=60;stage=1
        elseif args.stage=='shop' then
            assert(stage==1 and G.STATE==G.STATES.SHOP and G.GAME.round==1 and #G.jokers.cards==0)
            for _,area in ipairs({G.shop_jokers,G.shop_booster})do
                for i=#area.cards,1,-1 do area.cards[i]:remove()end
            end
            for index=1,2 do
            local pack=Card(G.shop_booster.T.x,G.shop_booster.T.y,G.CARD_W*1.27,G.CARD_H*1.27,
                G.P_CARDS.empty,G.P_CENTERS.p_pc2_choices,{bypass_discovery_center=true,bypass_discovery_ui=true})
            pack.ability.booster_pos=index;create_shop_card_ui(pack,'Booster',G.shop_booster)
            pack:start_materialize();G.shop_booster:emplace(pack)end
            local c=create_card('Joker',G.shop_jokers,nil,nil,nil,nil,'j_joker','packprobe')
            c:set_edition(nil,true,true);c:set_cost();G.shop_jokers:emplace(c);create_shop_card_ui(c,'Joker',G.shop_jokers)
            stage=2
        else error('Unknown preparation stage')end
        respond({stage=stage,sealed=stage==2})
    end}))

-- Observation wrappers retain original calls, arguments, returns and exceptions.
local function pack(...)return {n=select('#',...),...}end
local frames,changed,errors,dropped,origin=0,0,0,0,nil
local tracked,events,actions,rows,objects,previewed={},{},{},{},{},{}
local signature=''
local function safe(f,...)
    local r=pack(pcall(f,...));if not r[1] then errors=errors+1 end
    return unpack(r,2,r.n)
end
local function info(c)
    objects[c.sort_id]=c
    return {id=c.sort_id,key=c.config.center.key,set=c.ability.set,cost=c.cost or 0,sell_cost=c.sell_cost or 0,
        added=c.added_to_deck==true,removed=c.REMOVED==true or c.removed==true,edition=c.edition~=nil}
end
local function list(a,preview)
    local out={};for _,c in ipairs(a and a.cards or {})do
        out[#out+1]=info(c);if preview then previewed[c.sort_id]=true end
    end;return out
end
local function log(kind,c)
    if #rows>=256 then dropped=dropped+1;return end
    rows[#rows+1]={frame=frames,kind=kind,id=c and c.sort_id or false,action=origin or 0,
        was_preview=c and previewed[c.sort_id]==true or false}
end
local old_event=EventManager.add_event
EventManager.add_event=function(self,event,...)
    safe(function()
        if origin and not tracked[event] then
            if #events>=1024 then dropped=dropped+1;return end
            local row={id=#events+1,action=origin,registered_frame=frames,calls=0,finished=false,trigger=event.trigger}
            tracked[event]=row;events[#events+1]=row
            local callback=event.func
            event.func=function(...)
                local before=origin;origin=row.action;row.calls=row.calls+1
                local r=pack(callback(...))
                if r[1]then row.finished=true end
                row.last_frame=frames;origin=before;return unpack(r,1,r.n)
            end
        end
    end)
    return old_event(self,event,...)
end
for _,name in ipairs({'add_to_deck','remove'})do
    local original=Card[name]
    Card[name]=function(self,...)
        local r=pack(original(self,...))
        if objects[self.sort_id]then safe(log,name,self)end
        return unpack(r,1,r.n)
    end
end
for _,name in ipairs({'buy','pack','sell','next_round','select','play'})do
    local endpoint=assert(BB_DISPATCHER.endpoints[name]);local execute=endpoint.execute
    endpoint.execute=function(args,respond,...)
        local row={id=#actions+1,method=name,request_id=BB_DISPATCHER.Server.current_request_id,
            started_frame=frames,response_calls=0}
        actions[#actions+1]=row;local before=origin;origin=row.id
        local function response(...)
            row.response_calls=row.response_calls+1;row.response_frame=frames
            return respond(...)
        end
        local r=pack(execute(args,response,...));origin=before;return unpack(r,1,r.n)
    end
end
local function snapshot()
    local state='unknown';for k,v in pairs(G.STATES)do if G.STATE==v then state=k end end
    local locks={};for k,v in pairs(G.CONTROLLER.locks or {})do if v then locks[#locks+1]=k end end
    return {frame=frames,state=state,state_complete=G.STATE_COMPLETE==true,locked=G.CONTROLLER.locked==true,
        locks=locks,paused=G.SETTINGS.paused==true,stop_use=G.GAME.STOP_USE or 0,
        play_count=G.play and #G.play.cards or 0,pack_open=G.pack_cards~=nil and not G.pack_cards.REMOVED,
        preview=list(G.pack_cards,true),owned=list(G.jokers),offers=list(G.shop_jokers),packs=list(G.shop_booster),
        choices=G.GAME.pack_choices or 0,dollars=G.GAME.dollars or 0,stage=stage,
        chips=G.GAME.chips or 0,hands=G.GAME.current_round and G.GAME.current_round.hands_played or 0,round=G.GAME.round or 0}
end
local update=love.update
love.update=function(...)
    local r=pack(update(...));frames=frames+1
    safe(function()
        local s=snapshot();local p={s.state,s.choices,s.dollars,#s.locks,tostring(s.locked),s.stop_use}
        for _,a in ipairs({s.preview,s.owned,s.offers,s.packs})do
            p[#p+1]='area';for _,c in ipairs(a)do p[#p+1]=c.id end
        end
        local value=table.concat(p,':')
        if value~=signature then signature=value;changed=frames;log('state_change')end
    end)
    return unpack(r,1,r.n)
end
assert(BB_DISPATCHER.register({name='poc.pc2.observe',description='Read-only native preview/commit/cancel lifecycle',schema={},
    execute=function(args,respond)
        local s=snapshot();s.quiet_frames=frames-changed;s.observer_errors=errors;s.dropped=dropped
        s.rows=rows;s.events=events;s.actions=actions;s.objects={};s.pending_events=0;s.ledger=PC2_STATUS()
        for _,c in pairs(objects)do s.objects[#s.objects+1]=info(c)end
        for _,q in pairs(G.E_MANAGER.queues)do for _,e in ipairs(q)do
            if tracked[e]then s.pending_events=s.pending_events+1 end
        end end
        respond(s)
    end}))

local core_cases=assert(SMODS.load_file('core_cases.lua','poc_pc2_fixture'))()
assert(BB_DISPATCHER.register({name='poc.pc2.core',description='Isolated core protocol states, not game callbacks',schema={},
    execute=function(args,respond)respond(core_cases(assert(PC2_MODEL)))end}))
