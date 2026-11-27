-- One event per promised product: each releases only the slot it just filled.
local M={}

local function promised(card)
    return card.ability.extra.products
end

function M.can_use(card)
    local inventory=G.consumeables
    if not inventory or card.area~=inventory then return false end
    local others=#inventory.cards-1
    local reserved=G.GAME.consumeable_buffer or 0
    return others+reserved+promised(card)<=inventory.config.card_limit
end

local function deliver_one()
    G.E_MANAGER:add_event(Event({trigger='after',delay=0.2,func=function()
        SMODS.add_card({key='c_mercury',area=G.consumeables})
        G.GAME.consumeable_buffer=G.GAME.consumeable_buffer-1
        return true
    end}))
end

function M.use(card)
    local job=promised(card)
    G.GAME.consumeable_buffer=(G.GAME.consumeable_buffer or 0)+job
    for _=1,job do deliver_one() end
end

return M
