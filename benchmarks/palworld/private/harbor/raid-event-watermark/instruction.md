# Harbor workspace

Complete this task in `/app/mod`; every required file must be written under that directory.

# Revisioned Raid Contributions with Watermarks

## Required files

```text
Info.json
scripts/main.lua
scripts/watermark/core.lua
scripts/services/watermark_service.lua
```

## Background and goals

Raid contribution events arrive out of order and may later have their values corrected or be retracted. The server seals only after the authoritative watermark; it is forbidden to treat "the largest event sequence number" as "earlier events have all arrived". Implement the exact boundary between window settlement and irreversible sealing.

## Plain-Lua API and inputs

```lua
Core.new()
Core.load(data)
core:observe({id="hit1",member="m1",tick=9,amount=20,revision=0,deleted=false})
core:advance(watermark)
core:result(window)
core:snapshot()
core:save()
```

tick, amount, revision, watermark are non-negative integers. Windows have a fixed width of 10 and are numbered `tick // 10`; watermark starts at 0 and means all events with `tick < watermark` are closed. `deleted` must be explicitly a boolean; true means this event contributes no score, and a later higher revision may restore it before sealing.

## Core semantics

1. IDs are globally unique; the first acceptance freezes member/tick. The same ID with a different member or tick returns `identity_conflict`, with no exemption even if the revision is older.
2. Process in the following priority: full-field validation → frozen-identity check → equal-revision deduplication/conflict → old revision → watermark → admission. An equal revision with identical amount/deleted returns `{ok=true,duplicate=true}`, even if already sealed; different content returns `revision_conflict`.
3. A lower revision returns `stale_revision`; a higher revision or a brand-new event with tick < watermark returns `late_event`. tick == watermark can still be admitted. A higher revision replaces the old value rather than adding to it; other IDs must not be discarded because a higher revision arrived first.
4. advance is monotonically non-decreasing; an older value gives `stale_watermark`. An equal value is idempotent. result is allowed only when the window's right endpoint <= watermark; otherwise `not_final`. advance does not require every window to have events.
5. A sealed window sums the non-deleted contributions using each event's final revision; the highest total wins, and ties go to the byte-lexicographically smallest member ID. Valid zero-score events also participate; an entirely empty or entirely retracted window has no member, amount=0.
6. `result(w)` returns `{window=w,member=winner,amount=total}`, omitting member for an empty window. `snapshot` is `{watermark=n,results={...}}`, listing only sealed windows with at least one non-deleted event, in ascending window order. Raw events are not exposed.
7. Save all information needed for deduplication, including retraction tombstones; after load, old events must not be resurrected. After sealing, the winner cannot be modified.
8. Invalid input returns `invalid_request`, and rejections have no side effects; returned query tables and saves are deep copies. The permutation-invariance promise applies only to sets of events in the same open window whose IDs/revisions do not conflict and which all arrive before the advance; no false promise is made about arbitrary reorderings that cross the watermark.

## Public example

hit1=m1, tick9, revision2, amount7 arrives first; revision1, amount90 arriving afterwards should be rejected. hit2=m2,tick9,amount7 must still be admitted. After advance(10) the result is m1/7; sending hit1 revision3 again is rejected, but an exact retry of revision2 is a successful deduplication. A new event at tick10 belongs to the next window.

## Dedicated-server service contract

`Observe(event)`, `Advance(watermark)`, `Result(window)` correspond to the core. The watermark comes from a trusted collection coordinator and must not be advanced automatically from the local wall clock or the largest tick seen; this task tests only the settlement protocol and makes no claim of intercepting real in-game damage.

## Acceptance and distinguishing wrong implementations

- Out-of-order revisions, duplicate conflicts, retraction arriving first, restoration after retraction.
- Consistency across all small permutations and with save/load at every step; identity-conflict priority.
- tick9/10, watermark10, empty windows and zero-score members.
- advance jumps, partial windows, exact retry after sealing and rejection of new revisions.
- Implementations that sum by arrival, ignore tombstones, or use <= as the lateness condition must fail.

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
