# Server-authoritative Build Quota Auditor

Implement a server-only Mindustry build-159 JVM plugin that enforces deterministic rolling build
quotas without trusting client identity, team, block, cost, or completion state. The solution must
contain a pure Java state machine and a Mindustry adapter. No external dependencies or custom game
content are allowed.

## Required files

```text
plugin.hjson
build-reference.sh
src/BuildQuotaEngine.java
src/BuildQuotaAuditorPlugin.java
```

## Public core API

`BuildQuotaEngine` must expose constructors `(Policy, PersistedState)` and `(Policy)`, plus:

```java
Decision begin(BuildIntent intent);
Decision finish(String requestId);
Decision cancel(String requestId);
Decision remove(Removal removal);
void playerOffline(String playerId);
Snapshot snapshot(long tick);
PersistedState save();
```

Expose nested immutable public records `Policy(long windowTicks, Map<String,Integer> playerLimits,
Map<String,Integer> teamLimits)`, `BuildIntent(String requestId,String playerId,int teamId,String
blockName,int tilePos,long tick)`, `Removal(String requestId,int teamId,String blockName,int tilePos,
long tick)`, `Decision(String requestId,Status status,boolean accepted,String reason)`, `Reservation`,
`Usage`, `Snapshot`, and `PersistedState`, and enum `Status { REJECTED, RESERVED, COMMITTED,
CANCELLED, REFUNDED }`. Record component order printed here is fixed where shown; document all
remaining component orders are fixed as follows:

```java
record Reservation(String requestId,String playerId,int teamId,String blockName,int tilePos,long tick)
record Usage(String requestId,String playerId,int teamId,String blockName,int tilePos,long tick)
record Snapshot(long tick,List<Reservation> reservations,List<Usage> usage,
                Map<String,Decision> decisions)
record PersistedState(long lastTick,List<Reservation> reservations,List<Usage> usage,
                      Map<String,Decision> decisions)
```

`Snapshot.usages()` and `PersistedState.usages()` must return the same immutable usage list, and
`PersistedState()` must create an empty state at tick zero.

## Required behavior

- Validate identifiers, non-derelict teams, lowercase base-game block names, positions, monotonic
  non-negative ticks, and policy counts before mutation.
- Both policy maps are keyed by lowercase base-game **block name**, not by player or team ID. The
  optional `"*"` key is the fallback for blocks without an exact entry; a missing exact and
  wildcard entry means unlimited. Values are non-negative build counts. `playerLimits` applies
  separately to each `(playerId, blockName)` pair and `teamLimits` to each `(teamId, blockName)`.
- Deduplicate request IDs before accounting. A retry returns the stored decision without charging.
- `begin` atomically reserves both player and team capacity. `finish` commits once; `cancel`
  releases only a live reservation. A `Removal.requestId` is the removal operation's own
  idempotency key; it refunds the earliest committed usage matching team, block and tile exactly
  once, rather than naming the original build request.
- Expire rolling-window usage deterministically by `(tick, requestId)`. Offline players retain
  committed usage but their unfinished reservations are cancelled exactly once.
- Snapshots and persisted state are sorted defensive immutable copies. Loading malformed state
  preserves identifiable recoverable accounting instead of silently granting capacity.

## Mindustry integration

- Extend `mindustry.mod.Plugin`; expose `instance()`, `engine()`, `exportState()`, and `importState()`.
- Derive player UUID, team, block, tile and build state from server objects. Never accept these
  values from a client RPC.
- Correlate `BlockBuildBeginEvent` and `BlockBuildEndEvent`; handle deconstruction, cancellation,
  `PlayerLeave`, `ResetEvent`, and `WorldLoadEvent` without double charge or double refund.
- Reject over-quota construction on the application thread and safely remove only the correlated
  illegal build plan/building. Cancellation must not create resources or affect another builder.
- Persist state through a build-159 `CustomChunk` using `DataInput` and `DataOutput` and recover
  reservations after the world is ready.

## Metadata

```hjson
name: "build-policy-auditor"
displayName: "Server-authoritative Build Quota Auditor"
main: "BuildQuotaAuditorPlugin"
version: "1.0.0"
minGameVersion: 159
```

The private evaluator injects duplicate/cancel/offline/window-boundary sequences, then creates real
players, teams, build plans and buildings on a temporary headless map. It verifies exact accounting,
safe rejection, refund behavior, save reload, and deterministic snapshots.

## Mindustry build 159 compatibility

`SaveFileReader.CustomChunk` requires these exact methods:

- `void write(java.io.DataOutput output) throws java.io.IOException`
- `void read(java.io.DataInput input) throws java.io.IOException`

Register it with `SaveVersion.addCustomChunk(String, CustomChunk)`.
Do not use `arc.util.io.Reads` or `arc.util.io.Writes` for these methods.
Mindustry build 159 `Plugin` does not declare a `dispose()` lifecycle method.
