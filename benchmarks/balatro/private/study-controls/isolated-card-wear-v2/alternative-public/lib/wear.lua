-- Wear lives beside the card, keyed by physical object, so no center or ability table is shared.
local M={}
local FRESH=2
local spent=setmetatable({},{__mode='k'})

function M.remaining(card)
    return FRESH-(spent[card] or 0)
end

function M.apply(card,center)
    if card.config.center.key~=center.key then card:set_ability(center) end
    spent[card]=nil
end

function M.score(card)
    if M.remaining(card)<=0 then return end
    spent[card]=(spent[card] or 0)+1
    if M.remaining(card)==0 then
        spent[card]=nil
        card:set_ability(G.P_CENTERS.c_base)
    end
    return {chips=20}
end

return M
