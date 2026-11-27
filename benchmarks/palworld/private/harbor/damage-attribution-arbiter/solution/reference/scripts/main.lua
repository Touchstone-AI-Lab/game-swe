local UEHelpers = require("UEHelpers")
local DamageArbiterService = require("services.damage_arbiter_service")

local service = nil
local hook_pre = nil
local hook_post = nil
local sweep_loop = nil

local function unwrap(context)
    if context == nil or type(context.get) ~= "function" then return nil end
    local object = context:get()
    if object ~= nil and object:IsValid() then return object end
    return nil
end

local function unmount()
    if hook_pre ~= nil or hook_post ~= nil then
        UnregisterHook("/Script/Engine.Actor:ReceiveAnyDamage", hook_pre, hook_post)
        hook_pre, hook_post = nil, nil
    end
    if sweep_loop ~= nil and type(sweep_loop.Cancel) == "function" then sweep_loop:Cancel() end
end

local function mount()
    if service ~= nil then return end
    service = DamageArbiterService.new()
    RheniumService = service
    hook_pre, hook_post = RegisterHook(
        "/Script/Engine.Actor:ReceiveAnyDamage",
        function(context)
            local actor = unwrap(context)
            if actor ~= nil then service:Track(actor) end
        end)
    NotifyOnNewObject("/Script/Engine.Pawn", function(object)
        if object ~= nil and object:IsValid() then service:Track(object) end
    end)
    sweep_loop = LoopAsync(1000, function()
        ExecuteInGameThread(function() service:Sweep() end)
        return false
    end)
    RegisterConsoleCommandGlobalHandler("rhenium_damage", function(_command, parts, ar)
        ExecuteInGameThread(function()
            local result = service:Observe({
                sequence = tonumber(parts[1]),
                attacker_id = parts[2],
                target_id = parts[3],
                amount = tonumber(parts[4]),
                tick = os.time(),
            })
            if ar ~= nil and type(ar.Log) == "function" then ar:Log(result.code or "accepted") end
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
