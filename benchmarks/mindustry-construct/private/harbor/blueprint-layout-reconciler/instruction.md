# Blueprint Layout Reconciler

Implement a Mindustry build-159 server plugin that brings a region of the live world to a desired
layout. A deterministic pure-Java `LayoutReconciler` compares the observed buildings with the desired
ones and plans the removals, rotations and placements; the plugin observes real buildings and applies
single operations to the server's world.

## Required files

```text
plugin.hjson
build-reference.sh
src/LayoutReconciler.java
src/BlueprintReconcilerPlugin.java
```

## Exact public core API

All types are nested in the default-package `public final class LayoutReconciler`:

```java
public enum Kind { REMOVE, ROTATE, PLACE }
public record Cell(int x, int y, String block, int size, int rotation) {}
public record Op(int seq, Kind kind, int x, int y, String block, int size, int rotation) {}
public record Pricing(Map<String, Integer> cost, int refundPercent) {}
public record Plan(List<Op> ops, List<Cell> deferred, int kept, int untouched,
                   long spent, long refunded) {}
public record Checkpoint(List<Op> ops, int next) {}

public LayoutReconciler(int width, int height, Pricing pricing);
public static int low(int origin, int size);
public Plan plan(List<Cell> observed, List<Cell> desired, long budget);
public List<Cell> applyTo(List<Cell> observed, List<Op> ops);
public Checkpoint begin(Plan plan);
public Checkpoint advance(Checkpoint checkpoint, Op done);
```

The core is stateless after construction: no call changes the result of a later call, and no
argument list or map is modified. Every returned list is immutable.

### Footprints

A cell is a building whose origin tile is `(x, y)`. Its footprint is the square of `size` by `size`
tiles whose lowest column is `low(x, size)` and lowest row is `low(y, size)`, where
`low(origin, size) = origin - (size - 1) / 2` with Java integer division. This is the footprint the
game gives a building: a size-2 building covers `x..x+1`, a size-3 building `x-1..x+1`, a size-4
building `x-1..x+2`.

### Validation

Throw `IllegalArgumentException` for:

- a constructor `width` or `height` below 1, a null `pricing`, a null cost map, a null or blank
  block name in it, a null or negative cost, or a `refundPercent` outside `0..100`. The cost map is
  copied; changing the caller's map afterwards has no effect;
- in `plan` and `applyTo`: a null list or a null cell; a null or blank block; a `size` outside
  `1..8`; a `rotation` outside `0..3`; a footprint that is not entirely inside
  `0 <= column < width`, `0 <= row < height`; two cells of the same list whose footprints share a
  tile; in `plan` also a negative `budget`, or any observed or desired block without a cost.

### Planning

1. A desired cell **matches** an observed cell with the same `x`, `y`, `block` and `size`. When the
   rotations are equal the cell is kept and counts in `kept`; otherwise the plan has one `ROTATE`
   operation carrying the desired rotation.
2. An unmatched observed cell is removed (`REMOVE`, carrying the observed block, size and rotation)
   when its footprint shares a tile with the footprint of at least one unmatched desired cell.
   Otherwise it is left alone and counts in `untouched`.
3. Every unmatched desired cell is a placement candidate. Candidates are considered larger `size`
   first, then lower `y`, then lower `x`.
4. Funds start at `budget` plus the refunds of all removals; a removal refunds
   `cost * refundPercent / 100` rounded down, and `refunded` is their sum. A candidate whose cost
   is at most the remaining funds becomes a `PLACE` operation and its cost is deducted. A candidate
   that does not fit goes to `deferred` in consideration order, and later candidates are still
   considered. `spent` is the sum of the placed costs. Rotations are free. Removals are planned
   whether or not the desired cells they make room for are deferred. Use `long` arithmetic.
5. `ops` lists every `REMOVE` ordered by lower `y` then lower `x`, then every `ROTATE` in the same
   order, then every `PLACE` in consideration order. `seq` numbers the operations `0, 1, 2, ...`
   in that order.

### Replay

`applyTo` validates `observed` as above and applies `ops` in list order to a copy. `REMOVE` and
`ROTATE` require a cell with the operation's `x`, `y`, `block` and `size`; `ROTATE` sets its
rotation. `PLACE` requires the footprint to be inside the bounds and to share no tile with any
current cell. A null operation list or a null operation is an `IllegalArgumentException`; an
operation whose requirement does not hold is an `IllegalStateException`. The result is sorted by
lower `y` then lower `x`. Planning again from `applyTo(observed, plan.ops())` with the same desired
list and budget `0` yields no operation whose kind is `REMOVE` or `ROTATE`.

### Checkpoints

`begin(plan)` returns `Checkpoint(plan.ops(), 0)`; a null plan is an `IllegalArgumentException`.
`advance` first validates the checkpoint and throws `IllegalArgumentException` for a null checkpoint, null `ops`, a `next` outside
`0..ops.size()`, or operations whose `seq` values are not `0, 1, 2, ...` in list order. For a valid checkpoint it
throws `IllegalStateException` when the checkpoint is complete (`next == ops.size()`) or when `done` does
not equal `ops.get(next)`. Otherwise it returns a new checkpoint with the same operations and
`next + 1`; the argument is unchanged.

## Plugin contract

`BlueprintReconcilerPlugin` is a default-package `public final` class extending
`mindustry.mod.Plugin`:

```java
public BlueprintReconcilerPlugin();
public static BlueprintReconcilerPlugin instance();
public LayoutReconciler core(LayoutReconciler.Pricing pricing);
public List<LayoutReconciler.Cell> observe(int x0, int y0, int x1, int y1);
public boolean apply(LayoutReconciler.Op op, mindustry.game.Team team);
public Object exportState();
```

- `core(pricing)` returns a `LayoutReconciler` for the width and height of the loaded world.
- `observe` reads the server's world. The rectangle is inclusive; `x0 > x1` or `y0 > y1` is an
  `IllegalArgumentException`, and the part outside the world is ignored. It returns one cell for
  every building of any team whose footprint shares a tile with the rectangle: the building's
  origin tile, block name, block size and rotation. A building that covers several tiles is
  returned once. The list is immutable and sorted by lower `y` then lower `x`.
- `apply` performs one operation on the server's world and returns `true`, or changes nothing and
  returns `false`. It returns `false` for a null operation or team, a block name the game does not
  know, a `size` that is not that block's size, a `REMOVE` or `ROTATE` when no building of that
  block has that origin, and a `PLACE` when a footprint tile is outside the world, holds a building
  or is not an air tile. After `REMOVE` no footprint tile holds a building. After `ROTATE` the same
  block stands at the origin with the requested rotation. After `PLACE` a building of that block
  and team stands at the origin with the requested rotation.
- `exportState()` returns an immutable `List<LayoutReconciler.Op>` of the operations `apply` has
  performed since the plugin was created, in order; rejected operations are not listed.

Do not use custom content, external dependencies, wall-clock time, threads or network access.

## Metadata

```hjson
name: "layout-reconciler"
displayName: "Blueprint Layout Reconciler"
main: "BlueprintReconcilerPlugin"
version: "1.0.0"
minGameVersion: 159
```

The evaluator checks footprints and validation, matching, conflict removal and ordering, budget
and refunds, replay, checkpoints, plugin loading, and observation and reconciliation of real
buildings in a real build-159 headless world.
