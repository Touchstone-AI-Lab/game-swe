local M={}
local cache=setmetatable({},{__mode='k'})
local function state(card)
    cache[card]=cache[card] or card.ability.extra;return cache[card]
end
function M.remaining(card)return state(card).uses end
function M.apply(card,center)
    if card.config.center.key==center.key then state(card)end
    card:set_ability(center)
    
end
function M.score(card)
    local current=state(card)
    if current.uses>0 then
        current.uses=current.uses-1
        local reward=current.uses>0 and 20 or 0
        if current.uses==0 then card:set_ability(G.P_CENTERS.c_base)end
        return {chips=reward}
    end
end
return M
