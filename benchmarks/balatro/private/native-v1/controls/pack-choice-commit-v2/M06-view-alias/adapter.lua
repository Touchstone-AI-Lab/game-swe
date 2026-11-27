return function(M)
    local A={};local game,state,active
    local function current()
        if game~=G.GAME then game=G.GAME;state=M.new();active=nil end
        return state
    end
    function A.status()return M.view(current())end
    function A.preview(booster,card,index,reward)
        local s=current();local session=tostring(booster.sort_id);local preview=tostring(card.sort_id)
        assert(M.begin(s,session).ok);assert(M.register(s,session,preview,reward).ok)
        card.ability.pc2_origin={session=session,preview=preview,index=index,reward=reward}
        active=session
    end
    function A.acquire(card)
        local origin=card.ability.pc2_origin;if not origin then return end
        local s=current();local commit='acquire:'..origin.preview
        local result=M.commit(s,origin.session,origin.preview,commit)
        assert(result.ok,'Pack acquisition rejected: '..tostring(result.code))
        if not result.new then return end
        G.E_MANAGER:add_event(Event({trigger='after',delay=0.1,func=function()
            local receipt=M.settle(s,result.ticket)
            assert(receipt.ok,'Pack settlement rejected')
            if receipt.amount~=0 then ease_dollars(receipt.amount)end
            return true
        end}))
    end
    function A.close()
        if active then assert(M.close(current(),active).ok);active=nil end
    end
    return A
end
