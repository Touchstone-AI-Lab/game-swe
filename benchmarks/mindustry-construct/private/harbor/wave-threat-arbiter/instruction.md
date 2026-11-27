# Wave Threat Response and Repair Arbiter

Implement a build-159 server plugin that turns real wave, enemy, damage and unit lifecycle events
into deterministic defense and repair assignments. Keep the event/assignment engine pure Java and
all authority in the server adapter.

## Required files

```text
plugin.hjson
build-reference.sh
src/ThreatArbiter.java
src/WaveThreatArbiterPlugin.java
```

## Public core API

```java
ThreatArbiter(Policy policy);
ThreatArbiter(Policy policy, PersistedState state);
Result observeThreat(Threat threat);
Result observeDamage(Damage damage);
Result registerResponder(Responder responder);
Result heartbeat(String assignmentId, int unitId, long tick);
Result resolve(String eventId, long tick);
Result removeResponder(int unitId, long tick);
WaveReport endWave(int wave, long tick);
TickReport tick(long tick);
Snapshot snapshot(long tick);
PersistedState save();
```

Expose immutable records `Policy`, `Threat`, `Damage`, `Responder`, `Event`, `Assignment`, `Result`,
`WaveReport`, `TickReport`, `Snapshot`, and `PersistedState`, enums `EventKind { DEFEND, REPAIR }`,
`EventStatus { OPEN, ASSIGNED, RESOLVED, EXPIRED }`, and `ResponderKind { COMBAT, REPAIR }`.
`Policy` components are `(long leaseTicks,long agingTicks,int persistentRepairWaves)` and `Responder` components are `(int unitId,ResponderKind kind,int teamId,int tilePos,boolean alive,long revision)`.
`Threat` components are `(String eventId,int wave,int enemyId,String enemyType,int tilePos,int
severity,long tick)` and `Damage` components are `(String eventId,int wave,int buildingPos,String
blockName,int damage,int strategicValue,long tick)`.

The remaining fixed record components and helper are:

```java
record Event(String eventId,EventKind kind,int wave,int sourceId,String sourceType,
             int tilePos,int priority,long createdTick,long updatedTick,EventStatus status)
record Assignment(String assignmentId,String eventId,int unitId,long assignedTick,
                  long heartbeatTick,long leaseUntilTick)
record Result(boolean changed,String reason,Event event,Assignment assignment)
record WaveReport(int wave,long tick,int resolved,int expired,int retained,
                  int released,List<Event> events)
record TickReport(long tick,int expiredAssignments,int assignmentsCreated,
                  List<Assignment> assignments)
record Snapshot(long tick,List<Event> events,List<Responder> responders,
                List<Assignment> assignments)
record PersistedState(List<Event> events,List<Responder> responders,
                      List<Assignment> assignments,long nextAssignmentId,
                      Set<String> sourceKeys,Set<Integer> endedWaves)

boolean Result.accepted(); // false only when reason is "rejected"
PersistedState(List<Event> events,List<Responder> responders,
               List<Assignment> assignments,long nextAssignmentId)
```

## Required behavior

- Validate all IDs, waves, ticks, server-derived positions/types and positive values before
  mutation. Deduplicate equivalent source events and request IDs across reload.
- Order open events by effective priority: severity/strategic value plus deterministic aging, then
  creation tick and event ID. One owner per event and one live assignment per responder.
- Match responder capability, distance and team deterministically. Heartbeats renew only matching
  assignments. Death, despawn and timeout requeue unresolved work exactly once.
- Wave end resolves or expires only that wave, releases responders, and leaves persistent repair
  work according to policy. Repeated cleanup is idempotent.
- Snapshot/save collections are sorted immutable copies; reload preserves aging and assignment IDs.

## Mindustry integration

- Extend `Plugin`; expose `instance()`, `arbiter()`, `exportState()`, and `importState()`.
- Consume `WaveEvent`, `UnitSpawnEvent`, `UnitDestroyEvent`, building-damage/tile events,
  `ResetEvent`, and `WorldLoadEvent`; derive every entity, team and distance from server state.
- Assign only real compatible base-game units and never touch an unrelated replacement entity.
- Private tests spawn real enemies/responders, damage real buildings, destroy responders, end a
  wave and reload the save while asserting exact ownership and deterministic reassignment.
- Persist through a named build-159 `CustomChunk` and reconcile after entities load.

## Metadata

```hjson
name: "threat-response-arbiter"
displayName: "Wave Threat Response and Repair Arbiter"
main: "WaveThreatArbiterPlugin"
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
