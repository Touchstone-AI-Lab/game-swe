local generation=assert(SMODS.load_file('lib/generation.lua'))()
SMODS.Consumable {
    key='generator',set='Tarot',config={extra={products=2}},cost=4,
    loc_txt={name='Configured Generator',text={'Create {C:planet}#1#{} Mercury Planets','Needs room after consumption'}},
    unlocked=true,discovered=true,pos={x=0,y=0},
    loc_vars=function(self,info_queue,card)return {vars={card.ability.extra.products}}end,
    can_use=function(self,card)return generation.can_use(card)end,
    use=function(self,card)generation.use(card)end
}
