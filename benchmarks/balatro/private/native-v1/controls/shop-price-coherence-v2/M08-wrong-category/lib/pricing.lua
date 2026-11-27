return function(base,category,sources)
    -- Missing category guard.
    local fixed,numerator,denominator=0,1,1
    for _,source in pairs(sources)do
        if source.kind=='flat' then fixed=fixed+1
        elseif source.kind=='ratio' then numerator=numerator*2;denominator=denominator*3
        elseif source.kind=='coupon' and source.available then fixed=fixed+2 end
    end
    return math.max(1,math.floor((base-fixed)*numerator/denominator))
end
