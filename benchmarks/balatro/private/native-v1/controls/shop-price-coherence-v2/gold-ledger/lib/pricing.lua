return function(base,category,sources)
    if category~='eligible_joker' then return base end
    local fixed,ratios=0,0
    for _,s in pairs(sources)do
        if s.kind=='flat'then fixed=fixed+1
        elseif s.kind=='coupon' and s.available then fixed=fixed+2
        elseif s.kind=='ratio'then ratios=ratios+1 end
    end
    return math.max(1,math.floor((base-fixed)*(2^ratios)/(3^ratios)))
end
