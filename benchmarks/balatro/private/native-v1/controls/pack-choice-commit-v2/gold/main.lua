local id=SMODS.current_mod.id
local R=assert(SMODS.load_file('lib/transitions.lua',id))()
PC2_MODEL=assert(SMODS.load_file('lib/ledger.lua',id))()(R)
local adapter=assert(SMODS.load_file('adapter.lua',id))()(PC2_MODEL)
PC2_STATUS=adapter.status
for _,definition in ipairs({{'copper',3},{'silver',5},{'gold',7}})do
    local key,reward=definition[1],definition[2]
    SMODS.Joker {
        key=key,rarity=1,cost=4,unlocked=true,discovered=true,blueprint_compat=false,pos={x=0,y=0},
        loc_txt={name='Signing '..key,text={'When chosen from its pack: {C:money}$'..reward..'{} once'}},
        add_to_deck=function(self,card,from_debuff)if not from_debuff then adapter.acquire(card)end end
    }
end
SMODS.Booster {
    key='choices',cost=4,weight=0,pos={x=0,y=0},config={extra=3,choose=2},
    loc_txt={name='Signing Choices',group_name='Signing Choices',text={'Choose up to {C:attention}2{} of {C:attention}3{} signing Jokers'}},
    create_card=function(self,booster,index)
        local key=({'j_pc2_copper','j_pc2_silver','j_pc2_gold'})[index]
        local card=create_card('Joker',G.pack_cards,nil,nil,nil,nil,key,'pc2');card:set_edition(nil,true,true)
        adapter.preview(booster,card,index,({3,5,7})[index]);return card
    end
}
local function pack(...)return {n=select('#',...),...}end
local finish=G.FUNCS.end_consumeable
G.FUNCS.end_consumeable=function(...)
    local result=pack(finish(...));adapter.close();return unpack(result,1,result.n)
end
