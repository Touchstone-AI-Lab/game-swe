# Validation

> **Revision 2026-10-22 (catalog 5.0.0, task 2.0.0):** this revision adds three supplementary
> regressions to the exam and the starter (`../../../supplementary-regressions/`) and runs the
> shared 54-case verifier `../../../verifiers/exodus-v2/`. Its two-way controls were measured in the
> real game on 2026-10-22 (UTC) on the second controlled host (NixOS x86_64, prepared
> `afterbirth-plus-1.06.t1` runtime, verifier image `sha256:c0560b37db5a…`) through the Hub
> (`evaluate_task`, profile `full`): the base passed 42 and failed 12 cases with reward 0
> (run `run-a71fd9a832b0434d`), failing exactly the predicted set; the gold passed 54/54 with reward 1 (run `run-bfa69e70e55c47e4`).
> Both runs completed 3/3 processes with 0 fatal markers. The `controls.tsv` rows are this
> revision's; everything below this block describes earlier revisions and remains history
> only.

> **Revision 2026-09-26 (catalog 4.3.0, task 1.1.0):** this revision adds report EX-184 to the
> exam and reverts its upstream repair in the starter. Its two-way controls were measured in
> the real game on 2026-09-26 (UTC) on an Ubuntu 24.04 x86_64 Azure D4s_v5 host with Docker whose runtime was prepared by the managed `rhenium runtime prepare` flow (verifier image `sha256:649bcb926ce0…`), through the
> task's own `tests/run-game.sh` and the frozen three-process verifier: the base passed
> 28 and failed 7 cases with reward 0, failing exactly the
> previous measured set plus `forbidden_fruit`; the gold passed 35/35 with reward
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
29 and failed 6 cases with reward 0, failing exactly the predicted set; the gold passed
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

With it, through `rhenium run isaac-rebirth/core/isaac-exodus-orphaned-effects … --profile full` (an
isolated Hub state seeded only with the operator Hub's runtime record, so concurrent
work could not lock its database):

| tree | score | complete | pass / fail | failed cases | run | finished (UTC) |
| --- | --- | --- | --- | --- | --- | --- |
| base (unchanged starter) | 10 | true | 29 / 6 | `baseball_mitt_delayed_hit`, `familiar_cleanup`, `headcase_orphan_lob`, `iron_lung_orphan_gas`, `ritual_candle`, `ritual_candle_cadence` | `run-5d16d1a9632e4471` | 2026-09-24T00:25 |
| gold, run 1 | 100 | true | 35 / 0 | - | `run-ccb962f6fcef4e38` | 2026-09-24T00:29 |
| gold, run 2 | 100 | true | 35 / 0 | - | `run-28187332910f475c` | 2026-09-24T01:10 |
| gold, run 3 | 100 | true | 35 / 0 | - | `run-729d7efbc4bf456a` | 2026-09-24T05:03 |

The base fails exactly the measured set of `controls.tsv`. The gold ran 3 times with identical case outcomes.
