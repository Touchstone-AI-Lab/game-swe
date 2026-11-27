# Terraria task 04 design: Quality of Terraria Space Wand authority and geometry

## Candidate and provenance

- Upstream: `https://github.com/487666123/ImproveGame`
- Frozen revision: `284fa78849f2234e70300f101a92a36db34b256d`
- Upstream version: Quality of Terraria 1.8.3
- License: MIT, Copyright (c) 2022 局长
- Platform: Terraria 1.4.4.9 and the tModLoader 1.4.4 stable API
- Production path: the Space Wand derives tile sets from player drag geometry,
  applies tile placement/replacement and inventory consumption, and executes
  multiplayer requests on the receiving authority before synchronizing every
  affected tile neighborhood.

The feature was selected from active upstream history. Commit
`0e52de3b0554f9bbc5120e64f83a4aa7338b158c` is an explicit multiplayer
Space Wand synchronization fix. The frozen revision retains that fix and the
same shape, operation, and packet paths.

## Operator reports to preserve in the task contract

1. Eight-way line direction is deterministic at sector boundaries; line
   selection includes both endpoints, never yields an out-of-world tile, and
   stops when its clipped path reaches the safe world margin.
2. Corner selection follows vertical-first or horizontal-first control state,
   visits the shared corner once, and never resumes another leg after clipping.
3. Filled and outline rectangles respect their documented 60/160 limits,
   include each selected tile once for degenerate dimensions, and clip to the
   same safe world margin.
4. Filled, thin-outline, and connected-outline circles respect their 49.5/99.5
   radius limits, contain no duplicates, and exclude unsafe border tiles.
5. A successful operation consumes exactly the resource actually used and
   aggregates one count per consumed item type. Failed placement, forbidden
   replacement, insufficient pick power, or missing tile-wand ammo is atomic.
6. Replacement and slope behavior must preserve the existing tile rules:
   matching tiles may be reshaped without consumption; rope cannot replace a
   platform or rail; successful replacement/place consumes once; and a solid
   placement only resets the below slope when that tile is outside the same
   selection.
7. Packet receive treats sender and serialized enum/coordinate fields as
   untrusted, performs no work for an invalid request, executes each deduplicated
   tile bottom-to-top for gravity-sensitive placements, sends the required
   synchronization coverage, reports consumed resources to the sender, and
   broadcasts at most one dig sound when something changed.

## Expected repair shape

The retained production files are:

- `Content/Items/SpaceWand.Shapes.cs`
- `Content/Items/SpaceWand.Operations.cs`
- `Content/Packets/SpaceWandOperation.cs`

A correct repair must coordinate geometry, tile mutation, inventory accounting,
and network authority. Public types and method signatures remain unchanged.
Small definitions from unretained ImproveGame partials and engine types are
provided by projection stubs; they contain no replacement shape, operation, or
packet implementation.

## Evaluation boundary

The evaluator compiles the three production files directly in a .NET 8 source
projection. Private engine doubles record world mutation, inventory, packet,
sound, and tile-sync effects. They invoke `GetSelectedTiles`, `OperateTile`,
and the real `SpaceWandOperation.Receive`/send-coverage path. Public smoke
compilation uses an independent stub copy and contains no behavioral oracle.

## Difficulty and fairness review

This is a hard task because the same selection must agree across lazy geometry
enumerators, a deduplicated operation set, Terraria replacement rules,
inventory/tile-wand consumption, server execution order, and several tile-sync
strategies. Failures at a clipped corner, zero-width rectangle, circle border,
or malicious packet are not repaired by one generic bounds check.

The task remains fair: the prompt names geometry limits, clipping, ordering,
authority, atomicity, and synchronization effects. The visible stubs document
the platform calls and record their effects. No assertion relies on rendering,
real-time input, undisclosed Terraria assets, or a hidden item ID. Difficulty
comes from one real cross-file feature, not from unrelated algorithms.

## Design and implementation verdict

Accepted and locally audited. The 46 named contracts cover seven independent
behavior groups and match the executable case list one-for-one. The frozen
starter passes 31/46 cases while the oracle passes 46/46; both source
projections compile with zero warnings and zero errors. The oracle diff is
regenerated from repository-relative paths so the validation artifact is
portable. The task is a mature mod feature with documented multiplayer defect
history, three interacting production files, and a faithful source-projection
boundary.

## Contract correction (2026-09-22)

The original prompt described all half-sector ties as clockwise while the
frozen source and test preserved `+22.5° -> RightDown` and `-22.5° -> RightUp`.
It also did not state the oracle's no-dig-sound rule for reshaping a matching
tile. Both requirements are now explicit in the public exam and case map; a
fresh strict attempt is required for the corrected revision.

## Revision 2: failed fallback must restore terrain

Audit of the oracle found a genuine gap in the prompt's existing atomicity rule: if replacement fails,
the fallback kills the old tile, and the subsequent place also fails, the
oracle left the old tile absent. The corrected oracle restores its type and
block shape. Two new cases exercise direct operation and server packet
behavior. The starter is 31/48 and oracle 48/48. This fixes benchmark
correctness. An independent exact-revision run is required.

## Revision 3: consumption veto is not placement veto

The ordinary tModLoader `ConsumeItem` hook may suppress stack consumption
without cancelling an already valid tile use. The frozen production path
places first and calls `TryConsumeItem` afterward, so this behavior is
grounded in the same operation. The public contract now distinguishes
successful placement from successful resource consumption for ordinary
materials and tile-wand ammo; the packet path still syncs the changed tile
and sound but reports no consumed resource. Three new cases cover these
cross-state outcomes. The corrected oracle is 51/51 and starter 33/51. A
fresh revision-3 strict run is required.

## Revision 4: transactional mutation ledger

The prior authority path still conflated `playSound` with world mutation. That
misses a matching-tile slope reshape or an external below-tile slope reset,
because both change terrain without consuming an item or playing a dig sound.
It also synchronizes every selected coordinate after any successful placement,
including failed and already-matching no-ops. Revision 4 records the exposed
state of each target and possible below-tile support around the real
`OperateTile` call, derives an exact committed dirty set, and bases outline or
filled synchronization on that set. Partial inventory success, silent slope
changes, restored failures, deterministic packet order, resource reporting,
and sound now remain independent state dimensions.

The same revision closes two connected transaction gaps. Engine placement and
replacement primitives are allowed to change exposed tile fields before
reporting failure, so the operation snapshots and restores `HasTile`,
`TileType`, and `BlockType`; a false replacement is restored before the
kill-then-place fallback observes it. Forbidden replacement and denied pounding
cannot reshape the target. Finally, all public shape helpers reject non-finite
vectors and use overflow-safe conversion for extreme finite endpoints, keeping
the intended drag quadrant and existing world/size limits.

Sixteen new cases exercise these interactions, bringing the exact revision to
67 cases in ten groups. The frozen starter passes 34/67 and the oracle passes
67/67.

## Revision 5: postcondition journals and request authentication

Revision 4 still trusted the Boolean returned by `WorldGen.PlaceTile` and
`WorldGen.ReplaceTile`. That is not a sound engine transaction boundary: the
official tModLoader documentation explicitly says the `PlaceTile` return does
not reliably describe success and recommends checking the target coordinate.
The new contract therefore commits only when the target actually contains the
requested tile type. False-with-postcondition is a success; true-without-
postcondition is a failure. Replacement restores its baseline before deciding
whether to enter the kill/place fallback, and the fallback uses the same rule.

The old three-field target snapshot was also narrower than real tile mutation.
Revision 5 captures the clipped 3-by-3 neighborhood before `CanPlace` and
restores seven exposed fields (`HasTile`, `TileType`, `BlockType`, both frame
coordinates, tile color, and actuation) on every failed path. This covers
loader hooks, placement/replacement primitives, framing, and local neighbor
effects without introducing a parallel placement implementation.

At request scope, the packet captures the union of every selected tile's 3-by-3
neighborhood before the first operation and compares final full state after the
batch. Dirty synchronization can therefore include a committed frame-only or
neighbor mutation outside the selected set, while a restored transient does
not leak into packets. Server authority also requires a living,
building-enabled sender who still holds an actual `SpaceWand` mod item.

Fifteen cases across four new groups bring the revision to 82 cases in 14
groups. The oracle passes 82/82 and the frozen starter passes 33/82. Public
starter and oracle smoke builds complete with zero warnings and zero errors.
