local M={}

local function state(card)
    return card.ability.extra
end
function M.remaining(card)return state(card).uses end
function M.apply(card,center)
    local previous=card.config.center.key==center.key and state(card).uses or 0
    card:set_ability(center)
    card.ability.extra.uses=previous+2
end
function M.score(card)
    local current=state(card)
    if current.uses>0 then
        current.uses=current.uses-1
        local reward=20
        if current.uses==0 then card:set_ability(G.P_CENTERS.c_base)end
        return {chips=reward}
    end
end
return M
