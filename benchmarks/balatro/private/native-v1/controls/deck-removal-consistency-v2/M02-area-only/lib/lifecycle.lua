local M={}
function M.targets()
    local selected={}
    for _,card in ipairs(G.hand.highlighted)do selected[#selected+1]=card end
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
