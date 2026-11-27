return function(R)
    local M={}
    local function derived(s)
        local d,result=R.import({version=1,events=s.events})
        assert(d,result.code);return d
    end
    function M.new()return {events={}}end
    function M.apply(s,e)
        local d=derived(s);local result=R.step(d,e)
        if result.ok and #d.history>#s.events then s.events[#s.events+1]=R.copy(e)end
        return R.copy(result)
    end
    function M.view(s)return R.view(derived(s))end
    function M.snapshot(s)return {version=1,events=R.copy(s.events)}end
    function M.restore(s,snapshot)
        local d,result=R.import(snapshot)
        if d then s.events=R.copy(d.history)end
        return result
    end
    return M
end
