> Historical validation for pack version 1.0.0 (2026-09-24).

# Acceptance record: recipesmith-config-recipes

Real Paper 1.21.11 build 132 server, runtime `minecraft/paper-1.21.11-132-construct` prepared with
`rhenium runtime prepare`, every control evaluated through the Hub with
`rhenium run minecraft/construct/recipesmith-config-recipes <submission>` (offline Maven build, `--network=none`).

| Control | Submission | Run | Score | Complete | Failed cases |
| --- | --- | --- | --- | --- | --- |
| reference-1 | skeleton + `solution/after` | `run-46f9e33d5dd04f15` | 100.0 | True | none |
| reference-2 | skeleton + `solution/after` | `run-ec5bd86de76b478b` | 100.0 | True | none |
| reference-3 | skeleton + `solution/after` | `run-e4578f888bf74b2c` | 100.0 | True | none |
| starter | the unchanged skeleton (`nop`) | `run-932b40cfb3d24f35` | 10.0 | True | 16 of 17 (every case but the sentinel) |
| target-negative | reference + the study-controls target-negative patch | `run-a15a1c7fb10d4aa8` | 10.0 | True | `disable and enable edit the file` |
| alternative | skeleton + the study-controls alternative tree | `run-2edae80190e148f1` | 100.0 | True | none |

## Pack 1.3.0 authoring change (2026-09-26)

At the benchmark author's direction, the `crafting permissions hide recipes from unauthorized players` server checkpoint was removed to lower task difficulty. The task and reference plugin remain unchanged; catalog, Harbor manifest, clause map, case-contract table, and public hidden-coverage summary now list the remaining 18 cases.

| Control | Run | Outcome |
| --- | --- | --- |
| reference (`solution/after`) before checkpoint removal | `run-584c4b4f4e4843a7` | Paper 1.21.11 build 132; 18/19 cases passed. All 18 cases retained in pack 1.3.0 passed; the removed case failed with a `ClassCastException` in its test inventory setup. Offline Maven build passed. |
| NOP (unchanged skeleton), pack 1.3.0 | `run-c6ecde38476d4369` | Paper 1.21.11 build 132; 1/18 passed (sentinel only), 17 failed; complete negative control |

The cache-built verifier image contains the current suite and matching task manifest, and its build used `--network=none`. Catalog, manifest and task TOML case counts agree at 18; `git diff --check` passed.
