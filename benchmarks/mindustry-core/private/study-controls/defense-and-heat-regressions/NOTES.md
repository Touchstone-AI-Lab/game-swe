# mindustry/mindustry-core/defense-and-heat-regressions — E0 notes

Repair task over the Mindustry v159.7 game sources (GPL-3.0). Upstream provenance and the
defect analysis are in `benchmarks/mindustry-core/private/harbor/defense-and-heat-regressions/NOTES.md`.

## Roles

- 11 cases: 3 `target`, 5 `preserved`, 1 `runtime-sentinel` (all `server:`), 2 `static` (`check:submission-shape`, `check:offline-build`).
- Every public expected-behaviour clause is asserted by at least one target or preserved case
  (`clause-map.json`); the scope clause (changes stay in the compiled source roots) is `weak`.

## Controls (real evaluator, 2026-09-24)

Each control was evaluated with `rhenium run` on the prepared runtime; patches apply with
`patch -p1` inside `mindustry/`, trees are copied over it.

| control | kind | what it is | run | score | failed cases | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-8399669fde374efd` | 10.0 | `an idle turret keeps its reload interval when it engages`; `a disabled heat redirector passes no heat`; `a shockwave tower spares bullets outside its circular range` | admissible |
| `reference` | reference | starter + `solution/after`, three runs | `run-7c9ac7b5f15840e4`, `run-737ad02c36164c2e`, `run-b01415ea60a0403c` | 100.0, 100.0, 100.0 | none | admissible |
| `target-negative-skip-disabled-update-only` | target-negative | reference, but a disabled conductor still computes heat when its neighbours pull it | `run-1e64cf5ace5d4730` | 10.0 | `a disabled heat redirector passes no heat` | admissible |
| `compat-negative-reset-reload-after-shot` | compat-negative | reference plus a reload counter emptied after every shot instead of keeping the remainder | `run-e6227f4569314416` | 10.0 | `a turret with faster ammunition keeps its average fire rate` | admissible |
| `alternative-a` | alternative | own repair: reload stops once a shot is loaded, disabled conductors zero their heat in updateHeat, squared-distance range test | `run-059f7bc89827492c` | 100.0 | none | admissible |
## Superseded alternative

The first version of `alternative-a` clamped the reload counter to exactly the reload time.
That discards the fractional remainder a turret keeps between shots, so a duo firing
silicon (1.5x reload speed) fired every 14 ticks instead of every 13⅓: it failed the
preserved case `a turret with faster ammunition keeps its average fire rate`
(`run-1ca3625f65e14df6`, 10/100), the same behaviour the compat-negative control encodes.
It was an incorrect repair, not an over-constrained assertion; the current
`alternative-a` stops reload progress once a shot is loaded and keeps the remainder
(`run-059f7bc89827492c`, 100/100).
