-- Behaviour-only assertions against Wiremod on a headless server: real gate entities,
-- real Expression 2 chips owned by a bot, the addon's port API and its script compiler.
local GATE_MODEL = "models/jaanus/wiretool/wiretool_gate.mdl"
local CHIP_MODEL = "models/beer/wiremod/gate_e2.mdl"
local spawned = {}

local function track( ent )
    spawned[ #spawned + 1 ] = ent
    return ent
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

local function makeGate( action )
    local gate = ents.Create( "gmod_wire_gate" )
    gate:SetModel( GATE_MODEL )
    gate:SetPos( Vector( #spawned * 20, 0, 100 ) )
    gate:Spawn()
    gate:Setup( action )
    return track( gate )
end

-- A Constant Value entity is the simplest real wire source; gates read their inputs
-- only through wires, exactly as on a live server.
local function makeValue( number )
    local source = ents.Create( "gmod_wire_value" )
    source:SetModel( "models/kobilica/value.mdl" )
    source:SetPos( Vector( #spawned * 20, -200, 100 ) )
    source:Spawn()
    source:Setup( { { DataType = "NORMAL", Value = tostring( number ) } } )
    return track( source )
end

local function wireUp( destination, inputName, source, outputName )
    local link = "rhenium_probe_" .. destination:EntIndex()
    WireLib.Link_Start( link, destination, destination:GetPos(), inputName, "cable/rope", Color( 255, 255, 255 ), 1 )
    WireLib.Link_End( link, source, source:GetPos(), outputName, nil )
end

local function makeChip( owner, code )
    local chip = MakeWireExpression2( owner, Vector( #spawned * 20, 200, 100 ), Angle( 0, 0, 0 ), CHIP_MODEL )
    track( chip )
    chip:Setup( code, {} )
    return chip
end

local function runE2( code, owner )
    local ok, fn = E2Lib.compileScript( code, owner )
    if not ok then return "compile error: " .. tostring( fn ) end
    local ran, err = fn()
    if not ran then return "runtime error: " .. tostring( err ) end
    return "ok"
end

-- Runs the checks of an async case and always finishes it exactly once: an unexpected
-- Lua error is recorded as the case's failure instead of leaving it to time out.
local function settle( expect, done, body )
    local ok, err = pcall( body )
    expect( ok and "completed" or tostring( err ) ).to.equal( "completed" )
    done()
end

local function isZeroVector( v )
    return isvector( v ) and v.x == 0 and v.y == 0 and v.z == 0
end

local function isZeroAngle( a )
    return isangle( a ) and a.p == 0 and a.y == 0 and a.r == 0
end

return {
    groupName = "Wiremod gates, ports, chips and holograms",
    afterEach = function()
        for _, ent in ipairs( spawned ) do SafeRemoveEntity( ent ) end
        spawned = {}
    end,
    cases = {
        {   name = "sentinel: the addon, its gates and its chips are loaded",
            func = function()
                expect( WireLib ).to.exist()
                expect( GateActions ).to.exist()
                expect( MakeWireExpression2 ).to.beA( "function" )
                expect( runE2( "A = 2 * 3\nassert(A == 6)" ) ).to.equal( "ok" )
            end },

        {   name = "A: a derivative gate drops back to zero once its input settles",
            async = true, timeout = 20,
            func = function()
                local gate = makeGate( "derive" )
                timer.Simple( 0.3, function()
                    wireUp( gate, "A", makeValue( 10 ), "1" )
                    timer.Simple( 0.6, function()
                        settle( expect, done, function()
                            expect( gate.Outputs.Out.Value ).to.equal( 0 )
                        end )
                    end )
                end )
            end },

        {   name = "A: vector and angle derivative gates never report an infinite rate",
            func = function()
                local vec = makeGate( "vector_derive" )
                local ang = makeGate( "angle_derive" )
                expect( isZeroVector( vec.Outputs.Out.Value ) ).to.beTrue()
                expect( isZeroAngle( ang.Outputs.Out.Value ) ).to.beTrue()
                local state = {}
                GateActions.vector_derive.reset( state )
                expect( isZeroVector( GateActions.vector_derive.output( state, Vector( 1, 2, 3 ) ) ) ).to.beTrue()
                local astate = {}
                GateActions.angle_derive.reset( astate )
                expect( isZeroAngle( GateActions.angle_derive.output( astate, Angle( 1, 2, 3 ) ) ) ).to.beTrue()
            end },

        {   name = "preserved: an ordinary gate still follows its inputs at once",
            func = function()
                local gate = makeGate( "floor" )
                wireUp( gate, "A", makeValue( 2.7 ), "1" )
                expect( gate.Outputs.Out.Value ).to.equal( 2 )
                local other = makeGate( "floor" )
                wireUp( other, "A", makeValue( -1.5 ), "1" )
                expect( other.Outputs.Out.Value ).to.equal( -2 )
            end },

        {   name = "B: outputs added in front of existing ones keep a consistent order",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    settle( expect, done, function()
                        local chip = makeChip( bot, "@outputs A B\nA = 1\nB = 2\n" )
                        expect( chip.error ).to.beFalse()
                        chip:Setup( "@outputs X A B\nX = 3\nA = 1\nB = 2\n", {} )
                        expect( chip.error ).to.beFalse()
                        local outputs = chip.Outputs
                        expect( outputs.X.Num ).to.equal( 1 )
                        expect( outputs.A.Num ).to.equal( 2 )
                        expect( outputs.B.Num ).to.equal( 3 )
                        WireLib.RefreshSpecialOutputs( chip )
                        expect( chip.Outputs.X ).to.exist()
                        expect( chip.Outputs.A ).to.exist()
                        expect( chip.Outputs.B ).to.exist()
                    end )
                end )
            end },

        {   name = "preserved: a chip's outputs carry the values it assigns",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    settle( expect, done, function()
                        local chip = makeChip( bot, "@outputs A B\nA = 1\nB = 2\n" )
                        expect( chip.error ).to.beFalse()
                        expect( chip.Outputs.A.Value ).to.equal( 1 )
                        expect( chip.Outputs.B.Value ).to.equal( 2 )
                        expect( chip.Outputs.A.Num ).to.equal( 1 )
                        expect( chip.Outputs.B.Num ).to.equal( 2 )
                    end )
                end )
            end },

        {   name = "C: unlimited mode lets a loop use the raised per-tick budget",
            async = true, timeout = 20,
            func = function()
                local previous = GetConVar( "wire_expression2_unlimited" ):GetString()
                RunConsoleCommand( "wire_expression2_unlimited", "1" )
                timer.Simple( 0.3, function()
                    local result = runE2( "@strict\nI = 0\nwhile (perf()) { I++ }\nassert(I > 0)" )
                    RunConsoleCommand( "wire_expression2_unlimited", previous )
                    -- The restored setting only applies on a later frame; finish after it
                    -- so the cases that follow run with the normal budget again.
                    timer.Simple( 0.3, function()
                        settle( expect, done, function()
                            expect( result ).to.equal( "ok" )
                        end )
                    end )
                end )
            end },

        {   name = "preserved: the normal per-tick budget still stops a runaway loop",
            func = function()
                expect( runE2( "@strict\nI = 0\nwhile (perf()) { I++ }\nassert(I > 0)" ) ).to.equal( "ok" )
                local runaway = runE2( "@strict\nI = 0\nwhile (1) { I++ }" )
                expect( string.StartWith( runaway, "runtime error: tick quota exceeded" ) ).to.beTrue()
            end },

        {   name = "D: a timer still exists while its last run executes",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    local chip = makeChip( bot, [[
@strict
@outputs Seen Reps Ran
timer("probe", 0.1, 1, function() {
    Seen = timerExists("probe")
    Reps = timerGetReps("probe")
    Ran = 1
})
]] )
                    expect( chip.error ).to.beFalse()
                    timer.Simple( 1, function()
                        settle( expect, done, function()
                            expect( chip.error ).to.beFalse()
                            expect( chip.Outputs.Ran.Value ).to.equal( 1 )
                            expect( chip.Outputs.Seen.Value ).to.equal( 1 )
                            expect( chip.Outputs.Reps.Value ).to.equal( 1 )
                        end )
                    end )
                end )
            end },

        {   name = "preserved: a finished timer is gone afterwards",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    local chip = makeChip( bot, [[
@outputs Runs After
timer("probe", 0.1, 2, function() {
    Runs++
})
timer("check", 0.8, 1, function() {
    After = timerExists("probe") + 10
})
]] )
                    expect( chip.error ).to.beFalse()
                    timer.Simple( 1.5, function()
                        settle( expect, done, function()
                            expect( chip.error ).to.beFalse()
                            expect( chip.Outputs.Runs.Value ).to.equal( 2 )
                            expect( chip.Outputs.After.Value ).to.equal( 10 )
                        end )
                    end )
                end )
            end },

        {   name = "E: hologram functions return neutral values when there is no hologram",
            func = function()
                expect( runE2( [[
assert(holoCreate(1) == noentity())
assert(holoScale(42) == vec(0, 0, 0))
assert(holoBodygroups(42, 0) == 0)
assert(holoAnimLength(42) == 0)
assert(holoGetAnimFrame(42) == 0)
assert(holoGetAnims(42):count() == 0)
]] ) ).to.equal( "ok" )
            end },

        {   name = "preserved: an existing hologram reports its own properties",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    local chip = makeChip( bot, [[
@outputs Made Scale:vector
interval(200)
if (first()) { exit() }
if (!Made) {
    holoCreate(1, entity():pos() + vec(0, 0, 40), vec(2, 2, 2))
    Made = holoEntity(1):isValid()
    Scale = holoScale(1)
}
]] )
                    expect( chip.error ).to.beFalse()
                    timer.Simple( 2.5, function()
                        settle( expect, done, function()
                            expect( chip.error ).to.beFalse()
                            expect( chip.Outputs.Made.Value ).to.equal( 1 )
                            local scale = chip.Outputs.Scale.Value
                            expect( isvector( scale ) and scale.x == 2 and scale.y == 2 and scale.z == 2 ).to.beTrue()
                        end )
                    end )
                end )
            end },

        {   name = "F: calling a function by name as a statement works",
            func = function()
                expect( runE2( "function number probe() { return 1 }\n\"probe\"()\nDone = 1\nassert(Done == 1)" ) ).to.equal( "ok" )
                expect( runE2( "\"curtime\"()\nDone = 1\nassert(Done == 1)" ) ).to.equal( "ok" )
            end },

        {   name = "preserved: calling a function by name for its value works",
            func = function()
                expect( runE2( "function number probe() { return 7 }\nN = \"probe\"()[number]\nassert(N == 7)" ) ).to.equal( "ok" )
            end },
    },
}
