-- No charge storage knowledge; loc_vars is the public pure semantic display read.
local KEY='j_dc2_charge'
local seen_targets={}
local function pack(...) return {n=select('#', ...), ...} end
local loaded=setmetatable({}, {__mode='k'})
local fixture_calls, load_count, add_count, frames = 0,0,0,0
local events, dropped = {}, 0
local function charge(card)
    local value=card.config.center:loc_vars({},card).vars[1]
    assert(type(value)=='number', 'Charge display must be numeric')
    return value
end
local old_load=Card.load
Card.load=function(self, ...)
    local r=pack(old_load(self,...))
    if self.config.center.key==KEY then loaded[self]=true;load_count=load_count+1;seen_targets[self.sort_id]=self end
    return unpack(r,1,r.n)
end
local old_add=SMODS.add_card
SMODS.add_card=function(...)
    local r=pack(old_add(...))
    if r[1] and r[1].config.center.key==KEY then add_count=add_count+1;seen_targets[r[1].sort_id]=r[1] end
    return unpack(r,1,r.n)
end
local old_calc=Card.calculate_joker
Card.calculate_joker=function(self, context, ...)
    local e
    if self.config.center.key==KEY and (context.pre_discard or context.discard or context.joker_main or context.after) then
        e={id=self.sort_id,pre_discard=context.pre_discard==true, discard=context.discard==true,
            joker_main=context.joker_main==true, after=context.after==true,
            individual=context.individual==true, repetition=context.repetition==true,
            before=charge(self), hand_count=context.full_hand and #context.full_hand or 0}
    end
    local r=pack(old_calc(self,context,...))
    if e then
        e.charge_after=charge(self)
        if #events<256 then events[#events+1]=e else dropped=dropped+1 end
    end
    return unpack(r,1,r.n)
end
local old_update=love.update
love.update=function(...)
    frames=frames+1
    return old_update(...)
end

local prepared=false
assert(BB_DISPATCHER.register({name='poc.dc2.prepare',description='One initial target-free-state fixture',schema={},
    requires_state={G.STATES.BLIND_SELECT},execute=function(args,respond)
        assert(not prepared and G.GAME.round==0 and G.GAME.pseudorandom.seed=='DURABLE2' and #G.jokers.cards==0)
        assert(#G.consumeables.cards==0)
        SMODS.add_card({key=KEY,area=G.jokers,no_edition=true})
        for i=1,2 do SMODS.add_card({key='c_dc2_recruit',area=G.consumeables,no_edition=true})end
        local keys={'H_8','D_8','C_8','S_8'}
        for i,c in ipairs(G.playing_cards)do c:set_base(G.P_CARDS[keys[(i-1)%4+1]])end
        G.hand:change_size(8-G.hand.config.card_limit)
        G.GAME.round_resets.hands=20;G.GAME.round_resets.discards=20
        G.GAME.starting_params.ante_scaling=100
        prepared=true;fixture_calls=fixture_calls+1
        respond({prepared=true,fixture_calls=fixture_calls})
    end}))
assert(BB_DISPATCHER.register({name='poc.dc2.observe',description='Read-only multi-instance charge and native lifecycle',schema={},
    execute=function(args,respond)
        local targets={}
        for _,c in ipairs(G.jokers and G.jokers.cards or {})do
            if c.config.center.key==KEY then targets[#targets+1]={id=c.sort_id,charge=charge(c),loaded=loaded[c]==true,
                key=c.config.center.key,edition=c.edition~=nil,debuff=c.debuff==true}end
        end
        local inventory,objects={},{}
        for id,c in pairs(seen_targets)do objects[#objects+1]={id=id,removed=c.REMOVED==true or c.removed==true}end
        table.sort(objects,function(a,b)return a.id<b.id end)
        for _,c in ipairs(G.consumeables and G.consumeables.cards or {})do
            inventory[#inventory+1]={id=c.sort_id,key=c.config.center.key}
        end
        respond({targets=targets,objects=objects,inventory=inventory,fixture_calls=fixture_calls,load_count=load_count,add_count=add_count,
            frame=frames,chips=G.GAME.chips or 0,events=events,dropped=dropped,
            joker_count=G.jokers and #G.jokers.cards or 0,capacity=G.jokers and G.jokers.config.card_limit or 0})
    end}))

local core_cases=assert(SMODS.load_file('core_cases.lua','poc_dc2_fixture'))()
assert(BB_DISPATCHER.register({name='poc.dc2.core',description='Isolated public-core protocol tests; no gameplay callbacks',schema={},
    execute=function(args,respond)respond(core_cases(assert(DC2_MODEL)))end}))
