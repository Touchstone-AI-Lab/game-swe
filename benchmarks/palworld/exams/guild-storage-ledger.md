---
difficulty: hard
estimated_minutes: 360
domains:
  - quotas
  - idempotency
  - inventory
  - persistence
---

# Server-authoritative Guild Storage Ledger

## Background and goals

The dedicated server periodically issues preconfigured supply bundles to guild members. Quotas, bundle contents, member active status and cycle transitions are all decided by the server side; the client may submit only a request identifier and a bundle identifier. Retries, out-of-order delivery, quota exhaustion, delivery failures and server restarts must never cause the ledger to issue twice or leak quota.

Implement a plain-Lua ledger module, a dedicated-server service module, and an entry script that wires both into UE4SS.

## Required files

```text
Info.json
scripts/main.lua
scripts/guildledger/ledger.lua
scripts/services/guild_storage_service.lua
```

Plain module exports:

```lua
Ledger.new(options)
Ledger.load(data, options)

ledger:begin_cycle(cycle)
ledger:set_member(member_id, active)
ledger:claim(member_id, request_id, bundle_id, cycle)
ledger:commit(token)
ledger:rollback(token)
ledger:snapshot()
ledger:save()
```

`options` contains at least `bundles` (a mapping from bundle identifier to `{ [item_id] = count }`) and `quota` (number of claims allowed per member per cycle).

## Core semantics

1. `begin_cycle` accepts only strictly increasing non-negative integers. An old cycle must be rejected, and must not reset quotas or change any state.
2. `claim` must deduplicate by `member_id/request_id` before touching the quota. A retry returns the original pending or final result and does not create a second reservation.
3. Bundle contents may be resolved only from `options.bundles`. Unknown bundles, inactive members, insufficient quota and invalid quantities are all rejected with a stable error code.
4. A successful `claim` generates a unique reservation token and immediately reduces the available quota. `commit(token)` may consume it only once, and `rollback(token)` may release it only once; repeated calls on an already finalized token must have no side effects.
5. `snapshot()` returns a new table each time, in deterministic order, and must not expose any private structure other than the token sequence's internal counter. Caller modifications to the snapshot must not affect the ledger.
6. `save()` returns a serializable table; `Ledger.load(data, options)` fully round-trips cycle, quotas, reservations, request results and the token sequence, and does not replay already committed requests.
7. The core module must load and run in a plain Lua environment without any UE4SS global objects.

## UE4SS integration

- The service module is mounted only in the dedicated server process; the entry script must first wait for the world to be ready, then perform the dedicated-server check, and only then register any callbacks.
- The service module exposes `Claim(controller, request_id, bundle_id)`, `Save()` and `Load(data)`.
- Item delivery goes through an injected inventory adapter: `commit` only after every entry is confirmed successful; if any entry fails, the already delivered part must first be removed and then `rollback`.
- Player identity is derived by the server side from the controller; a member identifier passed in by the client is never accepted.
- State persistence goes through an injected storage adapter; the service module itself must not hard-code any absolute path.
- All long-lived callbacks must be registered and released in pairs.

## UE4SS API usage contract

The following signatures are taken from the UE4SS Lua API documentation and the official Palworld mod packaging documentation and may be used directly:

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
    function(Context, Pawn)
        local Controller = Context:get()
        if Controller ~= nil and Controller:IsValid() then
            service:Track(Controller)
        end
    end)

UnregisterHook("/Script/Engine.PlayerController:ServerAcknowledgePossession", pre, post)

RegisterConsoleCommandGlobalHandler("rhenium_supply", function(Cmd, CommandParts, Ar)
    ExecuteInGameThread(function()
        local member_id = service:MemberIdOf(service:CurrentController())
        local result = service:Claim(member_id, CommandParts[1], CommandParts[2])
        Ar:Log(result.code)
    end)
    return true
end)
```

A hook fires only after the hooked function has finished executing, and callback order cannot be assumed. Parameters may be `RemoteUnrealParam` and must be `:get()` before use. `FindFirstOf("PalPlayerController")` and `StaticFindObject(path)` are used to resolve engine objects; do not cache raw pointers across ticks.

`Info.json` must declare the package name and an install rule with `"Type": "Lua"`, `"IsServer": true`; `scripts/main.lua` is the UE4SS entry file.

## Dedicated-server service contract

After `scripts/main.lua` confirms it is running in a dedicated server, it must publish the mounted service instance as the single global `RheniumService`, and must not pollute any other global name. The service instance supplies its own timestamps; callers do not pass `now`.

```lua
RheniumService:Track(controller)                       -- Register a validated controller
RheniumService:MemberIdOf(controller)                  -- Server-derived member identifier; returns nil for an unknown controller
RheniumService:CurrentController()                     -- Issuer of the current console command; returns nil if it cannot be determined
RheniumService:BeginCycle(cycle)                       -- Forwards to ledger:begin_cycle
RheniumService:Claim(member_id, request_id, bundle_id) -- Reserve, deliver, commit or roll back; returns the core module's result table
RheniumService:Save()                                  -- Plain data table
RheniumService:Load(data)
```

## Return conventions

Every method that can fail returns a table: `{ ok = true, ... }` on success, `{ ok = false, code = "<stable error code>" }` on failure. Query methods return the data table directly. The fields that this task must implement are listed below.

```lua
ledger:begin_cycle(cycle) -- { ok = true, cycle = n } | { ok = false, code = "invalid_cycle" | "stale_cycle" }
ledger:set_member(id, active) -- { ok = true, member_id = id, active = bool } | { ok = false, code = "invalid_member" }
ledger:claim(member_id, request_id, bundle_id, cycle)
-- { ok = true, token = "<unique>", bundle_id = id, items = { [item_id] = count }, duplicate = bool }
-- { ok = false, duplicate = bool, code = "invalid_request" | "unknown_bundle" | "inactive_member" | "quota_exhausted" | "stale_cycle" }
ledger:commit(token) -- { ok = true, state = "committed" } | { ok = false, code = "unknown_token" | "token_consumed" }
ledger:rollback(token) -- { ok = true, state = "rolled_back" } | { ok = false, code = "unknown_token" | "token_consumed" }
ledger:snapshot() -- { cycle = n, pending = n, committed = n, rolled_back = n,
                  --   members = { { member_id = "...", remaining = n }, ... } in lexicographic order of member_id }
ledger:save() -- Plain data table
```

A retry of the same `member_id/request_id` returns the **original result** with `duplicate` set to `true`. `snapshot()` must not contain the keys `requests`, `reservations` or `tokens`.

## Acceptance

- Retries do not consume quota twice or duplicate items.
- A rollback restores capacity exactly once.
- Cycle transitions are monotonic and persist across restarts.
- Client-forged bundle contents and member identities have no effect.
- The core module loads and runs even without UE4SS global objects.
- Headless dedicated-server tests verify service mounting, delivery, rollback and save/load.

Only documented UE4SS APIs and the official Palworld packaging format may be used; echoing an individual's request details to other clients is forbidden.
