# dst/core/glassic-api-regressions — E0 notes

Repair task over the vendored Glassic API library mod (Apache-2.0) at upstream commit `795af813e0`. The starter reverts `bd4c073` (a sorted recipe's old slot set to nil, leaving a gap in the filter) and `234b02c` (the spawn-request clean-up removes every character with mod skins, including base-game ones), adapted to the current file layout (`utils/skinhandler.lua`). Since task version 2.0.0 it also reverts `2a96834` ("Fix a crash": `AnimState:GetSkinBuild` returns nil for an unskinned entity and raises during its removal), `6721c64` (the skin inventory lists mod skins whatever their test says) and the skin-selection part of the base commit `795af81` (the `CheckOwnership` replacement inside `DefaultSkinSelectionPopup.GetSkinsList` names its inventory argument `self` again, so the popup's character is never seen). The reference is the upstream tree.

## Roles

- 16 cases: 8 `target`, 6 `preserved`, 1 `runtime-sentinel`, 1 `static`.
- Clauses that are not fully asserted: `expect-sort-order` (weak: Asserted for RecipeSortAfter and RecipeSortBefore with an explicit filter on TOOLS; sorting across all filters (no filter argument) is not exercised); `expect-plain-spawn` (weak: Asserted before any mod skins are registered); `expect-mod-borrowed` (weak: The request's result and the list afterwards are asserted; membership during the request is not observed); `expect-exclusive` (weak: Checked for one item (the axe) and two characters (Wendy and Wilson)).
- Known limits of the suite are listed under `known_issues` in `clause-map.json`.

## Version 2.0.0 validation (real dedicated server, networkless)

Run on 2026-10-28 on the Linux x86_64 lab host. The starter (`nop`) and the reference (`oracle`) ran through `private/harbor/scripts/validate-task.sh`, and every control ran on the same per-task Harbor verifier image. That image is built from the task's `tests/` on `gcb-dst-dedicated-verifier:24700372` (Steam app 343050, build 24700372) and runs the repository's evaluator against the real dedicated server without network. These runs have no Hub run ids: `rhenium run` was not repeated for 2.0.0, and the managed runtime was not prepared again.

| run | result |
| --- | --- |
| starter (`nop`) | 10; complete; fails exactly the 8 target cases |
| reference (`oracle`) | 100; complete; all 15 server cases pass |

| control | kind | result |
| --- | --- | --- |
| `target-negative-sort-leaves-hole` | target-negative | 10; fails only the three sorting cases that check for holes |
| `target-negative-vanilla-character-still-removed` | target-negative | 10; fails only `a vanilla character that receives mod skins stays selectable` |
| `target-negative-unowned-skins-listed` | target-negative | 10; fails only `a mod skin that its test refuses is left out of the inventory` |
| `target-negative-skin-build-fallback-unguarded` | target-negative | 10; fails only `an item without a skin reports an empty skin build` and `an item's skin build can be read while the item is removed` |
| `target-negative-popup-character-shadowed` | target-negative | 10; fails only `a character-exclusive skin is not offered to another character` |
| `compat-negative-borrowed-characters-kept` | compat-negative | 10; every target passes; fails only `a mod character that receives mod skins is only borrowed into the base character list` |
| `compat-negative-skin-build-fallback-removed` | compat-negative | 10; every target passes; fails only `an item with a mod skin reports the mod skin's build` |
| `alternative-a` | alternative | 100; all 15 server cases pass |

## Version 1.0.0 record (superseded)

The runs below graded the 9-case suite of task version 1.0.0 through `rhenium run`.

### Two-way validation (real dedicated server through `rhenium run`, networkless)

| run | run id | result |
| --- | --- | --- |
| `starter` | `run-6a26d61f176240ac` | 10; fails exactly the 4 target cases |
| `reference-r1` | `run-695af0a2274046d2` | 100; admissible |
| `reference-r2` | `run-8c0e64555ac84482` | 100; admissible |
| `reference-r3` | `run-ae75498cf25e4f68` | 100; admissible |

The three reference runs gave identical case outcomes.

Incomplete evaluations are not evidence either way and were rerun; in each, the congested Docker daemon did not create the verifier container within the 300 s timeout or the container produced no trusted report: `run-28c2916970dc4755` (starter).

### Controls (real dedicated server through `rhenium run`, networkless)

| control | kind | what it is | run id | result |
| --- | --- | --- | --- | --- |
| `target-negative-sort-leaves-hole` | target-negative | Reference with bd4c073 reverted: the moved recipe's slot is set to nil and leaves a gap. | `run-6b10590d00d240a4` | 10; fails only `sorting a recipe after a later one keeps every recipe of the filter listed`; `sorting a recipe before an earlier one keeps every recipe of the filter listed`; `sorting a recipe to the end of a filter keeps every recipe listed`; admissible |
| `target-negative-vanilla-character-still-removed` | target-negative | Reference whose clean-up removes every character with mod skins instead of only the ones it added. | `run-7aba8e13d30045eb` | 10; fails only `a vanilla character that receives mod skins stays selectable`; admissible |
| `compat-negative-borrowed-characters-kept` | compat-negative | Reference that keeps Wilson listed by deleting the clean-up loop, which leaves borrowed mod characters in DST_CHARACTERLIST. | `run-d518d0ec48744b5e` | 10; every target passes; fails only `a mod character that receives mod skins is only borrowed into the base character list`; admissible |
| `alternative-a` | alternative | Independent fix: the sort shifts the following recipes down instead of calling table.remove; the clean-up removes only the characters recorded in the starter's own added list. | `run-9eda921044bd49b3` | 100; admissible |
