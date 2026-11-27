local UEHelpers = require("UEHelpers")
local GuildStorageService = require("services.guild_storage_service")

local hook_pre = nil
local hook_post = nil
local service = nil

local function controller_from_context(context)
    if context == nil or type(context.get) ~= "function" then return nil end
    local controller = context:get()
    if controller ~= nil and controller:IsValid() then return controller end
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
end

local function mount()
    if service ~= nil then return end
    service = GuildStorageService.new()
    RheniumService = service

    hook_pre, hook_post = RegisterHook(
        "/Script/Engine.PlayerController:ServerAcknowledgePossession",
        function(context, _pawn)
            local controller = controller_from_context(context)
            if controller ~= nil then service:Track(controller) end
        end)

    RegisterConsoleCommandGlobalHandler("rhenium_supply", function(_cmd, parts, ar)
        ExecuteInGameThread(function()
            local controller = FindFirstOf("PalPlayerController")
            local result = service:Claim(controller, parts[1], parts[2])
            if ar ~= nil and type(ar.Log) == "function" then ar:Log(result.code or "ok") end
        end)
        return true
    end)
end

local function mount_when_ready()
    local world = UEHelpers.GetWorld()
    if world == nil or not world:IsValid() then
        ExecuteWithDelay(1000, function()
            ExecuteInGameThread(mount_when_ready)
        end)
        return
    end
    if not UEHelpers.GetKismetSystemLibrary():IsDedicatedServer(world) then return end
    mount()
end

mount_when_ready()

return { Unmount = unmount }
