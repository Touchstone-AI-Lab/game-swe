---
difficulty: hard
estimated_minutes: 960
domains:
  - min-cut
  - hard-constraints
  - canonical-optimum
  - recovery
---

# Canonical Base Containment Under Coupled Costs

Build a server-authoritative planner for holding or evacuating connected base zones. A locally cheap decision can cut a critical supply link. The planner must optimize the whole directed network, preserve a stable previous plan, and recover without trusting a forged cached optimum. Start from the empty workspace.

## Required files and API

```text
Info.json
scripts/main.lua
scripts/containment/core.lua
scripts/services/containment_service.lua
```

The core file returns a table `Core` with `Core.new()` and `Core.load(data)`. Its instances expose `core:plan(request)`, `core:snapshot()` and `core:save()`. The core must not use UE4SS globals, filesystem access, `require`, or other external libraries.

```lua
core:plan({
    revision=0,
    nodes={{id="a",cost0=9,cost1=0},{id="b",cost0=0,cost1=8}},
    arcs={{id="bridge",from="a",to="b",penalty=20}},
    requires={}
})
```

All four request fields are required. `nodes` is a dense array of 0–48 records `{id,cost0,cost1,locked?}`. `arcs` is a dense array of 0–256 records `{id,from,to,penalty}`. `requires` is a dense array of 0–128 records `{from,to}`. A dense array has only integer keys 1 through its length, with no holes or extra keys. Every table must be plain, with no metatable. All supplied data are acyclic. Unknown fields are invalid at every request-record level.

IDs contain 1–32 ASCII bytes matching `[A-Za-z0-9_-]+`. Node IDs are unique. Arc IDs are unique within the separate arc namespace. Every endpoint must name a node. Parallel arcs with different IDs are allowed and their penalties add. Self arcs are allowed and never cross the partition. Duplicate `requires` pairs are invalid; a self requirement is legal and redundant. Costs and penalties are finite mathematical integers in 0–1,000,000. `locked`, when present, is exactly the integer 0 or 1. Revision is a finite integer in 0–1,000,000,000. Boolean values are not numbers.

## Exact objective and history

Assign each node label 0 (evacuate) or 1 (hold). A lock fixes its node's label. A requirement `from -> to` forbids holding `from` while evacuating `to`.

For a feasible labeling, energy is the sum of every node's selected `cost0` or `cost1`, plus every directed arc's `penalty` whose source is 1 and destination is 0. A reverse crossing is free. Minimize the following tuple in order:

1. Total energy.
2. Number of labels changed from the baseline defined below.
3. The label vector in ascending node-ID byte order, with 0 before 1.

For each request, a surviving node's baseline is its label in the last accepted plan. A new node's baseline is 0. Removed nodes do not count toward changes. The initial baseline is therefore all zero. The baseline is fixed before optimizing the request; it is not updated during search.

Return exactly `{ok=true,revision,energy,changes,labels}`. `labels` is a dense, ID-sorted array of `{id,label}` records for all nodes. In the example, holding both zones gives energy 8 and is optimal. Choosing each node's cheaper label independently gives the wrong answer.

Full structural validation comes first. Malformed input returns `{ok=false,code="invalid_request"}`. A structurally valid revision not greater than the last accepted revision returns `stale_revision`, even if its hard constraints are infeasible. Otherwise, an unsatisfiable set of locks and requirements returns `infeasible`. Each failure returns only `ok=false` and `code`, and leaves the revision, baseline, request and result unchanged. Initial revision is -1; revision 0 is valid. An accepted empty graph has zero energy and changes.

Equivalent node, arc and requirement permutations must give identical results. Compare raw ID strings, including proper prefixes. Do not depend on `pairs` order. Preserve every objective level. A bounded integer reduction is permitted only if it provably preserves these levels without overflow; a positional exponential encoding of the lexical vector is not permitted.

The 48-node/256-arc limit must be supported without enumerating all partitions. Use polynomially bounded graph optimization, including polynomially many constrained optimizations if needed. The existing evaluator's CPU and memory limits remain in force; no particular machine's millisecond timing is a semantic rule.

## Snapshot and recovery format

Every input, result, snapshot and save must be detached from the others. `snapshot()` initially returns `{revision=-1,labels={}}`; after success it returns a detached copy of the last complete success result.

`save()` returns a fresh plain table with exactly these fields:

```lua
{version=1, revision=last_revision, request=normalized_request,
 baseline={{id="a",label=0}, ...}, result=last_success_result}
```

For an uninitialized core, omit `request`, use `baseline={}`, and use the initial snapshot as `result`. Normalize nodes by ID, arcs by arc ID, and requirements by `(from,to)` byte order. Preserve all specified record fields and omit absent locks. A nonempty saved baseline contains exactly one ID-sorted record per current node, including newly introduced nodes, with its pre-optimization baseline label.

`Core.load` validates the complete schema, version, revision, normalized request, complete baseline and cached result. It must independently recompute the canonical optimum for the saved request and baseline, and reject inconsistent objectives or labels. Reject unknown state/result fields and unsupported versions. Raise an error containing `invalid_state`; do not silently reset. A correctly typed baseline is authoritative persisted history, not a cryptographic authenticity claim. Load must deeply detach its state from the supplied table.

## UE4SS server service and lifecycle

Publish only the global `RheniumService`. It exposes `Plan(request)`, `Reset()`, `Snapshot()`, `Save()`, `Load(data)` and `Unmount()`. The first four forward the corresponding core behavior; `Reset()` creates an empty core and returns `{ok=true}`. `Load` constructs and validates a candidate core before replacing the live one, returns `{ok=true}`, and propagates `invalid_state` on rejection without changing the live service.

Only mount on a real dedicated server. Use `require("UEHelpers")`, wait for a valid `UEHelpers.GetWorld()`, and evaluate `UEHelpers.GetKismetSystemLibrary():IsDedicatedServer(world)`. Schedule initialization and asynchronous callbacks with `ExecuteInGameThread(function() ... end)`; retry unavailable worlds with `ExecuteWithDelay(1000, callback)`.

Register exactly one hook using the verified native signature:

```lua
local pre,post = RegisterHook(
    "/Script/Engine.PlayerController:ServerAcknowledgePossession",
    function(Context) -- Context:get() returns the controller; check IsValid in the game thread.
    end)
UnregisterHook("/Script/Engine.PlayerController:ServerAcknowledgePossession",pre,post)
```

Register exactly one read-only command with `RegisterConsoleCommandGlobalHandler("rhenium_containment", callback)`. Dispatch its work to the game thread and print the current revision. It must not accept mutations or infer an authenticated caller from `FindFirstOf`. No undocumented Palworld fields or client-supplied inventory changes are required: graph inputs are trusted server snapshots.

`Unmount` is idempotent, releases the exact hook pair once, and makes existing hook/console callbacks inert. After unmount, `Plan`, `Reset` and `Load` return `{ok=false,code="unmounted"}` before doing anything else. `Save` and `Snapshot` remain read-only. Do not retain raw controller pointers across ticks.

`Info.json` contains a nonempty `PackageName`, a string `Version`, and an `InstallRule` entry with `Type="Lua"`, `Targets=["./scripts"]`, and `IsServer=true`.

## Evaluation boundary

This is a construct task, not a repair task. All required files must be authored from scratch. A `full` pass requires static checks, sandboxed Lua behavior, and every real dedicated-server assertion. An unavailable or reduced engine run is incomplete. Portable Harbor simulation is not real-engine evidence. Difficulty and the suggested duration are author estimates, not measured model pass rates.
