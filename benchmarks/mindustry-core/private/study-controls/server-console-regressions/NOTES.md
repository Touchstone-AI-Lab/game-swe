# mindustry/mindustry-core/server-console-regressions — E0 notes

Repair task over the Mindustry v159.7 game sources (GPL-3.0). Upstream provenance and the
defect analysis are in `benchmarks/mindustry-core/private/harbor/server-console-regressions/NOTES.md`.

## Roles

- 12 cases: 4 `target`, 5 `preserved`, 1 `runtime-sentinel` (all `server:`), 2 `static` (`check:submission-shape`, `check:offline-build`).
- Every public expected-behaviour clause is asserted by at least one target or preserved case
  (`clause-map.json`); the scope clause (changes stay in the compiled source roots) is `weak`.

## Controls (real evaluator, 2026-09-24)

Each control was evaluated with `rhenium run` on the prepared runtime; patches apply with
`patch -p1` inside `mindustry/`, trees are copied over it.

| control | kind | what it is | run | score | failed cases | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-ae147d1991044e25` | 10.0 | `pause on and pause off set the requested state`; `host without a map while shuffling is off keeps the console working`; `pardon lets a kicked player connect again`; `player records survive a server restart` | admissible |
| `reference` | reference | starter + `solution/after`, three runs | `run-44e5500cf7b143c8`, `run-071586d83e6f4772`, `run-99580f0240cc44b1` | 100.0, 100.0, 100.0 | none | admissible |
| `target-negative-pause-off-toggles` | target-negative | reference, but pause off still toggles the state | `run-391180f4e3e949ff` | 10.0 | `pause on and pause off set the requested state` | admissible |
| `compat-negative-pause-without-game` | compat-negative | reference plus a pause command that no longer requires a running game | `run-366e12186ca84786` | 10.0 | `pause refuses to run without a game` | admissible |
| `alternative-a` | alternative | own repair: host refuses with an error when shuffling yields no map, pause only changes a differing state, pardon forgives every recorded address, PlayerInfo marked serializable | `run-63afb65d4db74169` | 100.0 | none | admissible |
