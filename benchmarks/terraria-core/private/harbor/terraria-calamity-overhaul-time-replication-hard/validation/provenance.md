# Provenance and review receipt

## Frozen source

- Repository: `https://github.com/hocha113/CalamityOverhaul`
- Commit: `91d8ea961644a48d20d051ace9a948dbf9f8298c`
- Mod version: Calamity Overhaul 0.9209
- License: MIT
- Platform context: Terraria 1.4.4.9 and tModLoader 1.4.4 stable API

The starter retains the two frozen upstream production files byte-for-byte,
plus the upstream build metadata and license. The package contains source and
license only; the repository's thousands of content assets, referenced mods,
DLLs, Git data, caches, and build output are excluded.

## Real production path

`NetworkEntityIdentity` is the time-control feature's wire and live-resolution
boundary for NPCs and projectiles. `TimeControlReplicationSystem` owns deferred
work for entities that have not spawned locally yet, cancellation and expiry,
world cleanup, and the versioned snapshot used to initialize late-joining
clients across Cyber Domain Freeze, Cyber Banish, boss execution, and hack
effects. The evaluator invokes these production files; doubles supply only
engine arrays, loader counts, generation storage, logging, and those four
external snapshot delegates.

## Historical grounding

The retained subsystem was introduced and revised in upstream commits
`160c6d54e20295dc26a304f1fbd4b9001cbdc272`,
`b370d15701d0536a295d952320c6f9b351e383f1`, and
`5beb7fdcad1d9a26d0e20fc37ff2bb7bfe0270a1`. At the frozen revision,
wire-sentinel bounds differ from live-array bounds, resolution trusts configured
array sizes, an existing deferred key keeps stale work, immediate callback
exceptions escape, a resolved callback can erase a reentrant replacement,
expiry and diagnostic-deadline addition can wrap, snapshot diagnostic state
survives a world transition, failed send sections remain as zero-length
placeholders, and receive applies sections before the whole frame is
structurally known to be valid.

## Fairness and uniqueness

All 78 cases map to explicit prompt clauses. The prompt states sentinel values,
inclusive/exclusive bounds, unreadable codec behavior, compound identity,
duplicate and reentrant refresh semantics, expiry, cancellation, diagnostic
deadlines and lifecycle reset, snapshot magic/version/IDs, maximum payload,
complete structural validation, per-section fault isolation, the combined
start-of-tick record snapshot, accepted enqueue order, world transitions, and
authority loss during callbacks. Tests use visible engine arrays and
deterministic delegates; no random world state, rendering, hidden type names,
or undocumented network opcode is involved. This task is distinct from the
other Terraria tasks because it couples generation-aware live entity discovery
with a bounded, callback-reentrant cross-kind deferred queue and a
length-delimited multi-subsystem late-join snapshot.

## Revision history

Revision 2 adds three cases for immediate resolution superseding an older
same-key pending record. Its starter passes 34/64 and oracle 64/64.

Revision 3 replaces the two independent pending-store walks with one
frame-stable transaction. It captures exact record identities, accepted
cross-kind order, one frame value, and a world lifetime; refresh, cancellation,
requeue, callback recursion, and world replacement cannot leak new work into
the active batch. The same world-lifetime and authority invariants now protect
untrusted snapshot writer and reader callbacks. The frozen starter reaches
35/78 and the corrected oracle 78/78.
