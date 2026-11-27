-- Behaviour-only assertions about what a job or category declares and what actually
-- reaches the player: which definitions the gamemode accepts, and which of the values
-- in an accepted one are applied.

-- These routines belong to the submission, so a repair is free to change what they hand
-- back. Read defensively: a wrong shape must fail an assertion, not raise.
local function ok( v ) return v == true end

local n = 0
local function uniqueCmd() n = n + 1 return "gcbprobe" .. n end

local function baseJob()
    return {
        name = "Probe Job",
        color = Color( 1, 2, 3 ),
        model = "models/player/kleiner.mdl",
        description = "a job used to check a definition is judged correctly",
        weapons = {},
        command = uniqueCmd(),
        max = 0,
        salary = 45,
        admin = 0,
        vote = false,
        hasLicense = false,
        candemote = false,
        category = "Citizens",
    }
end

local function baseCategory()
    return { name = "Probe Category", categorises = "jobs", startExpanded = true,
             color = Color( 1, 2, 3 ) }
end

-- Applying a job's movement and health settings needs a class to read them from.
local CLASS = 0
local function applyClass( ply, fields )
    CLASS = CLASS + 1
    local name = "gcb_probe_class_" .. CLASS
    player_manager.RegisterClass( name, table.Merge( {
        WalkSpeed = 200, RunSpeed = 400, CrouchedWalkSpeed = 0.5, DuckSpeed = 0.5,
        UnDuckSpeed = 0.5, JumpPower = 200, CanUseFlashlight = true,
        MaxHealth = 100, StartHealth = 100, StartArmor = 0, DropWeaponOnDie = false,
        TeammateNoCollide = true, AvoidPlayers = true, UseVMHands = true,
    }, fields ), "player_default" )
    player_manager.SetPlayerClass( ply, name )
    ply:applyPlayerClassVars( true )
end

local function subject() return player.GetAll()[ 1 ] end

return {
    groupName = "DarkRP job loadout regressions",
    cases = {
        {   name = "sentinel: the gamemode and its definition checkers are loaded",
            func = function()
                expect( DarkRP ).to.exist()
                expect( DarkRP.validateJob ).to.beA( "function" )
                expect( DarkRP.validateCategory ).to.beA( "function" )
                expect( DarkRP.validateEntity ).to.beA( "function" )
                expect( subject() ).to.exist()
            end },

        -- Positive control: a well-formed job is accepted. Holds on both trees, so a
        -- submission that simply refuses every definition cannot score.
        {   name = "control: a job that declares everything properly is accepted",
            func = function()
                expect( ok( DarkRP.validateJob( baseJob() ) ) ).to.beTrue()
            end },

        -- Positive control: a plainly wrong field is still refused on both trees.
        {   name = "control: a job whose name is not text is refused",
            func = function()
                local job = baseJob()
                job.name = 5
                expect( ok( DarkRP.validateJob( job ) ) ).to.beFalse()
            end },

        {   name = "A: a job that lists no model at all is refused",
            func = function()
                local job = baseJob()
                job.model = {}
                expect( ok( DarkRP.validateJob( job ) ) ).to.beFalse()
            end },

        {   name = "B: a job with nothing said about it is refused",
            func = function()
                local job = baseJob()
                job.description = nil
                expect( ok( DarkRP.validateJob( job ) ) ).to.beFalse()
            end },

        {   name = "C: a category that does not say how it opens is refused",
            func = function()
                local cat = baseCategory()
                cat.startExpanded = nil
                expect( ok( DarkRP.validateCategory( cat ) ) ).to.beFalse()
            end },

        {   name = "D: a job that declares it cannot walk does not walk",
            func = function()
                local ply = subject()
                applyClass( ply, { WalkSpeed = 0 } )
                expect( ply:GetWalkSpeed() ).to.equal( 0 )
            end },

        {   name = "E: a job starts a player on the health it declares, not on its ceiling",
            func = function()
                local ply = subject()
                applyClass( ply, { MaxHealth = 200, StartHealth = 50 } )
                expect( ply:GetMaxHealth() ).to.equal( 200 )
                expect( ply:Health() ).to.equal( 50 )
            end },

        {   name = "F: a job that sets no running speed runs at the speed for its side",
            func = function()
                local ply = subject()
                expect( ply:isCP() ).to.beFalse()
                applyClass( ply, { RunSpeed = -1 } )
                expect( ply:GetRunSpeed() ).to.equal( GAMEMODE.Config.runspeed )
            end },

        {   name = "G: a job that declares a health ceiling of zero is held to it",
            func = function()
                local ply = subject()
                applyClass( ply, { MaxHealth = 0, StartHealth = 0 } )
                expect( ply:GetMaxHealth() ).to.equal( 0 )
            end }
    }
}
