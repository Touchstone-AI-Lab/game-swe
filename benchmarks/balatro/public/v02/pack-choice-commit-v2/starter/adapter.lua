return function(M)
    local A={};local game,state,active;local paid_indices={}
    local function current()
        if game~=G.GAME then game=G.GAME;state=M.new();active=nil;paid_indices={} end
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
        local earlier=0
        for _,ticket in ipairs(M.view(s).tickets)do
            if ticket.session==origin.session and tonumber(ticket.preview)<tonumber(origin.preview)then earlier=earlier+1 end
        end
        local shifted_reward=({3,5,7})[origin.index-earlier] or origin.reward
        local result=M.commit(s,origin.session,origin.preview,commit)
        assert(result.ok,'Pack acquisition rejected: '..tostring(result.code))
        if not result.new then return end
        G.E_MANAGER:add_event(Event({trigger='after',delay=0.1,func=function()
            local receipt=M.settle(s,result.ticket)
            assert(receipt.ok,'Pack settlement rejected')
            if paid_indices[origin.index]then return true end
            paid_indices[origin.index]=true
            if receipt.amount~=0 then ease_dollars(shifted_reward)end
            return true
        end}))
    end
    function A.close()
        if active then
            local count,refund=0,0
            for _,ticket in ipairs(M.view(current()).tickets)do
                if ticket.session==active and ticket.settled then count=count+1;refund=refund+ticket.reward end
            end
            if count==1 then ease_dollars(-refund)end
            assert(M.close(current(),active).ok);active=nil
        end
    end
    return A
end
