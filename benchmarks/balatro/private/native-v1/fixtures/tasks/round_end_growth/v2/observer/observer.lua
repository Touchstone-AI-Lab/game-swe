local sealed, frames = false, 0
local events, preparation = {}, {}
local function target()
    assert(G.jokers and #G.jokers.cards == 1, 'Expected one candidate')
    return G.jokers.cards[1]
end
local old_update = love.update
love.update = function(dt) frames = frames + 1; return old_update(dt) end
local old_calculate = Card.calculate_joker
local function pack(...) return {n=select('#', ...), ...} end
Card.calculate_joker = function(self, context)
    local e
    if self.config.center.key == 'j_poc_growth' and (context.end_of_round or context.joker_main) then
        e={round=G.GAME.round, main_eval=context.main_eval == true, end_of_round=context.end_of_round == true,
           individual=context.individual == true, repetition=context.repetition == true,
           held=#G.hand.cards, before=self.ability.extra.growth, scoring_name=context.scoring_name}
    end
    local values = pack(old_calculate(self, context))
    if e then e.after=self.ability.extra.growth; events[#events+1]=e end
    assert(#events < 600, 'Observation bound')
    return unpack(values,1,values.n)
end
assert(BB_DISPATCHER.register({name='poc.prepare',description='One-time mixed-eights preparation',schema={},
    requires_state={G.STATES.BLIND_SELECT},execute=function(args,respond)
        assert(not sealed and G.GAME.round == 0 and #G.jokers.cards == 0, 'Fresh scenario required')
        SMODS.add_card({key='j_poc_growth',area=G.jokers})
        local keys={'H_8','D_8','C_8','S_8'}
        for i,card in ipairs(G.playing_cards) do card:set_base(G.P_CARDS[keys[(i-1)%4+1]]) end
        G.hand:change_size(6-G.hand.config.card_limit)
        G.GAME.round_resets.blind_choices.Boss='bl_ox'
        preparation={candidate='SMODS.add_card',card_bases='52 mixed-suit rank 8',hand_limit=6,boss='bl_ox',sealed=true}
        sealed=true
        respond(preparation)
    end}))
assert(BB_DISPATCHER.register({name='poc.observe',description='Read-only growth v2 engine fields',schema={},
    execute=function(args,respond)
        assert(sealed, 'Prepare first')
        local card=target()
        local plain, suits=true, {}
        for _,c in ipairs(G.playing_cards) do
            if c.edition or c.seal or c.debuff or c.config.center.key~='c_base' or c.base.id~=8 then plain=false end
            suits[c.base.suit]=true
        end
        local suit_count=0; for _ in pairs(suits) do suit_count=suit_count+1 end
        respond({growth=card.ability.extra.growth,frame=frames,round=G.GAME.round,chips=G.GAME.chips,
            joker_key=card.config.center.key,joker_count=#G.jokers.cards,joker_debuff=card.debuff == true,
            joker_edition=card.edition ~= nil,plain=plain,suit_count=suit_count,hand_limit=G.hand.config.card_limit,
            hand_count=#G.hand.cards,blind_key=G.GAME.blind and G.GAME.blind.config.blind.key,
            high_level=G.GAME.hands['High Card'].level,pair_level=G.GAME.hands['Pair'].level,
            four_level=G.GAME.hands['Four of a Kind'].level,events=events,preparation=preparation})
    end}))
