# Transactional Item Reservation Ledger

Implement a Mindustry build-159 server plugin with a deterministic pure-Java `ReservationLedger`.
It reserves server-observed stock without duplicating or oversubscribing it.

## Required files

```text
plugin.hjson
build-reference.sh
src/ReservationLedger.java
src/ItemReservationLedgerPlugin.java
```

## Exact public core API

All types are nested in the default-package `public final class ReservationLedger`:

```java
public enum Status { RESERVED, COMMITTED, CANCELLED, EXPIRED, REJECTED }
public record Request(String id, int sourcePos, String item, int amount, long tick, long ttl) {}
public record Entry(String id, int sourcePos, String item, int amount,
                    long created, long expires, Status status) {}
public record Decision(String id, Status status, int reserved, String reason) {}
public record PersistedState(long lastTick, List<Entry> entries) {}

public ReservationLedger();
public ReservationLedger(PersistedState state);
public Decision reserve(Request request, int available);
public Decision commit(String id, long tick);
public Decision cancel(String id, long tick);
public List<Entry> expire(long tick);
public List<Entry> snapshot();
public PersistedState save();
```

Logical ticks are globally monotonic and non-negative; stale ticks throw
`IllegalArgumentException` without mutation. A reservation request is invalid when null, when its
ID or item is null/blank, when `sourcePos < 0`, `amount <= 0`, `ttl <= 0`, or
`available < 0`; return `REJECTED, reserved=0, reason="invalid"`. Before accounting, expire
entries whose `expires <= tick`. Compute already-reserved stock only from live `RESERVED`
entries with the same source position and item. Reject insufficient stock with reason
`"insufficient"`; otherwise create an entry expiring at `tick + ttl` using overflow-safe
arithmetic and return reason `"ok"`.

Request IDs are idempotent: a duplicate returns the existing status, reports its amount only while
still reserved, and uses reason `"duplicate"`. Commit and cancel transition only a live
reservation. Any missing or non-reserved ID returns `REJECTED, reserved=0,
reason="not reserved"`. Expiration returns an immutable position-independent list of newly expired
entries. Snapshots and saved entries are immutable defensive copies sorted by ID. Loading rejects
null state, `lastTick < -1`, null entries, duplicate IDs, and malformed persisted values without
silently discarding identifiable accounting.

## Plugin contract

`ItemReservationLedgerPlugin` is a default-package `public final` class extending
`mindustry.mod.Plugin` and exposes:

```java
public ItemReservationLedgerPlugin();
public static ItemReservationLedgerPlugin instance();
public ReservationLedger core();
public Object exportState(); // returns core().save()
```

The adapter must derive source position, item, and available stock from the server. Do not trust
client-provided inventory or use custom content, external dependencies, wall-clock time, threads, or
network access.

## Metadata

```hjson
name: "stockpile-hold-ledger"
displayName: "Transactional Item Reservation Ledger"
main: "ItemReservationLedgerPlugin"
version: "1.0.0"
minGameVersion: 159
```

The evaluator checks invalid/stale input, oversubscription, duplicate transitions, exact expiry
boundaries, persistence, plugin loading, and operation in a real build-159 headless world.
