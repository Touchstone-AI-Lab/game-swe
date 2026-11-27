# Harbor workspace

Complete this task in `/app/mod`; every required file must be written under that directory.

# Globally Optimal Pal Workforce Matching

## Required files

```text
Info.json
scripts/main.lua
scripts/workforce/core.lua
scripts/services/workforce_service.lua
```

## Background and goals

In a base, different Pals can each take on only some of the jobs; handling one locally highest-reward job first may occupy the only Pal able to complete another job. Implement a globally optimal one-to-one assigner; greedy approaches or enumerating all permutations must not be used to get by at maximum scale.

## Plain-Lua API and inputs

```lua
Core.new()
Core.load(data)
core:plan({revision=1, pals={{id="a"},{id="b"}}, jobs={
  {id="cook",priority=5,costs={a=2,b=3}},
  {id="mine",priority=5,costs={a=1}}
}})
core:snapshot()
core:save()
```

`pals` and `jobs` are hole-free dense arrays of 0–12 elements, with IDs unique within each. costs is a map from pal ID to non-negative integer cost; a missing edge means unsuitable, and cost 0 is a legal edge. An edge pointing to a nonexistent Pal is invalid. priority and revision are non-negative integers. Each round's input is a complete authoritative snapshot and does not inherit old edges.

## Core semantics

1. Each Pal is assigned at most one job, and each job is assigned at most one Pal; any job may be left unfilled.
2. Compare strictly by a four-level objective: maximize the sum of priority of assigned jobs; then maximize the number of jobs; then minimize the sum of costs; finally minimize the lexicographic order of the assignment vector. These objectives must not be merged using large weights that could overflow or lose precision.
3. The assignment vector is ordered by job ID in byte-lexicographic order; each element is a pal ID or the unassigned marker `~`. Compare the elements' raw strings (a short prefix is less than the longer string); `~` is greater than all legal IDs. It is not a comparison of a string containing only the assigned entries.
4. Return `{ok=true,revision,priority,count,cost,assignments}`; assignments contains only the assigned entries `{job,pal}`, in ascending job ID order.
5. Full input validation comes before the revision check; invalid input returns `invalid_request`, and valid input whose revision is not greater than the last successful revision returns `stale_revision`. Neither changes state. The initial revision is -1; revision 0 is allowed.
6. Equivalent permutations of pals/jobs/edge maps must yield field-by-field identical answers. Do not depend on pairs order, and do not wrongly prune candidates that would win on the third- or fourth-level objective in later jobs.
7. `snapshot` returns the last successful complete result, initially `{revision=-1,assignments={}}`. Input, results and save/load are all isolated from each other against aliasing.
8. Must handle 12×12 fully connected and sparse trap graphs; required to stay within O(J·P·2^P) candidate transitions, with an additional O(J+P) comparison/copy overhead allowed. Hidden tests include the maximum scale; specific machine milliseconds are not used as a semantic criterion.

## Public example

The optimal solution for the above input is cook→b, mine→a, total priority=10, count=2, cost=4. Choosing the lowest-cost a for cook first loses mine. When there is additionally an available job with priority=0, it must not be ignored just because the first objective does not increase.

## Dedicated-server service contract

`Plan(input)` and `Snapshot()` correspond to the core. Suitability and costs are tables sampled by the trusted server; this task does not require guessing undocumented properties of the Pal UObject. The service must not expose the cost table as a writable console entry point.

## Acceptance and distinguishing wrong implementations

- Verify small graphs with an independent exhaustive oracle, comparing the four-level objective rather than only total cost.
- Local greedy traps, priority taking precedence over count, zero priority, zero cost, no available edges.
- Lexicographic traps such as `a`/`a0`, different input permutations, and unassigned positions.
- Optimality and normal termination on 12×12 fully connected; revision rejection after save and restore.
- Implementations that delete one objective level or switch to first-fit must fail.

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
