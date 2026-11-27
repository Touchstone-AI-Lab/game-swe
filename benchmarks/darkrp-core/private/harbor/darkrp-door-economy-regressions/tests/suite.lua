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

-- Behaviour-only assertions. Where a case can be driven with stand-in tables it is,
-- so it does not depend on a bot whose database record never finishes loading.
local entMeta = FindMetaTable( "Entity" )
local plyMeta = FindMetaTable( "Player" )
local n = 0
local function uniq( p ) n = n + 1 return p .. "t2b" .. n end

-- A stand-in player: only the two identity methods the door code uses, deliberately
-- given DIFFERENT values so a lookup by the wrong one cannot pass by coincidence.
local function fakePly( userId, entIndex, teamNr )
    return { UserID = function() return userId end,
             EntIndex = function() return entIndex end,
             Team = function() return teamNr end,
             SteamID64 = function() return "7656119" .. tostring( userId ) end,
             -- keysOwn books ownership into these two on the way out. They are
             -- bookkeeping, not authorisation: without them the REFUSED attempt would
             -- error for an unrelated reason and the negative control would be vacuous.
             OwnedNumz = 1,
             Ownedz = {} }
end
-- A stand-in door: any entity method the implementation reaches for resolves through
-- the real Entity metatable, so restructuring the implementation cannot fail it.
-- Any entity method the implementation reaches for resolves through the real Entity
-- metatable; anything it does not define resolves to an inert no-op, so an
-- implementation that restructures these functions cannot fail on an unmodelled stub.
local function fakeDoor( data, owner )
    return setmetatable( {
        getDoorData = function() return data end,
        getDoorOwner = function() return owner end,
        IsVehicle = function() return false end,
        EntIndex = function() return 4321 end,
        CPPIGetOwner = function() return nil end,
        CPPISetOwner = function() end
    }, { __index = function( _, key )
        local inherited = entMeta[ key ]
        if inherited ~= nil then return inherited end
        return function() return nil end
    end } )
end

local GCB_SUITE = {
    groupName = "DarkRP regressions (batch B)",
    cases = {
        {   name = "sentinel: the gamemode is loaded",
            func = function()
                expect( DarkRP ).to.exist(); expect( FAdmin ).to.exist(); expect( CAMI ).to.exist()
            end },

        -- P: affordability
        {   name = "P: a negative price is never affordable",
            func = function()
                local ply = { getDarkRPVar = function() return 500 end }
                expect( plyMeta.canAfford( ply, -100 ) ).to.beFalse()
            end },
        {   name = "P: ordinary prices are unaffected",
            func = function()
                local ply = { getDarkRPVar = function() return 500 end }
                expect( plyMeta.canAfford( ply, 100 ) ).to.beTrue()
                expect( plyMeta.canAfford( ply, 600 ) ).to.beFalse()
            end },

        -- Q: door ownership
        -- Asserted through the observable (can the owner lock it?) rather than through
        -- isKeysOwnedBy's return value: a solution that recognises the owner at the call
        -- sites instead of inside that predicate is behaviourally correct and must pass.
        {   name = "Q: whoever owns a door can lock it",
            func = function()
                local ply = fakePly( 7, 3, 9911 )
                local door = fakeDoor( { extraOwners = {} }, ply )
                expect( plyMeta.canKeysLock( ply, door ) or false ).to.beTrue()
                expect( plyMeta.canKeysUnlock( ply, door ) or false ).to.beTrue()
                local stranger = fakePly( 8, 4, 9912 )
                expect( plyMeta.canKeysLock( stranger, door ) or false ).to.beFalse()
            end },

        -- R: door allow list
        -- Driven end to end through the public door API -- grant access, take the
        -- door, then ask who owns it -- rather than asserting what isKeysAllowedToOwn
        -- returns. A solution that honours the allow list somewhere other than inside
        -- that predicate is behaviourally correct and passes.
        -- The door is ALREADY OWNED by someone else, so only the allow-list path can
        -- grant ownership. Both the authorised and the unauthorised attempt are made,
        -- and both must complete without error: asserting only the granted half would
        -- be satisfied by an implementation that simply lets EVERYONE take the door.
        {   name = "R: a door's allow list decides who may take it",
            func = function()
                local owner    = fakePly( 9, 5, 1 )
                local grantee  = fakePly( 7, 3, 1 )
                local stranger = fakePly( 8, 4, 1 )
                local door = fakeDoor( { owner = 9 } )
                door.isKeysOwned  = function() return true end
                door.getDoorOwner = function() return owner end

                local realUpdate = DarkRP.updateDoorData
                DarkRP.updateDoorData = function() end
                entMeta.addKeysAllowedToOwn( door, grantee )
                local grantedOk = pcall( entMeta.keysOwn, door, grantee )
                local refusedOk = pcall( entMeta.keysOwn, door, stranger )
                DarkRP.updateDoorData = realUpdate

                expect( grantedOk ).to.beTrue()
                expect( refusedOk ).to.beTrue()
                expect( entMeta.isKeysOwnedBy( door, grantee ) or false ).to.beTrue()
                expect( entMeta.isKeysOwnedBy( door, stranger ) or false ).to.beFalse()
            end },

        {   name = "S: every team listed for a group chat can see it",
            func = function()
                local gm = GM or GAMEMODE
                DarkRP.createGroupChat( 4242, 4243 )
                local pred = gm.DarkRPGroupChats[ #gm.DarkRPGroupChats ]
                expect( pred ).to.beA( "function" )
                expect( pred( fakePly( 1, 1, 4242 ) ) ).to.beTrue()
                expect( pred( fakePly( 1, 1, 4243 ) ) ).to.beTrue()
                expect( pred( fakePly( 1, 1, 4244 ) ) ).to.beFalse()
            end },

        -- T: chat command registration
        {   name = "T: a chat command declared with capitals can still be found",
            func = function()
                local nm = "T2BMixedCase" .. n
                DarkRP.declareChatCommand{ command = nm, description = "probe", delay = 0 }
                expect( DarkRP.getChatCommand( string.lower( nm ) ) ).to.exist()
            end },

        -- U: agendas
        {   name = "U: the job that manages an agenda can update it",
            async = true, timeout = 60,
            func = function()
                RunConsoleCommand( "bot" )
                timer.Simple( 5, function()
                    local ply
                    for _, p in ipairs( player.GetAll() ) do
                        if IsValid( p ) and p:IsPlayer() then ply = p break end
                    end
                    expect( IsValid( ply ) ).to.beTrue()
                    local t = ply:Team()
                    DarkRP.createAgenda( uniq( "T2B Agenda " ), t, { t } )
                    local realCan = GAMEMODE.canChatCommand
                    GAMEMODE.canChatCommand = function() return true end
                    pcall( DarkRP.getChatCommand( "agenda" ).callback, ply, "t2b agenda body" )
                    GAMEMODE.canChatCommand = realCan
                    local agenda = ply:getAgendaTable()
                    expect( agenda ).to.exist()
                    expect( agenda.text ).to.equal( "t2b agenda body" )
                    done()
                end )
            end },

        -- V: money on the ground
        {   name = "V: money a player dropped is recognised as money",
            func = function()
                local bag = setmetatable( { IsSpawnedMoney = true,
                    GetClass = function() return "t2b_not_the_config_class" end },
                    { __index = entMeta } )
                expect( entMeta.isMoneyBag( bag ) ).to.beTrue()
                local prop = setmetatable( {
                    GetClass = function() return "t2b_not_the_config_class" end },
                    { __index = entMeta } )
                expect( entMeta.isMoneyBag( prop ) ).to.beFalse()
            end },

        -- W: doors assigned to a job
        {   name = "W: a job assigned to a door can lock it",
            func = function()
                local ply = fakePly( 7, 3, 4321 )
                local door = setmetatable( {
                    getDoorData = function() return { teamOwn = { [ 4321 ] = true } } end,
                    getDoorOwner = function() return nil end
                }, { __index = entMeta } )
                expect( plyMeta.canKeysLock( ply, door ) or false ).to.beTrue()
                local outsider = fakePly( 8, 4, 4322 )
                expect( plyMeta.canKeysLock( outsider, door ) or false ).to.beFalse()
            end },

        -- X: buy-menu item removal
        {   name = "X: removing a buy-menu item takes its command with it",
            async = true, timeout = 30,
            func = function()
                local cmd = string.lower( uniq( "t2bcmd" ) )
                DarkRP.createEntity( uniq( "T2B Ent " ), {
                    ent = "prop_physics", model = "models/props_c17/oildrum001.mdl",
                    price = 10, max = 1, cmd = cmd, category = "Other" } )
                -- the item's command is registered a frame later, upstream
                timer.Simple( 1, function()
                    local idx
                    for i, v in pairs( DarkRPEntities ) do
                        if v.cmd == cmd then idx = i end
                    end
                    expect( idx ).to.exist()
                    expect( DarkRP.getChatCommand( cmd ) ).to.exist()
                    DarkRP.removeEntity( idx )
                    expect( DarkRP.getChatCommand( cmd ) ).to.beNil()
                    done()
                end )
            end }
    }
}

return GCB_SUITE
