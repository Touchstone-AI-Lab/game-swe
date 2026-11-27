local id=SMODS.current_mod.id
local R=assert(SMODS.load_file('lib/rules.lua',id))()
DC2_MODEL=assert(SMODS.load_file('lib/ledger.lua',id))()(R)
local adapter=assert(SMODS.load_file('adapter.lua',id))()(DC2_MODEL)
SMODS.Joker {
    key='charge',rarity=1,cost=4,unlocked=true,discovered=true,blueprint_compat=false,pos={x=0,y=0},
    loc_txt={name='Durable Charge',text={'Each discard: {C:mult}+2{} charge (max 6)',
        'Next hand uses and consumes charge','(Currently {C:mult}#1#{} charge)'}},
    loc_vars=function(self,info_queue,card)return {vars={adapter.display(card)}}end,
    add_to_deck=function(self,card,from_debuff)if not from_debuff then adapter.add(card)end end,
    remove_from_deck=function(self,card,from_debuff)if not from_debuff then adapter.remove(card)end end,
    calculate=function(self,card,context)return adapter.calculate(card,context)end
}
SMODS.Consumable {
    key='recruit',set='Tarot',cost=3,pos={x=0,y=0},
    loc_txt={name='Recruit',text={'Create one fresh {C:attention}Durable Charge{} Joker','Requires room'}},
    can_use=function(self,card)return G.jokers and #G.jokers.cards<G.jokers.config.card_limit end,
    use=function(self,card)SMODS.add_card({key='j_dc2_charge',area=G.jokers,no_edition=true})end
}
