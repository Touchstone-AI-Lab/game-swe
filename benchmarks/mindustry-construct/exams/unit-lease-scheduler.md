# Lease-based Unit Task Scheduler

Implement a server-only build-159 plugin that deterministically leases real Mono, Poly and Mega
units to mining, repair and transport tasks. Use a pure Java scheduler plus a Mindustry adapter; no
custom units, blocks, maps, assets, threads, wall-clock time, or external libraries.

## Required files

```text
plugin.hjson
build-reference.sh
src/LeaseScheduler.java
src/UnitLeaseSchedulerPlugin.java
```

## Public core API

```java
LeaseScheduler(Policy policy);
LeaseScheduler(Policy policy, PersistedState state);
Result upsertTask(Task task);
Result registerUnit(UnitRecord unit);
Result heartbeat(String leaseId, int unitId, long tick);
Result complete(String leaseId, int unitId, long tick);
Result removeUnit(int unitId, long tick);
Result cancelTask(String taskId, long tick);
TickReport tick(long tick);
Snapshot snapshot(long tick);
PersistedState save();
```

Expose nested public immutable `Policy`, `Task`, `UnitRecord`, `Lease`, `Result`, `TickReport`,
`Snapshot`, and `PersistedState` records and enums `TaskKind { MINE, REPAIR, TRANSPORT }`,
`TaskStatus { QUEUED, LEASED, COMPLETED, CANCELLED }`, and `UnitKind { MONO, POLY, MEGA }`.
`Policy` components are `(long leaseTicks,long agingTicks,int maximumPriority)`.
`Task` components are `(String taskId,TaskKind kind,int priority,long createdTick,int targetPos,
String itemName,int amount)` and `UnitRecord` components are `(int unitId,UnitKind kind,int teamId,
boolean alive,long revision)`.

The remaining fixed record components and helper methods are:

```java
record Lease(String leaseId,String taskId,int unitId,long grantedTick,
             long heartbeatTick,long expiresTick)
record Result(boolean success,boolean changed,String message,Lease lease)
record TickReport(long tick,List<Lease> assigned,List<Lease> released,Snapshot snapshot)
record Snapshot(long tick,List<Task> tasks,Map<String,TaskStatus> taskStatuses,
                List<UnitRecord> units,List<Lease> leases)
record PersistedState(Policy policy,long lastTick,long nextLeaseSequence,List<Task> tasks,
                      Map<String,TaskStatus> taskStatuses,List<UnitRecord> units,List<Lease> leases)

boolean Result.accepted();        // alias for success
String Result.code();             // alias for message
List<Lease> TickReport.assignments();
List<Lease> TickReport.expirations();
TaskStatus Snapshot.status(String taskId);
```

## Required behavior

- Validate finite monotonic ticks, IDs, priorities, positions, amounts and compatible unit/task
  kinds before mutation; deduplicate requests and stale unit revisions.
- Sort eligible tasks by effective priority with deterministic aging, then creation tick and task
  ID. Sort units by kind capability and unit ID. Results may never depend on hash iteration order.
- One live lease per task and unit. Heartbeats extend only the matching lease. Expiry, death,
  despawn or unit-type replacement releases and requeues exactly once.
- Prevent starvation while preserving explicit priority. Completion and cancellation are
  idempotent. Save/load retains sequencing and never resurrects a completed lease.
- Every returned collection is a fresh immutable deterministic copy.

## Mindustry integration

- Extend `Plugin`; expose `instance()`, `scheduler()`, `exportState()`, and `importState()`.
- Resolve units by server-side ID and confirm team, type, alive state and controller before every
  assignment. Clients may submit only intent IDs.
- Observe `UnitCreateEvent`, `UnitDestroyEvent`, `UnitChangeEvent`, `ResetEvent`, and
  `WorldLoadEvent`; reconcile actual unit changes on the application thread.
- Create real Mono, Poly and Mega units in private tests and apply base-game mining/repair/transport
  controllers without granting impossible commands.
- Persist through a named `CustomChunk` and recover leases only after units exist.

## Metadata

```hjson
name: "support-unit-leases"
displayName: "Lease-based Unit Task Scheduler"
main: "UnitLeaseSchedulerPlugin"
version: "1.0.0"
minGameVersion: 159
```

Private assertions cover ordering, aging, timeout, heartbeat, duplicate requests, death,
reconstruction, reload and real-unit reassignment on a headless server.

## Mindustry build 159 compatibility

`SaveFileReader.CustomChunk` requires these exact methods:

- `void write(java.io.DataOutput output) throws java.io.IOException`
- `void read(java.io.DataInput input) throws java.io.IOException`

Register it with `SaveVersion.addCustomChunk(String, CustomChunk)`.
Do not use `arc.util.io.Reads` or `arc.util.io.Writes` for these methods.
Mindustry build 159 `Plugin` does not declare a `dispose()` lifecycle method.
