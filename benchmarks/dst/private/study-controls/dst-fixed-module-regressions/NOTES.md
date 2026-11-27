# dst/core/dst-fixed-module-regressions — E0 notes

Repair task over the vendored DST Fixed server mod (Apache-2.0) at upstream commit `841cd02d5d`, with six optional modules enabled (five before task version 2.0.0). The starter reverts five upstream fixes: `44d9e2e` ("Fix issue that ipairs not working"), `f435f2e` ("Fix containers not dropping everything"), `cbd4ee9` ("pass portal instance on deactivation"), `72b78c8` ("Fix all blockable_pooping targets dropping a bung after one of them gets blocked") and `2f5482b` ("Fix an issue with the amount of dropped moonglass"). Since task version 2.0.0 it also reverts the stack fix of `170b20b` ("Fix removing whole stack of rename items instead of one") and `c4c2875` ("Fix not work": the Glommer statue's full work is set before a save loads, so a statue from a base-game save keeps `maxwork = -1` and refuses every repair), and the task switches on `GLOMMER` (Glommer Statue Repairing). The reference is the upstream tree.

A Mourning Glory into Dug Grave defect (`b94f96f`, "Fixed crash on mound loading") was tried first and dropped: on the real server the reverted code raises while the world populates its graves, before the suite can run, so every attempt that missed it would end incomplete instead of failing.

## Roles

- 20 cases: 8 `target`, 8 `preserved`, 1 `runtime-sentinel`, 2 `setup`, 1 `static`.
- Every exam clause is asserted.
- `naming a watch uses up one Feather Pencil of a stack` also fails in the starter because naming never starts there; `target-negative-whole-pencil-stack-used` shows that it detects the stack defect on its own.
- Known limits of the suite are listed under `known_issues` in `clause-map.json`.

## Version 2.0.0 validation (real dedicated server, networkless)

Run on 2026-10-28 on the Linux x86_64 lab host. The starter (`nop`) and the reference (`oracle`) ran through `private/harbor/scripts/validate-task.sh`, and every control ran on the same per-task Harbor verifier image. That image is built from the task's `tests/` on `gcb-dst-dedicated-verifier:24700372` (Steam app 343050, build 24700372) and runs the repository's evaluator against the real dedicated server without network. These runs have no Hub run ids: `rhenium run` was not repeated for 2.0.0, and the managed runtime was not prepared again.

| run | result |
| --- | --- |
| starter (`nop`) | 10; complete; fails exactly the 8 target cases |
| reference (`oracle`) | 100; complete; all 19 server cases pass |

| control | kind | result |
| --- | --- | --- |
| `target-negative-extra-moon-glass-kept` | target-negative | 10; fails only `the celestial portal receives exactly one moon glass per dial` |
| `target-negative-watch-hooks-still-skipped` | target-negative | 10; fails only the three watch-naming cases |
| `target-negative-whole-pencil-stack-used` | target-negative | 10; fails only `naming a watch uses up one Feather Pencil of a stack` |
| `target-negative-statue-max-work-set-before-load` | target-negative | 10; fails only `a Glommer statue saved before the option was switched on can be repaired with Marble` |
| `compat-negative-temporary-portal-never-registered` | compat-negative | 10; every target passes; fails only `using a Desert Stone opens a temporary Lazy Deserter that other portals lead to` |
| `compat-negative-statue-repairs-unbounded` | compat-negative | 10; every target passes; fails only `a partly mined Glommer statue is repaired with Marble up to full and no further` |
| `alternative-a` | alternative | 100; all 19 server cases pass |

## Version 1.0.0 record (superseded)

The runs below graded the 15-case suite of task version 1.0.0 through `rhenium run`.

### Two-way validation (real dedicated server through `rhenium run`, networkless)

| run | run id | result |
| --- | --- | --- |
| `starter` | `run-d7405ab36f5b4d17` | 10; fails exactly the 6 target cases |
| `reference-r1` | `run-9f78d9a1cc1f427a` | 100; admissible |
| `reference-r2` | `run-16270aa81f4145e2` | 100; admissible |
| `reference-r3` | `run-a5e12765b4bf456b` | 100; admissible |

The three reference runs gave identical case outcomes.

Incomplete evaluations are not evidence either way and were rerun; in each, the congested Docker daemon did not create the verifier container within the 300 s timeout or the container produced no trusted report: `run-649e33b15fe94b49` (reference-r1), `run-39d86458d7414ff2` (reference-r1), `run-a95599b10a3f4365` (reference-r1), `run-8a3bd403d0384201` (reference-r2), `run-e0a11590fd36400e` (starter), `run-c96d5ef809d14206` (starter), `run-3c45c936fc3247d1` (starter).

The suite was revised once during validation. A reference run on the final images (`run-c7dc48041b564f71`) failed `the celestial portal receives exactly one moon glass per dial` with no glass found. The portal and the first dial stood at fixed offsets from the spawn portal, and moon glass that is flung onto an ocean tile sinks, so on a world whose coastline passes there the glass could vanish; this is the most likely cause, but it was not confirmed from the server log. The suite now places every check that looks for dropped items (the turf of the combined helm, the dial without a portal, and the celestial portal) at the nearest offset where all ground within the search radius is land, keeping the old offset when it qualifies. Case names, roles and the exam did not change. Every run above and below is on the revised suite. The earlier round on the old suite (starter, three references, three controls and the alternative, all as declared) is superseded: `run-1739c3d4e0044f24`, `run-429ebb943de74a0f`, `run-e6cd1e3feeba4f73`, `run-3d9ca22957344661`, `run-b9d855edfb5e4844`, `run-1bbd37738b1142a4`, `run-a4e63920a95f4011`, `run-7c89bf51a4ad4a25`.

### Controls (real dedicated server through `rhenium run`, networkless)

| control | kind | what it is | run id | result |
| --- | --- | --- | --- | --- |
| `target-negative-extra-moon-glass-kept` | target-negative | Reference with the moon glass count fix reverted: the portal still gets one extra piece. | `run-2f8c9d5e9c404c92` | 10; fails only `the celestial portal receives exactly one moon glass per dial`; admissible |
| `target-negative-watch-hooks-still-skipped` | target-negative | Reference with only the writeable-layout loop fixed; the watch prefab hooks still iterate the set with ipairs. | `run-5237f5a08bd84cfd` | 10; fails only `a Backtrek Watch can be given a name that shows in its display name`; `a named Rift Watch keeps its name across a save and reload`; admissible |
| `compat-negative-temporary-portal-never-registered` | compat-negative | Reference that silences the stop error by never announcing the temporary portal, so no other Lazy Deserter links to it. | `run-bdd5cf7e30b04672` | 10; every target passes; fails only `using a Desert Stone opens a temporary Lazy Deserter that other portals lead to`; admissible |
| `alternative-a` | alternative | Independent fix: explicit watch list, per-dial stack arithmetic, per-creature GenerateLoot override for the bung, contents dropped at the combiner, portal passed through a local. | `run-7bcf6bab8fcd4ea7` | 100; admissible |
