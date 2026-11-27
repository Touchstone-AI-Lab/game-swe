local M={}
function M.targets()
    local selected={}
    for _,card in ipairs(G.hand.highlighted)do selected[#selected+1]=card end
    return selected
end
function M.destroy(selected)
    SMODS.destroy_cards(selected)
end
return M
