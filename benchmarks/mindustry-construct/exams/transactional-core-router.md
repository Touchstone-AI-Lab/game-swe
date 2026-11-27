# Transactional Core Stockpile Router

Build a server-only Mindustry JVM plugin that transfers base-game items between registered storage buildings without item loss or duplication. The implementation must remain correct across duplicate requests, partial adapter failures, building removal, and save/load recovery.

The submission is evaluated with pure-Java hidden assertions and a real Mindustry headless server. Do not add custom blocks, items, units, maps, sprites, or third-party runtime dependencies.

Use the supplied `build-reference.sh` as the public compilation check:

```sh
./build-reference.sh
```

The build uses Mindustry server build 159 from `MINDUSTRY_SERVER_JAR`.

## Required files

```text
plugin.hjson
src/TransferEngine.java
src/TransactionalCoreRouterPlugin.java
```

## Public core API

`TransferEngine.java` must declare the following public types in the default package:

```java
public final class TransferEngine {
    public TransferEngine(Adapter adapter);
    public TransferEngine(Adapter adapter, PersistedState persisted);

    public TransferResult transfer(TransferRequest request);
    public RecoveryReport recover();
    public TransferResult status(String requestId);
    public PersistedState save();
}
```

The same file must expose these nested public types:

```java
public interface Adapter {
    StorageSnapshot snapshot(int buildingPos);
    int capacity(int buildingPos, String itemName);
    RemovedItems remove(int buildingPos, String itemName, int amount);
    void add(int buildingPos, RemovedItems items);
    void restore(int buildingPos, StorageSnapshot snapshot);
    void checkpoint(PersistedState state);
}

public record TransferRequest(
    String requestId,
    int sourcePos,
    int destinationPos,
    String itemName,
    int amount
) {}

public enum Phase {
    REJECTED,
    PREPARED,
    SOURCE_REMOVED,
    COMMITTED,
    ROLLED_BACK,
    RECOVERY_REQUIRED
}

public record TransferResult(
    String requestId,
    Phase phase,
    boolean successful,
    String reason
) {}

public record ItemPortion(
    String itemName,
    int amount
) {}

public record RemovedItems(
    java.util.List<ItemPortion> portions
) {}

public record StorageSnapshot(
    int buildingPos,
    java.util.Map<String, Integer> items
) {}

public record PersistedTransfer(
    TransferRequest request,
    Phase phase,
    StorageSnapshot sourceBefore,
    StorageSnapshot destinationBefore,
    RemovedItems removed,
    String reason
) {}

public record PersistedState(
    java.util.Map<String, PersistedTransfer> transfers
) {}

public record RecoveryReport(
    int committed,
    int rolledBack,
    int stillRecoverable
) {}
```

Additional private types and methods are allowed. The public signatures, package name, enum constants, and record component order are fixed.

## Core behavior

1. Validate the complete request before calling any adapter mutation method. A valid request has a non-blank request ID, different non-negative source and destination positions, a non-blank lowercase item name, and a strictly positive amount.
2. Deduplicate by `requestId`. Once an ID has been observed, every retry must return its stored result without taking another snapshot or mutating either storage building. Reusing an ID with different request fields must return the original result.
3. Call `snapshot` for the source and destination, then preflight source availability and destination capacity. A failed preflight must not call `remove`, `add`, or `restore`.
4. Before removing items, store a `PREPARED` transfer containing both snapshots and call `checkpoint` with a fresh complete persisted state.
5. After a successful removal, store the exact returned `RemovedItems`, change the phase to `SOURCE_REMOVED`, and checkpoint again before calling `add`.
6. Commit only after `add` returns successfully. Store `COMMITTED` and checkpoint the committed state.
7. If `remove` fails, restore the source snapshot and record `ROLLED_BACK`. If source restoration fails, record `RECOVERY_REQUIRED`.
8. If `add` fails, restore the destination snapshot first and the source snapshot second. Both restore calls must be attempted even if the first fails. Record `ROLLED_BACK` only when both restorations succeed; otherwise record `RECOVERY_REQUIRED`.
9. `recover()` must process unfinished transfers in ascending request-ID order. `PREPARED` transfers restore both snapshots. `SOURCE_REMOVED` transfers first attempt to finish the destination add; if that fails, they compensate destination then source. Recovery is idempotent.
10. `status`, `save`, snapshots, maps, and lists must be defensive immutable copies. Caller mutation must never alter engine state.
11. Reject null adapter return values, negative counts, mismatched building positions, unexpected item names, arithmetic overflow, and malformed persisted state without silently losing an existing recoverable record.
12. Core code must not import `arc.*` or `mindustry.*`, access globals, start threads, read files, or use wall-clock time.

## Mindustry integration API

`TransactionalCoreRouterPlugin` must extend `mindustry.mod.Plugin` and expose:

```java
public static TransactionalCoreRouterPlugin instance();

public TransferEngine.TransferResult request(
    String requestId,
    int sourcePos,
    int destinationPos,
    String itemName,
    int amount
);

public TransferEngine.RecoveryReport recover();
public TransferEngine.PersistedState exportState();
public void importState(TransferEngine.PersistedState state);
```

The plugin must implement the adapter with base-game Mindustry objects:

- Resolve buildings on the server with `Vars.world.build(position)`; never accept a `Building`, `Item`, item count, capacity, team, or snapshot supplied by a client.
- Accept only existing, enabled storage buildings with item modules. Source and destination must belong to the same non-derelict team.
- Resolve items from base-game content by lowercase name. Unknown or modded items are rejected.
- Read and mutate inventory through each building's real item module. Capacity must be calculated from the destination block's item capacity and current inventory.
- Perform every world mutation on the Mindustry application thread. The plugin must not create worker threads.
- Observe `BlockDestroyEvent`, `TileChangeEvent`, `ResetEvent`, and `WorldLoadEvent`. A pending transfer that references a removed or replaced building must be recovered or marked recoverable without touching an unrelated replacement building.
- Register a server command named `router-transfer` with arguments `<request-id> <source-pos> <destination-pos> <item> <amount>`. Parsing failures must not mutate state.
- Persist `PersistedState` in a named custom save chunk and call `recover()` after the world and saved entities are ready. Corrupt or missing chunk data must not crash server startup.
- On build 159, `mindustry.io.SaveFileReader.CustomChunk` declares
  `void write(java.io.DataOutput output) throws java.io.IOException` and
  `void read(java.io.DataInput input) throws java.io.IOException`; register it with
  `mindustry.io.SaveVersion.addCustomChunk(String, CustomChunk)`.
- On `ResetEvent`, clear world-bound transaction state and building identities, but keep
  `instance()` bound to the active plugin instance.
- Mindustry build 159 `Plugin` does not declare a `dispose()` lifecycle method. Do not add an
  `@Override dispose()` method; perform reset cleanup from the registered server events.

## Metadata contract

`plugin.hjson` must contain:

```hjson
name: "core-stockpile-router"
displayName: "Transactional Core Stockpile Router"
main: "TransactionalCoreRouterPlugin"
description: "Crash-safe server-authoritative stockpile transfers."
version: "1.0.0"
minGameVersion: 159
```

No dependency may bundle Mindustry, Arc, or another copy of the public API classes into the output JAR.

## Dedicated-server assertions

The private test runner will:

- create real base-game storage buildings on a temporary map and seed them with copper, lead, and graphite;
- verify a successful transfer changes inventories exactly once;
- retry the same request and verify no duplicate mutation;
- test insufficient source stock and insufficient destination capacity;
- inject failures after prepare, after source removal, and during destination addition;
- verify compensation order and exact restoration;
- reload every persisted phase and run recovery twice;
- destroy or replace a referenced building during a pending transfer;
- pass malformed commands, item names, counts, positions, snapshots, and persisted records;
- verify deterministic immutable results and stable request ordering;
- save and reload the world and confirm that committed requests remain deduplicated.

## Acceptance criteria

- No execution path loses or duplicates items.
- A committed request never invokes adapter operations again.
- Intent is checkpointed before the first inventory mutation.
- Partial failures compensate in the required order.
- Recovery is deterministic, idempotent, and reload-safe.
- All authority and item resolution remain on the server.
- The plugin loads without a graphical client and all dedicated-server assertions complete.
