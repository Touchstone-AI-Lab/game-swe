# dst/core/dsmmo-release-regressions — E0 notes

Repair task over the vendored DsMMO server mod (Apache-2.0) at upstream commit `783ab7baff`. The starter reverts `0d7c62d` and `6d1351f` ("Crash when attacked by darkness"), `c957bd5` ("fixed Crash when using DIG as a beaver") and the crash fixes of `783ab7b` ("fixed: various crashes"). Since task version 2.0.0 it also reverts two fixes of `9b93e05` ("several crash-fixes"): the Exp-gain check in `DsMMO:OnLoad`, so a save made under another Exp-gain setting keeps its stale levels, and the argument check of the `#dsmmo eat` command, so an incomplete command raises a Lua error. The reference is the upstream tree.

## Roles

- 16 cases: 7 `target`, 7 `preserved`, 1 `runtime-sentinel`, 1 `static`.
- Clauses that are not fully asserted: `expect-attack-exp` (weak: Asserted with a creature attacker only; the no-attacker branch is only checked for errors and bees).
- Known limits of the suite are listed under `known_issues` in `clause-map.json`.

## Version 2.0.0 validation (real dedicated server, networkless)

Run on 2026-10-28 on the Linux x86_64 lab host. The starter (`nop`) and the reference (`oracle`) ran through `private/harbor/scripts/validate-task.sh`, and every control ran on the same per-task Harbor verifier image. That image is built from the task's `tests/` on `gcb-dst-dedicated-verifier:24700372` (Steam app 343050, build 24700372) and runs the repository's evaluator against the real dedicated server without network. These runs have no Hub run ids: `rhenium run` was not repeated for 2.0.0, and the managed runtime was not prepared again.

| run | result |
| --- | --- |
| starter (`nop`) | 10; complete; fails exactly the 7 target cases |
| reference (`oracle`) | 100; complete; all 15 server cases pass |

| control | kind | result |
| --- | --- | --- |
| `target-negative-self-attack-still-retaliated` | target-negative | 10; fails only `a player who hurts themselves is not chased by their own bee` |
| `target-negative-stale-levels-kept` | target-negative | 10; fails only `a save made under another Exp-gain setting gets its levels recalculated` |
| `compat-negative-haunt-branch-removed` | compat-negative | 10; every target passes; fails only `Ghosty fireflies turn a haunted evil flower into fireflies` |
| `compat-negative-eat-command-removed` | compat-negative | 10; every target passes; fails only `the full #dsmmo eat command still exchanges experience for sanity` |
| `alternative-a` | alternative | 100; all 15 server cases pass |

## Version 1.0.0 record (superseded)

The runs below graded the 12-case suite of task version 1.0.0 through `rhenium run`.

### Two-way validation (real dedicated server through `rhenium run`, networkless)

| run | run id | result |
| --- | --- | --- |
| `starter` | `run-55a6a259dc114bd4` | 10; fails exactly the 5 target cases |
| `reference-r1` | `run-013bd4d7a2ca4964` | 100; admissible |
| `reference-r2` | `run-42b1cb1e5d0246ae` | 100; admissible |
| `reference-r3` | `run-ac62b8437a834714` | 100; admissible |

The three reference runs gave identical case outcomes.

### Controls (real dedicated server through `rhenium run`, networkless)

| control | kind | what it is | run id | result |
| --- | --- | --- | --- | --- |
| `target-negative-self-attack-still-retaliated` | target-negative | Reference without the attacker-is-the-player check: a player who hurts themselves still gets a bee. | `run-58560bff13444f7d` | 10; fails only `a player who hurts themselves is not chased by their own bee`; admissible |
| `compat-negative-haunt-branch-removed` | compat-negative | Reference that silences the haunt error by deleting the whole HAUNT branch, which also removes Ghosty fireflies. | `run-cc93b6fdde01488d` | 10; every target passes; fails only `Ghosty fireflies turn a haunted evil flower into fireflies`; admissible |
| `alternative-a` | alternative | Independent fix: nil-safe event data, early return for missing or self attackers after the experience, a health-and-combat test for Explosive touch, a local tool check for digging. | `run-663722ae965149ef` | 100; admissible |
