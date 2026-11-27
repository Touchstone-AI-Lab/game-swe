local UEHelpers = require("UEHelpers")
local RaidDispatchService = require("services.raid_dispatch_service")

local service = nil
local hook_pre = nil
local hook_post = nil
local sweep_loop = nil

local function controller(context)
    if context == nil or type(context.get) ~= "function" then return nil end
    local value = context:get()
    if value ~= nil and value:IsValid() then return value end
    return nil
end

local function unmount()
    if hook_pre ~= nil or hook_post ~= nil then
        UnregisterHook(
            "/Script/Engine.PlayerController:ServerAcknowledgePossession",
            hook_pre,
            hook_post)
        hook_pre, hook_post = nil, nil
    end
    if sweep_loop ~= nil and type(sweep_loop.Cancel) == "function" then sweep_loop:Cancel() end
end

local function mount()
    if service ~= nil then return end
    service = RaidDispatchService.new()
    RheniumService = service
    hook_pre, hook_post = RegisterHook(
        "/Script/Engine.PlayerController:ServerAcknowledgePossession",
        function(context)
            local value = controller(context)
            if value ~= nil then service:Track(value) end
        end)
    sweep_loop = LoopAsync(1000, function()
        ExecuteInGameThread(function() service:Sweep() end)
        return false
    end)
    RegisterConsoleCommandGlobalHandler("rhenium_raid_queue", function(_command, parts, ar)
        ExecuteInGameThread(function()
            local result = service:Enqueue(parts[1], parts[2], tonumber(parts[3]))
            if ar ~= nil and type(ar.Log) == "function" then ar:Log(result.code or "queued") end
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
