-- Behaviour-only assertions against StarfallEx, driven through real starfall_processor
-- chips owned by a bot on a headless server. Each chip runs a small script and the case
-- reads back the values that script left in its own global environment.
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

local chips = {}
local function runChip( owner, files, main )
    local chip = ents.Create( "starfall_processor" )
    chip:SetModel( "models/spacecode/sfchip.mdl" )
    chip:SetPos( Vector( 0, 0, 100 + #chips * 8 ) )
    chip:Spawn()
    chips[ #chips + 1 ] = chip
    local ok, thrown = pcall( chip.Compile, chip, { owner = owner, mainfile = main or "main.txt", files = files } )
    local env = chip.instance and chip.instance.env or {}
    local err = chip.error and chip.error.message or nil
    if not ok then err = "compile raised: " .. tostring( thrown ) end
    return chip, env, err
end

local function script( body )
    return { [ "main.txt" ] = "--@server\n" .. body }
end

local function near( a, b ) return isnumber( a ) and math.abs( a - b ) < 1e-3 end

-- Runs the checks of an async case and always finishes it exactly once: an unexpected
-- Lua error is recorded as the case's failure instead of leaving it to time out.
local function settle( expect, done, body )
    local ok, err = pcall( body )
    expect( ok and "completed" or tostring( err ) ).to.equal( "completed" )
    done()
end

return {
    groupName = "StarfallEx",
    afterAll = function()
        for _, chip in ipairs( chips ) do SafeRemoveEntity( chip ) end
    end,
    cases = {
        {   name = "sentinel: the addon and its processor are loaded",
            func = function()
                expect( SF ).to.exist()
                expect( SF.Instance ).to.exist()
                expect( scripted_ents.GetStored( "starfall_processor" ) ).to.exist()
            end },

        {   name = "A: loadstring runs the chunk in the environment it is given",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    settle( expect, done, function()
                        local _, env, err = runChip( bot, script( [[
local e = { marker = 42 }
local f = loadstring( "M2 = marker return marker", "chunk", e )
R = f()
R2 = e.M2
LEAK = M2
]] ) )
                        expect( err ).to.beNil()
                        expect( env.R ).to.equal( 42 )
                        expect( env.R2 ).to.equal( 42 )
                        expect( env.LEAK ).to.beNil()
                    end )
                end )
            end },

        {   name = "preserved: loadstring without an environment runs in the chip",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    settle( expect, done, function()
                        local _, env, err = runChip( bot, script( [[
X = 5
local f = loadstring( "Y = X * 2 return X" )
R = f()
]] ) )
                        expect( err ).to.beNil()
                        expect( env.R ).to.equal( 5 )
                        expect( env.Y ).to.equal( 10 )
                    end )
                end )
            end },

        {   name = "B: a removed entity can still be turned into text",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    local _, env, err = runChip( bot, script( [[
local p = prop.create( chip():getPos() + Vector( 0, 0, 60 ), Angle(), "models/props_junk/PopCan01a.mdl", true )
p:remove()
timer.simple( 0.3, function()
    OK, S = pcall( tostring, p )
    DONE = true
end )
]] ) )
                    timer.Simple( 1.5, function()
                        settle( expect, done, function()
                            expect( err ).to.beNil()
                            expect( env.DONE ).to.beTrue()
                            expect( env.OK ).to.beTrue()
                            expect( env.S ).to.equal( "(null entity)" )
                        end )
                    end )
                end )
            end },

        {   name = "preserved: a live entity turns into its usual text",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    settle( expect, done, function()
                        local chip, env, err = runChip( bot, script( [[
S = tostring( chip() )
]] ) )
                        expect( err ).to.beNil()
                        expect( env.S ).to.equal( tostring( chip ) )
                    end )
                end )
            end },

        {   name = "C: a permitted chip can hand its owner a weapon",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    settle( expect, done, function()
                        bot:SetUserGroup( "superadmin" )
                        bot:StripWeapons()
                        local _, env, err = runChip( bot, script( [[
OK, ERR = pcall( function() return owner():giveWeapon( "weapon_357" ) end )
]] ) )
                        bot:SetUserGroup( "user" )
                        expect( err ).to.beNil()
                        expect( env.OK ).to.beTrue()
                        expect( bot:HasWeapon( "weapon_357" ) ).to.beTrue()
                    end )
                end )
            end },

        {   name = "preserved: an unpermitted chip still cannot hand out weapons",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    settle( expect, done, function()
                        bot:SetUserGroup( "user" )
                        bot:StripWeapons()
                        local _, env, err = runChip( bot, script( [[
OK, ERR = pcall( function() return owner():giveWeapon( "weapon_357" ) end )
]] ) )
                        expect( err ).to.beNil()
                        expect( env.OK ).to.beFalse()
                        expect( bot:HasWeapon( "weapon_357" ) ).to.beFalse()
                    end )
                end )
            end },

        {   name = "D: skipping past the end of a string stream leaves it usable",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    settle( expect, done, function()
                        local _, env, err = runChip( bot, script( [[
local ss = bit.stringstream( "abc" )
ss:skip( 10 )
OK, POS = pcall( function() return ss:tell() end )
OK2, OUT = pcall( function() ss:write( "d" ) return ss:getString() end )
]] ) )
                        expect( err ).to.beNil()
                        expect( env.OK ).to.beTrue()
                        expect( env.POS ).to.equal( 4 )
                        expect( env.OK2 ).to.beTrue()
                        expect( env.OUT ).to.equal( "abcd" )
                    end )
                end )
            end },

        {   name = "preserved: skipping inside a string stream still works",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    settle( expect, done, function()
                        local _, env, err = runChip( bot, script( [[
local ss = bit.stringstream( "abcdef" )
ss:skip( 2 )
R = ss:read( 2 )
T = ss:tell()
]] ) )
                        expect( err ).to.beNil()
                        expect( env.R ).to.equal( "cd" )
                        expect( env.T ).to.equal( 5 )
                    end )
                end )
            end },

        {   name = "E: quaternion slerp lands halfway between its ends",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    settle( expect, done, function()
                        local _, env, err = runChip( bot, script( [[
local s = math.sqrt( 0.5 )
local a = Quaternion( s, 0, 0, s )
local r = math.slerpQuaternion( a, Quaternion( 1, 0, 0, 0 ), 0.5 )
R = { r[1], r[2], r[3], r[4] }
local q = math.slerpQuaternion( a, a, 0.5 )
Q = { q[1], q[2], q[3], q[4] }
]] ) )
                        expect( err ).to.beNil()
                        local r, q, s = env.R or {}, env.Q or {}, math.sqrt( 0.5 )
                        expect( near( r[1], 0.92388 ) and near( r[2], 0 ) and near( r[3], 0 ) and near( r[4], 0.38268 ) ).to.beTrue()
                        expect( near( q[1], s ) and near( q[2], 0 ) and near( q[3], 0 ) and near( q[4], s ) ).to.beTrue()
                    end )
                end )
            end },

        {   name = "preserved: quaternion slerp at zero returns its start",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    settle( expect, done, function()
                        local _, env, err = runChip( bot, script( [[
local s = math.sqrt( 0.5 )
local r = math.slerpQuaternion( Quaternion( s, 0, 0, s ), Quaternion( 1, 0, 0, 0 ), 0 )
R = { r[1], r[2], r[3], r[4] }
]] ) )
                        expect( err ).to.beNil()
                        local r, s = env.R or {}, math.sqrt( 0.5 )
                        expect( near( r[1], s ) and near( r[2], 0 ) and near( r[3], 0 ) and near( r[4], s ) ).to.beTrue()
                    end )
                end )
            end },

        {   name = "F: a chip that includes a data file compiles and can read it",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    settle( expect, done, function()
                        local _, env, err = runChip( bot, {
                            [ "main.txt" ] = "--@server\n--@includedata data.txt\nD = getScripts()[ \"data.txt\" ]\n",
                            [ "data.txt" ] = "not {lua",
                        } )
                        expect( err ).to.beNil()
                        expect( env.D ).to.equal( "not {lua" )
                    end )
                end )
            end },

        {   name = "preserved: a chip that includes a script can require it",
            async = true, timeout = 30,
            func = function()
                withBot( function( bot )
                    settle( expect, done, function()
                        local _, env, err = runChip( bot, {
                            [ "main.txt" ] = "--@server\n--@include lib.txt\nL = require( \"lib.txt\" )\n",
                            [ "lib.txt" ] = "return 7",
                        } )
                        expect( err ).to.beNil()
                        expect( env.L ).to.equal( 7 )
                    end )
                end )
            end },
    },
}
