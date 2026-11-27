return function(R)
    local M={}
    function M.new()return R.empty()end
    for _,name in ipairs({'begin','register','commit','close','settle'})do
        local operation=name
        M[operation]=function(s,...)local result=R.step(s,operation,{...});return result end
    end
    function M.view(s)return R.view(s)end
    return M
end
