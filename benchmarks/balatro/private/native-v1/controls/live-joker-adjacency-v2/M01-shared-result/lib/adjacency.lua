local M={}
local shared
function M.begin_hand() shared=nil end
function M.count(card,cards)
    if shared~=nil then return shared end
    local index
    for i,c in ipairs(cards)do if c==card then index=i;break end end
    if not index then return 0 end
    
    local count=0
    for _,i in ipairs({index-1,index+1})do
        
        local other=cards[i]
        if other and other~=card and other.config.center.rarity==1  then count=count+1 end
    end
    shared=count
    return count
end
return M
