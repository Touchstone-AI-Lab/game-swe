local adjacency=assert(SMODS.load_file('lib/adjacency.lua'))()
SMODS.Joker {
    key='neighbors',rarity=1,cost=4,config={extra={}},pos={x=0,y=0},
    loc_txt={name='Common Neighbors',text={'+3 Mult per immediately adjacent Common Joker'}},
    calculate=function(self,card,context)
        if context.before then adjacency.begin_hand() end
        if context.joker_main then return {mult=3*adjacency.count(card,G.jokers.cards)} end
    end
}
