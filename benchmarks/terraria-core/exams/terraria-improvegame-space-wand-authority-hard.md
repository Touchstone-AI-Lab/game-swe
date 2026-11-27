# Repair Quality of Terraria Space Wand authority and geometry

The frozen Quality of Terraria 1.8.3 source contains related Space Wand
failures across selection geometry, tile transactions, and multiplayer
execution. Repair the existing production code; do not replace it with a
parallel selection or placement implementation.

Work in these files:

- `Content/Items/SpaceWand.Shapes.cs`
- `Content/Items/SpaceWand.Operations.cs`
- `Content/Packets/SpaceWandOperation.cs`

Keep existing public types and method signatures. Keep the submission
source-only; do not add binaries, archives, build output, or dependencies.

## Required behavior

### Generate deterministic, safe selections

Keep the existing eight 45-degree direction sectors and their boundary policy.
Cardinal and diagonal directions must be stable. At the half-sector boundary
on either side of Right, the positive-angle boundary selects RightDown and the
negative-angle boundary selects RightUp, as in the frozen source.

Lines include their valid start and end tiles. Corners use vertical-then-
horizontal order normally and horizontal-then-vertical when `lastControlLeft`
is true; the shared vertex appears once. If either path reaches the unsafe
world margin, stop before that tile and do not resume another corner leg.

Filled rectangles are limited to 60 by 60 selected tiles and outlines to 160
by 160. Degenerate one-row, one-column, or one-tile outlines contain no
duplicates. Filled circles cap their radius at 49.5 tiles and outlines at
99.5 tiles. Preserve the existing thin versus connected-outline neighbor
rules. Every shape must yield unique tiles that satisfy
`WorldGen.InWorld(x, y, 10)`; unsafe starts yield nothing.

Treat both vectors as untrusted even when shape helpers are called directly:
if either vector has a non-finite component, return an empty selection. Very
large but finite endpoints must not overflow tile conversion or distance
arithmetic. They preserve the drag quadrant and the normal size caps; lines
and corners continue in that direction only until the safe world margin.

### Keep placement and inventory changes atomic

Reject an unsafe coordinate before calling tile loaders or indexing the world.
Missing inventory resources or tile-wand ammo, `TileLoader.CanPlace` rejection,
a placement that does not establish its requested tile, forbidden replacement,
insufficient pick power, and the rope-over-platform/rail rule must not consume
an item or leave any local terrain mutation behind.

On success, consume exactly one actual resource and increment that type once
in `itemsConsumed`. A tile wand consumes its ammo rather than the wand itself.
An ordinary non-consumable item is not decremented or reported. An already
matching tile may be reshaped without consumption or a dig sound. Successful replacement, or
the kill-then-place fallback when replacement fails, consumes once.
When `ItemLoader.ConsumeItem` vetoes consumption for an otherwise valid
placement, the tile change still succeeds and synchronizes normally, but the
inventory stack is unchanged and that resource is absent from `itemsConsumed`.
This also applies to tile-wand ammo; a consumption veto is not a placement
veto.
If that fallback kills the old tile but cannot establish the new one, restore
the complete original local terrain state; it is a failed operation and sends
no packets.

Do not trust the boolean returned by `WorldGen.PlaceTile` or
`WorldGen.ReplaceTile` as the commit decision. These engine primitives may
return false after establishing the requested tile or true without doing so.
A placement/replacement commits exactly when the target actually has a tile of
the requested type afterward. Thus a false return with that postcondition is a
success, while a true return without it is a failure. Restore before attempting
the kill-then-place fallback so the kill observes the original state, and judge
the fallback by the same postcondition.

The transaction boundary for one selected coordinate is its clipped 3-by-3
tile neighborhood. Snapshot it before `TileLoader.CanPlace`; a rejecting loader
or failed primitive may have mutated any tile in that neighborhood. Rollback
must restore `HasTile`, `TileType`, `BlockType`, `TileFrameX`, `TileFrameY`,
`TileColor`, and `IsActuated` for every tile in the neighborhood. A forbidden
replacement must not reshape the target. An already matching tile may be
reshaped only when `WorldGen.CanPoundTile` permits it; denial leaves the entire
transaction neighborhood unchanged.

Preserve slope behavior: apply the requested block shape after a successful
solid/platform operation. A solid placement resets the tile below only when
that below tile is not part of the same selected set.

### Validate and execute multiplayer requests authoritatively

`Receive` runs only in server mode. Treat `Sender`, all serialized enum values,
and both vectors as untrusted. Reject an out-of-range, inactive, dead, or
building-disabled sender, and reject a sender whose held item's `ModItem` is
not `SpaceWand`. Also reject an undefined enum or non-finite coordinate. Every
rejection has no world, inventory, sync, or sound side effects.

For a valid request, deduplicate the selected set and operate it in descending
Y order (with deterministic X order inside a row) so gravity-sensitive tiles
are placed bottom-to-top. Before the first operation, snapshot the union of the
clipped 3-by-3 transaction neighborhoods around all deduplicated selected
coordinates. After the whole request, compare every captured tile using all
seven fields listed above. This final-state ledger is independent from resource
use and dig sound: restored transient mutations and final no-ops are not dirty;
a target slope/frame change, external support reset, or committed neighboring
engine mutation is dirty even if it consumes nothing and plays no dig sound.
If inventory runs out partway through a request, only final committed changes
are dirty. If no tile is dirty, send no tile-sync, consumption, or sound packet.
Otherwise:

- outline/line/corner shapes send one 3-by-3 neighborhood per dirty tile, in
  descending Y and then ascending X order;
- filled shapes send one bounding rectangle around the dirty tiles, expanded
  by one tile on every side;
- consumed counts are sent once to the originating sender when nonempty; and
- at most one dig sound is broadcast for the operation.

## Public check

Run `python3 tools/smoke.py` to compile the three production files in the
offline .NET 8 source projection. It contains no behavioral assertions.
Private evaluation uses separate engine doubles and invokes the production
shape, operation, and receive methods directly. The full profile also compiles
submitted production sources into a verifier mod and runs task-specific
sentinels inside pinned tModLoader `2026.7.3.0` on a Terraria `1.4.4.9`
dedicated server.
