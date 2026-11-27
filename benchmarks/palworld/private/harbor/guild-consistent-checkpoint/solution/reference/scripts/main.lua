local UEHelpers = require("UEHelpers")
local Service = require("services.checkpoint_service")
local service
local active = true
local hook_pre, hook_post
local hook_path = "/Script/Engine.PlayerController:ServerAcknowledgePossession"
local function unmount()
    if not active then return end
    active = false
    if hook_pre ~= nil then
        UnregisterHook(hook_path, hook_pre, hook_post)
        hook_pre, hook_post = nil, nil
    end
end
local function start()
    ExecuteInGameThread(function()
        if not active or service ~= nil then return end
        local world = UEHelpers.GetWorld()
        if world == nil or not world:IsValid() then
            ExecuteWithDelay(1000, start)
            return
        end
        if not UEHelpers.GetKismetSystemLibrary():IsDedicatedServer(world) then return end
        service = Service.new()
        service.Unmount = unmount
        RheniumService = service
        hook_pre, hook_post = RegisterHook(hook_path, function(context)
            ExecuteInGameThread(function()
                if not active then return end
                local controller = context:get()
                if controller == nil or not controller:IsValid() then return end
            end)
        end)
        RegisterConsoleCommandGlobalHandler("rhenium_checkpoint", function()
            ExecuteInGameThread(function()
                if active then print("rhenium_checkpoint ready") end
            end)
            return true
        end)
    end)
end
start()
