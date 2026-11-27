local M={}
local positions=setmetatable({},{__mode='k'})
function M.begin_hand() end
function M.count(card,cards)
    
    local index
    for i,c in ipairs(cards)do if c==card then index=i;break end end
    if not index then return 0 end
    positions[card]=positions[card] or index;index=positions[card]
    local count=0
    for _,i in ipairs({index-1,index+1})do
        
        local other=cards[i]
        if other and other~=card and other.config.center.rarity==1  then count=count+1 end
    end
    
    return count
end
return M
