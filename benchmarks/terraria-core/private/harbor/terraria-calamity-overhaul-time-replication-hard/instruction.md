# Repair Calamity Overhaul time-control replication

The frozen Calamity Overhaul 0.9209 source combines generation-aware NPC
identity, projectile identity, deferred entity binding, cancellation, and a
sectioned late-join snapshot. Boundary values can alias wire sentinels,
shortened engine arrays can throw, duplicate deferred work stays stale,
callback failures escape, timer arithmetic can wrap, and a malformed or failed
snapshot section can corrupt the rest of the frame. Repair the existing
production path; do not add a parallel identity, queue, or snapshot system.

Work in these files:

- `Content/TimeFreezes/NetworkEntityIdentity.cs`
- `Content/TimeFreezes/TimeControlReplicationSystem.cs`

Keep the existing public and internal type and method names. Keep the
submission source-only; do not add binaries, archives, build output, or
dependencies.

## Required behavior

### Keep entity identities valid on the wire and in live arrays

An NPC identity requires a nonnegative index below `Main.maxNPCs` and below
the reserved `ushort.MaxValue` wire sentinel, a loaded positive type, and a
nonzero generation. Capturing an active NPC assigns its time-freeze generation
when needed. Resolution also checks the actual `Main.npc` array length, active
state, type, and exact generation, returning false rather than indexing a
shorter array.

A projectile identity requires an owner below both `Main.maxPlayers` and the
reserved `byte.MaxValue` sentinel, a nonnegative identity, and a loaded
positive type. Resolution scans only the intersection of
`Main.maxProjectiles` and the actual projectile-array length and succeeds only
for one exact active match; zero or multiple matches fail.

Both `Write` methods emit their existing fixed-width canonical sentinel when
the identity is invalid and return false. Both `TryRead` methods return a
default identity and false for a null, truncated, unreadable, or semantically
invalid frame. Valid identities round-trip without changing their fields.

### Make deferred binding fresh, bounded, and exception-safe

NPC and projectile queue requests require a strictly positive activation ID,
a valid identity, positive remaining frames, and a non-null callback. If an
entity already resolves, invoke the callback immediately; a throwing callback
is logged and returns `Rejected` rather than escaping.

An unresolved request is keyed by source type, activation ID, and identity.
Submitting the same key again replaces its callback and refreshes its expiry
from the current frame so the newest replicated work wins. Other source types,
activation IDs, and identities remain independent. The existing shared NPC
plus projectile capacity remains enforced, including while full duplicate
refreshes are allowed.

If an older request for that same key is pending when a new request finds the
entity already resolved, consume the older pending record before applying the
new callback. The old callback must not run on a later tick, even if the new
immediate callback throws; pending work for other keys is unaffected.

Clamp a wait to 120 frames and compute its absolute expiry without unsigned
wraparound. Work is expired when the current frame reaches that boundary.
Once an entity resolves, consume the old pending record before invoking its
callback. Invoke that callback at most once, and do not restore the consumed
record if it throws. If the callback reentrantly submits fresher work for the
same key while the entity is temporarily unresolved, that replacement remains
queued for a later tick, including when the current callback then throws.
Ambiguous projectiles remain queued until one match is available or the
request expires.

Preserve the existing exact NPC/projectile cancellation, source-and-activation
cancellation, all-work-for-source cancellation, and world clear/unload
cleanup boundaries. Pending-drop and snapshot-failure diagnostics remain
rate-limited for 300 frames. Compute both diagnostic deadlines without
unsigned wraparound, and reset both throttles during world clear/unload so a
new world does not inherit suppressed diagnostics.

### Process pending work as one frame-stable transaction

At the start of `PreUpdateEntities`, capture one current frame, the current
world lifetime, and the exact pending-record objects from both the NPC and
projectile stores. Visit that combined snapshot in the order in which the
unresolved requests were accepted, independent of entity kind. A duplicate
refresh is a newly accepted record and receives a new position in that order.
Before handling each item, confirm that the same record object is still
current for its key, and resolve its entity at that time rather than caching a
live entity for the whole batch.

Only records in that start-of-tick snapshot may run or expire during the
current call. Work submitted by a callback, a refreshed later key, and a key
that is cancelled and requeued all wait for a later tick, including when the
new work has the other entity kind. Use the single captured frame for every
NPC and projectile expiry decision. A reentrant `PreUpdateEntities` call is a
no-op.

If `ClearWorld` or `OnWorldUnload` occurs while a callback is running, abort
the remainder of the captured batch. Work queued for the new world from that
callback remains pending but cannot run until a later tick.

### Emit only encodable late-join sections

Only a server writes the snapshot. Keep magic `0x31524354`, version `1`, the
existing section IDs 1 through 4, and deterministic ID order. Serialize each
section into isolation before writing the outer frame. A section is included
only when its writer returns true, does not throw, and produces at most
`ushort.MaxValue` bytes. Omit a failed or oversized section entirely and make
the outer count equal the sections actually written; do not emit a zero-length
placeholder for failure. A payload of exactly `ushort.MaxValue` bytes is valid.

Section writers are untrusted callbacks. A reentrant `NetSend` call is a
no-op. If a writer changes the world lifetime or the process stops being a
server, discard the complete outer snapshot and write no bytes for that call,
even if earlier sections serialized successfully.

### Validate a complete frame before applying any section

Only a multiplayer client reads the snapshot. Reject a wrong magic/version,
more than 16 sections, duplicate section ID, truncated header, truncated
payload, or structurally invalid frame before invoking any known section
reader. This prevents an earlier section from applying when a later section
proves that the frame is malformed. Unknown IDs remain length-delimited and
are skipped.

After structural validation, invoke known readers in ascending section-ID
order, independent of wire order. A known reader must return true and consume
its full isolated payload. A false return, unread bytes, or exception logs that
section's existing rejection and does not prevent later valid sections from
being attempted.

Known section readers are also untrusted callbacks. A reentrant `NetReceive`
call is a no-op. If a reader changes the world lifetime or the process stops
being a multiplayer client, let that isolated reader finish but do not attempt
any later section from the old frame.

## Public check

Run `python3 tools/smoke.py` to compile the two production files in the offline
.NET 8 source projection. It contains no behavioral assertions. Private
evaluation invokes the production codecs, live resolution, pending lifecycle,
and late-join framing directly with separate engine and subsystem doubles. The
full profile also compiles submitted production sources into a verifier mod and
runs task-specific sentinels inside pinned tModLoader `2026.7.3.0` on a
Terraria `1.4.4.9` dedicated server.
