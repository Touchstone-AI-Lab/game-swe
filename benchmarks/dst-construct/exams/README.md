# Rhenium Don't Starve Together engineering exams

Each Markdown file in `exams/` is one self-contained hard engineering task. File names are for
maintainers; a copy placed in an isolated attempt directory is always named `EXAM.md`, so the
model never sees the internal task id or an ordinal.

| Exam | Domains | Suggested time |
| --- | --- | ---: |
| [Server-authoritative Camp Supply Ledger](camp-supply-ledger.md) | quotas, idempotency, inventory, persistence | 360 min |
| [Crash-safe Container Transfer](container-transfer-transaction.md) | transactions, containers, recovery, actions | 420 min |
| [Lease-based Rescue Dispatch Queue](rescue-dispatch-queue.md) | scheduling, leases, player-lifecycle, replication | 390 min |
| [Server-authoritative World Rule Ballot](world-rule-ballot.md) | voting, server-authority, timers, replication | 360 min |
| [Deterministic Combat Target Arbiter](combat-target-arbiter.md) | combat, event-ordering, leases, determinism | 390 min |
| [Server-authoritative Waystone Route Network](waystone-route-network.md) | pathfinding, server-authority, inventory, persistence | 420 min |
| [Server-authoritative Status Effect Stack](status-effect-stack.md) | status-effects, timers, combat, persistence | 390 min |
| [Server-authoritative Camp Fuel Ration Allocator](fuel-ration-allocator.md) | resource-allocation, fairness, fueled, persistence | 390 min |
| [Server-authoritative Two-player Trade Escrow](trade-escrow-exchange.md) | trading, transactions, inventory, persistence | 390 min |
| [Server-authoritative Loot Roll Arbiter](loot-roll-arbiter.md) | loot, determinism, server-authority, persistence | 390 min |

## Common rules

1. Write every Lua file yourself, starting from an empty workspace.
2. The pure core module must run in plain Lua without any DST global.
3. Authoritative state and validation of untrusted input belong on the master simulation.
4. Duplicates, reordering, expiry, failure compensation and save/load must have deterministic semantics.
5. Use only base-game APIs, prefabs, components and assets; each exam gives the key call signatures,
   checked against the scripts of the pinned server build.
6. A complete result requires passing the hidden plain-Lua tests and the hidden assertions on the
   headless dedicated server.
