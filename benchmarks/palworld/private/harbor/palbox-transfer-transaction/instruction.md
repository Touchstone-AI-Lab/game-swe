# Harbor workspace

Complete this task in `/app/mod`; every required file must be written under that directory.

# Crash-safe Palbox Transfer Transaction

## Background and goals

The server needs to atomically transfer Pal entries between two server-side containers. Insufficient capacity, partial adapter failures, duplicate requests and server restarts may occur between any two steps. Whenever a crash happens, the recovery procedure must bring both containers back to a consistent state.

Implement a plain-Lua transfer transaction, a dedicated-server service module, and a UE4SS entry script.

## Required files

```text
Info.json
scripts/main.lua
scripts/palboxtransfer/transaction.lua
scripts/services/palbox_transfer_service.lua
```

Plain module exports:

```lua
Transaction.new(adapter, persisted)
Transaction.load(adapter, data)

transaction:transfer(request)
transaction:recover()
transaction:status(request_id)
transaction:save()
```

`request` contains `request_id`, `source_id`, `destination_id`, `pal_id` and a positive integer `count`.

The injected adapter provides:

```lua
adapter.snapshot(container_id)
adapter.capacity(container_id, pal_id)
adapter.remove(container_id, pal_id, count)
adapter.add(container_id, entries)
adapter.restore(container_id, snapshot)
```

## Core semantics

1. Identical containers, invalid identifiers and a `count` that is not a positive integer must be rejected before calling any adapter.
2. The order is fixed: pre-check source quantity and destination capacity → persist the `prepared` intent → remove from source → add to destination → mark `committed`.
3. When `add` fails, first restore the destination snapshot, then restore the source snapshot; if the compensation itself fails, a recoverable error must be recorded rather than silently swallowed.
4. Deduplicate by `request_id`, consistently after success, after failure and after reload; a request that is already `committed` must not call any adapter method again.
5. Source entries are selected in ascending slot order, and `pal_id`, quantity, level and gender metadata are preserved as-is.
6. `recover()` completes or safely compensates every persisted stage, and repeated calls are idempotent.
7. The core module must not contain any UE4SS global object and must run in a plain Lua environment.

## UE4SS integration

- The entry script must first wait for the world to be ready, then perform the dedicated-server check, and only then register any callbacks.
- The service module exposes `Track(object, stable_id)`, `Transfer(request)`, `Recover()`, `Save()` and `Load(data)`.
- Container objects are resolved and tracked by the server side itself; the client may provide only identifiers, not entry data.
- Expose only one console command entry point; all arguments are validated as strings before conversion.
- All state modifications must be executed back on the game thread.

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

NotifyOnNewObject("/Script/Pal.PalPlayerController", function(Controller)
    if Controller:IsValid() then
        service:Track(Controller, tostring(Controller:GetFullName()))
    end
end)

local pre, post = RegisterHook(
    "/Script/Engine.PlayerController:ServerAcknowledgePossession",
    function(Context) service:Attach(Context:get()) end)
UnregisterHook("/Script/Engine.PlayerController:ServerAcknowledgePossession", pre, post)

RegisterConsoleCommandGlobalHandler("rhenium_palbox", function(Cmd, CommandParts, Ar)
    ExecuteInGameThread(function()
        Ar:Log(service:Transfer({
            request_id = CommandParts[1],
            source_id = CommandParts[2],
            destination_id = CommandParts[3],
            pal_id = CommandParts[4],
            count = tonumber(CommandParts[5]),
        }).code)
    end)
    return true
end)
```

`NotifyOnNewObject` must use the full class path (for example `/Script/Pal.PalPlayerController`); a bare class name is rejected by UE4SS. It also fires for subclasses, and the callback receives only the constructed object. `ExecuteAsync` and `ExecuteWithDelay` may be used only for sampling, not for state changes.

`Info.json` must declare the package name and an install rule with `"Type": "Lua"`, `"IsServer": true`.

## Dedicated-server service contract

After `scripts/main.lua` confirms it is running in a dedicated server, it must publish the mounted service instance as the single global `RheniumService`, and must not pollute any other global name. The service instance supplies its own timestamps; callers do not pass `now`.

```lua
RheniumService:Track(object, stable_id)  -- Register a validated container object under a stable identifier
RheniumService:Attach(controller)        -- Register a validated controller
RheniumService:Transfer(request)         -- Forwards to transaction:transfer; returns the core module's result table
RheniumService:Recover()                 -- Forwards to transaction:recover
RheniumService:Save()                    -- Plain data table
RheniumService:Load(data)
```

## Return conventions

Every method that can fail returns a table: `{ ok = true, ... }` on success, `{ ok = false, code = "<stable error code>" }` on failure. Query methods return the data table directly. The fields that this task must implement are listed below.

```lua
transaction:transfer(request)
-- { ok = true, state = "committed", duplicate = bool }
-- { ok = false, duplicate = bool, state = "rejected" | "compensated" | "unrecoverable",
--   code = "invalid_request" | "same_container" | "insufficient_source" | "insufficient_capacity" | "adapter_error" }
transaction:recover() -- { ok = true, recovered = n, compensated = n }
transaction:status(request_id)
-- { state = "unknown" | "prepared" | "committed" | "compensated" | "unrecoverable", code = string | nil }
transaction:save() -- Plain data table
```

`adapter.remove` and `adapter.add` return an `entries` table to indicate success, and `nil, code` to indicate failure. `adapter.capacity` returns the quantity that can be accommodated. `adapter.snapshot` returns an opaque snapshot value, and `adapter.restore` accepts that same value.

## Acceptance

- A capacity failure modifies neither container.
- Partial failures are compensated in reverse order.
- The recovery procedure completes or safely compensates every persisted stage.
- Retries after success, after failure and after restart are all idempotent.
- The core module contains no UE4SS global objects.
- Headless dedicated-server tests verify service mounting, real transfers, rollback and reload.

Only documented UE4SS APIs and the official Palworld packaging format may be used.
