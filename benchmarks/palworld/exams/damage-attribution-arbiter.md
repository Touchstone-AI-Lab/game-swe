---
difficulty: hard
estimated_minutes: 390
domains:
  - combat
  - event-ordering
  - determinism
  - leases
---

# Deterministic Damage Attribution Arbiter

## Background and goals

UE4SS hooks fire only after the hooked function has finished executing, and async loops run outside the game thread. As a result, damage reports arrive out of order, arrive more than once, and even arrive after the target has already disappeared. The arbiter must give exactly the same attribution result for any arrival order, and use expiring claims to guarantee that each target has only one holder.

Implement a plain-Lua attribution arbiter, a dedicated-server service module, and a UE4SS entry script.

## Required files

```text
Info.json
scripts/main.lua
scripts/combat/arbiter.lua
scripts/services/damage_arbiter_service.lua
```

The plain module exports:

```lua
Arbiter.new(options)
Arbiter.load(data, options)

arbiter:observe(report)
arbiter:claim(attacker_id, target_id, tick)
arbiter:renew(token, tick)
arbiter:release(token, tick)
arbiter:resolve(target_id, tick)
arbiter:snapshot(tick)
arbiter:save(tick)
```

`report` contains `sequence`, `attacker_id`, `target_id`, a non-negative numeric `amount`, and `tick`. `options` contains at least `claim_seconds` (a positive number).

## Core semantics

1. `sequence` is a non-negative integer that is strictly increasing per target. A duplicate or smaller sequence must be ignored and marked as a duplicate in the return value.
2. Invalid reports (missing fields, negative amount, non-numeric tick) must be rejected before any state is modified.
3. Any arrival permutation of the same set of reports must produce exactly the same totals, so accumulation must follow sorted sequence rather than arrival order.
4. `claim` grants at most one live claim per target, records `expires_at` according to `options.claim_seconds`, and returns a unique token.
5. `renew` can only extend a live claim held by the same attacker; `release` can consume a token only once; a claim is implicitly released when it expires, with no explicit call needed.
6. `resolve(target_id, tick)` returns a deterministic holder, ordered by highest attributed total, then earliest first-contact sequence, then attacker ID in lexicographic order.
7. Later reports for an already-resolved target must be ignored, and the target must not be re-resolved with a different holder.
8. `snapshot` returns a new table containing only aggregate totals; `save/load` fully round-trips sequences, totals, live claims, expiry deadlines and resolution results.
9. The core module must run in an ordinary Lua environment without any UE4SS global objects.

## UE4SS integration

- The entry script must first wait for the world to be ready, then perform the dedicated-server check, and only then register any callback.
- The service module exposes `Observe(report)`, `Resolve(target_id)`, `Sweep(tick)`, `Save()` and `Load(data)`.
- Combatants are tracked via object-construction notifications; before reading properties, unwrap and check validity.
- Damage reports enter only through the console command; arguments are validated as strings before being converted.
- Sampling may be asynchronous; mutations must return to the game thread.

## UE4SS API usage contract

```lua
local UEHelpers = require("UEHelpers")

-- UE4SS starts Lua mods before the dedicated server owns a valid UWorld, so the
-- authority check and every registration must wait for the world to appear.
-- Palworld's shipping build does not export UGameplayStatics::IsDedicatedServer;
-- UKismetSystemLibrary::IsDedicatedServer is the reflected entry point.
local function MountWhenReady(mount)
    local world = UEHelpers.GetWorld()
    if world == nil or not world:IsValid() then
        ExecuteWithDelay(1000, function()
            ExecuteInGameThread(function() MountWhenReady(mount) end)
        end)
        return
    end
    if not UEHelpers.GetKismetSystemLibrary():IsDedicatedServer(world) then
        return
    end
    mount()
end

NotifyOnNewObject("/Script/Pal.PalPlayerCharacter", function(Character)
    if Character:IsValid() then
        ExecuteInGameThread(function() service:TrackCombatant(Character) end)
    end
end)

local pre, post = RegisterHook(
    "/Script/Engine.PlayerController:ServerAcknowledgePossession",
    function(Context)
        local Controller = Context:get()
        if Controller ~= nil and Controller:IsValid() then
            service:Attach(Controller)
        end
    end)
UnregisterHook("/Script/Engine.PlayerController:ServerAcknowledgePossession", pre, post)

RegisterConsoleCommandGlobalHandler("rhenium_damage", function(Cmd, CommandParts, Ar)
    ExecuteInGameThread(function()
        Ar:Log(service:Observe({
            sequence = tonumber(CommandParts[1]),
            attacker_id = CommandParts[2],
            target_id = CommandParts[3],
            amount = tonumber(CommandParts[4]),
            tick = tonumber(CommandParts[5]),
        }).code)
    end)
    return true
end)

LoopAsync(500, function()
    ExecuteInGameThread(function() service:Sweep(os.clock()) end)
    return false
end)
```

`NotifyOnNewObject` must use the full class path (for example `/Script/Pal.PalPlayerCharacter`); a bare class name is rejected by UE4SS. Hooks fire only after the hooked function returns, so before reading properties you must first unwrap the `RemoteUnrealParam` with `:get()`, then check it with `Object:IsValid()`.

`Info.json` must declare the package name and one install rule with `"Type": "Lua"` and `"IsServer": true`.

## Dedicated-server service contract

After confirming that it is running on a dedicated server, `scripts/main.lua` must publish the mounted service instance as the single global `RheniumService`, and must not pollute any other global name. The service instance supplies its own timestamps; callers do not pass `now`.

```lua
RheniumService:Attach(controller)         -- Register a validated controller
RheniumService:TrackCombatant(object)     -- Register a validated combatant
RheniumService:Observe(report)            -- Forwards to arbiter:observe; returns the core module's result table
RheniumService:Claim(attacker_id, target_id)
RheniumService:Resolve(target_id)         -- Forwards to arbiter:resolve
RheniumService:Sweep()                    -- Drops invalid objects and releases expired claims
RheniumService:Save()                     -- Plain data table
RheniumService:Load(data)
```

## Return conventions

Every method that can fail returns a table: `{ ok = true, ... }` on success, `{ ok = false, code = "<stable error code>" }` on failure. Query methods return data tables directly. The fields this task must implement are listed below.

```lua
arbiter:observe(report)
-- { ok = true, applied = bool, duplicate = bool }
-- { ok = false, code = "invalid_report" | "resolved" }
arbiter:claim(attacker_id, target_id, tick) -- { ok = true, token = "<unique>", expires_at = n } | { ok = false, code = "claimed" | "resolved" | "invalid_claim" }
arbiter:renew(token, tick) -- { ok = true, expires_at = n } | { ok = false, code = "unknown_token" | "expired" }
arbiter:release(token, tick) -- { ok = true } | { ok = false, code = "unknown_token" }
arbiter:resolve(target_id, tick) -- { ok = true, attacker_id = "...", total = n, final = bool } | { ok = false, code = "unknown_target" }
arbiter:snapshot(tick) -- { targets = { { target_id = "...", total = n, resolved = bool }, ... } in lexicographic order of target_id }
arbiter:save(tick) -- Plain data table
```

`snapshot` must not contain the `reports`, `claims` or `tokens` keys.

## Acceptance

- Any arrival permutation of the same batch of reports produces exactly the same totals.
- Duplicates and replays never inflate any total.
- The same target is never claimed by two attackers at once.
- Resolution order is deterministic, and a resolved target is final.
- The core module contains no UE4SS global objects.
- Headless dedicated-server tests verify service mounting, report intake, resolution and reload.

Only documented UE4SS APIs and the official Palworld packaging format may be used.
