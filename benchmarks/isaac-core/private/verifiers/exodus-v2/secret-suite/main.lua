local suite = RegisterMod("GameCodeBench Exodus Secret Room Verifier", 1)
local game = Game()

local state = "idle"
local enteredAt = 0
local passed = 0
local failed = 0
local recorded = {}
local stopped = false

local ids = {
    apocryphon = Isaac.GetItemIdByName("The Apocryphon"),
    blueMoon = Isaac.GetTrinketIdByName("Blue Moon"),
}

local function debug(prefix, message)
    Isaac.DebugString(prefix .. " " .. message)
end

local function enter(nextState)
    state = nextState
    enteredAt = game:GetFrameCount()
end

local function age()
    return game:GetFrameCount() - enteredAt
end

local function detailNumber(value)
    if value == nil then return "nil" end
    return tostring(value)
end

local function record(name, ok, detail)
    if recorded[name] then return end
    recorded[name] = true
    if ok then
        passed = passed + 1
        debug("[GCB_CASE]", "PASS " .. name .. " " .. detail)
    else
        failed = failed + 1
        debug("[GCB_CASE]", "FAIL " .. name .. " " .. detail)
    end
end

local function removeCollectible(player, itemId)
    for _ = 1, 8 do
        if not player:HasCollectible(itemId) then break end
        player:RemoveCollectible(itemId)
    end
end

local function removeTrinket(player, trinketId)
    for _ = 1, 4 do
        if not player:HasTrinket(trinketId) then break end
        player:TryRemoveTrinket(trinketId)
    end
end

local function statSnapshot(player)
    return {
        damage = player.Damage,
        delay = player.MaxFireDelay,
        speed = player.MoveSpeed,
        shot = player.ShotSpeed,
        luck = player.Luck,
        height = player.TearHeight,
    }
end

local function statsDiffer(left, right)
    return math.abs(left.damage - right.damage) > 0.01
        or math.abs(left.delay - right.delay) > 0.01
        or math.abs(left.speed - right.speed) > 0.01
        or math.abs(left.shot - right.shot) > 0.01
        or math.abs(left.luck - right.luck) > 0.01
        or math.abs(left.height - right.height) > 0.01
end

local function statDetail(stats)
    return "damage=" .. detailNumber(stats.damage)
        .. " delay=" .. detailNumber(stats.delay)
        .. " speed=" .. detailNumber(stats.speed)
        .. " shot=" .. detailNumber(stats.shot)
        .. " luck=" .. detailNumber(stats.luck)
        .. " height=" .. detailNumber(stats.height)
end

local function finish()
    if stopped then return end
    stopped = true
    debug("[GCB_SUMMARY]", "passed=" .. tostring(passed)
        .. " failed=" .. tostring(failed)
        .. " total=" .. tostring(passed + failed))
    enter("quit")
end

local function fatal(message)
    if stopped then return end
    debug("[GCB_FATAL]", tostring(message))
    finish()
end

local function recordRoomCases()
    local player = Isaac.GetPlayer(0)
    local room = game:GetRoom()
    local walls = 0
    local doors = 0
    for index = 0, room:GetGridSize() - 1 do
        local grid = room:GetGridEntity(index)
        if grid then
            if grid:GetType() == GridEntityType.GRID_WALL then
                walls = walls + 1
            elseif grid:GetType() == GridEntityType.GRID_DOOR then
                doors = doors + 1
            end
        end
    end
    record("blue_moon", room:GetType() == RoomType.ROOM_SECRET and walls >= 10 and doors >= 1,
        "room_type=" .. room:GetType() .. " walls=" .. walls .. " doors=" .. doors)

    local baseline = player:GetData().gcbApocryphonBaseline
    local after = statSnapshot(player)
    record("apocryphon_stats", baseline ~= nil and statsDiffer(baseline, after),
        "before={" .. (baseline and statDetail(baseline) or "nil")
            .. "} after={" .. statDetail(after) .. "}")
end

function suite:onGameStarted(isContinued)
    local ok, err = pcall(function()
        if ids.apocryphon <= 0 or ids.blueMoon <= 0 then
            error("missing Exodus item id")
        end
        local player = Isaac.GetPlayer(0)
        record("runtime_sentinel_secret", true,
            "frame=" .. game:GetFrameCount() .. " player_type=" .. player:GetPlayerType())
        removeCollectible(player, ids.apocryphon)
        removeTrinket(player, ids.blueMoon)
        player:AddCollectible(ids.apocryphon, 0, false)
        player:GetData().gcbApocryphonBaseline = statSnapshot(player)
        player:AddTrinket(ids.blueMoon, true)
        debug("[GCB_RUNTIME]", "suite_started continued=" .. tostring(isContinued))
        enter("transition_setup")
    end)
    if not ok then fatal(err) end
end

function suite:onNewRoom()
    if state == "blue_transition" then
        enter("secret_settle")
    end
end

local function runStep()
    if state == "transition_setup" and age() >= 5 then
        enter("blue_transition")
        Isaac.ExecuteCommand("goto s.secret.1")
    elseif state == "secret_settle" and game:GetRoom():GetFrameCount() >= 5 then
        recordRoomCases()
        finish()
    elseif state == "quit" and age() >= 5 then
        state = "exiting"
        Isaac.ExecuteCommand("quit")
    end
end

function suite:onUpdate()
    if state == "idle" or state == "exiting" then return end
    local ok, err = pcall(runStep)
    if not ok then fatal(err) end
end

suite:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, suite.onGameStarted)
suite:AddCallback(ModCallbacks.MC_POST_NEW_ROOM, suite.onNewRoom)
suite:AddCallback(ModCallbacks.MC_POST_UPDATE, suite.onUpdate)
