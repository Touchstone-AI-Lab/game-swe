return function(R)
    local M={}
    local function replay(s)
        local d=R.empty()
        for _,command in ipairs(s.commands)do
            local r=R.step(d,command.kind,command.args);assert(r.ok,'Invalid accepted journal')
        end
        return d
    end
    function M.new()return {commands={}}end
    for _,name in ipairs({'begin','register','commit','close','settle'})do
        local operation=name
        M[operation]=function(s,...)
            local args={...};local d=replay(s);local result,changed=R.step(d,operation,args)
            if changed then s.commands[#s.commands+1]={kind=operation,args=R.copy(args)}end
            return R.copy(result)
        end
    end
    function M.view(s)return R.view(replay(s))end
    return M
end
