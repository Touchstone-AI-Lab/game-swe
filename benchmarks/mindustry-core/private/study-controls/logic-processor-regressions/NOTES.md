# mindustry/mindustry-core/logic-processor-regressions — E0 notes

Repair task over the Mindustry v159.7 game sources (GPL-3.0). Upstream provenance and the
defect analysis are in `benchmarks/mindustry-core/private/harbor/logic-processor-regressions/NOTES.md`.

## Roles

- 13 cases: 4 `target`, 6 `preserved`, 1 `runtime-sentinel` (all `server:`), 2 `static` (`check:submission-shape`, `check:offline-build`).
- Every public expected-behaviour clause is asserted by at least one target or preserved case
  (`clause-map.json`); the scope clause (changes stay in the compiled source roots) is `weak`.

## Controls (real evaluator, 2026-09-24)

Each control was evaluated with `rhenium run` on the prepared runtime; patches apply with
`patch -p1` inside `mindustry/`, trees are copied over it.

| control | kind | what it is | run | score | failed cases | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-2964971c3042486d` | 10.0 | `sensor of an unsupported property yields null`; `format fills a placeholder when the print buffer is full`; `a replaced linked block is reachable under its new name`; `a world processor holding query results can be saved` | admissible |
| `reference` | reference | starter + `solution/after`, three runs | `run-1c5b0ca15bd84dbe`, `run-8be5ba344cd2405f`, `run-5028077495b84b04` | 100.0, 100.0, 100.0 | none | admissible |
| `target-negative-null-property-only` | target-negative | reference, but a failed sensor read is only cleared when the property itself is null | `run-9223591015ac4980` | 10.0 | `sensor of an unsupported property yields null` | admissible |
| `compat-negative-numbers-only-save` | compat-negative | reference plus processors that no longer save object-valued variables | `run-10cf32a632dc4a38` | 10.0 | `processor variables survive a save and reload` | admissible |
| `alternative-a` | alternative | own repair: null in the unsupported sensor branch, rename and re-assemble replaced links, format without the full-buffer guard, query results saved as null by the processor | `run-8bd414efc87749f9` | 100.0 | none | admissible |
