# Repair Fargo's Mutant Mod Enchanted Tree transactions

The frozen Fargo's Mutant Mod 3.4 source contains a related cluster of
regressions in the Enchanted Tree feature. Repair the existing production code
without replacing it with a parallel implementation.

Work in these files:

- `Common/Systems/Recipes/MiscRecipeSystem.cs`
- `Content/Items/Tiles/EnchantedTreeSheet.cs`
- `Content/Items/Tiles/EnchantedTreeTileEntity.cs`

Do not change public types or method signatures. Keep the submission
source-only; do not add build output, archives, binaries, or external
dependencies.

## Required behavior

### Insertion is one atomic tile interaction

When an active, living client player right-clicks an empty tree with a
non-favorited held stack:

- store the held item's exact type and prefix;
- consume exactly one item;
- return `true` from the accepted `RightClick` interaction;
- set `CursorInsertCooldown` to 10; and
- create the root fruit only when `IsItemDupable` accepts the stored type.

An empty held stack, a favorited item, an occupied tree, an existing fruit
branch, or server authority must reject insertion without changing the tree or
inventory. Single-player insertion must not send an Enchanted Tree fruit
packet. A multiplayer-client insertion that creates a fruit must send one
packet using the index of the tree's canonical top-left coordinate in
`EnchantedTreeSheet.EnchantedTrees`, even when the clicked tile is another cell
of the multi-tile.

### Removal respects cooldown and restores state once

The stored item cannot be removed while `CursorInsertCooldown` is positive.
Once it reaches zero, a valid right click must:

- spawn exactly one item with the stored type and prefix;
- clear `ItemType`;
- change every live fruit (`despawnTimer == 0`) to the first despawn step while
  leaving an already-despawning fruit's progress unchanged; and
- acknowledge the interaction.

### Build recipe branches at the correct lifecycle boundary

Construct `FargoItemSets.DuplicatableRecipes` in `PostSetupRecipes`, where the
complete recipe table is available. Recipes registered after `PostAddRecipes`
must be visible. Keep one dictionary entry per result and one occurrence of
each eligible ingredient, preserving recipe and ingredient discovery order.

Treat every `PostSetupRecipes` call as a fresh snapshot of the current
`Main.recipe` table. Rebuild the contents so results and ingredients that have
disappeared or become ineligible do not survive a later setup pass. Repeating
the same setup is idempotent. Preserve the identity of the existing static
`DuplicatableRecipes` dictionary while replacing its contents, because other
production code may retain that dictionary reference.

Follow the existing `FargoItemSets.DuplicatableItems` policy:

- directly duplicatable ingredients remain eligible;
- a `MaterialsDupable` result may expose an otherwise ordinary ingredient;
- `NotDupableFromDupable` ingredients remain excluded from that material
  expansion; and
- existing `IsItemDupable` handling for supported Fargo enchant, force, and
  soul items remains intact.

### Keep branch expansion and collapse coherent

Dragging a fruit with no direct child expands it once from
`FargoItemSets.DuplicatableRecipes`: add one child for each recipe entry in
stored order, link every child to the dragged fruit's current list index, and
place it on the next branch layer. A direct child still counts while it is
fading, so repeatedly grabbing its parent must not append duplicate children.

Revisiting a branch that already has a direct child keeps that child but starts
despawning every deeper live descendant of that branch, including descendants
reached through a fading direct child. Do not touch deep nodes belonging to a
different root or sibling branch merely because they have a larger `layer`.
Send one Enchanted Tree fruit packet from a multiplayer client when expansion
or descendant collapse actually changes branch state. Do not send that packet
when the branch is unchanged.

### Treat fruit duplication as one purchase transaction

When a grabbed fruit is dragged more than 100 pixels from its target, release
both the fruit and the player's `grabbedFruit` ownership, and set the fruit's
grab cooldown to 30 before attempting the purchase. The price is twice the
base value in `ContentSamples.ItemsByType`.

If `BuyItem` succeeds, spawn exactly one item with the fruit type and the
tree's stored prefix, mark its `FargoGlobalItem` with the local player in
`Grabbed` and `FromEnchantedTree = true`, and synchronize that spawned item.
If payment fails, charge nothing and create or synchronize no item; the release
and cooldown still apply.

### Preserve and replace persistent/network state

`SaveData`/`LoadData` must retain the stored item type and prefix. `NetSend`
and `NetReceive` must round-trip the stored header and each fruit's order,
type, center, target, velocity, parent index, layer, grab cooldown, and despawn
progress. A received snapshot replaces the previous fruit collection; stale
local fruit must not survive the receive.

`NetReceive` accepts at most 4,096 fruit records. Parse the complete declared
frame before changing `ItemType`, `Prefix`, or `Fruits`. A negative or excessive
count, truncated header/fruit record, or non-finite component of any fruit
center, target, velocity, or despawn timer is `InvalidDataException`. Grab
cooldowns and despawn timers must be non-negative.

Fruit records form an ordered forest. A root points `previousItem` to its own
list index and has `layer == 0`. Every non-root points to an earlier record and
has exactly its parent's layer plus one. Multiple roots are valid. Reject a
snapshot that violates this topology. Preserve the entire previous live state
on every receive rejection, including the fruit-list reference. A valid frame
replaces these three fields once and leaves the reader immediately after its
declared records so a following field remains readable.

Apply the same count, scalar, and ordered-forest validation before `NetSend`
publishes a frame. Invalid sender state must raise `InvalidDataException`
without writing any bytes or changing the writer stream's position or length.
Do not change the successful wire format.

### Keep the global update loop independent

An obsolete coordinate in `EnchantedTrees` may fail to resolve to a tile
entity. That entry must not prevent later valid trees from updating. When the
loop removes an expired fruit, it must still process the fruit that shifts into
the removed index during the same update, including adjacent expired fruit.

Remove expired fruit in place so the `Fruits` list object remains stable, then
restore the ordered-forest invariants for every survivor. Indices after the
removed slot shift down. Children of a removed non-root attach to that removed
node's surviving parent; children of a removed root become roots. Recompute
layers from the resulting parents. If the removed object is the local player's
`grabbedFruit`, clear that ownership reference.

The global coordinate table may contain the same valid tree coordinate more
than once. A tree must still be updated at most once per call: cooldowns,
despawn progress, purchases, and newly armed grab cooldowns each advance for
one logical frame only.

## Public check

Run `python tools/smoke.py` (or `python3` where applicable) to compile the
affected production files in the offline .NET 8 source projection. This
public check contains no behavioral
assertions. Private evaluation uses separate engine test doubles and invokes
the production methods directly. The full profile also compiles submitted
production sources into a verifier mod and runs task-specific sentinels inside
pinned tModLoader `2026.7.3.0` on a Terraria `1.4.4.9` dedicated server.
