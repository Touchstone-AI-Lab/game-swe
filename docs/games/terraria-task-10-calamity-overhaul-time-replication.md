# Terraria task 10 design: Calamity Overhaul time-control replication

## Candidate and provenance

- Upstream: `https://github.com/hocha113/CalamityOverhaul`
- Frozen revision: `91d8ea961644a48d20d051ace9a948dbf9f8298c`
- Upstream version: Calamity Overhaul 0.9209
- License: MIT
- Platform: Terraria 1.4.4.9 and the tModLoader 1.4.4 stable API
- Production path: time-control features encode live NPC/projectile identities,
  defer replicated work until matching entities exist, cancel or expire that
  work across world lifecycle events, and send a four-provider late-join
  snapshot from server to client.

The retained subsystem is grounded in upstream commits
`160c6d54e20295dc26a304f1fbd4b9001cbdc272`,
`b370d15701d0536a295d952320c6f9b351e383f1`, and
`5beb7fdcad1d9a26d0e20fc37ff2bb7bfe0270a1`.

## Operator reports to preserve in the task contract

1. NPC identities respect both live-array and fixed-width wire bounds, carry a
   nonzero spawn generation, resolve against the actual array, and use a
   canonical invalid sentinel.
2. Projectile identities respect owner wire bounds, resolve exactly one active
   owner/identity/type match within the actual array, and fail safely for
   invalid, truncated, or unreadable frames.
3. Deferred NPC work validates requests, invokes already-resolved work safely,
   refreshes duplicate keys, and preserves fresher same-key work submitted
   reentrantly by a resolving callback.
4. Deferred projectile work has the same callback and replacement guarantees,
   while ambiguous live matches remain pending; a replacement survives even
   when the callback that submitted it subsequently throws.
5. The shared pending store enforces capacity, clamped overflow-safe expiry,
   exact cancellation, world cleanup, and overflow-safe diagnostic throttles;
   a new world inherits neither pending callbacks nor suppressed diagnostics.
6. Server snapshot emission buffers each provider independently, omits false,
   throwing, and oversized providers, preserves deterministic IDs, and writes
   an exact outer count without corrupt placeholders.
7. Client snapshot receipt validates the whole frame before any apply, rejects
   duplicate or truncated framing, skips length-delimited unknown IDs, and
   invokes isolated known readers in canonical order without allowing one
   failed reader to block later sections.

## Expected repair shape

The retained production files are:

- `Content/TimeFreezes/NetworkEntityIdentity.cs`
- `Content/TimeFreezes/TimeControlReplicationSystem.cs`

The repair must coordinate fixed-width codecs with live Terraria arrays, two
typed pending dictionaries with a shared budget, callback reentrancy and
exception containment, saturating frame deadlines, ModSystem world cleanup,
and a two-phase sectioned snapshot protocol. The intended implementation
consumes a resolved pending record before running user code, so a reentrant
same-key submission is a distinct newer record rather than something removed
by the old callback's cleanup.

## Evaluation boundary

The evaluator compiles the two production files in a .NET 8 source projection.
Test doubles provide Terraria arrays and limits, loader counts, time-freeze
generation state, ModSystem hooks, logging, and the four existing snapshot
providers. Private cases invoke the production codecs, resolution loops,
pending lifecycle, and snapshot send/receive paths. Public smoke is
compile-only; the task does not claim a live tModLoader client, dedicated
server, or real socket.

## Difficulty and fairness review

This is hard because several locally reasonable fixes remain wrong when the
boundaries interact. Validity must agree with wire sentinels and shortened
arrays; projectile resolution must prove uniqueness; duplicate queue work may
arrive while capacity is full; callback code can mutate the same dictionary;
frame counters can approach `ulong.MaxValue`; and receive must separate
structural validation from ordered subsystem application. The two-phase frame
work and reentrant state-machine cleanup require more repository reasoning than
a collection of independent guard clauses and are comparable to, or above,
the accepted L4D2 hard lifecycle tasks.

The task is fair: every identity field, sentinel, bound, queue key, expiry
rule, reentrant replacement rule, diagnostic lifetime, section ID, frame
limit, and failure policy is explicit in the prompt. Tests use visible arrays
and deterministic delegates. No random game state, asset behavior, hidden
opcode, wall-clock timing, or verifier-only API is required.

## Design and implementation verdict

Accepted and locally audited. The strengthened revision has 61 named contracts
across seven coherent behavior groups. The frozen starter passes 34/61 while
the oracle passes 61/61; both source projections compile with zero warnings and
zero errors. The additional contracts are grounded in existing production
behavior rather than hidden difficulty, and strict calibration of the exact
strengthened revision remains pending.

## Revision 2: immediate work supersedes a pending callback

Audit of the 61-case oracle found that a pending request for a key could
survive a newer request that resolves the entity immediately. The obsolete
callback would then apply on the next tick, violating the newest-work-wins
queue invariant. The public prompt now states that the pending record is
consumed before the immediate callback, even if that callback throws. Three
new NPC/projectile cases cover this path. The frozen starter passes 34/64 and
the corrected oracle 64/64. The revision repairs task quality and needs a fresh
exact-revision strict run.

## Revision 3: frame-stable pending and snapshot transactions

Revision 2 still walked NPC and projectile dictionaries independently and let
callbacks mutate work that had not yet been visited. It also treated snapshot
providers as ordinary helpers even though they execute external subsystem code
inside world synchronization hooks. Revision 3 makes both boundaries explicit
state machines:

- one `PreUpdateEntities` call captures the exact pending records, one frame,
  one world lifetime, and global accepted order across both entity kinds;
- refreshed, cancelled-and-requeued, cross-kind, and recursively submitted
  work cannot join the active batch, while each entity is still resolved only
  when its turn arrives;
- a world transition aborts the old batch but preserves callback-created
  new-world work for a later tick;
- nested send/receive calls are no-ops, a send-side world or authority change
  discards the buffered outer frame, and a receive-side change stops later
  isolated section readers.

These fourteen cases are one coherent transaction boundary rather than
unrelated edge conditions. Every mutation and stop rule is stated in the
public prompt. The oracle passes 78/78 and the frozen starter passes 35/78.
