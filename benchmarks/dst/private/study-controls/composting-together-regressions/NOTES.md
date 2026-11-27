# dst/core/composting-together-regressions — E0 notes

Repair task over the vendored Composting Together mod (MIT) at upstream commit `16c995051d`, with Attract Fireflies set to `always`. The starter reverts six upstream fixes: `c625623` ("[config] bugfix"), `d3bbe2b` ("use correct production time values"), `0bd23c8` ("fix getstatus"), `4a19750` ("fixes for ondone (load & save)"), `2115763` ("fix save/load bugs") and `b846487` ("Remove ThePlayer-calls"). The reference is the upstream tree.

## Roles

- 14 cases: 8 `target`, 3 `preserved`, 1 `runtime-sentinel`, 1 `setup`, 1 `static`.
- Every exam clause is asserted.
- Known limits of the suite are listed under `known_issues` in `clause-map.json`.

## Two-way validation (real dedicated server through `rhenium run`, networkless)

| run | run id | result |
| --- | --- | --- |
| `starter` | `run-16e59c5e700b47f1` | 10; fails exactly the 8 target cases |
| `reference-r1` | `run-0522285ebb6c438a` | 100; admissible |
| `reference-r2` | `run-7bd28fd35a194667` | 100; admissible |
| `reference-r3` | `run-ef1f956bd0534884` | 100; admissible |

The three reference runs gave identical case outcomes.

## Controls (real dedicated server through `rhenium run`, networkless)

| control | kind | what it is | run id | result |
| --- | --- | --- | --- | --- |
| `target-negative-debug-durations-kept` | target-negative | Reference that still ships the test durations of 0.025 days. | `run-5147e80b32574cf4` | 10; fails only `a small batch takes three days to become compost`; admissible |
| `target-negative-old-load-restoration` | target-negative | Reference whose OnLoad still restores state the old way: idle piles become finished and finished piles lose their harvest tag. | `run-d518192913524618` | 10; fails only `a finished pile still offers its harvest after a save and reload`; `an empty pile stays empty and usable after a save and reload`; admissible |
| `compat-negative-composting-lost-on-load` | compat-negative | Reference whose OnLoad treats a pile that was composting as empty, which fixes the idle-pile report but loses running batches. | `run-f4b3ed7fab8849c4` | 10; every target passes; fails only `a composting pile that is saved and reloaded finishes on time`; admissible |
| `alternative-a` | alternative | Independent fix: named cost locals, production durations, events instead of player speech, ResetBatch on harvest, explicit phase restoration on load, DONE checked first. | `run-207b58c0ba234ca4` | 100; admissible |
