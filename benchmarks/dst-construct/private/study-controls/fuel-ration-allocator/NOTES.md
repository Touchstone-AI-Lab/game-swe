# fuel-ration-allocator — authoring notes

## Design rationale

The task is an integer resource allocator with a two-phase (reserve → settle) delivery protocol, wrapped by a
master-simulation world component that moves real items out of `inventory` and real fuel into `fueled`.

Core difficulty drivers, each published as an exact rule in `exam.md`:

* **Validation order and clock discipline.** time → ids → quantities, first failure wins; a call that fails validation changes
  nothing (not even the clock, not the request history); a call that passes validation advances the clock even when it then
  fails for a business reason. `report` carries *measurement* time: it is compared only with the consumer's own last report
  (strictly older = `stale`, equal = accepted) and never reads or writes the global clock. This resolves the conflict that a
  globally non-decreasing clock would otherwise make "stale report" unreachable.
* **Deposits.** Idempotency key is the pair (player, request). All three outcomes (`accepted`, `partial`, `depot_full`) are
  recorded and replayed; reserved units count against `depot_capacity`.
* **Allocation.** Priority classes ascending, inside a class unit-by-unit water-filling with ties to the smallest consumer id
  (plain string order, so `"f10" < "f2"`), `want = min(demand, max_units_per_round)`, `budget = max(0, available - reserve_floor)`.
  Every expected share in the suites was worked by hand (see comments in the suites and the examples below).
* **Rounds.** One open round; plan retry replays the original shares without re-reserving; `commit`/`abort` settle a share
  exactly once and any repeat replays the first settlement (checked before `over_delivery`); `close` aborts the pending
  shares; closed ids are dead forever; unregistering a consumer aborts its pending share.
* **Persistence.** `save` is plain data, `load` must not alias it, and an open round with one settled and two pending shares,
  the request history, closed ids, report times and the clock all survive.

DST layer: capacity rounds down and level rounds up (so `demand * unit_size` always fits the real component), delivery through
`fueled:DoDelta`, the committed amount is *measured* from `currentfuel`, `onremove` unregisters, `OnLoad` reconciles the
restored consumers with the entities tracked in session memory, and the time handed to the core must not regress although
`GetTime()` restarts per session.

### Engine facts verified in the pinned build (scripts.zip of `gcb-dst-dedicated-verifier:24700372`)

* `components/fueled.lua`: fields `maxfuel`, `currentfuel`; `DoDelta(amount, doer)` clamps to `[0, maxfuel]`, fires the
  section callback and `percentusedchange`; `InitializeFuelLevel(fuel)` sets `currentfuel` directly (used by the suite).
* `prefabs/campfire.lua`: `fueled` exists only on the master sim, `maxfuel = TUNING.CAMPFIRE_FUEL_MAX = 270`, start 135; the
  section callback at section 0 extinguishes the fire, makes it non-persistent and erodes it after 1 s — the suite therefore
  never sets a campfire to 0 fuel. Spawning ignites it and spawns the `campfirefire` FX child, which is removed with the fire.
  `prefabs/firepit.lua`: `maxfuel = 360`, start 180.
* `components/inventory.lua`: `Has(prefab, amount)` returns `enough, found`; `ConsumeByName(prefab, amount)` removes and
  destroys items across stacks; `GetItemByName`, `RemoveItem(item, wholestack)` and `stackable:Get(n)` are what the
  alternative uses.
* `entityscript.lua`: `ListenForEvent(event, fn, source)` stores the function in `source.event_listeners[event][listener]`;
  `DoPeriodicTask` records the task in `inst.pendingtasks` and `Periodic:Cancel()` clears it (`scheduler.lua`). The suite
  observes exactly these two engine tables for the cleanup obligations.
* `networkclientrpc.lua`: `AddModRPCHandler` stores the handler at `MOD_RPC_HANDLERS[namespace][MOD_RPC[namespace][name].id]`;
  the suite calls the registered handler directly.

## Hand-worked allocation examples used by the suites

* hidden case 3, plan `p1`: available 13, floor 2 → budget 11. Class 0 `pit` want 3 → 3. Class 2 `f10` (5), `f2` (1), `f3` (5)
  with 8 units: 1/1/1, then f10 2, f3 2, f10 3, f3 3, f10 4 → 4/1/3. Class 5 gets nothing. Plan `p2`: budget 30, every want is
  capped at 5 → f10 5, f3 5, z-low 5 (pit, f2, full have no demand).
* hidden case 5: budget 12 over four equal consumers → 3 each.
* server case 3: depot 11, floor 2 → budget 9. `pit-p` (firepit 290 fuel → level 20 of 24) takes 4. Class 1 has 5 units:
  `fire-a` (50 fuel → level 4, want 6) and `fire-b` (250 fuel → level 17, want 1): a, b, a, a, a → 4 and 1. Real fuel:
  350 / 110 / 265. With level rounded *down* fire-b would want 2 and the numbers change (negative `server-level-rounds-down`).
  Clipped round: depot 14 → budget 12 → `fire-a` 6 and `fire-d` 6, but `fire-d`'s real `maxfuel` was lowered to 120 after
  Track, so `DoDelta(90)` adds 60 fuel → 4 units committed, 2 returned, depot 4. (An implementation that re-derives capacity
  every round plans 4 for `fire-d` and lands on the same real numbers, so only reading-independent values are asserted.)
* server case 4: depot 8 → budget 6, the removed fire is unregistered so `keep-a` gets all 6 (60 → 150 fuel). After reload
  with 11 units: budget 9 between `keep-a` (level 10) and `late-c` (level 4), both want 6 → 5 and 4 (tie to `keep-a`).

## Controls

See `controls.tsv` (produced by `tools/run_controls.sh`; every row is a full-profile run on the real dedicated server).

* `reference`, `alternative`: 100, complete, passed. The alternative is structurally different: closure-based object with all
  state in upvalues, sorted arrays with binary search instead of maps, a closed-form water level instead of the unit loop, a
  table-driven validation pipeline, a different save layout, entity-side `onremove` listeners, a clamp-based time source
  instead of an offset, and stack-by-stack item removal through `GetItemByName`/`RemoveItem`/`stackable:Get`.
* `nop` (README only): 0, incomplete (no `modmain.lua`, the server suite cannot be injected), not passed.
* Negatives (each breaks one published obligation; all still load, so all are complete=true, passed=false):
  * core: `clock-advances-before-validation` (case 1), `dedupe-ignores-player` (2 + server cases 2 and 4, because `lookup` and
    `deposit` disagree), `reserved-units-ignore-capacity` (2),
    `fairness-tie-to-largest-id` (3 + server reload round), `reserve-floor-ignored` (3,4,5 + server), `stale-report-accepted`
    (3,6), `plan-retry-recomputes` (4,6), `closed-round-id-reusable` (4,6 + server), `repeat-commit-settles-again` (5,6),
    `unregister-keeps-share-reserved` (5), `load-drops-open-round` (6), `snapshot-leaks-consumer-rows` (6).
  * server-only (hidden suite stays green): `server-retry-removes-items-again`, `server-rpc-wrong-argument-order`,
    `server-level-rounds-down`, `server-commits-planned-without-measuring`, `server-onremove-handler-does-nothing`,
    `server-load-skips-reconcile`, `server-session-time-without-offset`, `server-task-not-cancelled` (this one also loses the
    `fuel-lifecycle` regex because `:Cancel(` disappears).
  Together they fail all 6 hidden cases and 3 of the 4 server cases; the attach/authority case is the allowed trivial one.

## Weak / unasserted points (also in `clause-map.json`)

* `removal_failed` (Deposit) cannot be provoked with the real inventory once `Has` succeeded — unasserted.
* The `abort` branch of `RunRound` for an entity that became unusable is unreachable on the real server because `onremove`
  unregisters first and step (1) of `RunRound` untracks invalid entities; the core-side abort semantics are asserted in hidden
  case 5.
* `OnLoad` step (1) (closing a restored open round) is unasserted: the component API always closes rounds synchronously, so
  no component-produced save contains an open round, and the suite cannot forge one without knowing the save layout.
* Periodic rounds (`ROUND_PERIOD`, the `auto-<n>` id and its persisted counter) are only covered by the regex check and by
  the "a world task disappears on component removal" observation; the suite cannot wait for timers.
* `cutgrass = 1`, `Track` with capacity < 1 or an invalid consumer id, `lookup` with malformed ids, `plan(<closed id>)`
  while another round is open (published: `round_open`), and "the snapshot does not expose request history" are published
  but not asserted.
* The `GetTime()` restart check replaces the global `GetTime` with a constant-zero function around `OnLoad` and two deposits
  and always restores it (also on failure). An implementation that cached `GetTime` in a local at file scope is not
  discriminated by this check, but it is not failed by it either.
* The client-side early return of `AddPrefabPostInit` is only a regex (a dedicated server is always the master sim).
* Deposit request history grows without bound by design (needed for exactly-once semantics); no retention rule is published.

## Not run

* No solver-model attempt was run against the exam; only the authored reference, alternative, NOP and mutants.
* Nothing was written to the benchmark repository; `pack/runtimes.json` is a verbatim copy and therefore has no binding for
  this task id (the scratch evaluation path does not read bindings).

## Reproduce

```
python3 tools/make_catalog.py        # pack/fixed-v1.json
python3 tools/make_negatives.py      # negatives/*.patch from the mutant table
python3 tools/make_clause_map.py     # clause-map.json
tools/run_controls.sh                # all controls on the real server -> controls.tsv (RESUME=1 to continue)
```
