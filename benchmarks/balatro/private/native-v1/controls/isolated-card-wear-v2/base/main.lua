local wear=assert(SMODS.load_file('lib/wear.lua'))()
SMODS.Enhancement {
    key='polish',config={extra={uses=2}},pos={x=1,y=1},
    loc_txt={name='Renewable Polish',text={'+20 Chips when scored','#1# uses remaining'}},
    loc_vars=function(self,info_queue,card)return {vars={wear.remaining(card)}}end,
    calculate=function(self,card,context)
        if context.main_scoring and context.cardarea==G.play then return wear.score(card)end
    end
}
SMODS.Consumable {
    key='applicator',set='Tarot',cost=3,config={max_highlighted=1},pos={x=1,y=1},
    loc_txt={name='Polish Applicator',text={'Reset one ordinary or polished card to two fresh uses'}},
    can_use=function(self,card)
        return G.hand and #G.hand.highlighted==1 and (G.hand.highlighted[1].config.center.key=='c_base'
            or G.hand.highlighted[1].config.center.key=='m_icw2_polish')
    end,
    use=function(self,card)wear.apply(G.hand.highlighted[1],G.P_CENTERS.m_icw2_polish)end
}
