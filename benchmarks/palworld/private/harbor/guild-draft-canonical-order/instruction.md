# Harbor workspace

Complete this task in `/app/mod`; every required file must be written under that directory.

# Stable Guild Draft Under Conflicting Priorities

Build an authoritative guild draft planner. Guild preferences can form weighted cycles, campaign prerequisites impose hard precedence, and moving a participant too far can invalidate an otherwise reasonable plan. Compute an exact, canonical order with stable recovery. Start from the empty workspace.

## Required files and API

```text
Info.json
scripts/main.lua
scripts/draft/core.lua
scripts/services/draft_service.lua
```

The core returns `Core` with `Core.new()` and `Core.load(data)`. Instances provide `plan(request)`, `snapshot()` and `save()`, called with a colon. The core is ordinary Lua: no UE4SS globals, `require`, filesystem access or external libraries.

```lua
core:plan({revision=0,items={"a","b","c","d"},votes={},
           before={{from="d",to="a"}}})
```

All four request fields are required. `items` is a dense array of 0–16 unique IDs. `votes` contains 0–256 records `{id,from,to,weight}`. `before` contains 0–128 records `{from,to}`. Dense arrays have only integer keys 1 through their length, with no holes or extra keys. Every table is plain and has no metatable. Supplied data are acyclic. Unknown fields are invalid at every request-record level.

IDs contain 1–32 ASCII bytes matching `[A-Za-z0-9_-]+`. Vote IDs are unique in a separate namespace. All endpoints must name items, and `from` must differ from `to`. Repeated ordered vote pairs with different IDs are allowed and add their weights. Duplicate hard `before` pairs are invalid. Weights are finite mathematical integers in 0–1,000,000; zero is legal. Revision is a finite integer in 0–1,000,000,000. Booleans are not numbers.

## Baseline and exact ordering objective

Each request describes a complete new problem. Its baseline is the last accepted order with removed IDs deleted, followed by all new IDs in ascending raw-byte order. Initially it is the sorted item list. Positions are one-based.

Every output contains each current item exactly once and satisfies every hard `before` pair. A vote `from -> to` is violated if `from` appears after `to`. Minimize this tuple, in order:

1. Sum of violated vote weights.
2. Largest absolute displacement of any item from its baseline position.
3. Sum of all absolute displacements from baseline positions.
4. The full output ID sequence in raw-byte lexicographic order.

For no items, both displacement measures are zero. Do not merge the levels with arbitrary weights. In particular, a smaller prefix maximum is not sufficient to discard another prefix: later placements can equalize their maxima while preserving a better total displacement or lexical result.

Return exactly `{ok=true,revision,penalty,worst,movement,order}`. `order` is a dense array of all IDs. The example has the unique canonical result `{"b","d","a","c"}`, penalty 0, worst displacement 2 and total movement 6. The feasible order `{"c","d","a","b"}` has the same worst displacement but worse total movement.

Validate the whole request before checking revision. Malformed input returns `{ok=false,code="invalid_request"}`. A structurally valid revision not greater than the last accepted revision returns `stale_revision`, even if its hard graph has a cycle. Otherwise, if no feasible order exists, return `infeasible`. All failures contain only `ok=false` and `code`; no failure changes any state. Initial revision is -1, so revision 0 is valid.

Input permutations must not affect the result. Parallel votes must not be deduplicated by endpoint. A new accepted plan becomes the next request's baseline, including after save/load. A rejected plan does not become history.

Support the full 16-item limit without enumerating all permutations. An exact subset-based algorithm with at most O(N²·2^N·log(N+1)) work is sufficient; equivalent or better bounds are allowed. Retain all four objective levels. Existing evaluator CPU and memory limits are unchanged; machine-specific milliseconds are not semantic requirements.

## Snapshot and recovery format

Do not mutate inputs. Deeply detach inputs, returned results, snapshots and save/load data. Initially `snapshot()` returns `{revision=-1,order={}}`; after success it returns a copy of the complete last success result.

`save()` returns exactly:

```lua
{version=1,revision=last_revision,request=normalized_request,
 baseline={"a","b",...},result=last_success_result}
```

For an uninitialized core omit `request`, set `baseline={}`, and use the initial snapshot as `result`. Normalize items by ID, votes by vote ID, and hard pairs by `(from,to)` raw-byte order. A saved baseline is a complete permutation of the current item set representing the baseline used for that saved optimization, not the accepted output order unless they happen to match.

`Core.load` validates the exact schema, version, revision, normalized request and baseline permutation. It independently recomputes all four objective levels and the canonical order; a cached score or merely feasible permutation is not a certificate of optimality. Reject unknown state/result fields, inconsistent objectives, missing/duplicate baseline IDs and unsupported versions. Raise an error containing `invalid_state`; do not silently reset. The saved baseline is authoritative persisted history, not a cryptographic proof of earlier requests. Detach every restored table from caller data.

## UE4SS service and lifecycle

Publish only `RheniumService`, with `Plan`, `Reset`, `Snapshot`, `Save`, `Load` and `Unmount`. `Plan`, `Snapshot` and `Save` forward the core. `Reset` returns `{ok=true}` after constructing an empty core. `Load` fully validates a candidate before replacing the live core, returns `{ok=true}`, and propagates `invalid_state` without mutating the live service on failure.

Mount only after a valid `UEHelpers.GetWorld()` and `UEHelpers.GetKismetSystemLibrary():IsDedicatedServer(world)` succeed. Initialize and run asynchronous callers using `ExecuteInGameThread(callback)`; retry a missing world through `ExecuteWithDelay(1000,callback)`. Do not guess undocumented game APIs.

Register exactly one native hook and release its exact pair on unmount:

```lua
local pre,post=RegisterHook(
    "/Script/Engine.PlayerController:ServerAcknowledgePossession",
    function(Context) -- Read Context:get() only in the game thread, after checking IsValid.
    end)
UnregisterHook("/Script/Engine.PlayerController:ServerAcknowledgePossession",pre,post)
```

Register one read-only command with `RegisterConsoleCommandGlobalHandler("rhenium_draft",callback)`. It dispatches to the game thread and prints the current revision. It cannot accept ordering changes or infer a trusted caller through `FindFirstOf`. Preferences and prerequisites are trusted server data, not client-authorized mutations.

`Unmount` is idempotent and makes old hook/console callbacks inert. After unmount, `Plan`, `Reset` and `Load` return `unmounted` before any other processing. `Save` and `Snapshot` remain read-only. Do not cache raw controller pointers across ticks.

`Info.json` contains a nonempty `PackageName`, string `Version`, and a server-only Lua install rule with `Targets=["./scripts"]`.

## Evaluation boundary

This is a construct task. Author every required file from scratch. A `full` pass requires all static, sandboxed Lua and real dedicated-server assertions; missing engines and reduced runs are incomplete. Portable Harbor simulation is not engine evidence. Suggested duration and difficulty are author estimates. No model pass rate is claimed.
