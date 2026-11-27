# status-effect-stack — authoring notes

## Design rationale

The task is a server-authoritative timed status-effect manager. The pure core
(`scripts/statuseffects/stack.lua`) is driven only by `now` arguments; the world
component (`scripts/components/statuseffects.lua`) pushes the aggregate onto the
real `locomotor`, `combat` and `health` components.

What makes the core hard, and what each hidden case isolates:

1. *validation and request dedupe* — a fixed validation order (time, shape, history,
   unknown effect, unknown target), failures recorded under the request id, time
   rejections not recorded, the clock advancing on calls that are rejected later, and
   history surviving `remove_target`.
2. *stacking policies* — `refresh`, `extend` (capped at `extend_cap * duration`, default 3
   and an explicit 2) and `independent` (oldest replaced, expired instances never
   replaced), all against the inclusive boundary `now >= expires_at`.
3. *modifiers* — `mult ^ stacks` products and `tick_health * stacks` sums from live
   instances with no `tick` call at all, walked across five expiry boundaries.
4. *tick accrual* — the health change is the exact integral of a piecewise-constant
   rate clipped to each instance lifetime. The same script is played once with a
   single tick and once with eight ticks; totals must match the hand-computed values
   (`a/bleed -15`, `a/regen 4`, `a/venom -12`, `b/venom -32`). It covers a stack change
   mid-life, a dispelled instance, a replaced instance, expiry clipping and
   `remove_target` discarding unreported amounts.
5. *dispel order* — priority desc, `applied_at` asc, effect id asc, seq asc. Every
   tie-break level decides at least one removal, `refresh` keeping `applied_at` decides
   chill-before-hex, and a younger high-priority curse beats an older hex.
6. *save/load* — every timestamp is rebased by `now - saved now` (the component needs this
   because `GetTime()` restarts with the process), history is returned verbatim, the seq
   counter survives even when its highest instance is gone, unreported accrual survives,
   effects missing from the new options are dropped, and `load(nil)` yields an empty
   manager at the supplied clock. The saved table is deep-copied by a copier that rejects
   functions, userdata, metatables and non-plain keys.

All hidden-case numbers use dyadic values (0.5, 0.75, 1.25, 1.5, integers), so every
product, sum and integral is exact in binary floating point regardless of summation
order; `exam.md` says so. Each value was derived by hand from `exam.md` before the
reference was run (see "Hand derivations"); the reference and the alternative reproduced
them without any change to the expected numbers. One suite bug of mine (a snapshot row
count that forgot a still-live frenzy instance) was fixed in the suite, not in the
implementations.

## Hand derivations (effects as defined at the top of the hidden suite)

- Case 1: chill at 5 -> expires 13, remaining at 6 is 7. After the rejected call at 9 the clock
  is 9, so 8 is stale; `r9` at 9 refreshes -> stacks 2, expires 17. `remove_target` at 9 counts
  the one live chill.
- Case 2: chill 0 -> 8; refresh at 5/6/7 -> 13/14/15 with stacks 2/3/3; 0.5^3 = 0.125 at 14.5;
  expired at 15, new instance 15 -> 23. frenzy (D = 10, cap 3): 0 -> 10; at 4: min(6+10, 30) = 16 -> 20;
  at 4: min(16+10, 30) = 26 -> 30; at 5: min(25+10, 30) = 30 -> 35; expired at 35 -> new 45.
  cap 2: 20, then min(26, 20) -> 24. venom (M = 2): 0 -> 6, 1 -> 7, at 2 replaces seq 1 -> 8;
  at 7 only the third is live -> stacked, 13; at 13 none live -> applied, 19.
- Case 3 (target a): chill x2 (expires 9), frenzy (11), curse (21), venom x2 (8), regen (6).
  t=3: 0.25*1.25 = 0.3125, 1.5*0.5 = 0.75, -2-2+1 = -3, 6 instances. t=6: regen gone -> -4, 5.
  t=8: venoms gone -> 0, 3. t=9: chill gone -> 1.25, 2. t=11: frenzy gone -> 1, 0.5, 1. t=21: neutral.
  b at 21 with two frenzy stacks: 1.25^2 = 1.5625, 1.5^2 = 2.25.
- Case 4: a/bleed 1 stack on [0,2) and 2 stacks on [2,6): -1.5*2 - 3*4 = -15. a/regen [0,4): +4.
  a/venom [1,7): -12. b/venom: [0,3) dispelled -> -6; [4,5) replaced -> -2; [4,10) -> -12;
  [5,11) -> -12; total -32. c/venom is dropped by `remove_target` at 2 (the frequent player
  had already collected -1 at 0.5 and -1 at 1). tick(0.5): -0.75, +0.5, -1, -1.
- Case 5: priority 3 at age 0: curse, venom#1, venom#2 -> effect id then seq -> [curse, venom#1].
  Then venom#2 (3), chill (2, applied 0, two stacks), hex (2, applied 3). On b the curse applied
  at 11 (priority 3) goes before the hex applied at 10 (priority 2).
- Case 6: tick(5): venom 5 s -> -10, bleed 1 s -> -1.5. Saved at 7: venom expired at 6 with -2
  unreported; bleed has -3 unreported and expires at 8; chill x2 expires 12. Loaded at 100
  (shift 93): chill 95/105, bleed 101. tick(101): venom -2; bleed -3 - 1.5 = -4.5. Seqs 1-4 were
  used before the save (4 belonged to the removed target), so the next one must be > 4.
  Reduced options at 50: chill expires 55 and nothing else is left.
- Server: venom x2 at T and T+1: by T+3 -6-4 = -10 (90); by T+10 -6-8 (76); regen +2 by T+12
  and +2 more by its expiry T+14 (80). Persistence: saved at T+3 with chill 5 s and venom 3 s
  left; after reload at g: -4 by g+2 (90), -2 more by g+3 (88), chill gone after g+5.

The server suite drives the component with explicit integer-based `now` values about
1000 s ahead of `GetTime()` (one base per case, strictly increasing), which the exam
publishes as the component time contract: explicit `now` passes through, a missing
`now` means `math.max(GetTime(), largest accepted time)`, and `OnLoad` rebases onto
`GetTime()`. Server comparisons on values that went through a rebase use a 0.001
tolerance and probe expiry at +-0.5 s because `GetTime()` is a multiple of 1/30 and is
not exactly representable.

## Real engine evidence (server cases)

1. *attached and authoritative* — Track validation against real `health` (no health, dead
   via real `DoDelta`), id/entity binding rules, `unknown_target` / `unknown_source`,
   a health-only entity (no locomotor/combat), component `extend_cap = 3` and frenzy
   `max_stacks = 2`, the whitelisted `Cleanse` with identity from `player.userid`
   (an impostor entity carrying the same userid is refused), one instance per cleanse,
   venom-over-chill dispel priority, and the real `locomotor:GetSpeedMultiplier()`.
2. *real modifiers* — `locomotor:GetSpeedMultiplier()`, `combat.externaldamagemultipliers:Get()`
   and `combat:CalcDamage()` follow apply, retry, refresh, dispel, the exact expiry
   boundary and `Tick`; a foreign speed modifier from another source survives; a removed
   entity is forgotten and its id can be reused without leaking effects.
3. *damage over time and death* — real `health.currenthealth` moves by the published
   amounts (100 -> 90 -> 76 -> 78 -> 80), a stale `Tick` is refused, a real death through
   `health:DoDelta(-1000)` removes both engine modifiers and brings the entity's
   `death`/`onremove` listener counts back to the pre-Track baseline, regen never revives,
   and a death caused inside `Tick` (re-entrancy) is handled.
4. *persistence and removal* — `OnSave` data survives a plain deep copy, `OnLoad` restores
   remaining time relative to `GetTime()`, request history survives, `OnLoad(nil)` clears
   modifiers but keeps tracked entities, a saved target with no entity keeps its effects
   for the next `Track`, and `TheWorld:RemoveComponent("statuseffects")` cancels the periodic
   task (world pending task count drops), removes modifiers and listeners; the component is
   re-added so the world stays usable.

The published base-game names were checked against `data/databundles/scripts.zip` of the
image `gcb-dst-dedicated-verifier:24700372`: `LocoMotor:SetExternalSpeedMultiplier(source, key, m)`,
`RemoveExternalSpeedMultiplier(source, key)`, `GetSpeedMultiplier`, `Combat.externaldamagemultipliers`
(`SourceModifierList:SetModifier(source, m, key)`, `RemoveModifier(source, key)`, `Get`),
`Combat:CalcDamage`, `Combat:SetDefaultDamage`, `Health:DoDelta(amount, overtime, cause, ...)`,
`Health:IsDead`, `EntityScript:ListenForEvent/RemoveEventCallback/DoPeriodicTask/RemoveComponent`,
`Periodic:Cancel`, the `ms_playerjoined` and `ms_respawnedfromghost` events. `PushEvent` copies the
listener list before calling, so unregistering inside the `death` callback is safe.

## Controls (real dedicated server, full profile)

| control | kind | expected | observed_score | observed_passed | failed_cases |
|---|---|---|---|---|---|
| reference | positive | score=100 complete=true passed=true | 100.0 complete=true | true | - |
| alternative | positive | score=100 complete=true passed=true | 100.0 complete=true | true | - |
| nop | nop | passed=false | 0.0 complete=false | false | check:required-files; check:lua-syntax; hidden:validation and request dedupe leave no side effects; hidden:stacking policies honor caps and the exact expiry boundary; hidden:modifiers aggregate live stacks without any tick; hidden:tick accrual is exact and independent of tick frequency; hidden:dispel orders by priority age effect id and sequence; hidden:save load rebases time and keeps history and accrual cursor; check:implementation-depth; check:effects-authority; check:effects-engine-modifiers; check:effects-health; check:effects-lifecycle; check:effects-self-cleanse-rpc; server-status:failed:modmain.lua is required for headless server assertions |
| accrual-not-clipped-to-expiry | negative | passed=false | 75.0 complete=true | false | hidden:tick accrual is exact and independent of tick frequency; server:damage over time changes real health and death clears everything; server:effects survive OnSave and OnLoad and component removal cleans up |
| cleanse-without-whitelist | negative | passed=false | 90.0 complete=true | false | server:status effect component is attached and authoritative |
| death-keeps-engine-modifiers | negative | passed=false | 80.0 complete=true | false | server:damage over time changes real health and death clears everything; server:effects survive OnSave and OnLoad and component removal cleans up |
| dispel-ignores-priority | negative | passed=false | 85.0 complete=true | false | hidden:dispel orders by priority age effect id and sequence; server:status effect component is attached and authoritative |
| expiry-boundary-exclusive | negative | passed=false | 70.0 complete=true | false | hidden:stacking policies honor caps and the exact expiry boundary; hidden:modifiers aggregate live stacks without any tick; hidden:dispel orders by priority age effect id and sequence; hidden:save load rebases time and keeps history and accrual cursor; server:real locomotor and combat modifiers follow stacks dispel and expiry |
| failed-requests-not-recorded | negative | passed=false | 95.0 complete=true | false | hidden:validation and request dedupe leave no side effects |
| linear-stack-scaling | negative | passed=false | 75.0 complete=true | false | hidden:stacking policies honor caps and the exact expiry boundary; hidden:modifiers aggregate live stacks without any tick; hidden:save load rebases time and keeps history and accrual cursor; server:real locomotor and combat modifiers follow stacks dispel and expiry |
| load-without-rebase | negative | passed=false | 85.0 complete=true | false | hidden:save load rebases time and keeps history and accrual cursor; server:effects survive OnSave and OnLoad and component removal cleans up |
| onload-forgets-tracked-entities | negative | passed=false | 90.0 complete=true | false | server:effects survive OnSave and OnLoad and component removal cleans up |
| refresh-resets-applied-at | negative | passed=false | 85.0 complete=true | false | hidden:stacking policies honor caps and the exact expiry boundary; hidden:dispel orders by priority age effect id and sequence; hidden:save load rebases time and keeps history and accrual cursor |
| rejected-call-keeps-clock | negative | passed=false | 95.0 complete=true | false | hidden:validation and request dedupe leave no side effects |
| removal-leaves-task-running | negative | passed=false | 87.0 complete=true | false | check:effects-lifecycle; server:effects survive OnSave and OnLoad and component removal cleans up |
| seq-counter-not-persisted | negative | passed=false | 95.0 complete=true | false | hidden:save load rebases time and keeps history and accrual cursor |

What each control shows:

- `reference`, `alternative` — two structurally different implementations pass at 100.
  The reference settles accrual eagerly into per-target accumulators on every call and
  uses a metatable class with per-target instance lists; the alternative is a closure over
  one flat instance journal, keeps stack-count segments per instance and integrates them
  lazily inside `tick`, picks dispel victims by repeated selection instead of sorting, uses
  the affected entity (not the world) as modifier source, keeps bindings in one array and
  tracks players from inside the component.
- `nop` — README-only workspace fails everything (complete=false because there is no modmain to inject into).
- `expiry-boundary-exclusive` — `now > expires_at`; hidden 2, 3, 5, 6 and server 2.
- `failed-requests-not-recorded` — only successes enter the history; hidden 1.
- `rejected-call-keeps-clock` — an `invalid_argument` apply rolls the clock back; hidden 1.
- `accrual-not-clipped-to-expiry` — accrual runs to `now`; hidden 4 and server 3, 4.
- `linear-stack-scaling` — `1 + (mult - 1) * stacks`; hidden 2, 3, 6 and server 2.
- `dispel-ignores-priority` — hidden 5 and server 1 (venom-over-chill).
- `refresh-resets-applied-at` — hidden 2, 5, 6.
- `load-without-rebase` — hidden 6 and server 4.
- `seq-counter-not-persisted` — hidden 6 only.
- `death-keeps-engine-modifiers` — hidden all pass; server 3 and 4.
- `onload-forgets-tracked-entities` — hidden all pass; server 4.
- `removal-leaves-task-running` — hidden all pass; server 4. Deleting the only `:Cancel(` call also fails the `effects-lifecycle` regex, as it should.
- `cleanse-without-whitelist` — hidden all pass; server 1.

Every negative loads and runs (complete=true). Together they fail all six hidden cases and
all four server cases.

## Clause map summary

{'asserted': 62, 'weak': 5} over 67 clauses. Every core clause is asserted. Not fully asserted:

- `dst-4c` — Only Tick(stale) == false is asserted; the periodic task never fires inside the synchronous suite. A Lua error from the task before the suite runs would surface as a mod error line in the server log.
- `dst-11a` — The suite sees a pending world task disappear on removal; that the task really calls Tick() is only a regex.
- `dst-13a` — No real player can join the headless test server; regex only.
- `dst-13b` — Cleanse itself is asserted on the server; the RPC registration and its argument discipline are regex only.
- `accept-1` — none_of TODO/IMPLEMENT ME regex only.

## Known weaknesses / unasserted details

- The periodic task is only proven to exist and to be cancelled (world pending-task count);
  that it calls `Tick()` and that a stale periodic call stays silent cannot be observed by a
  synchronous suite.
- `ms_playerjoined` tracking and the RPC registration are regex-only: the headless server has no
  players and no client. `Cleanse`, which the RPC forwards to, is engine-tested.
- The `IsDead` guard in `Tick` is not isolated from the death cleanup (death removes the target,
  so no delta remains for a dead entity); the regex check covers the guard.
- `health:DoDelta`'s `overtime`/`cause` arguments are published but not asserted.
- Freshness of returned tables is asserted for `apply`, `snapshot` and `modifiers` only.
- `Stack.load` with malformed non-nil data is published but only `nil` is exercised.
- The request history is unbounded by design (no eviction rule is published).
- The suite reads two engine-internal tables, `entity.event_listeners` and `entity.pendingtasks`,
  to observe listener and task cleanup; both exist in this build (`entityscript.lua`) and the
  exam states that these counts are checked.
- The server suite sets `health.nofadeout = true` on its own entities so the real death path does
  not schedule `ErodeAway` (which needs an AnimState); this is suite setup, not a solver obligation.
- The reference is 845 raw lines (the existing five references are 634-934).

## Not run

- Nothing was skipped: every control listed above ran on the real dedicated server through
  `tools/eval.sh` after the last suite/catalog edit. No Windows, client or multi-shard run exists
  for this task (the harness is a single headless master shard).

## Helper scripts in this directory

`build_catalog.py` (writes pack/fixed-v1.json), `make_negatives.py` (regenerates negatives/*.patch),
`run_controls.sh` + `collect_controls.py` (run controls, write controls.tsv), `build_clause_map.py`,
`build_notes.py`, `runhidden.sh` (sandbox-only hidden run). `runs/` holds the raw evaluation output of
every control. The base-game scripts that were extracted from the image for API verification and the
patched mutant trees were deleted after use (licensed / generated content).
