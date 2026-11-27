-- Records what each physical instance added, so removal gives back exactly that amount.
local contributed=setmetatable({},{__mode='k'})

local function acquire(card)
    if contributed[card] then return end
    contributed[card]=card.ability.extra.amount
    G.hand:change_size(contributed[card])
end

local function release(card)
    local amount=contributed[card]
    if not amount then return end
    contributed[card]=nil
    G.hand:change_size(-amount)
end

SMODS.Joker {
    key='spacer',
    loc_txt={name='Reversible Hand Limit',text={'+2 hand limit while owned'}},
    config={extra={amount=2}},rarity=1,cost=2,unlocked=true,discovered=true,
    blueprint_compat=false,pos={x=0,y=0},
    add_to_deck=function(self,card,from_debuff)
        acquire(card)
    end,
    remove_from_deck=function(self,card,from_debuff)
        release(card)
    end
}
