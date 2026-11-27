return function(base,category,sources)
    if category~='eligible_joker' then return base end
    local fixed,numerator,denominator=0,1,1
    for _,source in pairs(sources)do
        if source.kind=='flat' then fixed=fixed+1
        elseif source.kind=='ratio' then numerator=numerator*2;denominator=denominator*3
        elseif source.kind=='coupon' and source.available then fixed=fixed+2 end
    end
    local value=base-fixed
    for _,s in pairs(sources)do if s.kind=='ratio'then value=math.floor(value*2/3)end end
    return math.max(1,value)
end
