# E0 notes: isaac-rebirth/core/isaac-exodus-callback-wiring (catalog 4.2.0; revised for 4.3.0 below)

Private maintenance material. Nothing here is copied into an attempt. The frozen
composite task (`isaac-exodus-release-regressions`) was only read; this task's controls,
clause map and notes live in this directory.

Reports in the exam: EX-184, EX-266, EX-318, EX-335, EX-342. The starter is the composite's fully fixed
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
| unchanged starter | 29 P / 6 F, complete, not passed | `run-53a3330aa22246a6` | 2026-09-23T23:33 |
| reference, run 1 | 35 P / 0 F, score 100, passed | `run-e927dd51622244cc` | 2026-09-23T23:41 |
| reference, run 2 | 35 P / 0 F, score 100, passed | `run-5fccce38bd0b4dc0` | 2026-09-24T00:56 |
| reference, run 3 | 35 P / 0 F, score 100, passed | `run-55f00c6b74de4498` | 2026-09-24T04:21 |

The starter fails exactly `anamnesis_charge`, `anamnesis_charge_persistence`, `apocryphon_stats`, `forbidden_fruit`, `headcase_orphan_lob`, `iron_lung_orphan_gas`, the
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
| `target-negative-ex266` | target-negative | reference with the EX-266 hunk of the composite gold.patch (8) reverted: the missing Apocryphon cache registration is the one repair left out |
| `compat-negative-mutant-clover-cache` | compat-negative | reference with the Mutant Clover MC_EVALUATE_CACHE registration dropped during a cache-callback audit; Mutant Clover is not reported in this exam |
| `alternative` | alternative | starter plus the composite task's independent alternative repairs of EX-184, EX-266, EX-318, EX-335, EX-342 only (its hunks 4, 6, 12, 23, 24); written differently from gold.patch, see NOTES.md |

Why the negative controls are valid instances:

- `target-negative-ex266` leaves one reported repair out and keeps every other one, so it should fail only that report's target cases.
- `compat-negative-mutant-clover-cache` repairs every report and breaks `mutant_clover_stack`: Task-preserve: Mutant Clover (composite EX-311) is not reported here and works in the starter. Two of this task's reports are missing or misplaced callback registrations, so a registration audit is where it breaks.

### Observed outcomes (Hub, real game, three processes, one run each)

| control | pass / fail | failed cases | `problems` (study verdict) | run |
| --- | --- | --- | --- | --- |
| `target-negative-ex266` | 34 / 1 | `apocryphon_stats` | none | `run-c0573c3d522f4786` |
| `compat-negative-mutant-clover-cache` | 34 / 1 | `mutant_clover_stack` | none | `run-07b5f16b3a154f56` |
| `alternative` | 35 / 0 | none | none | `run-b1dffb7429464f18` |

No run left a case unobserved and none emitted `GCB_FATAL`, unless the table says so.

## The alternative

It is the starter plus the composite task's independent alternative repairs (written from
the public reports, first-run 35/35 on the composite; see that task's NOTES.md) for this
task's reports only. None of its hunks is a gold hunk; where a report admits only a
one-token repair it necessarily coincides with gold, and the table says so.

| report | alternative repair |
| --- | --- |
| EX-184 | gates the bonus on `UseCount > 0` instead of dropping the `HasCollectible` test |
| EX-266 | registers the missing cache callback (the same one-line repair as gold) |
| EX-318 | tracks the active slot (`GetActiveItem`); on entering the slot Anamnesis receives its own remembered charge |
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

Report EX-217 was added to this exam and its upstream repair reverted in the starter, so `cursed_metronome` moved from preserved to target (clause-map.json). Base and gold were re-measured in the real game the same day (validation/controls.tsv and validation/README.md); the negative and alternative controls above are task 1.0.0 measurements and were not re-run.

## Catalog 5.0.0 revision (2026-10-22)

Three supplementary regressions (EX-427, EX-465, EX-467) were added to this exam and starter, and the task now runs the shared 54-case verifier `benchmarks/isaac-core/private/verifiers/exodus-v2/`. clause-map.json maps the 19 added cases: each one the starter fails is a target of the report whose regression it observes, every other is preserved. Newly failing in the starter: `birdbath_use_spawns`, `lil_rune_algiz_rune`, `lil_rune_jera_health`, `paper_cut_card_damage`.

Real game, second controlled host, Hub `evaluate_task` profile `full`: base 43/11 (run `run-7768b69c364a4277`), gold 54/0 (run `run-bc79a76810244455`), both complete with 3/3 processes and no fatal marker. The target-negative, compat-negative and alternative controls above were not re-run for this revision, and the alternative patches do not repair the supplementary regressions.
