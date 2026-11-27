-- Tallies the whole row once per hand and looks each physical instance up by identity.
local M={}
local tally

local function common(card)
    return card~=nil and card.config.center.rarity==1
end

local function neighbours(cards)
    local counts={}
    for i,card in ipairs(cards)do
        counts[card]=(common(cards[i-1]) and 1 or 0)+(common(cards[i+1]) and 1 or 0)
    end
    return counts
end

function M.begin_hand(cards)
    tally=neighbours(cards)
end

function M.count(card,cards)
    if tally==nil or tally[card]==nil then M.begin_hand(cards) end
    return tally[card] or 0
end

return M
