local M={}
function M.can_use(card)
    local quantity=card.ability.extra.products
    return G.consumeables and card.area==G.consumeables and
        #G.consumeables.cards-1+(G.GAME.consumeable_buffer or 0)+quantity<=G.consumeables.config.card_limit
end
function M.use(card)
    local quantity=card.ability.extra.products
    G.GAME.consumeable_buffer=G.GAME.consumeable_buffer+quantity
    G.E_MANAGER:add_event(Event({trigger='after',delay=1,blocking=false,blockable=false,
        func=function()
            for i=1,quantity do
                G.GAME.consumeable_buffer=G.GAME.consumeable_buffer-1
                if i<=2 then SMODS.add_card({key='c_mercury',area=G.consumeables})end
            end
            return true
        end}))
end
return M
