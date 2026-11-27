# mindustry/mindustry-core/data-patch-regressions — E0 notes

Repair task over the Mindustry v159.7 game sources (GPL-3.0). Upstream provenance and the
defect analysis are in `benchmarks/mindustry-core/private/harbor/data-patch-regressions/NOTES.md`.

## Roles

- 9 cases: 3 `target`, 3 `preserved`, 1 `runtime-sentinel` (all `server:`), 2 `static` (`check:submission-shape`, `check:offline-build`).
- Every public expected-behaviour clause is asserted by at least one target or preserved case
  (`clause-map.json`); the scope clause (changes stay in the compiled source roots) is `weak`.

## Controls (real evaluator, 2026-09-24)

Each control was evaluated with `rhenium run` on the prepared runtime; patches apply with
`patch -p1` inside `mindustry/`, trees are copied over it.

| control | kind | what it is | run | score | failed cases | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-635837b9fcfe4d59` | 10.0 | `a server-defined item can be used by a patch`; `patching a build tower also changes the drones it builds with`; `a patch for another planet is neither applied nor listed` | admissible |
| `reference` | reference | starter + `solution/after`, three runs | `run-7305d0e4ad074730`, `run-d0891aed0f734fc7`, `run-191fa39c14364ba3` | 100.0, 100.0, 100.0 | none | admissible |
| `target-negative-speed-only` | target-negative | reference, but a patched build tower only passes its build speed to the builder unit | `run-fab80952a1b840d9` | 10.0 | `patching a build tower also changes the drones it builds with` | admissible |
| `compat-negative-servers-drop-restricted-patches` | compat-negative | reference plus a dedicated server that drops every planet-restricted patch | `run-6f6a4ed570274c90` | 10.0 | `a planet-restricted patch applies on its planet` | admissible |
| `alternative-a` | alternative | own repair: patch sets applied by a separate method after custom content and skipped sets removed afterwards; build tower afterPatch copies its stats to the builder unit | `run-695cbf77e59e46f1` | 100.0 | none | admissible |
