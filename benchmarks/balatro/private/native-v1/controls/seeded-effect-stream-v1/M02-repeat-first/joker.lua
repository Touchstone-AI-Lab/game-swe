SMODS.Joker {
    key = 'private_stream',
    loc_txt = {name = 'Private Stream', text = {'Each player discard earns', 'one seeded $1 to $9 reward'}},
    rarity = 1, cost = 4, pos = {x = 0, y = 0}, config = {extra = {}},
    calculate = function(self, card, context)
        if context.pre_discard and not context.blueprint and not context.hook then
            card.ability.extra.first = card.ability.extra.first or (1 + math.floor(9 * pseudorandom('ses_private_v1')))
            ease_dollars(card.ability.extra.first, true)
        end
    end
}
