# dst/core/dst-fixed-bundle-regressions — E0 notes

Repair task over the vendored DST Fixed server mod (Apache-2.0) at upstream commit `841cd02d5d`, with Show Bundle and Inventory Unwrap enabled. The starter reverts four upstream fixes: `f46026c` ("preserve surprise gift behavior"), `e71c729` ("keep live creatures in inventory when unwrapping"), `77f8107` ("preserve special bundle items") and `c28d65c` ("Fix show bundle crashes with bundles generated from some sources"). Since task version 2.0.0 it also reverts the `show_spoiled` part of `b982089` ("Fix show_spoiled not working correctly"), so preview entries never carry the flag that the mod's `sbitemtile` draws the spoiled background from. The control `target-negative-surprises-still-held` (starter plus every fix but the surprise fix) was rebased onto the new starter and now also contains that fix. The reference is the upstream tree.

## Roles

- 15 cases: 6 `target`, 7 `preserved`, 1 `runtime-sentinel`, 1 `static`.
- Every exam clause is asserted.
- Known limits of the suite are listed under `known_issues` in `clause-map.json`.

## Version 2.0.0 validation (real dedicated server, networkless)

Run on 2026-10-28 on the Linux x86_64 lab host. The starter (`nop`) and the reference (`oracle`) ran through `private/harbor/scripts/validate-task.sh`, and every control ran on the same per-task Harbor verifier image. That image is built from the task's `tests/` on `gcb-dst-dedicated-verifier:24700372` (Steam app 343050, build 24700372) and runs the repository's evaluator against the real dedicated server without network. These runs have no Hub run ids: `rhenium run` was not repeated for 2.0.0, and the managed runtime was not prepared again.

| run | result |
| --- | --- |
| starter (`nop`) | 10; complete; fails exactly the 6 target cases |
| reference (`oracle`) | 100; complete; all 14 server cases pass |

| control | kind | result |
| --- | --- | --- |
| `target-negative-preview-left-broken` | target-negative | 10; fails only `the preview of a bundle the game wraps from prefab names lists every item` and `a saved bundle with a blank preview shows its items after loading` |
| `target-negative-surprises-still-held` | target-negative | 10; fails only `a surprise gift opened from the inventory releases its creature` |
| `target-negative-rot-background-dropped` | target-negative | 10; fails only `the preview shows Rot on the spoiled background it has in the inventory` |
| `compat-negative-drops-unpickable-items` | compat-negative | 10; every target passes; fails only `moongleam from a held bundle goes into the player's inventory` |
| `compat-negative-every-slot-spoiled` | compat-negative | 10; every target passes; fails only `the preview keeps fresh food's spoilage and leaves other items on a plain slot` |
| `alternative-a` | alternative | 100; all 14 server cases pass |

## Version 1.0.0 record (superseded)

The runs below graded the 12-case suite of task version 1.0.0 through `rhenium run`.

### Two-way validation (real dedicated server through `rhenium run`, networkless)

| run | run id | result |
| --- | --- | --- |
| `starter` | `run-4d375079026944d9` | 10; fails exactly the 5 target cases |
| `reference-r1` | `run-42730937bfbe4003` | 100; admissible |
| `reference-r2` | `run-ae843d265d8e4059` | 100; admissible |
| `reference-r3` | `run-595aa45485a2415e` | 100; admissible |

The three reference runs gave identical case outcomes.

### Controls (real dedicated server through `rhenium run`, networkless)

| control | kind | what it is | run id | result |
| --- | --- | --- | --- | --- |
| `target-negative-preview-left-broken` | target-negative | Reference with Show Bundle's preview fix reverted: prefab-name bundles and blank saved previews stay broken. | `run-446dfa8671174b94` | 10; fails only `a saved bundle with a blank preview shows its items after loading`; `the preview of a bundle the game wraps from prefab names lists every item`; admissible |
| `target-negative-surprises-still-held` | target-negative | Starter plus the preview fix and both unwrap events, but surprise gifts are still given to the inventory. | `run-559e3041ee2a4526` | 10; fails only `a surprise gift opened from the inventory releases its creature`; admissible |
| `compat-negative-drops-unpickable-items` | compat-negative | Reference with the upstream intermediate predicate of e71c729: every item that cannot be picked up and is not alive is dropped, which also drops Moongleam. | `run-1248bf4d0b634786` | 10; every target passes; fails only `moongleam from a held bundle goes into the player's inventory`; admissible |
| `alternative-a` | alternative | Independent fix: surprises detected by their SetCreatureSurprise method and events pushed after placement; prefab names resolved in a separate pass; stale previews found by missing prefabs. | `run-c6a5fd45491349dd` | 100; admissible |
