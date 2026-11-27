# dst/core/rescue-dispatch-queue — E0 notes

Task version 2.0.1. Construction from an empty starter.

## Preserved contracts

None. The starter workspace is empty (the starter run is incomplete, score 0, every case
`F`/unobserved), so no case can be `preserved` and there is **no compat-negative**. The task
enters general completion only.

## Controls

| control | kind | base | result (2026-09-21, real dedicated server, managed container) |
| --- | --- | --- | --- |
| `target-negative-expiry-boundary` | target-negative | reference + patch | 95.0, not passed; fails only `hidden:lease expiry requeues unresolved target`; admissible |
| `alternative-a` | alternative | starter + tree | 100.0, passed, every case `P`; admissible |
| `alternative-strict-reading` | alternative | starter + tree | 86.67, not passed; fails only `server:dispatch state persists`; NOT admissible (expected, see below) |

- `target-negative-expiry-boundary.patch`: one character in the reference core
  (`scripts/rescuedispatch/dispatch.lua:130`, `now >= lease.expires_at` -> `now > lease.expires_at`).
  It breaks one requested behavior, Core semantics item 6 "reaching the boundary counts as expired": a lease is still live exactly
  at its boundary, so the target is not requeued at `expires_at`. Everything else is the reference.
- `alternative-a`: a full mod written from the public exam, structurally different from the reference:
  - core is a closure over one private state record (no metatable class, no public fields); the
    reference is a `setmetatable` class with public maps;
  - one array of tickets in creation order with the lease nested in its ticket (one target/one helper is
    structural); the reference keeps three maps (`incidents`, `leases`, `helper_lease`);
  - deterministic insertion sort with a total-order comparator instead of `table.sort` over sorted keys;
  - idempotency history split into a request map and a per-helper volunteer map with one FIFO log; the
    reference uses one map with concatenated string keys;
  - different save format (`format = "rescuedispatch/1"`, nested leases), different lease id format;
  - extra module `scripts/rescuedispatch/wire.lua` shared by component (encode) and replica (decode);
    the reference has the codec inside the replica and the encoder inside the component;
  - the net variable is created in the `world` post-init before the client early return, exactly as the
    exam's API contract shows (`inst._rescue_state = net_string(...)`); the reference creates it in the
    replica constructor;
  - one shared callback object per event kind for all players (the engine passes the source entity),
    per-player revision counters; the reference allocates per-player closures and one global revision.
  Choices the exam leaves open and the alternative made on its own: recovery threshold 0.8
  (`options.recovery_percent`), severity 1..5 derived from server-observed health, requests for a target at
  or above the recovery threshold are rejected, a helper cannot be leased to their own incident.
  The result field names (`ok`, `target_id`, `lease_id`, `expires_at`, `snapshot.queue`, `snapshot.leases`)
  are not named by the exam; the alternative uses the names implied by the API parameter names, which is
  also what the private suite reads (recorded as a known issue).
- `alternative-strict-reading`: byte-identical to `alternative-a` except
  `scripts/components/rescuedispatch.lua`: it defines `function RescueDispatch:OnSave()` /
  `:OnLoad(data)` only as ordinary `Class` methods. `alternative-a` adds 15 lines in the constructor
  that install per-instance `self.OnSave` / `self.OnLoad` wrappers which supply the receiver when the
  caller omitted it (`diff -ru alternative-strict-reading alternative-a` shows exactly that hunk plus
  the forward declaration of the class local).

## Over-constraining assertion (decides admission)

`benchmarks/dst/server/rescue-dispatch-queue.lua:38` — `assert(type(service.OnSave()) == "table")` calls
`OnSave` with a dot, i.e. without a receiver. The engine and the exam (`OnSave/OnLoad`) only ever use
`component:OnSave()`. Observed on the real server for `alternative-strict-reading`:

```
server:dispatch state persists  FAILED
[string "../mods/rhenium_<id>/scripts/compon..."]:263: attempt to index local 'self' (a nil value)
```

Line 263 is the first use of `self` inside `RescueDispatch:OnSave()`. Lines 36-37 of the same case
(`service:OnSave()`, `service:OnLoad(data)`) pass, so the persistence itself works; only the
receiver-less call rejects the submission. All hidden cases, all source gates and the other two server
cases pass (86.67). The private suite therefore **rejects a valid public-exam implementation**; the
reference passes only through its per-instance rebinding
(`solution/reference/scripts/components/rescuedispatch.lua:52-62`).

Recommendation: do not count `server:dispatch state persists` as clean target evidence for
`dst-6` until line 38 is changed to `service:OnSave()` by the task owner (a benchmark-authoring
change, not done here). If the case cannot be excluded on its own, the task should be excluded, because a
full-profile pass is impossible for the ordinary class-method implementation.

## Other findings (details in clause-map.json)

- Clause coverage is thin: aging (`core-3b`), time validation (`1a`), stale revisions (`1b`) and the
  "no authoritative scheduling in the replica / base-game assets only" line (`accept-6`) have no case and
  are listed in `excluded_clauses`. `complete()` and `cancel()` are never called by any suite.
- All DST-integration clauses except "component attached" and "OnSave/OnLoad round trip" are backed only
  by source regexes (`weak`). The exam's statement that the server test triggers real events and asserts
  net state and cleanup is not true of `server/rescue-dispatch-queue.lua`.
- Fixture trap: targets at `health_percent = .5` must be accepted and `health_percent = 1` must close the
  incident, while the recovery threshold is not public.

## Not run

Nothing outstanding for this task: starter, reference and all three declared controls ran under the
full profile on the real dedicated server (runtime `dst/dst-dedicated-24700372`). No client was
connected in any run, so replica/netvar behavior on a client has no evidence, for the reference or for
the alternatives.

## Catalog 2.1.0 update

The sections above describe catalog 2.0.1 (study snapshot 5929c99). The server suite now calls `service:OnSave()` with a receiver; the exam publishes the option names, the recovery threshold with its default, every result field the suites read and the implementation-depth requirement. The former `alternative-strict-reading` is kept as `alternative-b` and passes at 100. Re-run on 2026-09-22: reference 100, alternative-a 100, alternative-b 100, target-negative-expiry-boundary fails `lease expiry requeues unresolved target` only.
