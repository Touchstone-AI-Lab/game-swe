local suite = RegisterMod("GameCodeBench Exodus James Verifier", 1)
local game = Game()

local state = "idle"
local enteredAt = 0
local passed = 0
local failed = 0
local recorded = {}
local stopped = false

local jamesType = Isaac.GetPlayerTypeByName("James")

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

local function bookOfSecretsEffectCount()
    local level = game:GetLevel()
    local count = 0
    for _, stateFlag in ipairs({
        LevelStateFlag.STATE_COMPASS_EFFECT,
        LevelStateFlag.STATE_MAP_EFFECT,
        LevelStateFlag.STATE_BLUE_MAP_EFFECT,
    }) do
        if level:GetStateFlag(stateFlag) then count = count + 1 end
    end
    return count
end

local function finish()
    if stopped then return end
    stopped = true
    debug("[GCB_SUMMARY]", "passed=" .. passed .. " failed=" .. failed
        .. " total=" .. (passed + failed))
    enter("quit")
end

local function fatal(message)
    if stopped then return end
    debug("[GCB_FATAL]", tostring(message))
    finish()
end

function suite:onGameStarted(isContinued)
    local ok, err = pcall(function()
        if jamesType < 0 then error("missing James player type") end
        local player = Isaac.GetPlayer(0)
        debug("[GCB_RUNTIME]", "suite_started continued=" .. tostring(isContinued)
            .. " player_type=" .. player:GetPlayerType()
            .. " james_type=" .. jamesType)
        if player:GetPlayerType() ~= jamesType then
            enter("restart_as_james")
        else
            record("runtime_sentinel_james", true,
                "frame=" .. game:GetFrameCount() .. " player_type=" .. player:GetPlayerType())
            enter("james_stage_setup")
        end
    end)
    if not ok then fatal(err) end
end

local function runStep()
    local player = Isaac.GetPlayer(0)
    if state == "restart_as_james" and age() >= 3 then
        enter("restart_requested")
        Isaac.ExecuteCommand("restart " .. jamesType)
    elseif state == "james_stage_setup" and age() >= 5 then
        enter("james_stage_check")
        Isaac.ExecuteCommand("stage 2")
    elseif state == "james_stage_check" and age() >= 10 then
        local effects = bookOfSecretsEffectCount()
        record("james_book_of_secrets_positive",
            player:GetPlayerType() == jamesType and effects >= 1,
            "player_type=" .. player:GetPlayerType()
                .. " expected_type=" .. jamesType .. " effects=" .. effects)
        finish()
    elseif state == "quit" and age() >= 5 then
        state = "exiting"
        Isaac.ExecuteCommand("quit")
    end
end

function suite:onUpdate()
    if state == "idle" or state == "restart_requested" or state == "exiting" then return end
    local ok, err = pcall(runStep)
    if not ok then fatal(err) end
end

suite:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, suite.onGameStarted)
suite:AddCallback(ModCallbacks.MC_POST_UPDATE, suite.onUpdate)
