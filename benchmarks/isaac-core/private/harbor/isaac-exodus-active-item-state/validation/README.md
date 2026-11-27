# Validation

> **Revision 2026-10-22 (catalog 5.0.0, task 2.0.0):** this revision adds three supplementary
> regressions to the exam and the starter (`../../../supplementary-regressions/`) and runs the
> shared 54-case verifier `../../../verifiers/exodus-v2/`. Its two-way controls were measured in the
> real game on 2026-10-22 (UTC) on the second controlled host (NixOS x86_64, prepared
> `afterbirth-plus-1.06.t1` runtime, verifier image `sha256:c0560b37db5a…`) through the Hub
> (`evaluate_task`, profile `full`): the base passed 42 and failed 12 cases with reward 0
> (run `run-6ed9bac6655440eb`), failing exactly the predicted set; the gold passed 54/54 with reward 1 (run `run-4ed10dc15a574b1f`).
> Both runs completed 3/3 processes with 0 fatal markers. The `controls.tsv` rows are this
> revision's; everything below this block describes earlier revisions and remains history
> only.

> **Revision 2026-09-26 (catalog 4.3.0, task 1.1.0):** this revision adds report EX-217 to the
> exam and reverts its upstream repair in the starter. Its two-way controls were measured in
> the real game on 2026-09-26 (UTC) on an Ubuntu 24.04 x86_64 Azure D4s_v5 host with Docker whose runtime was prepared by the managed `rhenium runtime prepare` flow (verifier image `sha256:649bcb926ce0…`), through the
> task's own `tests/run-game.sh` and the frozen three-process verifier: the base passed
> 26 and failed 9 cases with reward 0, failing exactly the
> previous measured set plus `cursed_metronome`; the gold passed 35/35 with reward
> 1. Both runs completed 3/3 processes with 0 fatal markers.
> The `controls.tsv` rows below are this revision's; the paragraphs about the 2026-09-20
> and 2026-09-23/24 measurements describe the previous revision (task 1.0.0) and remain
> history only.

`controls.tsv` records this task's two-way controls. The `predicted` rows were derived from
the frozen composite's `validation/predicate-matrix.tsv` before any real-game run: the base
should fail exactly the union of the reverted reports' flipped cases and the gold, the fully
fixed tree, should pass 35/35.

The `measured` rows are the real-game results of 2026-09-20 on the pinned native runtime, on
an Ubuntu 24.04 x86_64 host with Docker whose runtime was prepared by the managed `rhenium
runtime prepare` flow (verifier image
`sha256:649bcb926ce02775173e1243c4e42ef1a04308ced619568cbd55423148eb99c0`). The base passed
27 and failed 8 cases with reward 0, failing exactly the predicted set; the gold passed
35/35 with reward 1. Both runs completed all three game processes with no fatal marker.

## Hub validation on the congested Linux host (2026-09-23/24 UTC)

The first study baseline on the second controlled host (NixOS x86_64, Docker 29.8, prepared
runtime `isaac-rebirth/afterbirth-plus-1.06.t1`, verifier image
`sha256:c0560b37db5a…`) was incomplete for base and gold alike: with the frozen image's
`run-game.sh` one or two of the three game processes never started, because the offline
Steam client took 40 to 260 seconds to start on the saturated disk and dropped the launch
request. This task now ships its own `tests/run-game.sh` (see `tests/README.md`), which
the Hub mounts over the image's copy; the suites, `test.sh`, case names and pass rules
are unchanged.

With it, through `rhenium run isaac-rebirth/core/isaac-exodus-active-item-state … --profile full` (an
isolated Hub state seeded only with the operator Hub's runtime record, so concurrent
work could not lock its database):

| tree | score | complete | pass / fail | failed cases | run | finished (UTC) |
| --- | --- | --- | --- | --- | --- | --- |
| base (unchanged starter) | 10 | true | 27 / 8 | `anamnesis_charge`, `anamnesis_charge_persistence`, `forbidden_fruit`, `mutant_clover_stack`, `tragic_mushroom`, `tragic_mushroom_diminishing`, `tragic_mushroom_last_container`, `tragic_mushroom_repeat` | `run-04cc4232eaf24e98` | 2026-09-24T00:14 |
| gold, run 1 | 100 | true | 35 / 0 | - | `run-4b078c10db1c485d` | 2026-09-24T00:19 |
| gold, run 2 | 100 | true | 35 / 0 | - | `run-d73e41d29f1a4b39` | 2026-09-24T01:07 |
| gold, run 3 | 100 | true | 35 / 0 | - | `run-8a1cc298f28446eb` | 2026-09-24T04:55 |

The base fails exactly the measured set of `controls.tsv`. The gold ran 3 times with identical case outcomes.
