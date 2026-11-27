return function(Core)
    local states=setmetatable({},{__mode='k'})
    local quotes=setmetatable({},{__mode='k'})
    local rule_keys={j_sp2_flat=true,j_sp2_ratio=true,j_sp2_coupon=true}
    local function state()
        if not states[G.GAME]then states[G.GAME]=Core.new()end
        return states[G.GAME]
    end
    local function eligible(card)
        return card.ability and card.ability.set=='Joker' and not rule_keys[card.config.center.key]
    end
    local function pack(...)return {n=select('#',...),...}end
    local native_cost=Card.set_cost_value
    Card.set_cost_value=function(self,...)
        local r=pack(native_cost(self,...))
        if G.GAME and G.STATE==G.STATES.SHOP and not self.added_to_deck then
            local result=Core.quote(state(),tostring(self.sort_id),self.cost,
                eligible(self) and 'eligible_joker' or 'other')
            if result.ok then quotes[self]=result.quote;self.cost=result.quote.price end
        end
        return unpack(r,1,r.n)
    end
    local function refresh()
        for _,offer in ipairs(G.shop_jokers and G.shop_jokers.cards or {})do offer:set_cost()end
    end
    for _,spec in ipairs({{'flat',4,'Flat Clerk'},{'ratio',6,'Ratio Clerk'},{'coupon',4,'Coupon Clerk'}})do
        local kind,cost,name=spec[1],spec[2],spec[3]
        SMODS.Joker{
            key=kind,cost=cost,rarity=1,unlocked=true,discovered=true,blueprint_compat=false,pos={x=0,y=0},
            loc_txt={name=name,text={'Contributes its owned checkout rule'}},
            add_to_deck=function(self,card,from_debuff)
                local result=Core.add(state(),tostring(card.sort_id),kind)
                if result.ok then refresh()end
            end,
            remove_from_deck=function(self,card,from_debuff)
                local result=Core.remove(state(),tostring(card.sort_id))
                if result.ok then refresh()end
            end
        }
    end
    local native_context=SMODS.calculate_context
    SMODS.calculate_context=function(context,...)
        local r=pack(native_context(context,...))
        local card=type(context)=='table' and context.card
        if card and context.buying_card and not context.buying_self and eligible(card) and card.added_to_deck then
            local q=quotes[card]
            if q then
                local result=Core.commit(state(),'purchase:'..tostring(card.sort_id),q,
                    G.GAME.dollars-(G.GAME.bankrupt_at or 0))
                if result.ok then refresh()end
            end
        end
        return unpack(r,1,r.n)
    end
end
