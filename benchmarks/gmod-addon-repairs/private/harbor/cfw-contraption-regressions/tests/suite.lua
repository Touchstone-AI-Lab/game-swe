-- Behaviour-only assertions against Contraption Framework on a headless server. Cases
-- build real props, ragdolls, NPCs and bots, connect them with real constraints and
-- parenting, and read the contraption and family objects the addon publishes.
local CRATE = "models/props_junk/wood_crate001a.mdl"
local RAGDOLL = "models/Humans/Group01/male_07.mdl"
local spawned = {}

local function track( ent )
    spawned[ #spawned + 1 ] = ent
    return ent
end

local function makeProp( pos )
    local ent = ents.Create( "prop_physics" )
    ent:SetModel( CRATE )
    ent:SetPos( pos )
    ent:Spawn()
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

-- Runs the checks of an async case and always finishes it exactly once: an unexpected
-- Lua error is recorded as the case's failure instead of leaving it to time out.
local function settle( expect, done, body )
    local ok, err = pcall( body )
    expect( ok and "completed" or tostring( err ) ).to.equal( "completed" )
    done()
end

-- Constraint tracking starts one tick after a constraint is created.
local function afterTicks( fn )
    timer.Simple( 0.3, fn )
end

return {
    groupName = "Contraption Framework",
    afterEach = function()
        for _, ent in ipairs( spawned ) do
            if IsValid( ent ) and not ent:IsPlayer() then SafeRemoveEntity( ent ) end
        end
        spawned = {}
    end,
    cases = {
        {   name = "sentinel: the framework is loaded and tracking entities",
            func = function()
                expect( CFW ).to.exist()
                expect( CFW.connect ).to.beA( "function" )
                local ent = makeProp( Vector( 0, 0, 100 ) )
                expect( ent.CFW_GetContraption ).to.beA( "function" )
                expect( ent.GetFamily ).to.beA( "function" )
            end },

        {   name = "A: a parented group's total mass follows a member's new mass",
            func = function()
                local root = makeProp( Vector( 0, 0, 100 ) )
                local child = makeProp( Vector( 0, 0, 160 ) )
                child:SetParent( root )
                local family = root:GetFamily()
                expect( family ).to.exist()
                local before = family.totalMass
                local phys = child:GetPhysicsObject()
                phys:SetMass( phys:GetMass() + 100 )
                expect( math.abs( family.totalMass - ( before + 100 ) ) < 0.01 ).to.beTrue()
            end },

        {   name = "preserved: a welded contraption's total mass follows a member's new mass",
            async = true, timeout = 10,
            func = function()
                local a = makeProp( Vector( 200, 0, 100 ) )
                local b = makeProp( Vector( 200, 60, 100 ) )
                track( constraint.Weld( a, b, 0, 0, 0, true, false ) )
                afterTicks( function()
                    settle( expect, done, function()
                        local con = a:CFW_GetContraption()
                        expect( con ).to.exist()
                        expect( b:CFW_GetContraption() ).to.equal( con )
                        local before = con.totalMass
                        local phys = b:GetPhysicsObject()
                        phys:SetMass( phys:GetMass() + 50 )
                        expect( math.abs( con.totalMass - ( before + 50 ) ) < 0.01 ).to.beTrue()
                    end )
                end )
            end },

        {   name = "B: a parent that only vetoes children can refuse one",
            func = function()
                local parent = makeProp( Vector( 400, 0, 100 ) )
                local child = makeProp( Vector( 400, 0, 160 ) )
                local asked = 0
                parent.CFW_PreParented = function( _, candidate )
                    asked = asked + 1
                    return false
                end
                child:SetParent( parent )
                expect( asked ).to.equal( 1 )
                expect( IsValid( child:GetParent() ) ).to.beFalse()
                expect( child:CFW_GetContraption() ).to.beNil()
            end },

        {   name = "preserved: a parent with both hooks can refuse or accept children",
            func = function()
                local parent = makeProp( Vector( 600, 0, 100 ) )
                local refused = makeProp( Vector( 600, 0, 160 ) )
                local accepted = makeProp( Vector( 600, 60, 160 ) )
                local notified = {}
                parent.CFW_PreParented = function( _, candidate ) return candidate ~= refused end
                parent.CFW_OnParented = function( _, candidate, attached ) notified[ candidate ] = attached end
                refused:SetParent( parent )
                accepted:SetParent( parent )
                expect( IsValid( refused:GetParent() ) ).to.beFalse()
                expect( accepted:GetParent() ).to.equal( parent )
                expect( notified[ accepted ] ).to.beTrue()
                expect( notified[ refused ] ).to.beNil()
                expect( accepted:CFW_GetContraption() ).to.exist()
            end },

        {   name = "C: something parented to a player stays out of contraptions",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    settle( expect, done, function()
                        expect( IsValid( bot ) ).to.beTrue()
                        local hat = makeProp( bot:GetPos() + Vector( 0, 0, 80 ) )
                        hat:SetParent( bot )
                        expect( hat:GetParent() ).to.equal( bot )
                        expect( hat:CFW_GetContraption() ).to.beNil()
                        expect( bot:CFW_GetContraption() ).to.beNil()
                        hat:SetParent( nil )
                    end )
                end )
            end },

        {   name = "C: something parented to an NPC stays out of contraptions",
            func = function()
                local npc = track( ents.Create( "npc_citizen" ) )
                npc:SetPos( Vector( -400, 0, 0 ) )
                npc:Spawn()
                expect( IsValid( npc ) and npc:IsNPC() ).to.beTrue()
                local hat = makeProp( npc:GetPos() + Vector( 0, 0, 80 ) )
                hat:SetParent( npc )
                expect( hat:GetParent() ).to.equal( npc )
                expect( hat:CFW_GetContraption() ).to.beNil()
                expect( npc:CFW_GetContraption() ).to.beNil()
            end },

        {   name = "C: something parented to a nextbot stays out of contraptions",
            func = function()
                scripted_ents.Register( { Base = "base_nextbot", Type = "nextbot",
                    Initialize = function( self ) self:SetModel( "models/Kleiner.mdl" ) end,
                    RunBehaviour = function( self ) while true do coroutine.yield() end end }, "rhenium_cfw_nextbot" )
                local bot = track( ents.Create( "rhenium_cfw_nextbot" ) )
                bot:SetPos( Vector( -600, 0, 0 ) )
                bot:Spawn()
                expect( IsValid( bot ) and bot:IsNextBot() ).to.beTrue()
                local hat = makeProp( bot:GetPos() + Vector( 0, 0, 80 ) )
                hat:SetParent( bot )
                expect( hat:GetParent() ).to.equal( bot )
                expect( hat:CFW_GetContraption() ).to.beNil()
                expect( bot:CFW_GetContraption() ).to.beNil()
            end },

        {   name = "D: joining two bones of one ragdoll creates no contraption",
            async = true, timeout = 10,
            func = function()
                local rag = track( ents.Create( "prop_ragdoll" ) )
                rag:SetModel( RAGDOLL )
                rag:SetPos( Vector( 0, -400, 50 ) )
                rag:Spawn()
                expect( rag:GetPhysicsObjectCount() > 1 ).to.beTrue()
                local weld = constraint.Weld( rag, rag, 0, 1, 0, false, false )
                expect( IsValid( weld ) ).to.beTrue()
                afterTicks( function()
                    local linked = rag:CFW_GetContraption()
                    local selfLink = rag:GetCFWLink( rag )
                    SafeRemoveEntity( weld )
                    timer.Simple( 0.3, function()
                        settle( expect, done, function()
                            expect( linked ).to.beNil()
                            expect( selfLink ).to.beNil()
                            expect( rag:CFW_GetContraption() ).to.beNil()
                        end )
                    end )
                end )
            end },

        {   name = "preserved: welding two props makes one contraption until the weld goes",
            async = true, timeout = 10,
            func = function()
                local a = makeProp( Vector( 0, 400, 100 ) )
                local b = makeProp( Vector( 0, 460, 100 ) )
                local weld = constraint.Weld( a, b, 0, 0, 0, true, false )
                afterTicks( function()
                    local con = a:CFW_GetContraption()
                    local count = con and con.count
                    local shared = b:CFW_GetContraption() == con
                    SafeRemoveEntity( weld )
                    timer.Simple( 0.3, function()
                        settle( expect, done, function()
                            expect( con ).to.exist()
                            expect( count ).to.equal( 2 )
                            expect( shared ).to.beTrue()
                            expect( a:CFW_GetContraption() ).to.beNil()
                            expect( b:CFW_GetContraption() ).to.beNil()
                        end )
                    end )
                end )
            end },
    },
}
