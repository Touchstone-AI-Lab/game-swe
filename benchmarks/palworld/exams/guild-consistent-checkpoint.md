---
difficulty: hard
estimated_minutes: 720
domains:
  - causality
  - fixed-points
  - snapshots
  - recovery
---

# Greatest Causally Consistent Guild Checkpoint

## Required files

```text
Info.json
scripts/main.lua
scripts/checkpoint/core.lua
scripts/services/checkpoint_service.lua
```

## Background and goals

Each of a guild's bases produces its own ordered log; a cross-base receive record depends on a send record of another base. Logs are uploaded out of order and may contain holes. Given a backup upper bound, find the maximal causally consistent prefix vector: it must neither save a half transaction of "materials received but never sent", nor simply return all zeros to be safe.

## Plain-Lua API and inputs

```lua
Core.new({"a","b","c"})
Core.load(data)
core:append({shard="a",seq=1,deps={b=2}})
core:cut({a=10,b=10,c=10})
core:snapshot()
core:save()
```

new accepts a hole-free array of 1–16 unique shard IDs. seq is a positive integer; deps is a mapping from registered shards to non-negative sequence numbers; a missing entry is equivalent to no requirement, but an explicit 0 differs from a missing entry when comparing duplicate payloads. References across shards to events not yet received are allowed, as are cross-shard cyclic dependencies; a same-shard dependency must be strictly less than the event's own seq. limits must contain exactly all shards.

## Core semantics

1. append allows out-of-order arrival and deduplicates by `(shard,seq)`; an identical deps key-value mapping returns `{ok=true,duplicate=true}`, a different mapping is `event_conflict`; neither overwrites the old event.
2. cut selects, for each shard, a complete prefix `0..c[s]` starting from 1; it cannot cross a log hole, and `c[s] <= limits[s]`.
3. For every selected event e, each of its dependencies `(t,k)` must satisfy `c[t] >= k`; the entire selected prefix must be checked, not just the last event.
4. Return the unique componentwise-maximal valid vector: for every other valid vector d, `c[s] >= d[s]`. It is not an arbitrary solution with the maximal sum, and dropping all cycles for convenience is not allowed.
5. You may start from each shard's contiguous-prefix upper bound and repeatedly shrink until all dependencies are satisfied; once a shrink happens it must propagate to indirect dependencies, until a fixed point. Even if cross-shard dependencies form a cycle, the cycle may be kept as a whole when all required events exist and are within the bounds.
6. cut returns `{ok=true,vector={shard=n,...}}`; it is a pure query and does not change the log; filling holes or raising the bounds later may yield a larger result. Do not cache past shrinks as permanent discards.
7. snapshot returns `{shards={{id=...,count=number of distinct events received},...}}`, in ascending ID order; count is not the contiguous prefix length. save/load preserve holes and all deps.
8. An invalid event or invalid limits return `invalid_request`, with no side effects. An invalid configuration for new throws `invalid_options`. Tests use at most 16 shards and 256 events per shard; there is no need to enumerate all vectors.

## Public example

a1 depends on b2, b1 has no dependencies, b2 depends on c1, and c1 is missing; with limits={a=1,b=2,c=1} the result must be {a=0,b=1,c=0}, not one with a1 left over after a single round of shrinking. After c1 is added, the same query returns {a=1,b=2,c=1}.

## Dedicated-server service contract

`Reset(shards)` establishes the configuration; `Append(event)` and `Cut(limits)` map to the core. Reset's default configuration is `{"a","b","c"}`. These are trusted backup-coordinator interfaces; unauthenticated clients must not be allowed to forge log dependencies. This task computes a backup selection protocol; it does not operate on, or claim to fully parse, Palworld's actual save files.

## Acceptance and distinguishing wrong implementations

- Independently brute-force small vector spaces to verify validity and maximality.
- Multi-round cascades, cycles kept as a whole, and one end of a cycle being bounded causing cascading shrinks.
- Events after a hole must not be selected; recomputing after a hole is filled can grow the result.
- Duplicate conflicts, missing/extra limits, unknown dependencies, invalid self-dependencies.
- Implementations that do only a single pass, look only at the last event, zero out on cycles, or always return zero must fail.

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
