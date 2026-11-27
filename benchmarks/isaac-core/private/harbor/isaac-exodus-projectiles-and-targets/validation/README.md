# Validation

> **Revision 2026-10-22 (catalog 5.0.0, task 2.0.0):** this revision adds three supplementary
> regressions to the exam and the starter (`../../../supplementary-regressions/`) and runs the
> shared 54-case verifier `../../../verifiers/exodus-v2/`. Its two-way controls were measured in the
> real game on 2026-10-22 (UTC) on the second controlled host (NixOS x86_64, prepared
> `afterbirth-plus-1.06.t1` runtime, verifier image `sha256:c0560b37db5a…`) through the Hub
> (`evaluate_task`, profile `full`): the base passed 41 and failed 13 cases with reward 0
> (run `run-51a72eda520343c3`), failing exactly the predicted set; the gold passed 54/54 with reward 1 (run `run-ca7e490f135e48f3`).
> The predicted set was corrected once, after this revision's first base run of
> `isaac-exodus-tear-trajectory`: `welcome_mat_poof_at_rest` observes Baseball Mitt's impact
> poof, which EX-327 also breaks, so it fails in every starter that carries EX-327.
> Both runs completed 3/3 processes with 0 fatal markers. The `controls.tsv` rows are this
> revision's; everything below this block describes earlier revisions and remains history
> only.

> **Revision 2026-09-26 (catalog 4.3.0, task 1.1.0):** this revision adds report EX-274 to the
> exam and reverts its upstream repair in the starter. Its two-way controls were measured in
> the real game on 2026-09-26 (UTC) on an Ubuntu 24.04 x86_64 Azure D4s_v5 host with Docker whose runtime was prepared by the managed `rhenium runtime prepare` flow (verifier image `sha256:649bcb926ce0…`), through the
> task's own `tests/run-game.sh` and the frozen three-process verifier: the base passed
> 28 and failed 7 cases with reward 0, failing exactly the
> previous measured set plus `deja_vu_split_guard`; the gold passed 35/35 with reward
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

With it, through `rhenium run isaac-rebirth/core/isaac-exodus-projectiles-and-targets … --profile full` (an
isolated Hub state seeded only with the operator Hub's runtime record, so concurrent
work could not lock its database):

| tree | score | complete | pass / fail | failed cases | run | finished (UTC) |
| --- | --- | --- | --- | --- | --- | --- |
| base (unchanged starter) | 10 | true | 29 / 6 | `baseball_mitt_delayed_hit`, `grid_worm`, `grid_worm_bounce`, `grid_worm_heading`, `headcase_orphan_lob`, `lovely_fly_target` | `run-b646f11ec4b74d2b` | 2026-09-24T00:34 |
| gold, run 1 | 100 | true | 35 / 0 | - | `run-239ce8d6094f4d2a` | 2026-09-24T00:38 |
| gold, run 2 | 100 | true | 35 / 0 | - | `run-6097e1f90e6142da` | 2026-09-24T01:14 |
| gold, run 3 | 100 | true | 35 / 0 | - | `run-62d063e4c2c44c9f` | 2026-09-24T05:11 |

The base fails exactly the measured set of `controls.tsv`. The gold ran 3 times with identical case outcomes.
