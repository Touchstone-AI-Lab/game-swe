# Provenance and review receipt

## Frozen source

- Repository: `https://github.com/487666123/ImproveGame`
- Commit: `284fa78849f2234e70300f101a92a36db34b256d`
- Mod version: Quality of Terraria 1.8.3
- License: MIT, Copyright (c) 2022 局长
- Platform context: Terraria 1.4.4.9 and tModLoader 1.4.4 stable API

The retained starter production files preserve the recorded upstream source
content with the benchmark repository's required LF normalization; there is
no behavioral starter delta. Original upstream Git blob IDs are recorded
separately. The upstream license and build metadata are retained. No assets,
Git data, binaries, caches, or build output are packaged.

## Real production path

`SpaceWand.Shapes.cs` creates the exact drag selection used for preview and
execution. `SpaceWand.Operations.cs` mutates `WorldGen` tiles and accounts for
the player's real inventory resource. `SpaceWandOperation.Receive` is the
multiplayer authority path and emits item, sound, and tile synchronization.
Private tests compile and invoke those production methods; the engine doubles
only expose external APIs and record effects.

## Historical grounding

Upstream commit `0e52de3b0554f9bbc5120e64f83a4aa7338b158c` is explicitly titled
"Fix synchronization issue with Space Wand in multiplayer mode" and changes
the retained packet file from single-tile to neighborhood synchronization.
The task extends the same real authority/coverage invariant to validation,
execution order, bounded geometry, and atomic resource changes.

## Fairness and uniqueness

All 82 assertions map to prompt clauses in `case-contracts.tsv`. Limits and
the safe-world margin already appear in the visible production code; the
prompt makes the required boundary and authority behavior explicit. This task
differs from the prior tasks by coupling computational geometry, Terraria tile
replacement rules, inventory consumption, and untrusted packet execution.
The repeated Python runner is documented shared harness infrastructure; the
production files, prompt, oracle, and C# contract suite are independent.

## Revision history

Revision 3 adds atomic failed-fallback restoration and the tModLoader
consumption-veto boundary. The official `ItemLoader.ConsumeItem` contract
permits suppressing stack use without cancelling an item's effect:
https://docs.tmodloader.net/docs/stable/class_item_loader.html .

Revision 4 separates committed terrain mutation from resource use and dig
sound. Sixteen additional cases cover direct non-finite and extreme-finite
geometry, complete rollback of engine primitives that partially mutate before
returning false, replacement/pounding denial, silent target/support slope
changes, exact dirty-set synchronization, partial inventory completion, and
deterministic dirty packet order. These requirements stay on the same three
production files and existing engine contracts. The frozen starter passes
34/67 and the oracle passes 67/67.

Revision 5 replaces boolean-return-based placement commits with actual target
postconditions. This follows the official tModLoader `WorldGen.PlaceTile`
documentation, which explicitly warns that its Boolean result is unreliable
and recommends checking the target coordinates:
https://docs.tmodloader.net/docs/stable/class_world_gen.html . A per-operation
3-by-3 journal now restores all exposed tile identity, slope, frame, paint, and
actuation fields after loader rejection or failed placement. The server packet
captures the union of those neighborhoods before the batch and compares final
full state, so committed framing/neighbor effects synchronize while restored
transients do not. It also binds authority to a living, building-enabled sender
whose held `ModItem` is the actual `SpaceWand`.

Fifteen new cases cover false-with-commit and true-without-commit engine
results, grass and replacement variants, complete loader/placement/fallback
rollback, held-item and player-state authentication, frame-only dirtiness, and
committed or rolled-back neighbor effects. The frozen starter passes 33/82 and
the oracle passes 82/82.
