# Logic Link Lease Registry

Implement a Mindustry build-159 server plugin with a deterministic pure-Java `LogicLinkRegistry`
that grants exclusive, expiring target links to logic processors.

## Required files

```text
plugin.hjson
build-reference.sh
src/LogicLinkRegistry.java
src/LogicLinkRegistryPlugin.java
```

## Exact public core API

All types are nested in the default-package `public final class LogicLinkRegistry`:

```java
public record Claim(String owner, int processorPos, int targetPos, long tick, long ttl) {}
public record Lease(int targetPos, String owner, int processorPos, long expires) {}
public record Decision(boolean granted, Lease lease, String reason) {}
public record PersistedState(long lastTick, List<Lease> leases) {}

public LogicLinkRegistry();
public LogicLinkRegistry(PersistedState state);
public Decision claim(Claim claim);
public boolean release(String owner, int target, long tick);
public List<Lease> expire(long tick);
public List<Lease> snapshot();
public PersistedState save();
```

Claim rejects null input, null/blank owner, negative positions, non-positive TTL, negative tick, or
a tick older than the global `lastTick` with `IllegalArgumentException` before mutation. Expire
leases with `expires <= tick` before resolving a claim. A free target is granted through
`Lease(targetPos, owner, processorPos, tick + ttl)` with overflow-safe expiry and reason `"ok"`.
The same owner may renew or move its processor for the target. A different owner is denied with
`granted=false`, the existing lease, and reason `"owned"`.

`release` first expires at the supplied monotonic tick, then removes the target only when the
owner matches; it returns whether removal occurred. `expire` returns immutable newly expired
leases in ascending target position. Snapshot and persistence lists are immutable defensive copies
sorted by target position. Save/reload preserves `lastTick`, ownership, expiration boundaries,
and the next decision. Reject null persisted state and duplicate or malformed persisted targets
rather than silently replacing accounting.

## Plugin contract

`LogicLinkRegistryPlugin` is a default-package `public final` class extending
`mindustry.mod.Plugin` and exposes:

```java
public LogicLinkRegistryPlugin();
public static LogicLinkRegistryPlugin instance();
public LogicLinkRegistry core();
public Object exportState(); // returns core().save()
```

The adapter must derive processor identity, target position, ownership, and lifecycle from
server-owned buildings. Do not accept them from client RPC or add custom content, external
dependencies, wall-clock time, threads, or network access.

## Metadata

```hjson
name: "processor-link-leases"
displayName: "Logic Link Lease Registry"
main: "LogicLinkRegistryPlugin"
version: "1.0.0"
minGameVersion: 159
```

The evaluator checks ownership contention, renewal, release, exact expiration, deterministic
ordering, persistence, plugin loading, and behavior in a real build-159 headless world.
