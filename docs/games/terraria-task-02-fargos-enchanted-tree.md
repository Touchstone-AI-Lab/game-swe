# Terraria task 02 design: Fargo's Mutant Mod Enchanted Tree transactions

## Candidate and provenance

- Upstream: `https://github.com/Fargowilta/Fargowiltas`
- Frozen revision: `85246bb5e4d3b225028b1bf73cd6d99b81674307`
- Upstream version: Fargo's Mutant Mod 3.4
- License: MIT, Copyright (c) 2024 Fargo Team
- Platform: Terraria 1.4.4.9 and the tModLoader 1.4.4 stable API
- Production path: the Enchanted Tree tile accepts a player's held item,
  persists its type and prefix in a tile entity, exposes recipe-derived fruit,
  and synchronizes the resulting tree state in multiplayer.

The revision was selected after reviewing the upstream history rather than by
searching for an arbitrary class to mutate. Upstream commits
`97f0e061e46f5f5277f0ece3ba2118e4f107d77a` and
`85246bb5e4d3b225028b1bf73cd6d99b81674307` document real fixes to this
same feature: right-click acknowledgement, prefix retention, eligibility,
recipe setup timing, and insertion cooldown behavior.

Revision 2 also follows the production branch/purchase path introduced by
`f45bd3f8601391d6785e6d05b549d5d9221ab9b1`. That upstream change replaced a
special currency with `Player.BuyItem` at twice the base item value, and the
later `97f0e061e46f5f5277f0ece3ba2118e4f107d77a` fix propagated the stored
prefix to fruit-created items. The added contract preserves code already in
the frozen snapshot rather than inventing a new feature.

## Operator reports to preserve in the task contract

1. An accepted insertion must consume exactly one held item, preserve its
   prefix, acknowledge the right click, and arm the cursor-removal cooldown.
   Favorited, empty, occupied, or non-client interactions must not mutate the
   tree or inventory.
2. The click that inserts an item must not immediately enter the removal path;
   removal is unavailable until the cooldown reaches zero. A successful
   removal restores the stored type and prefix exactly once and marks every
   live fruit for despawn.
3. Recipe-derived branches must be built in `PostSetupRecipes`, after the
   complete recipe table exists. Results are unique dictionary keys and their
   eligible ingredients are unique while preserving recipe discovery order.
4. Duplication eligibility must honor the production `FargoItemSets` policy,
   including the distinction between directly duplicatable items,
   material-only items, `NotDupable`, and `NotDupableFromDupable` ingredients.
5. Tile-entity save/load and network round trips must preserve the stored item,
   prefix, fruit ordering, branch links, cooldowns, motion vectors, and despawn
   progress. Receiving a replacement snapshot must not retain stale fruit.
6. A missing tile entity in the global tree list must not prevent later valid
   trees from receiving their cooldown update. Fruit removal must not skip the
   element that shifts into the removed slot.
7. Multiplayer mutations must emit a tree-state synchronization event only
   when observable tree state changes, using the index of the tree's canonical
   top-left coordinate.
8. Dragging an unexpanded fruit creates ordered child branches with correct
   parent indices and layers. Existing direct children, including fading ones,
   prevent duplicate expansion; revisiting a branch collapses only deeper live
   descendants and synchronizes only when state changes.
9. Dragging a fruit beyond its target radius releases player ownership, arms
   the fruit cooldown, and performs one atomic purchase at twice base value.
   Success preserves the stored prefix, origin metadata, and item sync;
   insufficient funds create no item and consume no money.
10. Repeated recipe setup calls represent replacement snapshots, not append
    events. The static dictionary object stays stable while stale results and
    ingredients disappear and current discovery order is rebuilt.
11. Fruit snapshots are ordered forests: roots self-reference at layer zero,
    and every other node references an earlier parent at exactly the next
    layer. Both receive and send validate the bounded graph and its scalar
    state transactionally without changing the successful packet format.
12. Removing a fruit changes every later list index. Runtime removal must
    compact the graph in place, reconnect children deterministically, recompute
    layers, and clear player ownership if it points at the removed object.
    Branch collapse must use ancestry rather than global layer comparisons.
13. The coordinate registry is not guaranteed unique. A repeated coordinate
    must not make one tile entity experience multiple logical updates in the
    same frame.

## Expected repair shape

The broken snapshot will contain a coherent regression cluster in these real
production files:

- `Content/Items/Tiles/EnchantedTreeSheet.cs`
- `Content/Items/Tiles/EnchantedTreeTileEntity.cs`
- `Common/Systems/Recipes/MiscRecipeSystem.cs`

A correct repair is expected to touch all three files. It must reason about
the click transaction in the tile, the persisted/networked state in the tile
entity, and the post-recipe lifecycle in the recipe system. Public types and
method signatures remain unchanged.

## Evaluation boundary

The evaluator compiles the three production files directly in a .NET 8 source
projection. Engine-owned Terraria, XNA, and tModLoader types are represented by
deterministic test doubles, but the transaction, policy, recipe traversal,
serialization, and update-loop code under test is the upstream production
code. The projection is not a substitute implementation and does not claim to
run a tModLoader client or dedicated server.

Private cases will be behavior-named and mapped one-to-one to the prompt.
They will cover successful and rejected insertion/removal, duplicate recipes,
policy boundaries, binary replacement round trips, canonical tree indexing,
missing-tree continuation, adjacent fruit removal, branch expansion/collapse,
paid duplication success/failure, repeated recipe snapshots, canonical graph
validation, in-place graph compaction, ancestry-specific collapse, and
duplicate registry coordinates. Public smoke checks will compile the same
production files with a separate copy of the stubs.

## Difficulty and fairness review

This is a hard repository task because no single local edit repairs it. The
solver must trace state across a tile callback, a persistent/networked tile
entity, a late recipe lifecycle hook, static policy tables, and a global update
loop. Revision 2 also requires reconstructing the fruit-list graph (`previousItem`
and `layer`) and a payment/release transaction that couples cursor ownership,
cooldown, item metadata, and networking. Several symptoms share state
(`ItemType`, `Prefix`, `Fruits`, and `CursorInsertCooldown`) but have different
authority and timing rules.

Revision 4 raises the reasoning burden without adding unrelated APIs. The
solver must maintain an index-addressed forest under deletion, distinguish
ancestry from visual depth, validate the same wire invariant on both sides of
the protocol, rebuild a shared static collection without replacing its object,
and enforce once-per-frame semantics over a duplicate-prone registry. These
repairs interact: an apparently correct `RemoveAt` can silently corrupt later
network frames, and a global layer test can pass simple branch examples while
collapsing an unrelated tree.

The task remains fair: every required rule is stated as an operator-visible
behavior; all affected production files and policy enums are visible; and the
expected fixes follow ordinary C# collection, binary stream, and tModLoader
lifecycle semantics. No score depends on visuals, timing noise, private item
IDs, or an undocumented Terraria implementation detail.

Compared with accepted L4D2 hard tasks, the breadth is similar: three real
files, multiple lifecycle boundaries, serialization plus runtime state, and
negative controls. Difficulty comes from reconstructing one feature's
invariants, not from a large unrelated checklist or an all-or-nothing trap.

## Revision history and design verdict

Accepted for implementation. The feature is real and mature, the defects are
coherent, the intended repair is reviewable, and the source projection can
exercise the production path without bundling tModLoader or proprietary game
assets.

Revision 2 expanded the same production state machine to 41 cases in nine
behavior groups.

Revision 3 adds a single coherent network-transaction invariant rather than
unrelated edge cases. A received snapshot must be parsed and validated before
publication, with a bounded fruit count, complete records, finite spatial
vectors, and preservation of the previous live state (including list identity)
on any malformed frame. The public prompt spells out each rejection class and
the exact `InvalidDataException` contract. Nine new cases exercise distinct
parts of that invariant, including the accepted upper boundary and stream
alignment after a valid frame. This is ordinary defensive binary-protocol
behavior on the same production tile entity, and the oracle can satisfy it
without altering the packet format or unrelated gameplay.

Revision 4 extends four production invariants exposed by the same data model.
It adds 28 cases, bringing the task to 78 cases in 15 independently diagnosable
groups. Twelve cases define canonical sender/receiver graph validation, six
exercise deletion-time parent/layer compaction, five require replacement
recipe snapshots, two distinguish branch ancestry from global depth, and three
enforce once-per-frame registry processing. The cases use distinct state
transitions rather than repeated aliases of one assertion. The oracle preserves
the existing wire format, public APIs, collection identities required by the
prompt, and production update path.
