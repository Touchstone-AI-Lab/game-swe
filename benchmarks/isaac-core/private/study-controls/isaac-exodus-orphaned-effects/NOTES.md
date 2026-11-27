# E0 notes: isaac-rebirth/core/isaac-exodus-orphaned-effects (catalog 4.2.0; revised for 4.3.0 below)

Private maintenance material. Nothing here is copied into an attempt. The frozen
composite task (`isaac-exodus-release-regressions`) was only read; this task's controls,
clause map and notes live in this directory.

Reports in the exam: EX-203, EX-247, EX-327, EX-335, EX-342. The starter is the composite's fully fixed
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
| unchanged starter | 29 P / 6 F, complete, not passed | `run-5d16d1a9632e4471` | 2026-09-24T00:25 |
| reference, run 1 | 35 P / 0 F, score 100, passed | `run-ccb962f6fcef4e38` | 2026-09-24T00:29 |
| reference, run 2 | 35 P / 0 F, score 100, passed | `run-28187332910f475c` | 2026-09-24T01:10 |
| reference, run 3 | 35 P / 0 F, score 100, passed | `run-729d7efbc4bf456a` | 2026-09-24T05:03 |

The starter fails exactly `baseball_mitt_delayed_hit`, `familiar_cleanup`, `headcase_orphan_lob`, `iron_lung_orphan_gas`, `ritual_candle`, `ritual_candle_cadence`, the
set predicted from the composite's single-report predicate matrix and measured on
2026-09-20 on the Ubuntu host (`validation/controls.tsv`).

## Case roles

36 observed ids: 6 target, 26 preserved, 3 runtime-sentinel,
1 static (`check:submission-shape`). Target is exactly what the unchanged starter fails.

Preserved cases are of two kinds:

- the remaining 26 observe the composite's other reports, whose repairs the
  starter already contains. They are the evidence for `Task-preserve` ("Preserve behaviour
  outside the reported paths"), which is therefore `asserted` here, unlike in the
  composite map. `mutant_clover_room_reset` stays non-discriminating (composite clause
  `EX-311-preserve`).

## Controls

Every patch is applied with `patch -p1` from `/app/exodus` (`root` = `exodus`), as
`rhenium-study` applies it.

| control | kind | change |
| --- | --- | --- |
| `target-negative-ex335` | target-negative | reference with the two EX-335 Iron Lung hunks of the composite gold.patch (5, 6) reverted: gas cleanup still runs only from a living Iron Lung |
| `compat-negative-jera-duplicate-health` | compat-negative | reference with lilRuneFamiliarUpdate losing its duplicate HitPoints assignment while the ownership check is added to that function; the Jera duplicate health is not reported in this exam |
| `alternative` | alternative | starter plus the composite task's independent alternative repairs of EX-203, EX-247, EX-327, EX-335, EX-342 only (its hunks 1, 2, 3, 4, 11, 24); written differently from gold.patch, see NOTES.md |

Why the negative controls are valid instances:

- `target-negative-ex335` leaves one reported repair out and keeps every other one, so it should fail only that report's target cases.
- `compat-negative-jera-duplicate-health` repairs every report and breaks `lil_rune_jera_health`: Task-preserve: the Jera duplicate health (composite EX-281) is not reported here and works in the starter. The lost assignment sits in `lilRuneFamiliarUpdate`, where this task's EX-247 ownership check belongs.

### Observed outcomes (Hub, real game, three processes, one run each)

| control | pass / fail | failed cases | `problems` (study verdict) | run |
| --- | --- | --- | --- | --- |
| `target-negative-ex335` | 34 / 1 | `iron_lung_orphan_gas` | none | `run-c49808019616451a` |
| `compat-negative-jera-duplicate-health` | 34 / 1 | `lil_rune_jera_health` | none | `run-0d21ea07cd7c48e4` |
| `alternative` | 35 / 0 | none | none | `run-23398a8bcdaa47e4` |

No run left a case unobserved and none emitted `GCB_FATAL`, unless the table says so.

## The alternative

It is the starter plus the composite task's independent alternative repairs (written from
the public reports, first-run 35/35 on the composite; see that task's NOTES.md) for this
task's reports only. None of its hunks is a gold hunk; where a report admits only a
one-token repair it necessarily coincides with gold, and the table says so.

| report | alternative repair |
| --- | --- |
| EX-203 | frame-stamp timer (`LastPulseFrame`) with interval `max(1, ceil(delay/3))` instead of `math.ceil` in the modulo |
| EX-247 | one table-driven ownership sweep on `MC_POST_UPDATE` instead of five per-familiar checks |
| EX-327 | separate stance-independent `MC_POST_UPDATE` impact scan with a once-only marker |
| EX-335 | per-entity `MC_POST_EFFECT_UPDATE` callback filtered by the gas variant |
| EX-342 | stateless `MC_POST_UPDATE` scan; `DoLobbed` becomes derived state |

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

Three supplementary regressions (EX-427, EX-461, EX-406) were added to this exam and starter, and the task now runs the shared 54-case verifier `benchmarks/isaac-core/private/verifiers/exodus-v2/`. clause-map.json maps the 19 added cases: each one the starter fails is a target of the report whose regression it observes, every other is preserved. Newly failing in the starter: `big_scissors_trail`, `lil_rune_algiz_rune`, `lil_rune_jera_health`, `welcome_mat_flame_at_rest`, `welcome_mat_poof_at_rest`.

Real game, second controlled host, Hub `evaluate_task` profile `full`: base 42/12 (run `run-a71fd9a832b0434d`), gold 54/0 (run `run-bfa69e70e55c47e4`), both complete with 3/3 processes and no fatal marker. The target-negative, compat-negative and alternative controls above were not re-run for this revision, and the alternative patches do not repair the supplementary regressions.
