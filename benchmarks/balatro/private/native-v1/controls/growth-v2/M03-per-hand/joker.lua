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
        if context.after and context.main_eval and not context.blueprint and not context.game_over then
            card.ability.extra.growth = card.ability.extra.growth + 2
            return {message = 'Growth +2', colour = G.C.MULT}
        end
        if context.joker_main then
            return {mult = card.ability.extra.growth}
        end
    end
}
