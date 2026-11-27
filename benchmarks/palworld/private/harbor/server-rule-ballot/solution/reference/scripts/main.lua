local UEHelpers = require("UEHelpers")
local RuleBallotService = require("services.rule_ballot_service")

local service = nil
local hook_pre = nil
local hook_post = nil

local function schedule(milliseconds, callback)
    ExecuteWithDelay(milliseconds, function()
        ExecuteInGameThread(callback)
    end)
end

local function attach(context)
    if context == nil or type(context.get) ~= "function" then return end
    local controller = context:get()
    if controller ~= nil and controller:IsValid() then service:Attach(controller) end
end

local function unmount()
    if hook_pre ~= nil or hook_post ~= nil then
        UnregisterHook(
            "/Script/Engine.PlayerController:ServerAcknowledgePossession",
            hook_pre,
            hook_post)
        hook_pre, hook_post = nil, nil
    end
end

local function mount()
    if service ~= nil then return end
    service = RuleBallotService.new({ schedule = schedule })
    RheniumService = service
    hook_pre, hook_post = RegisterHook(
        "/Script/Engine.PlayerController:ServerAcknowledgePossession",
        function(context) attach(context) end)
    RegisterConsoleCommandGlobalHandler("rhenium_ballot", function(_command, parts, ar)
        ExecuteInGameThread(function()
            local result = service:Cast(
                service:CurrentController(), parts[1], parts[2], tonumber(parts[3]))
            if ar ~= nil and type(ar.Log) == "function" then ar:Log(result.code or "accepted") end
            print("[rhenium_ballot] " .. tostring(result.code or result.revision))
        end)
        return true
    end)
end

local function start()
    local world = UEHelpers.GetWorld()
    if world == nil or not world:IsValid() then
        ExecuteWithDelay(1000, function() ExecuteInGameThread(start) end)
        return
    end
    if not UEHelpers.GetKismetSystemLibrary():IsDedicatedServer(world) then return end
    mount()
end

start()

return { Unmount = unmount }
