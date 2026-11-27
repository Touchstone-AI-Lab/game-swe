---
difficulty: hard
estimated_minutes: 660
domains:
  - durability
  - idempotency
  - recovery
  - uncertain-outcomes
---

# Receipt-driven Supply Outbox Recovery

## Required files

```text
Info.json
scripts/main.lua
scripts/outbox/core.lua
scripts/services/outbox_service.lua
```

## Background and goals

When a guild distributes supplies, the external inventory may already have been written while the response is lost; the process may also crash after writing to the inventory but before recording the terminal state. Implement a durable outbox that recovers in order; it is forbidden to interpret "no confirmation received" as "not delivered". In this task the supply catalog and member identities are pre-resolved by the trusted service caller; the core only handles the distribution protocol.

## Plain-Lua API and inputs

```lua
Core.new()
Core.load(data)
core:submit({id="r1", member="m1", bundle="food", count=2}, journal)
core:drain(adapter, journal)
core:status(id)
core:snapshot()
core:save()
```

`journal(data)` is a synchronous, atomic full-state replacement: returning `true` means the data has been persisted; returning any other value or throwing means nothing was written to disk. It does not re-enter the core and may modify the table passed in; the core must not keep an alias of it. `save()` only exports data and cannot replace journal's persistence confirmation.

`adapter.lookup(request_id)` returns `absent`, `applied`, `rejected` or `unknown`; `adapter.deliver(record)` returns `applied`, `rejected` or `unknown`. Both may throw. The adapter deduplicates durably by request ID, and terminal receipts cannot change; `absent` is authoritative evidence of non-execution, `unknown` is not. The record passed to `deliver` contains the request fields, `seq` and `state="pending"`. The adapter may modify its arguments but must not re-enter. This task does not require implementing an impossible exactly-once on inventory systems that do not support idempotent receipts.

## Core semantics

1. `submit` first validates completely, then compares member, bundle, count by ID. An identical payload returns the original seq/state and `duplicate=true`; a different payload returns `request_conflict`; neither calls journal.
2. A new request must first journal the complete pending state, and only after confirmation be published to memory; sequence numbers increment starting from 1. On persistence failure return `storage_unavailable`; it occupies neither the ID nor a sequence number, and nothing is delivered.
3. `drain` processes pending in ascending seq order. Each time, lookup first; only on absent does it deliver. An existing terminal state is only persisted, not delivered again. unknown, an exception, or an invalid receipt immediately stops the whole round and returns `delivery_uncertain`; subsequent requests must not skip past it.
4. After obtaining a terminal state, journal the new state; on failure keep pending in memory, return `storage_unavailable` and stop. A retry must lookup again; it must not blindly resend or perform a reversal of a confirmed delivery.
5. Persisted terminal states are skipped permanently. `drain` returns `{ok=true,completed=n}` or `{ok=false,code=...,completed=n}`; n counts only terminal states successfully persisted in this round.
6. `status` returns `{state="unknown"}` or `{state="pending"|"applied"|"rejected",seq=n}`. `snapshot` returns only the three state counts, without member or supply details.
7. `save/load` preserve records, sequence numbers and terminal states; the caller may discard the instance at any journal boundary and recover with the last successfully written data. Storage and inventory are persisted separately; the two share no common transaction.
8. Validate first, then deduplicate; invalid fields give `invalid_request`. After a finite number of faults has ended, the adapter is eventually queryable and journal has recovered, repeated drain must complete all pending; safety must not be obtained by refusing to recover forever.

## Public example

submit r1 succeeds → lookup absent → deliver actually takes effect but returns unknown → drain uncertain → crash → load pending → lookup applied → journal applied. The total number of actual deliveries is 1. Implementing "deliver again immediately after unknown is returned" violates the call sequence, even if the adapter eventually deduplicates.

## Dedicated-server service contract

`Submit(request,journal)`, `Drain(adapter,journal)`, `Status(id)` correspond to the core methods of the same name. adapter/journal are objects injected by the trusted server; executable functions must never be constructed from console strings. The engine layer of this task verifies service mounting and protocol calls in a real UE4SS process; inventory side effects are injected by a controllable adapter, and no claim is made of operating on the real in-game inventory.

## Acceptance and distinguishing wrong implementations

- Crash recovery at every persistence boundary; in particular, delivered but terminal state not yet persisted.
- Stopping and continuing after journal returns false/throws, lookup unknown/throws, deliver unknown.
- Head-of-line blocking with multiple requests, rejected terminal state, payload conflict, deduplication across reloads.
- Malicious modification of journal/deliver arguments and of returned query tables must not pollute memory.
- An empty implementation must fail; "deliver first, then record pending", "treat unknown as absent", and "commit even though persistence failed" must be distinguished.

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
