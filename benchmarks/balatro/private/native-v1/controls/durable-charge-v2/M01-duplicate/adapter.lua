return function(M)
    local A={};local game,state,restored
    local participated=setmetatable({}, {__mode='k'})
    local function current()
        if game~=G.GAME then
            game=G.GAME;state=M.new();restored=game.dc2_snapshot~=nil
            if restored then assert(M.restore(state,game.dc2_snapshot).ok,'Invalid durable snapshot')end
        end
        return state
    end
    local function apply(event)
        local s=current();local result=M.apply(s,event)
        assert(result.ok,'Durable event rejected: '..tostring(result.code))
        game.dc2_snapshot=M.snapshot(s)
        return result
    end
    local function owner(card)return tostring(card.sort_id)end
    local function balance(card)
        local v=M.view(current());local id=owner(card)
        for _,row in ipairs(v.owners)do if row.id==id then return row.charge end end
        return 0
    end
    function A.display(card)return balance(card)end
    function A.add(card)apply({id='add:'..owner(card),kind='add',owner=owner(card)})end
    function A.remove(card)apply({id='remove:'..owner(card),kind='remove',owner=owner(card)})end
    function A.calculate(card,context)
        if context.blueprint or context.retrigger_joker then return end
        local id=owner(card)
        if context.pre_discard and not context.hook and #context.full_hand>0 then
            local event='d:'..G.GAME.round..':'..(G.GAME.current_round.discards_used+1)..':'..id
            apply({id=event,kind='discard',owner=id})
        end
        local token='h:'..G.GAME.round..':'..(G.GAME.hands_played+1)..':'..id
        if context.joker_main and participated[card]~=token then
            local amount=balance(card);participated[card]=token
            return {mult=amount}
        end
        if context.after and participated[card]==token then
            apply({id=token,kind='consume',owner=id})
        end
    end
    return A
end
