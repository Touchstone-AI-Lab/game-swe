-- Behaviour-only assertions about what the server writes down about a player and reads
-- back: the row created for someone new, the balance kept for them online and offline,
-- and the roleplay name they are known by.

-- These routines belong to the submission, so a repair is free to hand back something of
-- the wrong shape. Inside a timer an uncaught Lua error does not reach GLuaTest as a
-- failure -- the case never finishes and is recorded as a timeout, which reads as a
-- broken harness rather than a wrong answer. So read and call defensively.
local function call( fn, ... )
    return ( pcall( fn, ... ) )
end

local function field( row, key )
    if not istable( row ) then return nil end
    return row[ key ]
end

-- The database is the thing the reports are about, so read it back through the
-- gamemode's own database layer rather than through an in-memory copy.
local function readRow( uid, cb )
    MySQLite.query( "SELECT * FROM darkrp_player WHERE uid = " .. uid .. ";",
        function( rows ) cb( rows and rows[ 1 ] or nil, rows and #rows or 0 ) end,
        function() cb( nil, -1 ) end )
end

local function settle( fn ) timer.Simple( 2, fn ) end

local function subject() return player.GetAll()[ 1 ] end

-- Put the row into a known state before each case that does not test this routine.
local function seed( ply, name, wallet, salary, after )
    call( DarkRP.createPlayerData, ply, name, wallet, salary )
    settle( after )
end

return {
    groupName = "DarkRP persistence regressions",
    cases = {
        {   name = "sentinel: the gamemode and its player-record API are loaded",
            func = function()
                expect( DarkRP ).to.exist()
                expect( DarkRP.createPlayerData ).to.beA( "function" )
                expect( DarkRP.storeMoney ).to.beA( "function" )
                expect( DarkRP.storeRPName ).to.beA( "function" )
                expect( subject() ).to.exist()
            end },

        -- Positive control: an ordinary balance goes through the same check A and B
        -- change, at a value where neither can differ. Holds on both trees.
        {   name = "control: an ordinary balance is written down",
            async = true, timeout = 12,
            func = function()
                local ply = subject()
                seed( ply, "ControlMoney", 4242, 77, function()
                    call( DarkRP.storeMoney, ply, 1234 )
                    settle( function()
                        readRow( ply:SteamID64(), function( row )
                            expect( tonumber( field( row, "wallet" ) ) ).to.equal( 1234 )
                            done()
                        end )
                    end )
                end )
            end },

        -- Positive control: an ordinary name goes through the same guard E changes.
        {   name = "control: an ordinary name is written down",
            async = true, timeout = 12,
            func = function()
                local ply = subject()
                seed( ply, "ControlNameOld", 500, 45, function()
                    call( DarkRP.storeRPName, ply, "ControlNameNew" )
                    settle( function()
                        readRow( ply:SteamID64(), function( row )
                            expect( field( row, "rpname" ) ).to.equal( "ControlNameNew" )
                            done()
                        end )
                    end )
                end )
            end },

        {   name = "A: a new player's cash and pay are not written into each other",
            async = true, timeout = 12,
            func = function()
                local ply = subject()
                call( DarkRP.createPlayerData, ply, "NewJoiner", 4242, 77 )
                settle( function()
                    readRow( ply:SteamID64(), function( row )
                        expect( tonumber( field( row, "wallet" ) ) ).to.equal( 4242 )
                        expect( tonumber( field( row, "salary" ) ) ).to.equal( 77 )
                        done()
                    end )
                end )
            end },

        {   name = "B: a balance of nothing is written down like any other",
            async = true, timeout = 12,
            func = function()
                local ply = subject()
                seed( ply, "SpentEverything", 4242, 77, function()
                    call( DarkRP.storeMoney, ply, 0 )
                    settle( function()
                        readRow( ply:SteamID64(), function( row )
                            expect( tonumber( field( row, "wallet" ) ) ).to.equal( 0 )
                            done()
                        end )
                    end )
                end )
            end },

        {   name = "C: money given to an absent player reaches the record read back",
            async = true, timeout = 12,
            func = function()
                local ply = subject()
                local sid64 = ply:SteamID64()
                seed( ply, "AwayFromKeyboard", 4242, 77, function()
                    call( DarkRP.storeOfflineMoney, sid64, 999 )
                    settle( function()
                        readRow( sid64, function( row )
                            expect( tonumber( field( row, "wallet" ) ) ).to.equal( 999 )
                            done()
                        end )
                    end )
                end )
            end },

        {   name = "D: a name change announces the name that was in use before it",
            func = function()
                local ply = subject()
                local seen = nil
                hook.Add( "onPlayerChangedName", "gcb_name_probe", function( _, old )
                    seen = old
                end )

                call( DarkRP.storeRPName, ply, "TheNameBefore" )
                call( DarkRP.storeRPName, ply, "TheNameAfter" )
                hook.Remove( "onPlayerChangedName", "gcb_name_probe" )

                expect( seen ).to.equal( "TheNameBefore" )
            end },

        {   name = "E: a name too short to identify anyone is refused",
            async = true, timeout = 12,
            func = function()
                local ply = subject()
                seed( ply, "ProperName", 500, 45, function()
                    call( DarkRP.storeRPName, ply, "x" )
                    settle( function()
                        readRow( ply:SteamID64(), function( row )
                            expect( field( row, "rpname" ) ).to.equal( "ProperName" )
                            done()
                        end )
                    end )
                end )
            end },

        {   name = "F: a name nobody is using is reported as free",
            async = true, timeout = 12,
            func = function()
                local ply = subject()
                seed( ply, "SomebodyElse", 500, 45, function()
                    local answered, taken = false, nil
                    call( DarkRP.retrieveRPNames, "NoOneIsCalledThis47", function( t )
                        answered, taken = true, t
                    end )
                    settle( function()
                        expect( answered ).to.beTrue()
                        expect( taken ).to.beFalse()
                        done()
                    end )
                end )
            end },

        {   name = "G: an amount that is not a real number is refused, not rounded",
            func = function()
                expect( DarkRP.toInt( 7.9 ) ).to.equal( 7 )
                expect( DarkRP.toInt( "12" ) ).to.equal( 12 )
                expect( DarkRP.toInt( 0 / 0 ) ).to.beFalse()
            end },

        {   name = "H: a name is looked up as written, not as a pattern",
            func = function()
                -- Own the fixture. Nick() reports the roleplay name, and an earlier case
                -- deliberately tries to set a one-character one, so this case establishes
                -- the name it is about to search for instead of inheriting it. The name is
                -- long enough to pass every length check on every tree.
                local ply = subject()
                call( DarkRP.storeRPName, ply, "PatternProbe" )
                local nick = string.lower( ply:Nick() )
                expect( string.len( nick ) >= 3 ).to.beTrue()

                -- Derive the needles from that name: a fixed string whose literal prefix
                -- matches nobody would never reach the interesting part, because Lua's
                -- matcher only complains about what it actually has to look at.

                -- Holds on both trees: the name itself still finds the player.
                expect( DarkRP.findPlayer( nick ) ).to.exist()

                -- A character that is special to patterns and ordinary in a name.
                local dotted = string.sub( nick, 1, 1 ) .. "." .. string.sub( nick, 3 )
                expect( DarkRP.findPlayer( dotted ) ).toNot.exist()

                -- An unclosed bracket, reached because its prefix does match.
                local ok = pcall( DarkRP.findPlayer, string.sub( nick, 1, 2 ) .. "(" )
                expect( ok ).to.beTrue()
            end },

        {   name = "I: looking someone up by nothing at all finds nobody",
            func = function()
                expect( DarkRP.findPlayer( "" ) ).toNot.exist()
            end }
    }
}
