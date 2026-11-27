# E0 notes: isaac-rebirth/core/isaac-exodus-active-item-state (catalog 4.2.0; revised for 4.3.0 below)

Private maintenance material. Nothing here is copied into an attempt. The frozen
composite task (`isaac-exodus-release-regressions`) was only read; this task's controls,
clause map and notes live in this directory.

Reports in the exam: EX-184, EX-191, EX-303, EX-311, EX-318. The starter is the composite's fully fixed
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
| unchanged starter | 27 P / 8 F, complete, not passed | `run-04cc4232eaf24e98` | 2026-09-24T00:14 |
| reference, run 1 | 35 P / 0 F, score 100, passed | `run-4b078c10db1c485d` | 2026-09-24T00:19 |
| reference, run 2 | 35 P / 0 F, score 100, passed | `run-d73e41d29f1a4b39` | 2026-09-24T01:07 |
| reference, run 3 | 35 P / 0 F, score 100, passed | `run-8a1cc298f28446eb` | 2026-09-24T04:55 |

The starter fails exactly `anamnesis_charge`, `anamnesis_charge_persistence`, `forbidden_fruit`, `mutant_clover_stack`, `tragic_mushroom`, `tragic_mushroom_diminishing`, `tragic_mushroom_last_container`, `tragic_mushroom_repeat`, the
set predicted from the composite's single-report predicate matrix and measured on
2026-09-20 on the Ubuntu host (`validation/controls.tsv`).

## Case roles

36 observed ids: 8 target, 24 preserved, 3 runtime-sentinel,
1 static (`check:submission-shape`). Target is exactly what the unchanged starter fails.

Preserved cases are of two kinds:

- evidence for this exam's own preserve sentences: `mutant_clover_room_reset` (clause ids and notes as in the composite map);
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
| `target-negative-ex318` | target-negative | reference with the two EX-318 Anamnesis hunks of the composite gold.patch (2, 29) reverted; every other report stays repaired |
| `compat-negative-cursed-metronome` | compat-negative | reference plus a misdirected edit to the neighbouring Cursed Metronome conversion (same maxhp idiom as Tragic Mushroom): its drain is sized by the filled red hearts again; Cursed Metronome is not reported in this exam |
| `alternative` | alternative | starter plus the composite task's independent alternative repairs of EX-184, EX-191, EX-303, EX-311, EX-318 only (its hunks 12, 14, 15, 20, 21, 22, 23); written differently from gold.patch, see NOTES.md |

Why the negative controls are valid instances:

- `target-negative-ex318` leaves one reported repair out and keeps every other one, so it should fail only that report's target cases.
- `compat-negative-cursed-metronome` repairs every report and breaks `cursed_metronome`: Task-preserve: Cursed Metronome (composite EX-217) is not reported in this exam and already works in the starter. Its conversion is the closest code with the same `maxhp = ... - 2` idiom as Tragic Mushroom, so a misdirected heart fix is plausible.

### Observed outcomes (Hub, real game, three processes, one run each)

| control | pass / fail | failed cases | `problems` (study verdict) | run |
| --- | --- | --- | --- | --- |
| `target-negative-ex318` | 33 / 2 | `anamnesis_charge`, `anamnesis_charge_persistence` | none | `run-3f3f3a72ba4e4d98` |
| `compat-negative-cursed-metronome` | 34 / 1 | `cursed_metronome` | none | `run-ea1b67faebed4cd8` |
| `alternative` | 35 / 0 | none | none | `run-3895c798ace64bfb` |

No run left a case unobserved and none emitted `GCB_FATAL`, unless the table says so.

## The alternative

It is the starter plus the composite task's independent alternative repairs (written from
the public reports, first-run 35/35 on the composite; see that task's NOTES.md) for this
task's reports only. None of its hunks is a gold hunk; where a report admits only a
one-token repair it necessarily coincides with gold, and the table says so.

| report | alternative repair |
| --- | --- |
| EX-184 | gates the bonus on `UseCount > 0` instead of dropping the `HasCollectible` test |
| EX-191 | `AddMaxHearts(2 - max)` then fills whatever container is left (`max - hearts`) |
| EX-303 | closed-form accumulators (`DamageScale`, `DamageOffset`, `Speed`, `Range`) updated at use time instead of a `Uses` loop |
| EX-311 | `Used` stays a flag; a separate `RoomLuck` accumulator |
| EX-318 | tracks the active slot (`GetActiveItem`); on entering the slot Anamnesis receives its own remembered charge |

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

Three supplementary regressions (EX-441, EX-465, EX-447) were added to this exam and starter, and the task now runs the shared 54-case verifier `benchmarks/isaac-core/private/verifiers/exodus-v2/`. clause-map.json maps the 19 added cases: each one the starter fails is a target of the report whose regression it observes, every other is preserved. Newly failing in the starter: `birdbath_use_spawns`, `hurdle_heels_landing_stomp`, `ominous_lantern_put_away`.

Real game, second controlled host, Hub `evaluate_task` profile `full`: base 42/12 (run `run-6ed9bac6655440eb`), gold 54/0 (run `run-4ed10dc15a574b1f`), both complete with 3/3 processes and no fatal marker. The target-negative, compat-negative and alternative controls above were not re-run for this revision, and the alternative patches do not repair the supplementary regressions.
