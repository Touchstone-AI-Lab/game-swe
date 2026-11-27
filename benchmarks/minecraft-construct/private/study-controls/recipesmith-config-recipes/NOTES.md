> E0 controls for pack version 1.0.0 (2026-09-24).

# E0 notes: minecraft/construct/recipesmith-config-recipes

Private maintenance material. Never copy into an attempt or a model workspace.

Layout: construct task. The workspace holds `plugin/` (the frozen `pom.xml`, a minimal `plugin.yml` and an empty main class). Controls use `root` = `plugin`: patches apply with `patch -p1` from `/app/plugin`, the `alternative` tree is copied over `/app/plugin`. Reference = skeleton + `solution/after/` (`solution/solve.sh`).

## Case roles

19 cases: 2 `static` (`check:submission-shape`, `check:offline-build`), 1 `runtime-sentinel` (`server:Recipesmith is enabled`), 16 `target`, 0 `preserved`. A construct task has no preserved contract: the skeleton does nothing, and every target case fails on it.

## Controls

| control | kind | what it is | observed | admissible |
| --- | --- | --- | --- | --- |
| `starter` | starter | the unchanged skeleton | complete, fails every target case, passes the sentinel and both static checks (10/100) | yes |
| `reference` | reference | skeleton + `solution/after` | 17/17, 100 | yes |
| `target-negative-enable-waits-for-reload` | target-negative | reference whose `/recipes enable` only edits the file | fails exactly `disable and enable edit the file` (the lantern cannot be crafted after `enable`) | yes |
| `alternative` | alternative | independent plugin written from the exam alone | 17/17, 100 | yes |

## The alternative

Written by an isolated agent that read only the public exam and the skeleton (no suite, reference or other task), compiled against the pinned API and never run on a server before the control run: ten classes: a `RecipeKind` enum, a NUL path separator so dotted ids stay invalid ids, registration without resending and one `Bukkit.updateRecipes()`, in-memory bookkeeping of removed vanilla recipes. It scored 100 on its first run. The agent listed the points it found underspecified: the case of `type` values and of vanilla keys (kept exact; the suite uses lower case), tags inside material lists (accepted); no case depends on them.

## Runs

Engine: real Paper 1.21.11 build 132 in the prepared verifier image, `--network=none`, through `rhenium run minecraft/construct/recipesmith-config-recipes` (runtime `paper-1.21.11-132-construct`).

| control | run | score | complete | failed cases |
| --- | --- | --- | --- | --- |
| reference-1 | `run-46f9e33d5dd04f15` | 100.0 | True | none |
| reference-2 | `run-ec5bd86de76b478b` | 100.0 | True | none |
| reference-3 | `run-e4578f888bf74b2c` | 100.0 | True | none |
| starter | `run-932b40cfb3d24f35` | 10.0 | True | all but the sentinel |
| target-negative | `run-a15a1c7fb10d4aa8` | 10.0 | True | `disable and enable edit the file` |
| alternative | `run-2edae80190e148f1` | 100.0 | True | none |

Authoring runs before the Hub runs (same server image and suite, the trusted javac build instead of Maven) gave the same outcomes for the reference, the target-negative and the alternative.
