# Core Failover Coordinator

Implement a Mindustry build-159 server plugin with a deterministic pure-Java
`CoreFailoverCoordinator`. It selects one primary core from server-authenticated samples.

## Required files

```text
plugin.hjson
build-reference.sh
src/CoreFailoverCoordinator.java
src/CoreFailoverCoordinatorPlugin.java
```

## Exact public core API

All types are nested in the default-package `public final class CoreFailoverCoordinator`:

```java
public record Policy(double minHealth, long holdTicks) {}
public record CoreSample(int pos, double health, double capacity, boolean active) {}
public record Decision(int primary, boolean changed, String reason) {}
public record PersistedState(long lastTick, int primary, long selectedAt) {}

public CoreFailoverCoordinator(Policy policy);
public CoreFailoverCoordinator(Policy policy, PersistedState state);
public Decision observe(List<CoreSample> samples, long tick);
public PersistedState save();
public int primary();
```

Require finite `minHealth` in `[0,1]` and non-negative `holdTicks`. Reject null sample lists,
negative/non-monotonic ticks, null samples, negative positions, duplicate positions, non-finite or
out-of-range health, and non-finite or negative capacity with `IllegalArgumentException` before
mutation.

The initial primary is `-1`. If the current primary is active, meets `minHealth`, and fewer than
`holdTicks` have elapsed since selection, retain it and return reason `"hold"`. Otherwise choose
among active healthy samples by greatest capacity, then greatest health, then lowest position.
Return `primary=-1` and reason `"none"` when no candidate qualifies; otherwise use reason
`"selected"`. Set `changed` exactly when the primary position changes, and reset `selectedAt`
only on a change. Save/reload must preserve the next decision.

## Plugin contract

`CoreFailoverCoordinatorPlugin` is a default-package `public final` class extending
`mindustry.mod.Plugin` and exposes:

```java
public CoreFailoverCoordinatorPlugin();
public static CoreFailoverCoordinatorPlugin instance();
public CoreFailoverCoordinator core();
public Object exportState(); // returns core().save()
```

The adapter must derive core positions, health, capacity, and activity from server-owned buildings;
do not accept them from client RPC. Use no custom content, external dependency, wall clock, thread,
or network access.

## Metadata

```hjson
name: "core-continuity-manager"
displayName: "Core Failover Coordinator"
main: "CoreFailoverCoordinatorPlugin"
version: "1.0.0"
minGameVersion: 159
```

The evaluator checks validation, hold boundaries, deterministic tie-breaking, persistence, plugin
loading, and behavior in a real build-159 headless world.
