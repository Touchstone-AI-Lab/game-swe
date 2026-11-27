local M={}
function M.targets()
    local selected={}
    for i,card in ipairs(G.hand.highlighted)do if i<=2 then selected[#selected+1]=card end end
    return selected
end
function M.destroy(selected)
    SMODS.destroy_cards(selected)
end
return M
