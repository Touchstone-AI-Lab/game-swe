return function(R)
    local M={}
    function M.new()return R.empty()end
    for _,name in ipairs({'begin','register','commit','close','settle'})do
        local operation=name
        M[operation]=function(s,...)s.view_cache=nil;local result=R.step(s,operation,{...});return result end
    end
    function M.view(s)s.view_cache=s.view_cache or R.view(s);return s.view_cache end
    return M
end
