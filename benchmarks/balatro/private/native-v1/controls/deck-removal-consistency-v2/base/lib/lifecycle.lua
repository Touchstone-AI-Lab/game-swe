local M={}
function M.targets()
    local selected={}
    if #G.hand.highlighted>1 then
        for i=1,#G.hand.highlighted do selected[#selected+1]=G.hand.cards[i]end
    else
        for _,card in ipairs(G.hand.highlighted)do selected[#selected+1]=card end
    end
    return selected
end
function M.destroy(selected)
    if #selected>1 then
        for _,card in ipairs(selected)do G.hand:remove_card(card)end
    else
        SMODS.destroy_cards(selected)
    end
end
return M
