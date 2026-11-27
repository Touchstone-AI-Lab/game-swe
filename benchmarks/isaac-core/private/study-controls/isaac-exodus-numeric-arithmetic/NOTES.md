# E0 notes: isaac-rebirth/core/isaac-exodus-numeric-arithmetic (catalog 4.2.0; revised for 4.3.0 below)

Private maintenance material. Nothing here is copied into an attempt. The frozen
composite task (`isaac-exodus-release-regressions`) was only read; this task's controls,
clause map and notes live in this directory.

Reports in the exam: EX-191, EX-203, EX-217, EX-281, EX-303. The starter is the composite's fully fixed
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
| unchanged starter | 27 P / 8 F, complete, not passed | `run-792a4e73ae424e88` | 2026-09-23T23:52 |
| reference, run 1 | 35 P / 0 F, score 100, passed | `run-7e734c8a4f2c42cc` | 2026-09-24T00:01 |
| reference, run 2 | 35 P / 0 F, score 100, passed | `run-d821056862354cec` | 2026-09-24T00:59 |
| reference, run 3 | 35 P / 0 F, score 100, passed | `run-512a6ef54ed44da1` | 2026-09-24T04:29 |

The starter fails exactly `cursed_metronome`, `lil_rune_jera_health`, `ritual_candle`, `ritual_candle_cadence`, `tragic_mushroom`, `tragic_mushroom_diminishing`, `tragic_mushroom_last_container`, `tragic_mushroom_repeat`, the
set predicted from the composite's single-report predicate matrix and measured on
2026-09-20 on the Ubuntu host (`validation/controls.tsv`).

## Case roles

36 observed ids: 8 target, 24 preserved, 3 runtime-sentinel,
1 static (`check:submission-shape`). Target is exactly what the unchanged starter fails.

Preserved cases are of two kinds:

- the remaining 24 observe the composite's other reports, whose repairs the
  starter already contains. They are the evidence for `Task-preserve` ("Preserve behaviour
  outside the reported paths"), which is therefore `asserted` here, unlike in the
  composite map. `mutant_clover_room_reset` stays non-discriminating (composite clause
  `EX-311-preserve`).

## Controls

Every patch is applied with `patch -p1` from `/app/exodus` (`root` = `exodus`), as
`rhenium-study` applies it.

| control | kind | change |
| --- | --- | --- |
| `target-negative-ex203` | target-negative | reference with the EX-203 hunk of the composite gold.patch (3) reverted: Ritual Candle keeps its floor-rounded pulse interval |
| `compat-negative-lil-rune-ownership` | compat-negative | reference with lilRuneFamiliarUpdate losing its HasCollectible removal while the Lil Rune code is edited for the Jera duplicate health; Lil Rune cleanup is not reported in this exam |
| `alternative` | alternative | starter plus the composite task's independent alternative repairs of EX-191, EX-203, EX-217, EX-281, EX-303 only (its hunks 1, 2, 13, 14, 15, 18); written differently from gold.patch, see NOTES.md |

Why the negative controls are valid instances:

- `target-negative-ex203` leaves one reported repair out and keeps every other one, so it should fail only that report's target cases.
- `compat-negative-lil-rune-ownership` repairs every report and breaks `familiar_cleanup`: Task-preserve: familiar cleanup (composite EX-247) is not reported here and works in the starter. The removal it loses sits in `lilRuneFamiliarUpdate`, the function that holds this task's EX-281 Jera fix.

### Observed outcomes (Hub, real game, three processes, one run each)

| control | pass / fail | failed cases | `problems` (study verdict) | run |
| --- | --- | --- | --- | --- |
| `target-negative-ex203` | 33 / 2 | `ritual_candle`, `ritual_candle_cadence` | none | `run-c9ab78b40f314555` |
| `compat-negative-lil-rune-ownership` | 34 / 1 | `familiar_cleanup` | none | `run-96a0e8d9af794e4b` |
| `alternative` | 35 / 0 | none | none | `run-18ad9b966bf5405d` |

No run left a case unobserved and none emitted `GCB_FATAL`, unless the table says so.

## The alternative

It is the starter plus the composite task's independent alternative repairs (written from
the public reports, first-run 35/35 on the composite; see that task's NOTES.md) for this
task's reports only. None of its hunks is a gold hunk; where a report admits only a
one-token repair it necessarily coincides with gold, and the table says so.

| report | alternative repair |
| --- | --- |
| EX-191 | `AddMaxHearts(2 - max)` then fills whatever container is left (`max - hearts`) |
| EX-203 | frame-stamp timer (`LastPulseFrame`) with interval `max(1, ceil(delay/3))` instead of `math.ceil` in the modulo |
| EX-217 | capacity-sized drain with explicit zero guards |
| EX-281 | loop over two copies with `HitPoints = min(HitPoints, MaxHitPoints)` |
| EX-303 | closed-form accumulators (`DamageScale`, `DamageOffset`, `Speed`, `Range`) updated at use time instead of a `Uses` loop |

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

Report EX-266 was added to this exam and its upstream repair reverted in the starter, so `apocryphon_stats` moved from preserved to target (clause-map.json). Base and gold were re-measured in the real game the same day (validation/controls.tsv and validation/README.md); the negative and alternative controls above are task 1.0.0 measurements and were not re-run.

## Catalog 5.0.0 revision (2026-10-22)

Three supplementary regressions (EX-427, EX-463, EX-452) were added to this exam and starter, and the task now runs the shared 54-case verifier `benchmarks/isaac-core/private/verifiers/exodus-v2/`. clause-map.json maps the 19 added cases: each one the starter fails is a target of the report whose regression it observes, every other is preserved. Newly failing in the starter: `lil_rune_algiz_rune`, `new_run_starts_with_base_stats`, `unholy_mantle_burst`.

Real game, second controlled host, Hub `evaluate_task` profile `full`: base 42/12 (run `run-eef4de9af19e4489`), gold 54/0 (run `run-76630fe9a72b49b8`), both complete with 3/3 processes and no fatal marker. The target-negative, compat-negative and alternative controls above were not re-run for this revision, and the alternative patches do not repair the supplementary regressions.
