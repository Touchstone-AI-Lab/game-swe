-- Behaviour-only assertions against DarkRP's money handling. Each async case spawns
-- its own bot; a bot spawned by another case does not survive GLuaTest's async
-- boundary, so the reference from an earlier case cannot be reused.
local function withBot( fn )
    RunConsoleCommand( "bot" )
    timer.Simple( 5, function()
        local ply
        for _, p in ipairs( player.GetAll() ) do
            if IsValid( p ) and p:IsPlayer() then ply = p break end
        end
        fn( ply )
    end )
end
local function withTwoBots( fn )
    RunConsoleCommand( "bot" )
    RunConsoleCommand( "bot" )
    timer.Simple( 6, function()
        local found = {}
        for _, p in ipairs( player.GetAll() ) do
            if IsValid( p ) and p:IsPlayer() then found[ #found + 1 ] = p end
        end
        fn( found[ 1 ], found[ 2 ] )
    end )
end
local n = 0
local function uniq( p ) n = n + 1 return p .. "mny" .. n end

return {
    groupName = "DarkRP money regressions",
    cases = {
        {   name = "sentinel: the gamemode and its money API are loaded",
            func = function()
                expect( DarkRP ).to.exist()
                expect( DarkRP.payPlayer ).to.beA( "function" )
                expect( DarkRP.createMoneyBag ).to.beA( "function" )
            end },

        -- Positive control: untouched by every defect in this task and true on both
        -- trees. Whole-number affordability is identical however the rounding is done.
        {   name = "control: a whole amount larger than the wallet is not affordable",
            async = true, timeout = 60,
            func = function()
                withBot( function( ply )
                    expect( IsValid( ply ) ).to.beTrue()
                    -- A bot's data never finishes loading in a headless container, so
                    -- it keeps the flag that makes canAfford refuse everything outright.
                    -- Without clearing it this case would pass on EVERY tree, and the
                    -- control would fail on every tree, neither for the stated reason.
                    ply.DarkRPUnInitialized = nil
                    ply:setDarkRPVar( "money", 100 )
                    expect( ply:canAfford( 250 ) or false ).to.beFalse()
                    expect( ply:canAfford( 100 ) or false ).to.beTrue()
                    done()
                end )
            end },

        -- A: affordability of an amount that is not a whole number
        {   name = "A: an amount just above the wallet is not affordable",
            async = true, timeout = 60,
            func = function()
                withBot( function( ply )
                    expect( IsValid( ply ) ).to.beTrue()
                    -- A bot's data never finishes loading in a headless container, so
                    -- it keeps the flag that makes canAfford refuse everything outright.
                    -- Without clearing it this case would pass on EVERY tree, and the
                    -- control would fail on every tree, neither for the stated reason.
                    ply.DarkRPUnInitialized = nil
                    ply:setDarkRPVar( "money", 10 )
                    expect( ply:canAfford( 10.5 ) or false ).to.beFalse()
                    done()
                end )
            end },

        -- B: what the wallet notification is told
        {   name = "B: the wallet notification reports the balance before the change",
            async = true, timeout = 60,
            func = function()
                withBot( function( ply )
                    expect( IsValid( ply ) ).to.beTrue()
                    ply:setDarkRPVar( "money", 500 )
                    local seenBefore
                    local nm = uniq( "wallet" )
                    hook.Add( "playerWalletChanged", nm, function( _, _, before )
                        seenBefore = before
                    end )
                    ply:addMoney( 250 )
                    hook.Remove( "playerWalletChanged", nm )
                    expect( seenBefore ).to.equal( 500 )
                    done()
                end )
            end },

        -- C: very large sums
        {   name = "C: a very large money bag still holds a positive amount",
            func = function()
                local bag = DarkRP.createMoneyBag( Vector( 0, 0, 0 ), 3000000000 )
                expect( IsValid( bag ) ).to.beTrue()
                local held = bag:Getamount()
                SafeRemoveEntity( bag )
                expect( held > 0 ).to.beTrue()
            end },

        -- D: recognising money on the ground
        {   name = "D: money a player dropped is recognised as money",
            func = function()
                local ent = ents.Create( "prop_physics" )
                expect( IsValid( ent ) ).to.beTrue()
                ent:SetModel( "models/props_c17/oildrum001.mdl" )
                ent.IsSpawnedMoney = true
                local answer = ent:isMoneyBag()
                SafeRemoveEntity( ent )
                expect( answer or false ).to.beTrue()
            end },

        -- E: an amount that is not a number at all
        {   name = "E: a wallet is unharmed by an amount that is not a number",
            async = true, timeout = 60,
            func = function()
                withBot( function( ply )
                    expect( IsValid( ply ) ).to.beTrue()
                    ply:setDarkRPVar( "money", 750 )
                    local ok = pcall( ply.addMoney, ply, "not a number" )
                    expect( ok ).to.beTrue()
                    expect( ply:getDarkRPVar( "money" ) ).to.equal( 750 )
                    done()
                end )
            end },

        -- F: a limit of zero
        {   name = "F: a limit of zero lets a player keep placing the thing",
            async = true, timeout = 60,
            func = function()
                withBot( function( ply )
                    expect( IsValid( ply ) ).to.beTrue()
                    local entry = { cmd = uniq( "unlimited" ), max = 0 }
                    expect( ply:customEntityLimitReached( entry ) or false ).to.beFalse()
                    ply:addCustomEntity( entry )
                    ply:addCustomEntity( entry )
                    expect( ply:customEntityLimitReached( entry ) or false ).to.beFalse()
                    done()
                end )
            end },

        -- G: handing money to someone else
        {   name = "G: paying another player moves the money to that player",
            async = true, timeout = 60,
            func = function()
                withTwoBots( function( sender, receiver )
                    expect( IsValid( sender ) ).to.beTrue()
                    expect( IsValid( receiver ) ).to.beTrue()
                    expect( sender ~= receiver ).to.beTrue()
                    sender:setDarkRPVar( "money", 1000 )
                    receiver:setDarkRPVar( "money", 0 )
                    DarkRP.payPlayer( sender, receiver, 400 )
                    expect( receiver:getDarkRPVar( "money" ) ).to.equal( 400 )
                    expect( sender:getDarkRPVar( "money" ) ).to.equal( 600 )
                    done()
                end )
            end }
    }
}
