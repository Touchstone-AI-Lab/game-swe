# rimworld/core/research-organized-tab-state — E0 notes

Repair task over Research: Organized's research-tab visibility and persistent research window (MIT, exact upstream fix 4941919 over parent 8d978d5).
The evaluator reports each private assertion as `case:<id>` (from `runtime.caseOutcomes`)
plus the static `check:submission-shape` gate.

## Roles

- 23 cases: 6 `preserved`, 1 `runtime-sentinel`, 1 `setup`, 1 `static`, 14 `target` (3 preserved cases marked `overlap`).
- Weak clauses: delivery (see the clause notes).
- `edited-visibility-preserved`, `selected-project-preserved` and `current-tab-preserved` already pass on the starter, so they guard the fix rather than detect the defect.

## Controls (real RimWorld 1.6.4871 evaluator through the Hub, networkless, Linux x86_64 Docker host)

| control | kind | what it is | run | result |
| --- | --- | --- | --- | --- |
| `starter` | starter | unchanged starter | `run-6b4f699378f146f5` | score 10; fails `closed-view-recomputed` (target), `closed-window-tabs` (target), `collapse-default` (target), `expand-from-combined` (target), `explicit-closed-refresh` (target), `flags-follow-tabs` (target), `hidden-current-tab` (target), `new-tab-default-false` (target), `new-tab-default-true` (target), `open-view-recomputed` (target), `open-window-relayout` (target), `repeated-relayout` (target), `restored-defaults` (target), `selected-project-tab-preferred` (target); admissible |
| `reference` | reference | `solution/after` copied over the starter | `run-b6fe9cb17e2640fd` | score 100; every case passes; admissible |
| `target-negative-no-resize` | target-negative | reference that never rebuilds the native per-tab flag storage after re-indexing | `run-e1445a75a98c4e3b` | score 10; fails `collapse-default` (target), `expand-from-combined` (target), `flags-follow-tabs` (target), `new-tab-default-false` (target), `new-tab-default-true` (target), `repeated-relayout` (target), `restored-defaults` (target); admissible |
| `target-negative-stale-view` | target-negative | reference that keeps the window's stale cached view width | `run-60936b6699e149a5` | score 10; fails `closed-view-recomputed` (target), `open-view-recomputed` (target); admissible |
| `target-negative-open-window-only` | target-negative | reference that refreshes only a research window open on the window stack | `run-75c767f1633f4c3f` | score 10; fails `closed-view-recomputed` (target), `closed-window-tabs` (target), `explicit-closed-refresh` (target), `hidden-current-tab` (target), `selected-project-tab-preferred` (target); admissible |
| `compat-negative-eager-flag-map` | compat-negative | reference that creates the native flag map itself, all hidden, before the game does | `run-ca271812376c4d53` | score 10; fails `uninitialized-flags` (preserved); admissible |
| `alternative-a` | alternative | own fix: defName-keyed snapshot, freshly sized native map, window from the Research main button | `run-438925d0e12d41aa` | score 100; every case passes; admissible |

Recorded on 2026-10-29 with `rhenium-study e0 run`, in a study directory of its own on the Lab host.
The task's own acceptance controls (three reference runs, base, independent no-op and the five
authored negatives) are recorded in `private/harbor/research-organized-tab-state/validation/controls.json`.
