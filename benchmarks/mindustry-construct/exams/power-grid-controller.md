# Power-grid Fault Isolation and Load Shedding Controller

Implement a build-159 server plugin that controls base-game power consumers across network splits
and merges. The pure Java controller must be deterministic and independent of Mindustry globals;
the adapter must operate on real power graphs and buildings.

## Required files

```text
plugin.hjson
build-reference.sh
src/GridController.java
src/PowerGridControllerPlugin.java
```

## Public core API

```java
GridController(Policy policy);
GridController(Policy policy, PersistedState state);
Decision observe(GridSample sample);
Decision split(long parentGridId, List<GridSample> children, long tick);
Decision merge(List<Long> sourceGridIds, GridSample merged, long tick);
Decision removeGrid(long gridId, long tick);
Snapshot snapshot();
PersistedState save();
```

Expose immutable records `Policy(double shedRatio,double restoreRatio,long minimumOffTicks,long
minimumOnTicks)`, `Load(int buildingPos,int priority,double demand,boolean enabled)`, `GridSample(long
gridId,long revision,long tick,double production,double batteryStored,double batteryCapacity,
List<Load> loads)`, `LoadAction`, `Decision`, `GridState`, `Snapshot`, and `PersistedState`, plus enum
`Action { SHED, RESTORE, HOLD }`.

The remaining fixed record components and helpers are:

```java
record LoadAction(int buildingPos, Action action)
record Decision(long gridId,long revision,long tick,Action action,List<LoadAction> actions)
record LoadState(Load load,long changedTick)
record GridState(long gridId,long revision,long tick,double production,
                 double batteryStored,double batteryCapacity,List<LoadState> loads)
record Snapshot(List<GridState> grids)
record PersistedState(List<GridState> grids,List<Long> removedGridIds)

Decision(long gridId,long revision,long tick,List<LoadAction> actions)
static Decision hold(long gridId,long revision,long tick)
GridState(long gridId,long revision,long tick,List<LoadState> loads)
PersistedState(List<GridState> grids)
```

`LoadAction` may contain only `SHED` or `RESTORE`; `HOLD` is represented by an empty action list.
The aggregate `Decision.action` is `SHED` when any shed action exists, otherwise `RESTORE` when any
restore exists, otherwise `HOLD`.

## Required behavior

- Reject NaN, infinity, negative energy, invalid ratios, duplicate buildings, stale ticks/revisions
  and malformed persisted state without changing the previous valid state.
- Shed lowest-importance loads first and restore highest-importance loads first, breaking ties by
  building position. Apply hysteresis and minimum on/off durations exactly at boundaries.
- A decision must be stable for identical samples and must not oscillate under values between the
  shed and restore thresholds.
- Split transfers building history to exactly one child. Merge combines histories without losing
  minimum-time locks. Removed grids cannot later act through stale samples.
- Snapshots and persistence are sorted defensive immutable copies and reload produces the same next
  action sequence.

## Mindustry integration

- Extend `Plugin`; expose `instance()`, `controller()`, `exportState()`, and `importState()`.
- Derive graph identity, production, battery status, consumption and membership from real server
  buildings; never trust client energy or priority values.
- Control only configured base-game consumers by changing their enabled state on the application
  thread. Never disable generators, batteries, cores or unrelated replacement buildings.
- Reconcile graph split/merge and tile changes, `ResetEvent`, `WorldLoadEvent`, and save reload.
- Private tests construct real generators, batteries, nodes and consumers, force shortages and
  topology changes, and verify physical enabled states without oscillation.

## Metadata

```hjson
name: "grid-load-controller"
displayName: "Power-grid Fault Isolation Controller"
main: "PowerGridControllerPlugin"
version: "1.0.0"
minGameVersion: 159
```

## Mindustry build 159 compatibility

`SaveFileReader.CustomChunk` requires these exact methods:

- `void write(java.io.DataOutput output) throws java.io.IOException`
- `void read(java.io.DataInput input) throws java.io.IOException`

Register it with `SaveVersion.addCustomChunk(String, CustomChunk)`.
Do not use `arc.util.io.Reads` or `arc.util.io.Writes` for these methods.
Mindustry build 159 `Plugin` does not declare a `dispose()` lifecycle method.
