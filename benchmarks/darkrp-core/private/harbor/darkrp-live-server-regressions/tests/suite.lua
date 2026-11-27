-- Behaviour-only assertions. Each async case spawns its own bot; a bot spawned by
-- another case does not survive GLuaTest's async boundary.
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
local MODEL = "models/player/Group01/male_07.mdl"
local n = 0
local function uniq( p ) n = n + 1 return p .. "t2a" .. n end
local function mkJob( vote )
    return DarkRP.createJob( "T2A " .. uniq( "job" ), {
        color = Color( 20, 20, 20, 255 ), model = MODEL, description = "probe",
        weapons = {}, command = uniq( "cmd" ), max = 0, salary = 45,
        admin = 0, vote = vote and true or false, category = "Citizens" } )
end
local function ammoPresent( nm )
    for _, v in pairs( ( GM or GAMEMODE ).AmmoTypes ) do
        if v.name == nm then return true end
    end
    return false
end

return {
    groupName = "DarkRP regressions (batch A)",
    cases = {
        {   name = "sentinel: the gamemode is loaded",
            func = function()
                expect( DarkRP ).to.exist(); expect( FAdmin ).to.exist(); expect( CAMI ).to.exist()
            end },

        -- S: hitman registry
        {   name = "S: a job that does not exist cannot be made a hitman team",
            func = function()
                DarkRP.addHitmanTeam( 99999 )
                expect( DarkRP.getHitmanTeams()[ 99999 ] ).to.beNil()
            end },
        {   name = "S: a real job can still be made a hitman team",
            func = function()
                local t = mkJob( false )
                expect( t ).to.beA( "number" )
                DarkRP.addHitmanTeam( t )
                expect( DarkRP.getHitmanTeams()[ t ] ).to.beTrue()
            end },

        -- T: usergroup change notification
        {   name = "T: a usergroup change reports the group the player came from",
            async = true, timeout = 60,
            func = function()
                withBot( function( ply )
                    expect( IsValid( ply ) ).to.beTrue()
                    local entry = FAdmin.Commands.List[ "setaccess" ]
                    expect( entry ).to.beA( "table" )
                    FAdmin.Access.PlayerSetGroup( ply, "user" )
                    local sawFrom, sawTo
                    local rs, rp, rh = CAMI.SignalUserGroupChanged,
                                       FAdmin.Access.PlayerHasPrivilege, FAdmin.Access.PlayerIsHost
                    CAMI.SignalUserGroupChanged = function( p, from, to ) sawFrom, sawTo = from, to end
                    FAdmin.Access.PlayerHasPrivilege = function() return true end
                    FAdmin.Access.PlayerIsHost = function() return true end
                    pcall( entry.callback, ply, "setaccess", { ply:Nick(), "admin" } )
                    CAMI.SignalUserGroupChanged, FAdmin.Access.PlayerHasPrivilege,
                        FAdmin.Access.PlayerIsHost = rs, rp, rh
                    expect( sawTo ).to.equal( "admin" )
                    expect( sawFrom ).to.equal( "user" )
                    done()
                end )
            end },

        -- U: prompt cleanup
        {   name = "U: cleaning up a prompt that is already gone does not error",
            func = function()
                expect( pcall( DarkRP.destroyQuestion, "t2a_no_such_prompt" ) ).to.beTrue()
                expect( pcall( DarkRP.destroyQuestion, 876543 ) ).to.beTrue()
            end },

        -- V: demote feedback
        {   name = "V: demoting someone who is not here names who was looked for",
            async = true, timeout = 60,
            func = function()
                withBot( function( ply )
                    expect( IsValid( ply ) ).to.beTrue()
                    local said = {}
                    local realNotify, realCan = DarkRP.notify, GAMEMODE.canChatCommand
                    DarkRP.notify = function( _, _, _, msg ) said[ #said + 1 ] = tostring( msg ) end
                    GAMEMODE.canChatCommand = function() return true end
                    pcall( DarkRP.getChatCommand( "demote" ).callback, ply,
                           { "zzznosuchplayer", "some", "reason" } )
                    DarkRP.notify, GAMEMODE.canChatCommand = realNotify, realCan
                    local all = table.concat( said, " | " )
                    expect( #said > 0 ).to.beTrue()
                    expect( string.find( all, "zzznosuchplayer", 1, true ) ~= nil ).to.beTrue()
                    done()
                end )
            end },

        -- X: job removal
        {   name = "X: removing a job takes its vote command with it",
            async = true, timeout = 30,
            func = function()
                local t = mkJob( true )
                local cmd = "vote" .. RPExtraTeams[ t ].command
                timer.Simple( 1, function()
                    expect( DarkRP.getChatCommand( cmd ) ).to.exist()
                    DarkRP.removeJob( t )
                    expect( DarkRP.getChatCommand( cmd ) ).to.beNil()
                    done()
                end )
            end },

        -- Z: ammo registry
        {   name = "Z: removing an ammo type removes that one and no other",
            func = function()
                local a, b = uniq( "ammoA" ), uniq( "ammoB" )
                DarkRP.createAmmoType( "pistol", a, MODEL, 10, 30 )
                DarkRP.createAmmoType( "pistol", b, MODEL, 10, 30 )
                local entB
                for _, v in pairs( ( GM or GAMEMODE ).AmmoTypes ) do
                    if v.name == b then entB = v end
                end
                expect( entB ).to.exist()
                DarkRP.removeAmmoType( entB.id )
                expect( ammoPresent( b ) ).to.beFalse()
                expect( ammoPresent( a ) ).to.beTrue()
            end },

        -- AA: category mirroring
        {   name = "AA: a shipment category and its weapon copy do not share members",
            func = function()
                local nm = uniq( "T2A Cat " )
                DarkRP.createCategory{ name = nm, categorises = "shipments",
                    startExpanded = true, color = Color( 0, 107, 0, 255 ),
                    canSee = function() return true end, sortOrder = 250 }
                local cats = DarkRP.getCategories()
                local ship, weap
                for _, c in ipairs( cats.shipments ) do if c.name == nm then ship = c end end
                for _, c in ipairs( cats.weapons )   do if c.name == nm then weap = c end end
                expect( ship ).to.exist()
                expect( weap ).to.exist()
                local item = { name = uniq( "probe" ), category = nm }
                DarkRP.addToCategory( item, "shipments", nm )
                expect( #ship.members ).to.equal( 1 )
                expect( #weap.members ).to.equal( 0 )
            end },

        -- BB: re-declaring a category
        {   name = "BB: re-declaring a category keeps what was already in it",
            func = function()
                local nm = uniq( "T2A Cat " )
                local function make( order )
                    DarkRP.createCategory{ name = nm, categorises = "entities",
                        startExpanded = true, color = Color( 0, 107, 0, 255 ),
                        canSee = function() return true end, sortOrder = order }
                end
                make( 250 )
                DarkRP.addToCategory( { name = uniq( "probe" ), category = nm }, "entities", nm )
                make( 251 )
                local found
                for _, c in ipairs( DarkRP.getCategories().entities ) do
                    if c.name == nm then found = c end
                end
                expect( found ).to.exist()
                expect( #found.members ).to.equal( 1 )
            end },

        -- CC: dropped money
        {   name = "CC: dropped money survives an invalid physics object",
            func = function()
                local noPhys = setmetatable( {
                    PhysicsInit = function() return true end,
                    GetPhysicsObject = function() return NULL end
                }, { __index = function() return function() end end } )
                local ent = scripted_ents.GetStored( "spawned_money" )
                expect( ent ).to.exist()
                expect( pcall( ent.t.Initialize, noPhys ) ).to.beTrue()
            end }
    }
}
