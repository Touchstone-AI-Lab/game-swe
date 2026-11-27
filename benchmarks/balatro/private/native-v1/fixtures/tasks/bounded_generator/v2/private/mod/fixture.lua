-- One initial preparation only; configuration reads never change business state.
local prepared=false
local sources={}
local function configurations()
    local out={}
    for _,c in ipairs(sources)do out[#out+1]={sort_id=c.sort_id,products=c.ability.extra.products}end
    return {sources=out,default=G.P_CENTERS.c_bg2_generator.config.extra.products,fixture_calls=prepared and 1 or 0}
end
assert(BB_DISPATCHER.register({name='poc.bg2.prepare',description='One configured fresh capability scene',
    schema={mode={type='string',required=true}},requires_state={G.STATES.BLIND_SELECT},
    execute=function(args,respond)
        assert(not prepared and G.GAME.round==0 and #G.consumeables.cards==0 and #G.jokers.cards==0)
        assert(G.GAME.pseudorandom.seed=='BG2TASK' and G.GAME.consumeable_buffer==0)
        local scene=assert(({room={5,2,2},one={2,1},three={4,3},recover={3,3},mixed={5,1,3}})[args.mode])
        prepared=true
        G.consumeables:change_size(scene[1]-G.consumeables.config.card_limit)
        G.GAME.dollars=10
        for i=2,#scene do
            local c=SMODS.add_card({key='c_bg2_generator',area=G.consumeables})
            c.ability.extra.products=scene[i];sources[#sources+1]=c
        end
        SMODS.add_card({key='c_hermit',area=G.consumeables})
        respond(configurations())
    end}))
assert(BB_DISPATCHER.register({name='poc.bg2.config',description='Read-only prepared instance configuration',schema={},
    execute=function(args,respond)respond(configurations())end}))
