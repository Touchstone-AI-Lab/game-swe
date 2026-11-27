# mindustry/mindustry-core/payload-and-save-regressions — E0 notes

Repair task over the Mindustry v159.7 game sources (GPL-3.0). Upstream provenance and the
defect analysis are in `benchmarks/mindustry-core/private/harbor/payload-and-save-regressions/NOTES.md`.

## Roles

- 12 cases: 3 `target`, 6 `preserved`, 1 `runtime-sentinel` (all `server:`), 2 `static` (`check:submission-shape`, `check:offline-build`).
- Every public expected-behaviour clause is asserted by at least one target or preserved case
  (`clause-map.json`); the scope clause (changes stay in the compiled source roots) is `weak`.

## Controls (real evaluator, 2026-09-24)

Each control was evaluated with `rhenium run` on the prepared runtime; patches apply with
`patch -p1` inside `mindustry/`, trees are copied over it.

| control | kind | what it is | run | score | failed cases | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-49ccb04033ed457d` | 10.0 | `a derelict payload conveyor keeps its payload through a save`; `a builder with more than a thousand queued plans survives a save`; `a unit can set down a carried derelict block near a core` | admissible |
| `reference` | reference | starter + `solution/after`, three runs | `run-30e0d412410b4466`, `run-ac748f0a06fa4a67`, `run-791a22091b5d489a` | 100.0, 100.0, 100.0 | none | admissible |
| `target-negative-disabled-conveyors-sleep` | target-negative | reference, but payload conveyors still skip their whole update while disabled | `run-443cdc90c88a499f` | 10.0 | `a derelict payload conveyor keeps its payload through a save` | admissible |
| `compat-negative-drops-ignore-core-protection` | compat-negative | reference plus payload drops that ignore core protection for every team | `run-07753494365845fd` | 10.0 | `a unit cannot set down an enemy block inside a core's protected area` | admissible |
| `alternative-a` | alternative | own repair: payload placed on its conveyor while loading, only negative plan counts rejected, core protection skipped for derelict drops in the validPlace overload | `run-e789e35ee2444f88` | 100.0 | none | admissible |
