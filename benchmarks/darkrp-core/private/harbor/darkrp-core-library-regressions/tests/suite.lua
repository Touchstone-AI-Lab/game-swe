-- Behaviour-only assertions against DarkRP's public helper libraries. Every case is
-- pure: no bot, no database, no entity, so nothing here depends on server timing.
local function sorted( xs )
    local out = {}
    for _, v in pairs( xs ) do out[ #out + 1 ] = v end
    table.sort( out )
    return table.concat( out, "," )
end

return {
    groupName = "DarkRP core library regressions",
    cases = {
        {   name = "sentinel: the gamemode and its helper libraries are loaded",
            func = function()
                expect( DarkRP ).to.exist()
                expect( fn ).to.exist()
                expect( tc ).to.exist()
            end },

        -- A: selecting entries out of a table
        {   name = "A: selecting entries from a table keeps them under their own keys",
            func = function()
                local kept = fn.Filter( function( v ) return v > 1 end, { a = 1, b = 2, c = 3 } )
                expect( kept.b ).to.equal( 2 )
                expect( kept.c ).to.equal( 3 )
                expect( kept.a ).to.beNil()
            end },
        {   name = "A: selecting entries from a plain list still works",
            func = function()
                local kept = fn.Filter( function( v ) return v > 1 end, { 1, 2, 3 } )
                expect( sorted( kept ) ).to.equal( "2,3" )
            end },

        -- B: emptiness
        {   name = "B: a table with entries under other keys is not empty",
            func = function()
                expect( fn.Null( { [ 7 ] = true } ) ).to.beFalse()
                expect( fn.Null( { label = "x" } ) ).to.beFalse()
                expect( fn.Null( {} ) ).to.beTrue()
            end },

        -- C: folding
        {   name = "C: folding a list combines it from the far end inwards",
            func = function()
                local joined = fn.Foldr( function( x, acc ) return x .. acc end, "", { "a", "b", "c" } )
                expect( joined ).to.equal( "abc" )
            end },

        -- D: dropping the trailing entry
        {   name = "D: dropping the trailing entry of a list leaves the leading ones",
            func = function()
                local head = fn.Init( { 1, 2, 3 } )
                expect( #head ).to.equal( 2 )
                expect( head[ 1 ] ).to.equal( 1 )
                expect( head[ 2 ] ).to.equal( 2 )
            end },

        -- E: dropping the first entry
        {   name = "E: dropping the leading entry of a list leaves the rest in order",
            func = function()
                local rest = fn.Tail( { 1, 2, 3 } )
                expect( #rest ).to.equal( 2 )
                expect( rest[ 1 ] ).to.equal( 2 )
                expect( rest[ 2 ] ).to.equal( 3 )
            end },

        -- F: fields that may be left out
        {   name = "F: a field that may be left out is still checked when it is supplied",
            func = function()
                local check = tc.optional( isnumber )
                expect( check( nil ) or false ).to.beTrue()
                expect( check( 5 ) or false ).to.beTrue()
                expect( check( "not a number" ) or false ).to.beFalse()
            end },

        -- G: fields that must not be empty
        {   name = "G: a field that must not be empty rejects an empty table",
            func = function()
                local check = tc.nonEmpty()
                expect( check( {} ) or false ).to.beFalse()
                expect( check( { 1 } ) or false ).to.beTrue()
            end },

        -- H: numeric lower bound
        {   name = "H: a lower bound accepts larger numbers and rejects smaller ones",
            func = function()
                local check = tc.min( 5 )
                expect( check( 10 ) or false ).to.beTrue()
                expect( check( 5 ) or false ).to.beTrue()
                expect( check( 1 ) or false ).to.beFalse()
            end }
    }
}
