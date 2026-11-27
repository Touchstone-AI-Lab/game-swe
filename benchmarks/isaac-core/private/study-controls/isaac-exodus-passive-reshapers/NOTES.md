# E0 notes: isaac-rebirth/core/isaac-exodus-passive-reshapers (catalog 4.2.0; revised for 4.3.0 below)

Private maintenance material. Nothing here is copied into an attempt. The frozen
composite task (`isaac-exodus-release-regressions`) was only read; this task's controls,
clause map and notes live in this directory.

Reports in the exam: EX-226, EX-239, EX-251, EX-258. The starter is the composite's fully fixed
tree with only these reports' upstream fixes reverted, and the reference (starter plus
`solution/gold.patch`) is byte-identical to the composite reference (`main.lua`
`ee5753ae…`). Every case id, clause id and anchor below is the composite's; the exam's
report blocks and its Task and Notes sections are verbatim copies of the composite exam.

## Why the first study baseline was incomplete

The first `e0 baseline` attempts (2026-09-23 UTC) ended incomplete for starter and
reference alike: one or two of the three game processes never reported. Nothing in the
task caused it (the reference is byte-identical to the composite reference, which E0
admitted on 2026-09-20). The derived tasks used the frozen image's `run-game.sh`, which
sends `steam -applaunch` as soon as any Steam process exists and gives the game 180
seconds to appear. On the congested host (rotational RAID at 100 % utilisation, I/O
pressure around 20 % full) the offline client needed 40 to 260 seconds to start
(`System startup time`), dropped launch requests forwarded to its bootstrapper, and
some clients wedged (`SteamUI thread frame stalled`) and took no forwarded command at
all. The game therefore never started (`GCB_RUNTIME_INVALID game_start_timeout`); the
main suite runs first and hits the coldest client, which is why it was the process that
most often did not report. A manual run of the reference with the frozen launch script
(2026-09-23 UTC) failed all three processes that way.

The fix is the task's own `tests/run-game.sh`, mounted by the Hub over the image's copy
(see `private/harbor/<task>/tests/README.md`): it queues the launch request as soon as
the client proper is up, repeats an ignored request once, replaces a wedged client (up
to four starts per game process) and allows longer budgets. The suites, `test.sh`, case
names and pass rules are unchanged, and a retry only happens before the game process
exists. Across the 67 runs of all nine tasks on 2026-09-23/24 (UTC), 7 needed one client
restart, none needed a second, and none was incomplete. The frozen composite task still runs the
image's original script.

## Baseline (Hub, real game, three processes)

| tree | result | run | finished (UTC) |
| --- | --- | --- | --- |
| unchanged starter | 29 P / 6 F, complete, not passed | `run-e7e541c8170041ba` | 2026-09-23T22:36 |
| reference, run 1 | 35 P / 0 F, score 100, passed | `run-0091062844cb48ed` | 2026-09-23T22:51 |
| reference, run 2 | 35 P / 0 F, score 100, passed | `run-10865052ca144dbc` | 2026-09-24T00:47 |
| reference, run 3 | 35 P / 0 F, score 100, passed | `run-283401d8c3614e1a` | 2026-09-24T03:22 |

The starter fails exactly `beehive_early_wobble`, `blue_moon`, `broken_glasses`, `grid_worm`, `grid_worm_bounce`, `grid_worm_heading`, the
set predicted from the composite's single-report predicate matrix and measured on
2026-09-20 on the Ubuntu host (`validation/controls.tsv`).

## Case roles

36 observed ids: 6 target, 26 preserved, 3 runtime-sentinel,
1 static (`check:submission-shape`). Target is exactly what the unchanged starter fails.

Preserved cases are of two kinds:

- evidence for this exam's own preserve sentences: `beehive_mature_wobble`, `broken_glasses_floor_reset`, `grid_worm_cadence_regression` (clause ids and notes as in the composite map);
- the remaining 23 observe the composite's other reports, whose repairs the
  starter already contains. They are the evidence for `Task-preserve` ("Preserve behaviour
  outside the reported paths"), which is therefore `asserted` here, unlike in the
  composite map. `mutant_clover_room_reset` stays non-discriminating (composite clause
  `EX-311-preserve`).

## Controls

Every patch is applied with `patch -p1` from `/app/exodus` (`root` = `exodus`), as
`rhenium-study` applies it.

| control | kind | change |
| --- | --- | --- |
| `target-negative-ex226` | target-negative | reference with the two EX-226 Grid Worm hunks of the composite gold.patch (10, 11) reverted; every other report stays repaired (same file as the composite task's control) |
| `compat-negative-broken-glasses-floor-reset` | compat-negative | reference without the Broken Glasses reset in trinketNewFloor; the broken-world effect survives the floor change, against EX-251's own 'reset there' (same file as the composite task's control) |
| `alternative` | alternative | starter plus the composite task's independent alternative repairs of EX-226, EX-239, EX-251, EX-258 only (its hunks 7, 8, 9, 10, 19); written differently from gold.patch, see NOTES.md |
| `alternative-strict-reading` | alternative | same as alternative except the EX-226 rebound is a one-reversal-per-impact debounce without moving the tear; expected to be rejected by grid_worm_bounce only |

Why the negative controls are valid instances:

- `target-negative-ex226` leaves one reported repair out and keeps every other one, so it should fail only that report's target cases.
- `compat-negative-broken-glasses-floor-reset` repairs every report and breaks `broken_glasses_floor_reset`: EX-251's own "persist until the next floor and reset there"; the effect never ends once the target is repaired.

### Observed outcomes (Hub, real game, three processes, one run each)

| control | pass / fail | failed cases | `problems` (study verdict) | run |
| --- | --- | --- | --- | --- |
| `target-negative-ex226` | 32 / 3 | `grid_worm`, `grid_worm_bounce`, `grid_worm_heading` | none | `run-0be0ab545af0497d` |
| `compat-negative-broken-glasses-floor-reset` | 34 / 1 | `broken_glasses_floor_reset` | none | `run-3c499504383f40b2` |
| `alternative` | 35 / 0 | none | none | `run-52cc0ab4b9d2465e` |
| `alternative-strict-reading` | 34 / 1 | `grid_worm_bounce` | must resolve with every case passing; failed=['case:grid_worm_bounce'] unobserved=[] | `run-272070a64bbd4c8e` |

No run left a case unobserved and none emitted `GCB_FATAL`, unless the table says so.

## The alternative

It is the starter plus the composite task's independent alternative repairs (written from
the public reports, first-run 35/35 on the composite; see that task's NOTES.md) for this
task's reports only. None of its hunks is a gold hunk; where a report admits only a
one-token repair it necessarily coincides with gold, and the table says so.

| report | alternative repair |
| --- | --- |
| EX-226 | per-tear `GridWormAligned` flag and heading table; one reversal per impact and `Room:GetClampedPosition` |
| EX-239 | clears only the grid interior by row and column, plus a wall-type check |
| EX-251 | latches `Broke`, then acts on it (the same idea as the one-token gold) |
| EX-258 | a strength factor instead of an if/else |

## Strict reading: `grid_worm_bounce` over-constrains

Same finding as the composite task: `grid_worm_bounce` requires the tear to be at
least 35 units from the wall tile on the first frame its velocity is seen reversed,
which only a repair that also moves the tear passes. `alternative-strict-reading` is
the alternative without its `GetClampedPosition` line, a clean one-reversal-per-impact
rebound; measured 34 / 1, failing `grid_worm_bounce`. It is kept on purpose and is NOT an admissible alternative;
`e0 flag` marks `grid_worm_bounce` over-constrained from it. The assertion was not
edited.

## Not done / limits

- One target-negative and one compat-negative per task; the composite's
  `validation/predicate-matrix.tsv` covers every single-report flip in the other direction.
- Every result here is real-engine evidence from this Linux x86_64 Docker host's prepared
  runtime `isaac-rebirth/afterbirth-plus-1.06.t1` (verifier image `sha256:c0560b37db5a…`)
  through `rhenium run`, on an isolated Hub state seeded only with the operator Hub's
  runtime record (concurrent work kept locking the operator database). They were not
  recorded by `rhenium-study`; the study Hub must re-record them.
- The launch script was validated only on this host. It has not run on the WSL2 worker.

## Catalog 4.3.0 revision (2026-09-26)

Report EX-184 was added to this exam and its upstream repair reverted in the starter, so `forbidden_fruit` moved from preserved to target (clause-map.json). Base and gold were re-measured in the real game the same day (validation/controls.tsv and validation/README.md); the negative and alternative controls above are task 1.0.0 measurements and were not re-run.

## Catalog 5.0.0 revision (2026-10-22)

Three supplementary regressions (EX-441, EX-461, EX-436) were added to this exam and starter, and the task now runs the shared 54-case verifier `benchmarks/isaac-core/private/verifiers/exodus-v2/`. clause-map.json maps the 19 added cases: each one the starter fails is a target of the report whose regression it observes, every other is preserved. Newly failing in the starter: `big_scissors_trail`, `childs_leash_orbitals`, `grid_worm_heading_cross_axis`, `ominous_lantern_put_away`.

Real game, second controlled host, Hub `evaluate_task` profile `full`: base 43/11 (run `run-b53e9642577c485b`), gold 54/0 (run `run-0cbacd5edb834f3a`), both complete with 3/3 processes and no fatal marker. The target-negative, compat-negative and alternative controls above were not re-run for this revision, and the alternative patches do not repair the supplementary regressions.
