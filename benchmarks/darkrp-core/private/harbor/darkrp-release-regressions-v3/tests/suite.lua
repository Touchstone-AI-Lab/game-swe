local function entTable( class )
    local stored = scripted_ents.GetStored( class )
    return stored and stored.t
end

return {
    groupName = "DarkRP release regressions (extended)",
    cases = {
        {   -- PASS_TO_PASS sentinel
            name = "The gamemode is loaded",
            func = function()
                expect( DarkRP ).to.exist()
                expect( DarkRP.createJob ).to.beA( "function" )
                expect( GAMEMODE ).to.exist()
            end
        },

        -- ---- defect group A: arrested-player query API -------------------
        {
            name = "A: the arrested-player query API exists",
            func = function()
                expect( DarkRP.iterateArrestedPlayers ).to.beA( "function" )
                expect( DarkRP.arrestedPlayers ).to.beA( "function" )
                expect( DarkRP.arrestedPlayerCount ).to.beA( "function" )
            end
        },
        {
            name = "A: the arrested-player query API is self-consistent",
            func = function()
                local iterator = DarkRP.iterateArrestedPlayers()
                expect( iterator ).to.beA( "function" )
                expect( iterator() ).to.beNil()
                local list = DarkRP.arrestedPlayers()
                expect( list ).to.beA( "table" )
                expect( DarkRP.arrestedPlayerCount() ).to.equal( #list )
            end
        },

        -- ---- defect group B: spawned-entity failure paths -----------------
        {
            name = "B: spawned ammo survives a missing physics object",
            func = function()
                -- Permissive stand-in: anything the implementation calls on the
                -- entity resolves to a no-op, except GetPhysicsObject which hands
                -- back an invalid physics object. So this requires only the
                -- behaviour -- surviving that -- and not any particular set of calls.
                local noPhys = setmetatable( {
                    PhysicsInit = function() return true end,
                    GetPhysicsObject = function() return NULL end
                }, { __index = function() return function() end end } )
                expect( pcall( entTable( "spawned_ammo" ).Initialize, noPhys ) ).to.beTrue()
            end
        },
        {
            name = "B: spawned weapon survives a missing physics object",
            func = function()
                local noPhys = setmetatable( {
                    PhysicsInit = function() return true end,
                    GetWeaponClass = function() return "weapon_pistol" end,
                    GetPhysicsObject = function() return NULL end,
                    Getamount = function() return 1 end
                }, { __index = function() return function() end end } )
                expect( pcall( entTable( "spawned_weapon" ).Initialize, noPhys ) ).to.beTrue()
            end
        },

        -- ---- defect group C: disconnect cleanup hook ----------------------
        -- ---- defect group D: vote/question cleanup ------------------------
        {
            name = "D: destroying a question by an unknown id does not error",
            func = function()
                expect( DarkRP.destroyQuestion ).to.beA( "function" )
                expect( pcall( DarkRP.destroyQuestion, "gcb_no_such_question_id" ) ).to.beTrue()
                expect( pcall( DarkRP.destroyQuestion, 999999 ) ).to.beTrue()
            end
        },

        -- ---- defect group E: job creation ---------------------------------
        {
            name = "E: creating a job hands back the team number",
            func = function()
                local n = DarkRP.createJob( "GCB Cat Probe", {
                    color = Color( 20, 20, 20, 255 ),
                    model = "models/player/Group01/male_07.mdl",
                    description = "probe", weapons = {}, command = "gcbcatprobe",
                    max = 0, salary = 45, admin = 0, vote = false, category = "Citizens"
                } )
                expect( n ).to.beA( "number" )
                expect( RPExtraTeams[ n ] ).to.beA( "table" )
                expect( RPExtraTeams[ n ].name ).to.equal( "GCB Cat Probe" )
            end
        },

        -- ---- defect group F: shipment name lookup -------------------------
        -- Two faults that mask each other: neither the store nor the lookup
        -- normalises the name, so same-case lookups still work and the system
        -- looks fine. Fixing only one side breaks even those. Both assertions
        -- below must hold, which requires both halves to be correct.
        {
            name = "F: a shipment created with mixed case is found by its lower-case name",
            func = function()
                local nm = "GCB Ship Alpha"
                DarkRP.createShipment( nm, { model = "models/props_c17/oildrum001.mdl",
                    entity = "weapon_pistol", price = 100, amount = 1, separate = false,
                    pricesep = 0, noship = false, allowed = {}, category = "Other" } )
                expect( DarkRP.getShipmentByName( "gcb ship alpha" ) ).to.beA( "table" )
            end
        },
        {
            name = "F: a shipment created in lower case is found by a mixed-case name",
            func = function()
                local nm = "gcb ship beta"
                DarkRP.createShipment( nm, { model = "models/props_c17/oildrum001.mdl",
                    entity = "weapon_pistol", price = 100, amount = 1, separate = false,
                    pricesep = 0, noship = false, allowed = {}, category = "Other" } )
                expect( DarkRP.getShipmentByName( "GCB Ship Beta" ) ).to.beA( "table" )
            end
        },

        -- ---- defect group G: admin command gives no feedback ---------------
        -- Behavioural only: it must not blow up, and the admin must be told
        -- something. How the message is produced is not constrained.
        {
            name = "G: unrestricting a weapon with no argument tells the admin",
            async = true,
            timeout = 60,
            func = function()
                RunConsoleCommand( "bot" )
                timer.Simple( 5, function()
                    local ply
                    for _, p in ipairs( player.GetAll() ) do
                        if IsValid( p ) and p:IsPlayer() then ply = p break end
                    end
                    expect( IsValid( ply ) ).to.beTrue()

                    local entry = FAdmin.Commands.List[ "unrestrictweapon" ]
                    expect( entry ).to.beA( "table" )

                    -- capture whatever the command reports back to the admin
                    local told = false
                    local realSend = FAdmin.Messages.SendMessage
                    FAdmin.Messages.SendMessage = function( ... ) told = true end
                    -- give the player the privilege so we exercise the argument path
                    local realPriv = FAdmin.Access.PlayerHasPrivilege
                    FAdmin.Access.PlayerHasPrivilege = function() return true end

                    local ok = pcall( entry.callback, ply, "unrestrictweapon", {} )

                    FAdmin.Messages.SendMessage = realSend
                    FAdmin.Access.PlayerHasPrivilege = realPriv

                    expect( ok ).to.beTrue()   -- must not error on a missing argument
                    expect( told ).to.beTrue() -- and must not be silent
                    done()
                end )
            end
        }
    }
}
