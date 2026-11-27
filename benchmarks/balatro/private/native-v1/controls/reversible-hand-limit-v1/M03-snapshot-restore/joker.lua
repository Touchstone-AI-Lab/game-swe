SMODS.Joker {
    key='spacer',
    loc_txt={name='Reversible Hand Limit',text={'+2 hand limit while owned'}},
    config={extra={amount=2}},rarity=1,cost=2,unlocked=true,discovered=true,
    blueprint_compat=false,pos={x=0,y=0},
    add_to_deck=function(self,card,from_debuff)
        card.ability.extra.prior = G.hand.config.card_limit
        G.hand:change_size(card.ability.extra.amount)
    end,
    remove_from_deck=function(self,card,from_debuff)
        G.hand:change_size(card.ability.extra.prior - G.hand.config.card_limit)
    end
}
