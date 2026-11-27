return function(R)
    local M={}
    function M.new()return {data=R.empty()}end
    function M.apply(s,e)return R.step(s.data,e)end
    function M.view(s)return R.view(s.data)end
    function M.snapshot(s)return {version=1,events=R.copy(s.data.history)}end
    function M.restore(s,snapshot)
        s.data=R.empty()
        local replacement,result=R.import(snapshot)
        if replacement then s.data=replacement end
        return result
    end
    return M
end
