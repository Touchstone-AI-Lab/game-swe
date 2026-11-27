# Harbor workspace

Complete this task in `/app/mod`; every required file must be written under that directory.

# World Epoch Fencing and Timer Redelivery

## Required files

```text
Info.json
scripts/main.lua
scripts/epoch/core.lua
scripts/services/epoch_service.lua
```

## Background and goals

After a world switch or a service hot reload, old asynchronous callbacks may still enter the game thread; new and old acknowledgements from retries of the same task may also interleave. Implement double fencing: the world epoch rejects the old world, and the task generation rejects old attempts within the same world. Do not rely on successfully cancelling every callback that has already been enqueued.

## Plain-Lua API and inputs

```lua
Core.new()
Core.load(data)
core:mount(epoch, now)
core:schedule({id="reward1",payload="raid_reward",due=10})
core:poll(epoch, now)
core:ack({id="reward1",epoch=1,generation=1}, success)
core:cancel(id)
core:snapshot()
core:save()
```

epoch, now, due and generation are non-negative integers; for a valid mount the epoch must be greater than the current value. Initial values are epoch=0, now=0; the clock is logical time injected by the trusted server, not client time or the system wall clock. All now values are monotonically non-decreasing. payload is only a server whitelist key.

## Core semantics

1. mount, after full validation, checks in order that epoch strictly increases and that now does not go backwards; on success it returns all leased tasks to pending, preserving generation, due, done/canceled and the global time. Terminal states cannot be revived.
2. schedule before any mount is `not_mounted`. Validation of all fields precedes deduplication; the same ID with the same due/payload returns the original state with duplicate=true, a different payload is `request_conflict`. A due in the past is valid and can be dispatched on the next round.
3. poll first fully validates, then rejects an epoch that is not equal to the current value or is 0 (`stale_epoch`), then checks now (`stale_now`). A rejection must not advance time or modify tasks.
4. A successful poll changes all pending tasks with due<=now to leased, in ascending due order, then ascending ID byte order; each one's generation increments by one, and it returns `{ok=true,deliveries={{id,payload,epoch,generation},...}}`. A repeated poll does not redispatch leased tasks.
5. ack's success must be a boolean. Validation first, then epoch, then ID/leased state/generation; a mismatch is `stale_token`. success=true moves to done; false returns to pending, and the next poll produces a higher generation. The token's payload does not take part in authentication.
6. cancel of an unknown ID is `unknown_task`, of a done task is `already_done`; pending/leased/canceled all become canceled and succeed. After cancellation an old ack must not revive the task; IDs are never reused.
7. save/load preserve all state; load itself does not change the epoch. After restoring, the operator must mount with a higher epoch that is allocated and persisted externally before accepting callbacks. Never assume that a rolled-back save can produce a globally unique epoch by itself.
8. snapshot returns only `{epoch,now,pending,leased,done,canceled}`. Return values and saves share no aliases; invalid input is `invalid_request`, and rejections have no side effects.

## Public example

mount(1,0) → schedule(due=5) → poll(1,5) yields g1 → ack(g1,false) → poll(1,5) yields g2. A late ack(g1,true) must fail. After save and restore, mount(2,5); the old epoch1/g2 must also fail, while the redispatch returns epoch2/g3.

## Dedicated-server service contract

`Mount(epoch,now)`, `Schedule(request)`, `Poll(epoch,now)`, `Ack(token,success)` and `Cancel(id)` map to the core. The core only emits deliveries; the caller is responsible for the external business effects; at-least-once dispatch does not mean exactly-once rewards. Tests do not assume any unspecified game reward API. In real UE4SS, expired callbacks should be naturally rejected by the core because their callers hold an old epoch.

## Acceptance and distinguishing wrong implementations

- A failed retry within the same world produces a new generation and the old acknowledgement is rejected; double isolation after a world switch.
- An old epoch carrying a future now must not poison the current clock.
- Cancellation interleaved with a late success acknowledgement, cancellation after completion, payload conflicts, IDs not reused.
- Restoring leased tasks, terminal states not revived, ordering of equal due values, and the exact due instant.
- Implementations that compare only the epoch, compare only the generation, have load automatically reset counters, or commit callbacks unconditionally must fail.

## Shared data and recovery conventions

The core module is named `Core` (it returns a table containing new/load); instance methods are called with a colon. Business IDs are 1–64-byte ASCII `[A-Za-z0-9_-]+` and are ordered by raw bytes. Input integers range over 0–1,000,000 (except fields explicitly stated to be positive); internal accumulators, sequence numbers and generations are not clipped by this input bound. All data are acyclic plain Lua tables with no userdata/metatable. Extra input fields are ignored; inputs must not be mutated. Every command that can fail returns `{ok=false,code="<stable error code>"}`; success fields are as listed in each task. Fields not listed do not take part in judging.

`save()` returns a freshly built serialisable table containing `version=1`; the concrete internal layout is up to the implementation. `load` accepts its own valid save output; an unsupported version must raise an error containing `invalid_state`. Repairing arbitrarily corrupted saves is not required. load, save, queries and command results are all deeply isolated from aliasing, and a rejected operation does not change state. Tests assert only the public contract and do not inspect save field names (except version).

## UE4SS API usage contract

Reuse this project's existing UE4SS integration boundary. Do not guess at any other Palworld SDK function:

```lua
local UEHelpers = require("UEHelpers")
local function start()
    ExecuteInGameThread(function()
        local world = UEHelpers.GetWorld()
        if world == nil or not world:IsValid() then
            ExecuteWithDelay(1000, start)
            return
        end
        if not UEHelpers.GetKismetSystemLibrary():IsDedicatedServer(world) then return end
        -- Mount here; do not register callbacks while the world is not ready yet.
    end)
end
start()
-- Every registered handle pair must be released as a pair in Unmount.
local pre, post = RegisterHook(
    "/Script/Engine.PlayerController:ServerAcknowledgePossession",
    function(Context)
        ExecuteInGameThread(function()
            local controller = Context:get()
            if controller ~= nil and controller:IsValid() then
                -- Use the object only within this callback; do not cache raw pointers across ticks.
            end
        end)
    end)
UnregisterHook("/Script/Engine.PlayerController:ServerAcknowledgePossession", pre, post)
```

The last part above only illustrates the signatures; registration must actually take place inside the mount branch. The main script may publish only one global, `RheniumService`. The service provides `Reset(options)`, `Save()`, `Load(data)`, `Snapshot()`, `Unmount()` and the task-specific methods. Reset rebuilds an empty core; only checkpoint accepts configuration. Load returns `{ok=true}` and raises an error for an unsupported version; Snapshot forwards the core snapshot. Service methods are trusted server-internal call interfaces already on the game thread and return the core result directly; asynchronous callers must first ExecuteInGameThread.

The entry point registers exactly one read-only console command, `rhenium_<module directory name>`, which prints a fixed readiness text, accepts no business changes, and does not guess the caller's identity from FindFirstOf. Unmount is idempotent, cleans up hook handles, and turns every existing hook/command callback into a no-op without side effects; calling a console-unregistration API that is not given here is not required. The entry point scripts/main.lua must not end early with a top-level return, because the evaluator appends assertions to the end of a temporary copy; shutdown goes through RheniumService:Unmount(). Info.json contains a non-empty PackageName, a string Version, and an install rule with Type=Lua and IsServer=true.

## Evaluation boundary

As with the existing tasks, a Rhenium full score requires the static, plain-Lua behaviour and real Windows UE4SS dedicated-server assertions all to run; a missing engine must be an incomplete failure. Harbor runs only Lua 5.4 and simulated UE4SS, which is not real-engine evidence. Hidden tests cover the public rules above and their combinations; writing large amounts of useless code is not a source of difficulty. The duration is the author's estimate; model pass rates have not been measured.
