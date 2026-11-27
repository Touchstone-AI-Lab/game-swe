# E0 notes: isaac-rebirth/core/isaac-exodus-release-regressions (catalog 4.1.0)

Private maintenance material. Nothing here is copied into an attempt. The frozen
task tree (`exams/…md`, `private/harbor/<task>/{environment/exodus,tests,solution,validation}`)
was only read; every file of this study lives in this directory.

## Baseline

| tree | result | evidence |
| --- | --- | --- |
| unchanged starter (`main.lua` 9f307160…) | 9 P / 26 F, complete, not passed | real game, three processes |
| reference = starter + `solution/gold.patch` (`main.lua` ee5753ae…) | 35 P / 0 F, passed | real game, three processes |

Both agree with the private `NOTES.md` validation matrix.

## Case roles

36 observed ids: 26 target, 6 preserved, 3 runtime-sentinel, 1 static
(`check:submission-shape`).

`validation/case-contracts.tsv` labels eight cases `guard`. Two of them,
`tragic_mushroom_diminishing` (EX-303) and `anamnesis_charge_persistence` (EX-318),
fail in the unchanged starter, so they are evidence for the requested change and are
mapped `target`. That is why the target set has 26 cases and not the 24 the catalog
summary speaks of.

## Preserved contracts and where the exam states them

| case | clause | public text | strength |
| --- | --- | --- | --- |
| `grid_worm_cadence_regression` | `EX-226-preserve` | "Keep the existing later random-turn cadence; … must not make those periodic turns start sooner." | asserted |
| `deja_vu_normal_return` | `EX-274-preserve` | "Ordinary eligible, non-split tears must continue to return normally." | asserted |
| `broken_glasses_floor_reset` | `EX-251-preserve` | "… meant to persist until the next floor and reset there." | asserted; overlap (same sentence bounds the target) |
| `beehive_mature_wobble` | `EX-258-preserve` | "… before the normal wobble takes over." | asserted; overlap (upper bound of the half-strength window) |
| `james_book_of_secrets_positive` | `EX-296-preserve` | "That automatic use belongs to James's floor setup only" | asserted; overlap (same sentence scopes the target) |
| `mutant_clover_room_reset` | `EX-311-preserve` | "The whole temporary stack should continue to reset on entering another room." | **weak**, see below |

All six also cite `Task-preserve` ("Preserve behaviour outside the reported paths."),
which is `weak`: nothing outside the twenty reported items is observed.

`mutant_clover_room_reset` cannot fail for a broken reset. The suite replaces Mutant
Clover with Anamnesis in the active slot (`tests/suite/main.lua:383-385`) long before
it compares Luck (`:972-975`), and Exodus only adds the bonus while
`HasCollectible(MUTANT_CLOVER)`. Deleting `mutantCloverNewRoom`'s reset from the
reference would still leave Luck at the baseline. I therefore wrote no
compat-negative for it and recommend not counting this case as evidence of a kept
contract (it is harmless as a case; it is just uninformative).

## Controls

Every patch is applied with `patch -p1` from `/app/exodus` (`root` = `exodus`).

| control | kind | change | why it is a valid instance |
| --- | --- | --- | --- |
| `target-negative-ex226` | target-negative | reference with gold hunks 10 and 11 (Grid Worm) reverted | one report unrepaired, nineteen repaired; the cadence guard of the same report must stay green |
| `target-negative-ex274` | target-negative | reference with gold hunks 18 and 19 (Deja Vu `TEAR_SPLIT` test) reverted | one report unrepaired; the normal-return guard of the same report must stay green |
| `compat-negative-grid-worm-cadence` | compat-negative | reference, `entity.FrameCount > 20` → `> 10` in the periodic-turn branch | the historical over-fix the exam sentence was written against: opening direction, heading and rebound still work, periodic turns start ten frames sooner |
| `compat-negative-deja-vu-normal-return` | compat-negative | reference, `TearFlags & TEAR_SPLIT == 0` → `TearFlags \| TEAR_SPLIT == 0` in both branches | split tears stay excluded (target holds) but the test is false for every tear, so nothing returns any more |
| `compat-negative-broken-glasses-floor-reset` | compat-negative | reference, `Broke = false` removed from `trinketNewFloor` | the effect persists after the drop (target holds) and never ends at the next floor |
| `alternative` | alternative | starter + own repair of all twenty reports | see next section |
| `alternative-strict-reading` | alternative | `alternative` with a different EX-226 rebound | documents an over-constraining assertion; it is NOT admissible and is kept on purpose |

### Observed outcomes (real game, three processes, one run each, 2026-09-21)

| control | pass / fail | failed cases | `problems` |
| --- | --- | --- | --- |
| `target-negative-ex226` | 32 / 3 | `grid_worm`, `grid_worm_heading`, `grid_worm_bounce` (all target); `grid_worm_cadence_regression` stays P | none |
| `target-negative-ex274` | 34 / 1 | `deja_vu_split_guard` (target); `deja_vu_normal_return` stays P | none |
| `compat-negative-grid-worm-cadence` | 34 / 1 | `grid_worm_cadence_regression` (preserved; unchanged=2 of 12, minimum_dot=-1.0); all 26 target cases P | none |
| `compat-negative-deja-vu-normal-return` | 34 / 1 | `deja_vu_normal_return` (preserved; living_returned=0); all 26 target cases P | none |
| `compat-negative-broken-glasses-floor-reset` | 34 / 1 | `broken_glasses_floor_reset` (preserved; rgb=0,0,0 after `stage 1`); all 26 target cases P | none |
| `alternative` | 35 / 0 | none | none |
| `alternative-strict-reading` | 34 / 1 | `grid_worm_bounce` (reversed=true, distance=30.0) | "must resolve with every case passing" |

No control left a case unobserved and no run emitted `GCB_FATAL`. `rhenium-study e0 run` exits 1
for this task only because of the deliberately kept strict-reading control.

## The alternative

Written from the public reports and the starter source. It shares no hunk with
`gold.patch`; where a report admits only a one-token repair the token necessarily
coincides (EX-266 callback registration, EX-251 condition), and that is said here
rather than hidden.

| report | reference | alternative |
| --- | --- | --- |
| EX-184 | drops the `HasCollectible` test | gates the bonus on `UseCount > 0` |
| EX-191 | restructured branches, `AddHearts(2)` | `AddMaxHearts(2 - max)` then fills whatever container is left (`max - hearts`) |
| EX-303 | `Uses` counter, cache loop with `1/(1<<(i-1))` | closed-form accumulators (`DamageScale`, `DamageOffset`, `Speed`, `Range`) updated at use time; the cache applies them once |
| EX-203 | `math.floor` → `math.ceil` in the frame modulo | frame-stamp timer (`LastPulseFrame`) with interval `max(1, ceil(delay/3))`, computed once per update |
| EX-217 | `GetMaxHearts() - 2`, then `+ 2` for the pickup roll | capacity-sized drain with explicit zero guards |
| EX-226 | `FrameCount <= 1` branch with an if-chain; `Position += Velocity` on impact | per-tear `GridWormAligned` flag, heading lookup table with a dominant-axis fallback; one reversal per impact (debounce) and `Room:GetClampedPosition` |
| EX-239 | skips `GRID_WALL`/`GRID_DOOR` by type | clears only the interior of the grid by row/column, plus a wall-type check for non-rectangular rooms |
| EX-247 | a `HasCollectible` test in each of five familiar updates | one table-driven ownership sweep on `MC_POST_UPDATE` |
| EX-251 | `HasTrinket or Broke` | latch first, then act on `Broke` (same idea; one-token report) |
| EX-258 | if/else on `FrameCount > 20` | strength factor |
| EX-266 | registers the missing cache callback | same (nothing else repairs it) |
| EX-274 | adds a `TEAR_SPLIT` term to both conditions | one exclusion mask and a predicate shared by both branches |
| EX-281 | `HitPoints = MaxHitPoints` twice | loop of two copies, `HitPoints = min(HitPoints, MaxHitPoints)` |
| EX-289 | `IsVulnerableEnemy` → `IsActiveEnemy(false)` | keeps vulnerability and additionally requires `IsActiveEnemy(false)` |
| EX-296 | moves the use inside the James branch | early return for every other character |
| EX-311 | `Used` becomes a counter | `Used` stays a flag; a separate `RoomLuck` accumulator |
| EX-318 | polls `HasCollectible`, special-cases charge 6 | tracks the active slot (`GetActiveItem`); on entering the slot Anamnesis always receives its own remembered charge |
| EX-327 | drops the stance condition | separate stance-independent update with a once-only marker |
| EX-335 | global scan on `MC_POST_UPDATE` | per-entity `MC_POST_EFFECT_UPDATE` callback filtered by the gas variant |
| EX-342 | moves the scan to `MC_POST_UPDATE`, keeps the `DoLobbed` gate | stateless scan; `DoLobbed` becomes derived state |

Two facts about the pinned runtime were read from the local verifier image
(`resources/scripts/enums.lua`, nothing was copied out): `MC_POST_EFFECT_UPDATE` and the
other per-entity callbacks exist in v1.06.T1. Syntax was checked with a Lua 5.4 `luac -p`.

The alternative was not tuned on the private suite: it passed all 35 cases in its
first real-game run. One thing I knew from the suite before writing it is recorded
under "strict reading" below.

In the real game the alternative's rebound puts the tear 62 units from the struck wall
tile on the reversal frame (reference: 40). `GetClampedPosition(pos, tear.Size)` moves it
further into the room than I expected; it is a visible half-tile hop, still a clean
rebound.

## Strict reading: `grid_worm_bounce` over-constrains

`tests/suite/main.lua:929-932` requires the tear to be at least 35 units from the wall tile
on the first frame its velocity is seen reversed. Starter and reference both reverse on the
same frame; the starter is measured at 30.0, the reference at 40.0, and the only difference
is gold's `Position = Position + Velocity`. The public report says tears "invert their
velocity without leaving the collision tile, so they can oscillate in place instead of
rebounding cleanly". A repair that reverses once per impact and ignores the still-set
collision flag for the next few frames also rebounds cleanly (30 → 40 → 50 …) without
teleporting the tear, but is measured at 30 and rejected.

`alternative-strict-reading` is exactly that: the alternative without the
`GetClampedPosition` line. In the real game it reverses on the same frame as the reference
(age=2), is measured at 30.0 units and fails `grid_worm_bounce` only; its other 34 cases pass.
It is kept as an honest control. I had read the assertion before writing the passing
alternative, so the clamp in `alternative` is the one place where the suite, not only the
exam, influenced the code. The assertion was not edited.

## Exclusion recommendations

- Clauses `Notes-api` and `Notes-no-wholesale-replacement` are unasserted and excluded.
- `EX-311-preserve` / `mutant_clover_room_reset`: keep the case, do not count it as
  discriminating preserved evidence (see above).
- `EX-239` and `EX-266` are weak (>= 10 of 43 walls; any stat change in either direction).
- No task-level exclusion: three preserved cases were shown to be discriminating by an
  admissible compat-negative each (Grid Worm cadence, Deja Vu normal return, Broken Glasses
  floor reset). `beehive_mature_wobble` and `james_book_of_secrets_positive` read as
  discriminating from the suite source but were not exercised by a control.

## Not done / limits

- No compat-negative for `beehive_mature_wobble`, `james_book_of_secrets_positive` or
  `mutant_clover_room_reset` (the last one cannot be built, see above).
- Only two of the twenty possible single-report target-negatives were run; the private
  `validation/predicate-matrix.tsv` already covers the converse direction for all twenty.
- Every result above is real-engine evidence from the local prepared runtime
  `isaac-rebirth/afterbirth-plus-1.06.t1`; each control was run once.
