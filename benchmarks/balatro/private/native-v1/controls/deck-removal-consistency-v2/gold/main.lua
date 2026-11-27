local lifecycle=assert(SMODS.load_file('lib/lifecycle.lua'))()
SMODS.Consumable {
    key='clean_cut',set='Tarot',cost=3,config={max_highlighted=4},pos={x=2,y=2},
    loc_txt={name='Physical Batch Cut',text={'Permanently destroy up to {C:attention}4{} selected cards'}},
    can_use=function(self,card)return G.hand and #G.hand.highlighted>=1 and #G.hand.highlighted<=4 end,
    use=function(self,card)lifecycle.destroy(lifecycle.targets())end
}
