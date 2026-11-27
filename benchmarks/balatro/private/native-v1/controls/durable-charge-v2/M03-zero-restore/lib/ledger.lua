return function(R)
    local M={}
    function M.new()return {data=R.empty()}end
    function M.apply(s,e)return R.step(s.data,e)end
    function M.view(s)return R.view(s.data)end
    function M.snapshot(s)return {version=1,events=R.copy(s.data.history)}end
    function M.restore(s,snapshot)
        local replacement,result=R.import(snapshot)
        if replacement then
            for id,value in pairs(replacement.owners)do
                if value==0 then
                    for _,e in ipairs(replacement.history)do
                        if e.owner==id and e.kind=='consume' then replacement.owners[id]=2;break end
                    end
                end
            end
            s.data=replacement
        end
        return result
    end
    return M
end
