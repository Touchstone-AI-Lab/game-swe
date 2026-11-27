# E0 notes: isaac-rebirth/core/isaac-exodus-tear-trajectory (catalog 4.2.0; revised for 4.3.0 below)

Private maintenance material. Nothing here is copied into an attempt. The frozen
composite task (`isaac-exodus-release-regressions`) was only read; this task's controls,
clause map and notes live in this directory.

Reports in the exam: EX-203, EX-226, EX-258, EX-274, EX-327. The starter is the composite's fully fixed
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
| unchanged starter | 27 P / 8 F, complete, not passed | `run-952dff0997ac4be1` | 2026-09-23T21:54 |
| reference, run 1 | 35 P / 0 F, score 100, passed | `run-566720e53d734de2` | 2026-09-23T22:15 |
| reference, run 2 | 35 P / 0 F, score 100, passed | `run-cd262ef918a146fe` | 2026-09-24T00:42 |
| reference, run 3 | 35 P / 0 F, score 100, passed | `run-0a34e6b9fcc84d26` | 2026-09-24T03:18 |

The starter fails exactly `baseball_mitt_delayed_hit`, `beehive_early_wobble`, `deja_vu_split_guard`, `grid_worm`, `grid_worm_bounce`, `grid_worm_heading`, `ritual_candle`, `ritual_candle_cadence`, the
set predicted from the composite's single-report predicate matrix and measured on
2026-09-20 on the Ubuntu host (`validation/controls.tsv`).

## Case roles

36 observed ids: 8 target, 24 preserved, 3 runtime-sentinel,
1 static (`check:submission-shape`). Target is exactly what the unchanged starter fails.

Preserved cases are of two kinds:

- evidence for this exam's own preserve sentences: `beehive_mature_wobble`, `deja_vu_normal_return`, `grid_worm_cadence_regression` (clause ids and notes as in the composite map);
- the remaining 21 observe the composite's other reports, whose repairs the
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
| `compat-negative-grid-worm-cadence` | compat-negative | reference plus one token: periodic Grid Worm turns start after frame 10 instead of frame 20, against EX-226's own preserve sentence (same file as the composite task's control) |
| `alternative` | alternative | starter plus the composite task's independent alternative repairs of EX-203, EX-226, EX-258, EX-274, EX-327 only (its hunks 1, 2, 7, 9, 11, 16, 17, 19); written differently from gold.patch, see NOTES.md |
| `alternative-strict-reading` | alternative | same as alternative except the EX-226 rebound is a one-reversal-per-impact debounce without moving the tear; expected to be rejected by grid_worm_bounce only |

Why the negative controls are valid instances:

- `target-negative-ex226` leaves one reported repair out and keeps every other one, so it should fail only that report's target cases.
- `compat-negative-grid-worm-cadence` repairs every report and breaks `grid_worm_cadence_regression`: EX-226's own last sentence ("must not make those periodic turns start sooner"); the historical over-fix the sentence was written against.

### Observed outcomes (Hub, real game, three processes, one run each)

| control | pass / fail | failed cases | `problems` (study verdict) | run |
| --- | --- | --- | --- | --- |
| `target-negative-ex226` | 32 / 3 | `grid_worm`, `grid_worm_bounce`, `grid_worm_heading` | none | `run-f68d74d9dd5642e8` |
| `compat-negative-grid-worm-cadence` | 34 / 1 | `grid_worm_cadence_regression` | none | `run-b6fe88330f1e4991` |
| `alternative` | 35 / 0 | none | none | `run-92198c65aa6d4812` |
| `alternative-strict-reading` | 34 / 1 | `grid_worm_bounce` | must resolve with every case passing; failed=['case:grid_worm_bounce'] unobserved=[] | `run-db740b3a5a694a44` |

No run left a case unobserved and none emitted `GCB_FATAL`, unless the table says so.

## The alternative

It is the starter plus the composite task's independent alternative repairs (written from
the public reports, first-run 35/35 on the composite; see that task's NOTES.md) for this
task's reports only. None of its hunks is a gold hunk; where a report admits only a
one-token repair it necessarily coincides with gold, and the table says so.

| report | alternative repair |
| --- | --- |
| EX-203 | frame-stamp timer (`LastPulseFrame`) with interval `max(1, ceil(delay/3))` instead of `math.ceil` in the modulo |
| EX-226 | per-tear `GridWormAligned` flag and heading table; one reversal per impact and `Room:GetClampedPosition` |
| EX-258 | a strength factor instead of an if/else |
| EX-274 | one exclusion mask and a predicate shared by both branches |
| EX-327 | separate stance-independent `MC_POST_UPDATE` impact scan with a once-only marker |

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

Report EX-289 was added to this exam and its upstream repair reverted in the starter, so `lovely_fly_target` moved from preserved to target (clause-map.json). Base and gold were re-measured in the real game the same day (validation/controls.tsv and validation/README.md); the negative and alternative controls above are task 1.0.0 measurements and were not re-run.

## Catalog 5.0.0 revision (2026-10-22)

Three supplementary regressions (EX-441, EX-461, EX-469) were added to this exam and starter, and the task now runs the shared 54-case verifier `benchmarks/isaac-core/private/verifiers/exodus-v2/`. clause-map.json maps the 19 added cases: each one the starter fails is a target of the report whose regression it observes, every other is preserved. Newly failing in the starter: `baseball_mitt_return_flags`, `big_scissors_trail`, `grid_worm_heading_cross_axis`, `ominous_lantern_put_away`, `welcome_mat_poof_at_rest`.

Real game, second controlled host, Hub `evaluate_task` profile `full`: base 40/14 (run `run-fccc66ce487644a5`), gold 54/0 (run `run-31f397eb9c42456d`), both complete with 3/3 processes and no fatal marker. The target-negative, compat-negative and alternative controls above were not re-run for this revision, and the alternative patches do not repair the supplementary regressions.
