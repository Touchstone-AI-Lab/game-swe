-- Behaviour-only assertions against DarkRP's registration APIs. Every case drives a
-- public DarkRP.* entry point and reads the result back through a public getter, so
-- no case depends on a bot, the database or server timing.
local MODEL = "models/player/Group01/male_07.mdl"
local n = 0
local function uniq( p ) n = n + 1 return p .. "t3g" .. n end

return {
    groupName = "DarkRP registration regressions",
    cases = {
        {   name = "sentinel: the gamemode is loaded",
            func = function()
                expect( DarkRP ).to.exist()
                expect( DarkRP.createVehicle ).to.beA( "function" )
            end },

        -- A: vehicle declarations
        {   name = "A: a vehicle is accepted however its name is capitalised",
            func = function()
                local available = DarkRP.getAvailableVehicles()
                local name
                for k in pairs( available ) do name = k break end
                expect( name ).to.exist()
                local shouted = string.upper( name )
                expect( pcall( DarkRP.createVehicle, {
                    name = shouted, model = MODEL, price = 10,
                    allowed = { 1 }, category = "Other" } ) ).to.beTrue()
            end },

        -- Positive control. Declaring a command and finding it again is untouched by
        -- every defect in this task, so it holds on BOTH trees: a submission that
        -- simply refuses or breaks every registration cannot score.
        {   name = "control: a plainly declared command can be found again",
            func = function()
                local name = uniq( "plain" )
                DarkRP.declareChatCommand{ command = name, description = "probe", delay = 0 }
                local entry = DarkRP.getChatCommand( name )
                expect( entry ).to.exist()
                expect( entry.description ).to.equal( "probe" )
            end },

        -- B: door groups
        {   name = "B: a door group knows the name it was created under",
            func = function()
                local a = uniq( "grp" )
                DarkRP.createEntityGroup( a, 8821, 8822 )
                local group = RPExtraTeamDoors[ a ]
                expect( group ).to.exist()
                expect( group.name ).to.equal( a )
                expect( table.HasValue( group, 8821 ) ).to.beTrue()
                expect( table.HasValue( group, 8822 ) ).to.beTrue()
            end },

        -- C: command aliases
        {   name = "C: an alias answers with the behaviour of the command it stands for",
            func = function()
                local target, alias = uniq( "cmd" ), uniq( "alias" )
                DarkRP.declareChatCommand{ command = target, description = "probe", delay = 0 }
                DarkRP.chatCommandAlias( target, alias )
                local entry = DarkRP.getChatCommand( alias )
                expect( entry ).to.exist()
                expect( entry.description ).to.equal( "probe" )
            end },

        -- D: the command list
        {   name = "D: the listed commands come back in ascending order",
            func = function()
                local sortedCommands = DarkRP.getSortedChatCommands()
                expect( #sortedCommands > 1 ).to.beTrue()
                local previous
                for _, entry in ipairs( sortedCommands ) do
                    if previous then expect( entry.command >= previous ).to.beTrue() end
                    previous = entry.command
                end
            end },

        -- E: networked variables
        {   name = "E: re-declaring a networked value keeps its identity and updates both sides",
            func = function()
                local name = uniq( "var" )
                local function w1() end local function r1() end
                local function w2() end local function r2() end
                DarkRP.registerDarkRPVar( name, w1, r1 )
                local first = DarkRP.RegisteredDarkRPVars[ name ].id
                DarkRP.registerDarkRPVar( name, w2, r2 )
                local entry = DarkRP.RegisteredDarkRPVars[ name ]
                expect( entry.id ).to.equal( first )
                expect( entry.writeFn ).to.equal( w2 )
                expect( entry.readFn ).to.equal( r2 )
            end },

        -- F: demote groups
        -- Asserted through the observable -- are these two jobs still grouped? --
        -- rather than through how the registry represents the removal. Dropping the
        -- entries and disconnecting them both genuinely ungroup the jobs, and both
        -- must pass; only leaving them grouped may fail.
        {   name = "F: removing a demote grouping releases the jobs that were in it",
            func = function()
                local a, b = 8801, 8802
                DarkRP.createDemoteGroup( uniq( "dg" ), { a, b } )
                local grouped = DarkRP.getDemoteGroup( a )
                expect( grouped ).to.exist()
                expect( DarkRP.getDemoteGroup( b ) ).to.equal( grouped )

                DarkRP.removeDemoteGroup( grouped.name )
                expect( DarkRP.getDemoteGroup( a ) == DarkRP.getDemoteGroup( b ) ).to.beFalse()
            end },

        -- G: door variables
        {   name = "G: a door value's identifier points at its own slot",
            func = function()
                local name = uniq( "doorvar" )
                DarkRP.registerDoorVar( name, function() end, function() end )
                local byName = DarkRP.getDoorVarsByName()[ name ]
                expect( byName ).to.exist()
                expect( DarkRP.getDoorVars()[ byName.id ] ).to.equal( byName )
            end },

        -- H: agendas
        {   name = "H: every job listed on an agenda can read it",
            func = function()
                local a, b = 8811, 8812
                DarkRP.createAgenda( uniq( "Agenda " ), 8810, { a, b } )
                local agendas = DarkRP.getAgendas()
                expect( agendas[ a ] ).to.exist()
                expect( agendas[ b ] ).to.exist()
                expect( agendas[ b ] ).to.equal( agendas[ a ] )
            end }
    }
}
