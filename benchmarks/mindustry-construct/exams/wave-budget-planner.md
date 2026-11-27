# Deterministic Wave Budget Planner

Implement a Mindustry build-159 server plugin with a deterministic pure-Java `WaveBudgetPlanner`.
It converts an authoritative wave budget and candidate list into an immutable unit plan.

## Required files

```text
plugin.hjson
build-reference.sh
src/WaveBudgetPlanner.java
src/WaveBudgetPlannerPlugin.java
```

## Exact public core API

All types are nested in the default-package `public final class WaveBudgetPlanner`:

```java
public record Policy(int maxUnits, int reserve, int bossEvery) {}
public record Candidate(String type, int cost, int priority) {}
public record Plan(long wave, int budget, List<String> units, int spent) {}
public record PersistedState(long lastWave, List<Plan> plans) {}

public WaveBudgetPlanner(Policy policy);
public WaveBudgetPlanner(Policy policy, PersistedState state);
public Plan plan(long wave, int budget, List<Candidate> candidates);
public List<Plan> snapshot();
public PersistedState save();
```

Require `maxUnits > 0`, `reserve >= 0`, and `bossEvery > 0`. Reject negative or
non-monotonic waves, negative budgets, null candidate lists, null candidates, null/blank type names,
and non-positive costs with `IllegalArgumentException` before mutation. Candidate priority may be
any integer.

A repeated wave is idempotent and returns its stored plan without replanning. For a new wave, sort
candidates by descending priority and then ascending type. The spendable cap is
`max(0, budget - reserve)`. Visit candidates in that order and repeatedly add the candidate type
while the unit count remains below `maxUnits` and its cost fits the cap. On waves evenly divisible
by `bossEvery`, add at most one copy of each visited candidate before continuing to the next.
`spent` is the exact sum and may never exceed the cap. Use overflow-safe arithmetic.

Plans, unit lists, snapshots, and persisted lists must be immutable defensive copies. Snapshots are
sorted by ascending wave. Save/reload must preserve previous plans, `lastWave`, idempotency, and
the next plan.

## Plugin contract

`WaveBudgetPlannerPlugin` is a default-package `public final` class extending
`mindustry.mod.Plugin` and exposes:

```java
public WaveBudgetPlannerPlugin();
public static WaveBudgetPlannerPlugin instance();
public WaveBudgetPlanner core();
public Object exportState(); // returns core().save()
```

The adapter must derive wave, budget, and base-game unit candidates from server state. Do not accept
them through a client RPC or add custom content, external dependencies, wall-clock time, threads,
or network access.

## Metadata

```hjson
name: "wave-resource-allocator"
displayName: "Deterministic Wave Budget Planner"
main: "WaveBudgetPlannerPlugin"
version: "1.0.0"
minGameVersion: 159
```

The evaluator checks validation, budget and reserve boundaries, boss-wave behavior, deterministic
ordering, persistence, plugin loading, and operation in a real build-159 headless world.
