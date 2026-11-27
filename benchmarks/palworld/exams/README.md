# Rhenium Palworld UE4SS original systems-engineering exams

Each Markdown file in `exams/` is a self-contained, high-difficulty engineering exam. File names are for operator maintenance; when copied into the isolated answer directory each one is uniformly renamed to `EXAM.md`, so no internal task-id or numeric index is exposed to the model.

| Exam | Domains | Suggested time |
| --- | --- | ---: |
| [Server-authoritative Guild Storage Ledger](guild-storage-ledger.md) | quota, idempotency, inventory, persistence | 360 minutes |
| [Canonical Base Containment Under Coupled Costs](base-containment-mincut.md) | directed min-cut, hard constraints, history stability, canonical recovery | 960 minutes |
| [Lease-based Raid Dispatch Queue](raid-dispatch-queue.md) | scheduling, leases, player lifecycle, recovery | 390 minutes |
| [Server-authoritative World Rule Ballot](server-rule-ballot.md) | voting, server authority, timers, announcements | 360 minutes |
| [Stable Guild Draft Under Conflicting Priorities](guild-draft-canonical-order.md) | exact ordering, hard precedence, minimax displacement, recovery | 960 minutes |
| [Receipt-driven Supply Outbox Recovery](outbox-receipt-recovery.md) | persistence, external side effects, receipts, recovery | 660 minutes |
| [Globally Optimal Pal Workforce Matching](pal-workforce-optimal-matching.md) | exact optimization, matching, four-level objective, determinism | 720 minutes |
| [Revisioned Raid Contributions with Watermarks](raid-event-watermark.md) | event time, versions, retraction, watermark | 660 minutes |
| [Greatest Causally Consistent Guild Checkpoint](guild-consistent-checkpoint.md) | causality, sparse logs, fixed point, maximality | 720 minutes |
| [World Epoch Fencing and Timer Redelivery](world-epoch-fenced-timers.md) | epoch, generation, cancellation, restart recovery | 660 minutes |

The last five exams were added in catalog 1.1.0 and keep the `hard` format; the suggested times are
author estimates, not difficulty-calibrated against any specific model. Each exam includes a public contract,
behavioral assertions, dedicated-server assertions and a Harbor reference implementation. Their real-engine
validation status is independent of the first five exams; see [validation record for the added exams](../validation/advanced-controls.md).

## Shared rules

1. Complete all Lua files and the `Info.json` package manifest independently, starting from an empty workspace.
2. The plain core module must run in an ordinary Lua environment without any UE4SS global objects.
3. Authoritative state and validation of untrusted input must live in the dedicated server process.
4. Duplicates, reordering, expiry, failure compensation and restart recovery must have deterministic semantics.
5. Only documented UE4SS Lua APIs and the official Palworld mod packaging format may be used; the exam text gives verified signatures for the key calls.
6. A full score requires passing both the hidden plain-Lua tests and the hidden headless dedicated-server assertions.

Catalog 2.0.0 retires the Palbox transfer and damage attribution exams. Their
files remain for historical inspection. The active list above contains ten
construct tasks. The two replacements have new identities; their
[Linux control record](../validation/linux-controls.md) is separate from the
historical Windows evidence. The other eight exams remain byte-identical.
