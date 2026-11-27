SMODS.Joker {
    key = 'growth',
    loc_txt = {name = 'Round End Growth', text = {
        'Gains {C:mult}+2{} Mult after each',
        'completed blind', '(Currently {C:mult}+#1#{} Mult)'}},
    config = {extra = {growth = 0}},
    rarity = 1, cost = 4, unlocked = true, discovered = true,
    blueprint_compat = false, pos = {x = 0, y = 0},
    loc_vars = function(self, info_queue, card)
        return {vars = {card.ability.extra.growth}}
    end,
    calculate = function(self, card, context)
        if context.end_of_round and not context.individual and not context.repetition and not context.blueprint and not context.game_over then
            if card.ability.extra.last_awarded_round == G.GAME.round then return end
            card.ability.extra.last_awarded_round = G.GAME.round
            card.ability.extra.growth = card.ability.extra.growth + 2
            return {message = 'Growth +2', colour = G.C.MULT}
        end
        if context.joker_main then
            return {mult = card.ability.extra.growth}
        end
    end
}
