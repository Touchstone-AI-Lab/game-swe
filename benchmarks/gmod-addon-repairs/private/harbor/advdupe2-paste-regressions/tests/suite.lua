-- Behaviour-only assertions against Advanced Duplicator 2 on a headless server. Every
-- case builds real entities, copies them through the addon's own copy routine, removes
-- the originals and pastes the copy back, as the tool does for a player.
local CRATE = "models/props_junk/wood_crate001a.mdl"
local BARREL = "models/props_c17/oildrum001.mdl"
local spawned = {}

local function track( ent )
    spawned[ #spawned + 1 ] = ent
    return ent
end

local function makeProp( model, pos, scale )
    local ent = ents.Create( "prop_physics" )
    ent:SetModel( model )
    ent:SetPos( pos )
    if scale then ent:SetModelScale( scale, 0 ) end
    ent:Spawn()
    ent:Activate()
    local phys = ent:GetPhysicsObject()
    if IsValid( phys ) then phys:EnableMotion( false ) end
    return track( ent )
end

local function findBot()
    for _, p in ipairs( player.GetBots() ) do
        if IsValid( p ) then return p end
    end
end

local function withBot( fn )
    if IsValid( findBot() ) then
        timer.Simple( 0.2, function() fn( findBot() ) end )
        return
    end
    RunConsoleCommand( "bot" )
    timer.Simple( 4, function() fn( findBot() ) end )
end

-- Copy the contraption around `ent`, remove the originals, paste it back at `pos`.
local function copyAndPaste( owner, ent, pos, removeOriginals )
    local entities, constraints = AdvDupe2.duplicator.Copy( nil, ent, {}, {}, ent:GetPos() )
    if removeOriginals then
        for index in pairs( entities ) do SafeRemoveEntity( Entity( index ) ) end
    end
    local created, createdConstraints = AdvDupe2.duplicator.Paste( owner, entities, constraints, pos, Angle( 0, 0, 0 ), nil, false )
    for _, e in pairs( created ) do track( e ) end
    for _, c in pairs( createdConstraints ) do track( c ) end
    return created, createdConstraints, entities
end

-- Runs the checks of an async case and always finishes it exactly once: an unexpected
-- Lua error is recorded as the case's failure instead of leaving it to time out.
local function settle( expect, done, body )
    local ok, err = pcall( body )
    expect( ok and "completed" or tostring( err ) ).to.equal( "completed" )
    done()
end

local function only( tbl )
    local result
    for _, v in pairs( tbl ) do result = v end
    return result
end

return {
    groupName = "Advanced Duplicator 2",
    afterEach = function()
        for _, ent in ipairs( spawned ) do SafeRemoveEntity( ent ) end
        spawned = {}
    end,
    cases = {
        {   name = "sentinel: the addon and its duplicator are loaded",
            func = function()
                expect( AdvDupe2 ).to.exist()
                expect( AdvDupe2.duplicator.Copy ).to.beA( "function" )
                expect( AdvDupe2.duplicator.Paste ).to.beA( "function" )
                expect( AdvDupe2.SanitizeFilename ).to.beA( "function" )
            end },

        {   name = "preserved: a copied prop pastes at the requested place, frozen",
            func = function()
                local original = makeProp( CRATE, Vector( 0, 0, 200 ) )
                local created = copyAndPaste( nil, original, Vector( 100, 50, 300 ), true )
                local prop = only( created )
                expect( IsValid( prop ) ).to.beTrue()
                expect( prop:GetModel() ).to.equal( CRATE )
                expect( prop:GetPos():Distance( Vector( 100, 50, 300 ) ) < 1 ).to.beTrue()
                expect( prop:GetPhysicsObject():IsMotionEnabled() ).to.beFalse()
            end },

        {   name = "A: a prop saved at a larger scale pastes with a matching physics size",
            func = function()
                local small = makeProp( CRATE, Vector( 0, 0, 200 ) )
                local big = makeProp( CRATE, Vector( 200, 0, 200 ), 2 )
                local smallCopy = only( copyAndPaste( nil, small, Vector( 0, 300, 300 ), true ) )
                local bigCopy = only( copyAndPaste( nil, big, Vector( 300, 300, 300 ), true ) )
                expect( IsValid( smallCopy ) ).to.beTrue()
                expect( IsValid( bigCopy ) ).to.beTrue()
                expect( bigCopy:GetModelScale() ).to.equal( 2 )
                local ratio = bigCopy:GetPhysicsObject():GetVolume() / smallCopy:GetPhysicsObject():GetVolume()
                expect( ratio > 6 and ratio < 10 ).to.beTrue()
            end },

        {   name = "B: a piece that fails to paste leaves nothing behind",
            async = true, timeout = 10,
            func = function()
                local class = "rhenium_ad2_probe"
                scripted_ents.Register( { Type = "anim", Base = "base_anim",
                    Initialize = function( self ) self:PhysicsInit( SOLID_VPHYSICS ) end }, class )
                local before = #ents.FindByClass( class )
                local entities = { [ 1 ] = { Class = class, Model = CRATE, Skin = "broken",
                    PhysicsObjects = { [ 0 ] = { Pos = Vector( 0, 0, 0 ), Angle = Angle( 0, 0, 0 ) } } } }
                local pasted, created = pcall( AdvDupe2.duplicator.Paste, nil, entities, {}, Vector( 0, -300, 300 ), Angle( 0, 0, 0 ), nil, false )
                timer.Simple( 0.3, function()
                    settle( expect, done, function()
                        local leftovers = ents.FindByClass( class )
                        for _, e in ipairs( leftovers ) do SafeRemoveEntity( e ) end
                        expect( pasted ).to.beTrue()
                        expect( table.Count( created or {} ) ).to.equal( 0 )
                        expect( #leftovers ).to.equal( before )
                    end )
                end )
            end },

        {   name = "C: props a player pasted are released by unfreeze-all",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    settle( expect, done, function()
                        expect( IsValid( bot ) ).to.beTrue()
                        bot:UnfreezePhysicsObjects()
                        local original = makeProp( CRATE, Vector( 0, 0, 200 ) )
                        local prop = only( copyAndPaste( bot, original, Vector( -300, 0, 300 ), true ) )
                        expect( IsValid( prop ) ).to.beTrue()
                        expect( prop:GetPhysicsObject():IsMotionEnabled() ).to.beFalse()
                        local released = bot:UnfreezePhysicsObjects()
                        expect( released ).to.equal( 1 )
                        expect( prop:GetPhysicsObject():IsMotionEnabled() ).to.beTrue()
                    end )
                end )
            end },

        {   name = "D: a pasted rope counts against the rope limit",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    settle( expect, done, function()
                        expect( IsValid( bot ) ).to.beTrue()
                        local a = makeProp( CRATE, Vector( 0, 0, 200 ) )
                        local b = makeProp( CRATE, Vector( 0, 80, 200 ) )
                        track( constraint.Rope( a, b, 0, 0, Vector(), Vector(), 80, 0, 0, 1, "cable/rope", false ) )
                        local ropes, others = bot:GetCount( "ropeconstraints" ), bot:GetCount( "constraints" )
                        local _, constraints = copyAndPaste( bot, a, Vector( 0, 400, 300 ), true )
                        expect( table.Count( constraints ) ).to.equal( 1 )
                        expect( bot:GetCount( "ropeconstraints" ) ).to.equal( ropes + 1 )
                        expect( bot:GetCount( "constraints" ) ).to.equal( others )
                    end )
                end )
            end },

        {   name = "D: the rope limit is enforced when pasting",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    expect( IsValid( bot ) ).to.beTrue()
                    local limit = GetConVar( "sbox_maxropeconstraints" ):GetString()
                    RunConsoleCommand( "sbox_maxropeconstraints", "0" )
                    timer.Simple( 0.3, function()
                        local a = makeProp( CRATE, Vector( 0, 0, 200 ) )
                        local b = makeProp( CRATE, Vector( 0, 80, 200 ) )
                        track( constraint.Rope( a, b, 0, 0, Vector(), Vector(), 80, 0, 0, 1, "cable/rope", false ) )
                        local ok, created = pcall( function()
                            local _, constraints = copyAndPaste( bot, a, Vector( 0, -400, 300 ), true )
                            return table.Count( constraints )
                        end )
                        RunConsoleCommand( "sbox_maxropeconstraints", limit )
                        settle( expect, done, function()
                            expect( ok ).to.beTrue()
                            expect( created ).to.equal( 0 )
                        end )
                    end )
                end )
            end },

        {   name = "preserved: a pasted weld still counts as a constraint",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    settle( expect, done, function()
                        expect( IsValid( bot ) ).to.beTrue()
                        local a = makeProp( CRATE, Vector( 0, 0, 200 ) )
                        local b = makeProp( BARREL, Vector( 0, 60, 200 ) )
                        track( constraint.Weld( a, b, 0, 0, 0, true, false ) )
                        local others = bot:GetCount( "constraints" )
                        local created, constraints = copyAndPaste( bot, a, Vector( 400, 0, 300 ), true )
                        expect( table.Count( created ) ).to.equal( 2 )
                        expect( table.Count( constraints ) ).to.equal( 1 )
                        expect( bot:GetCount( "constraints" ) ).to.equal( others + 1 )
                    end )
                end )
            end },

        {   name = "E: file names lose the spaces around separators and dots",
            func = function()
                expect( AdvDupe2.SanitizeFilename( "my dupes / sub dir . txt" ) ).to.equal( "my dupes/sub dir.txt" )
                expect( AdvDupe2.SanitizeFilename( "a \\ b" ) ).to.equal( "a\\b" )
            end },

        {   name = "preserved: file names keep their other characters readable",
            func = function()
                expect( AdvDupe2.SanitizeFilename( 'a "b":c' ) ).to.equal( "a _b__c" )
                expect( AdvDupe2.SanitizeFilename( "tank   one" ) ).to.equal( "tank one" )
            end },

        {   name = "preserved: an encoded dupe decodes to the same contraption",
            func = function()
                local original = makeProp( CRATE, Vector( 0, 0, 200 ) )
                local entities, constraints = AdvDupe2.duplicator.Copy( nil, original, {}, {}, original:GetPos() )
                local encoded
                local dupe = { Entities = entities, Constraints = constraints,
                    HeadEnt = { Index = original:EntIndex(), Pos = original:GetPos(), Z = 0 } }
                local info = { name = "probe" }
                AdvDupe2.Encode( dupe, info, function( data ) encoded = data end )
                expect( isstring( encoded ) ).to.beTrue()
                local ok, dupe = AdvDupe2.Decode( encoded )
                expect( ok ).to.beTrue()
                expect( dupe.Entities[ original:EntIndex() ].Model ).to.equal( CRATE )
            end },
    },
}
