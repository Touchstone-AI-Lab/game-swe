-- Snapshots the selection by identity, then destroys each object through its own native call.
local M={}

function M.targets()
    local seen,selected={},{}
    for _,card in ipairs(G.hand.highlighted)do
        if not seen[card] then
            seen[card]=true
            selected[#selected+1]=card
        end
    end
    return selected
end

function M.destroy(selected)
    for _,card in ipairs(selected)do
        SMODS.destroy_cards({card})
    end
end

return M
