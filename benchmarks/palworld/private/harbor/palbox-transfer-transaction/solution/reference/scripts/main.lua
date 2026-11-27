local UEHelpers = require("UEHelpers")
local PalboxTransferService = require("services.palbox_transfer_service")

local service = nil
local hook_pre = nil
local hook_post = nil

local function unwrap(context)
    if context == nil or type(context.get) ~= "function" then return nil end
    local object = context:get()
    if object ~= nil and object:IsValid() then return object end
    return nil
end

local function unmount()
    if hook_pre ~= nil or hook_post ~= nil then
        UnregisterHook("/Script/Pal.PalMapObjectPalBox:OnUpdateContainer", hook_pre, hook_post)
        hook_pre, hook_post = nil, nil
    end
end

local function mount()
    if service ~= nil then return end
    service = PalboxTransferService.new()
    service:Recover()
    RheniumService = service

    NotifyOnNewObject("/Script/Pal.PalMapObjectPalBox", function(object)
        if object ~= nil and object:IsValid() then service:Track(object) end
    end)
    hook_pre, hook_post = RegisterHook(
        "/Script/Pal.PalMapObjectPalBox:OnUpdateContainer",
        function(context)
            local object = unwrap(context)
            if object ~= nil then service:Track(object) end
        end)

    RegisterConsoleCommandGlobalHandler("rhenium_palbox_transfer", function(_command, parts, ar)
        ExecuteInGameThread(function()
            local source = FindFirstOf("PalMapObjectPalBox")
            if source ~= nil and source:IsValid() then service:Track(source) end
            local result = service:Transfer({
                request_id = parts[1],
                source_id = parts[2],
                destination_id = parts[3],
                pal_id = parts[4],
                count = tonumber(parts[5]),
            })
            if ar ~= nil and type(ar.Log) == "function" then ar:Log(result.code or result.state) end
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
