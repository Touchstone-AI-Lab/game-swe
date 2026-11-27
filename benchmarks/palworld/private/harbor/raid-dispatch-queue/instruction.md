# Harbor workspace

Complete this task in `/app/mod`; every required file must be written under that directory.

# Lease-based Raid Dispatch Queue

## Background and goals

The server dispatches queued raid requests to a limited number of worker slots. Dispatch is done through expiring leases: after a worker obtains a lease it must renew it, and work whose worker dropped or timed out must be reclaimed and requeued. Ordering, reclamation and recovery must all be fully deterministic.

Implement a plain-Lua dispatch queue, a dedicated-server service module, and a UE4SS entry script.

## Required files

```text
Info.json
scripts/main.lua
scripts/raiddispatch/queue.lua
scripts/services/raid_dispatch_service.lua
```

Plain module exports:

```lua
Queue.new(options)
Queue.load(data, options)

queue:enqueue(request_id, member_id, priority, now)
queue:lease(worker_id, now)
queue:renew(token, now)
queue:complete(token, outcome, now)
queue:release(token, now)
queue:expire(now)
queue:snapshot(now)
queue:save(now)
```

`options` contains at least `lease_seconds` (a positive number) and `max_attempts` (a positive integer).

## Core semantics

1. `now` is a strictly monotonic non-negative timestamp. An old timestamp must be rejected and must not change any state.
2. Ready work is ordered by priority descending, then by enqueue sequence number ascending. Ordering must not depend on Lua table iteration order.
3. `enqueue` deduplicates by `request_id`; a duplicate request returns the existing pending, leased or final result and does not change the original position.
4. `lease` grants at most one live lease per request, the same worker must not hold two leases at the same time, records `expires_at` according to `options.lease_seconds`, and returns a unique token.
5. `renew` may only extend a live lease held by the same worker; `complete` and `release` may each consume a token only once.
6. `expire(now)` puts expired requests back into the ready set at their original priority and sequence number and increments the attempt count; a request exceeding `max_attempts` enters a terminal state and is no longer dispatched.
7. `snapshot` returns a newly built deterministic table that exposes only aggregate counts and must not leak worker or member identity mappings. `save/load` fully round-trips the ready order, live leases, expiry deadlines, attempt counts and the token sequence.
8. The core module must run in a plain Lua environment without any UE4SS global objects.

## UE4SS integration

- The entry script must first wait for the world to be ready, then perform the dedicated-server check, and only then register any callbacks.
- The service module exposes `Join(controller)`, `Sweep(now)`, `Save()` and `Load(data)`.
- Join events come from a controller hook; leave events must be derived by periodically scanning the validity of tracked objects, rather than assuming a disconnect callback exists.
- The async scan only samples; all queue modifications must be executed back on the game thread.
- All hooks must be released when the service shuts down.

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

local pre, post = RegisterHook(
    "/Script/Engine.PlayerController:ServerAcknowledgePossession",
    function(Context)
        local Controller = Context:get()
        if Controller ~= nil and Controller:IsValid() then
            ExecuteInGameThread(function() service:Join(Controller) end)
        end
    end)

LoopAsync(1000, function()
    ExecuteInGameThread(function() service:Sweep(os.time()) end)
    return false
end)

UnregisterHook("/Script/Engine.PlayerController:ServerAcknowledgePossession", pre, post)

RegisterConsoleCommandGlobalHandler("rhenium_raid", function(Cmd, CommandParts, Ar)
    Ar:Log(service:Describe(CommandParts[1]))
    return true
end)
```

`LoopAsync` stops only when the callback returns `true`. `Object:IsValid()` is the only reliable way to determine whether a tracked controller still exists; once it becomes invalid it must be removed from the tracking table immediately.

`Info.json` must declare the package name and an install rule with `"Type": "Lua"`, `"IsServer": true`.

## Dedicated-server service contract

After `scripts/main.lua` confirms it is running in a dedicated server, it must publish the mounted service instance as the single global `RheniumService`, and must not pollute any other global name. The service instance supplies its own timestamps; callers do not pass `now`.

```lua
RheniumService:Join(controller)                          -- Register a validated controller
RheniumService:Enqueue(request_id, member_id, priority)  -- Forwards to queue:enqueue
RheniumService:Lease(worker_id)                          -- Forwards to queue:lease
RheniumService:Renew(token)
RheniumService:Complete(token, outcome)
RheniumService:Release(token)
RheniumService:Sweep()                                   -- Reclaim invalidated controllers and call queue:expire
RheniumService:Describe(request_id)                      -- Aggregate description string for use by the console command
RheniumService:Save()                                    -- Plain data table
RheniumService:Load(data)
```

## Return conventions

Every method that can fail returns a table: `{ ok = true, ... }` on success, `{ ok = false, code = "<stable error code>" }` on failure. Query methods return the data table directly. The fields that this task must implement are listed below.

```lua
queue:enqueue(request_id, member_id, priority, now)
-- { ok = true, request_id = id, sequence = n, duplicate = bool }
-- { ok = false, duplicate = bool, code = "invalid_request" | "stale_now" }
queue:lease(worker_id, now)
-- { ok = true, token = "<unique>", request_id = id, expires_at = n }
-- { ok = false, code = "empty" | "worker_busy" | "invalid_worker" | "stale_now" }
queue:renew(token, now) -- { ok = true, expires_at = n } | { ok = false, code = "unknown_token" | "expired" }
queue:complete(token, outcome, now) -- { ok = true, state = "completed", outcome = outcome } | { ok = false, code = ... }
queue:release(token, now) -- { ok = true, state = "ready" } | { ok = false, code = ... }
queue:expire(now) -- { ok = true, expired = n, exhausted = n }
queue:snapshot(now) -- { ready = n, leased = n, completed = n, exhausted = n, order = { request_id, ... } }
queue:save(now) -- Plain data table
```

`order` is the dispatch order of the current ready queue and contains only `request_id`. `snapshot` must not contain the keys `members`, `workers` or `leases`.

## Acceptance

- Priority and sequence-number ordering is fully deterministic.
- The same request is never leased by two workers at the same time.
- After a lease expires, the work is put back without losing its attempt history.
- Snapshots must not leak member or worker identities.
- The core module contains no UE4SS global objects.
- Headless dedicated-server tests verify service mounting, lease granting, expiry sweeps and reload.

Only documented UE4SS APIs and the official Palworld packaging format may be used.
