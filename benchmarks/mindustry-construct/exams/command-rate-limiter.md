# Server Command Rate Limiter

Implement a Mindustry build-159 server plugin with a deterministic, dependency-free Java
`CommandRateLimiter` core. The core uses logical ticks only and must preserve its next decision
sequence across save/reload.

## Required files

```text
plugin.hjson
build-reference.sh
src/CommandRateLimiter.java
src/CommandRateLimiterPlugin.java
```

## Exact public core API

All types are nested in the default-package `public final class CommandRateLimiter`:

```java
public record Policy(int capacity, int refill, long windowTicks, long banTicks) {}
public record Decision(String player, boolean allowed, int remaining, long bannedUntil) {}
public record State(String player, int tokens, long windowStart, long bannedUntil) {}
public record PersistedState(long lastTick, List<State> states) {}

public CommandRateLimiter(Policy policy);
public CommandRateLimiter(Policy policy, PersistedState state);
public Decision allow(String player, long tick);
public List<State> snapshot();
public PersistedState save();
```

`Policy` requires positive `capacity`, `refill`, and `windowTicks`; `banTicks` is non-negative.
Reject a null/blank player or a negative/non-monotonic tick with `IllegalArgumentException` before
mutation. A new player starts with `capacity` tokens and a window beginning at its first tick.
At each complete `windowTicks` interval, add `refill` tokens, capped at `capacity`, and advance the
stored window start by the same number of complete intervals. An allowed command consumes exactly
one token. When an unbanned player has no token, deny the command and set `bannedUntil` to
`tick + banTicks`; commands before that tick remain denied. The boundary `tick == bannedUntil` is
eligible again. Use overflow-safe refill arithmetic.

Snapshots must be immutable defensive copies sorted lexicographically by player. Save/reload must
preserve `lastTick`, ordering, tokens, window starts, bans, and the next decision.

## Plugin contract

`CommandRateLimiterPlugin` must be a default-package `public final` class extending
`mindustry.mod.Plugin`. It must provide:

```java
public CommandRateLimiterPlugin();
public static CommandRateLimiterPlugin instance();
public CommandRateLimiter core();
public Object exportState(); // returns core().save()
```

The no-argument constructor must publish the instance and create a usable core. Do not accept
player identity or tick values through a client RPC; an actual adapter must derive them from
server-owned state. No custom game content, external dependency, thread, wall clock, or network
access is allowed.

## Metadata

```hjson
name: "command-traffic-guard"
displayName: "Server Command Rate Limiter"
main: "CommandRateLimiterPlugin"
version: "1.0.0"
minGameVersion: 159
```

The evaluator checks validation without partial mutation, refill and ban boundaries, deterministic
ordering, persistence, plugin loading, and operation inside a real build-159 headless world.
