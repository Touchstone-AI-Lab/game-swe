# Repair Terraria Overhaul entity-backed chunk lifetime

The frozen Terraria Overhaul 5.0.0.38 source contains a related cluster of
failures in the data store and the chunk system built on top of it. Repair the
existing production implementation; do not replace it with a parallel entity
store or a benchmark-only chunk manager.

Work in these files:

- `Core/Data/DataStorage.cs`
- `Core/Data/SparseSet.cs`
- `Core/Data/Entities.cs`
- `Core/Chunks/Chunks.cs`
- `Utilities/BitMasks.cs`

Keep existing types and method signatures. Keep the submission source-only;
do not add binaries, archives, build output, or external dependencies.

## Required behavior

### Keep component identity and dynamic masks stable

`Component.Invalid` is the reserved zero handle. Every registered component
must receive a nonzero, stable, unique handle. When registration grows the
number of mask words per entity at either the 64- or 128-component boundary,
repack existing entity, query-inclusion, and query-exclusion masks by entity or
query row. No existing bit may move to another row or word.

Queries created before growth must retain their `With<T>` and `Without<T>`
meaning, and entities populated before growth must retain their components.
Registration must advance the global mask width even when no entity has been
created yet. Components above the first and second word boundaries must work
for later entities and for include/exclude queries created during that
pre-allocation registration phase.

Component lookup by simple `Type.Name` is deterministic. A name owned by one
registered type resolves repeatedly to that type's stable handle. If two
distinct registered component types have the same simple name, the name is
ambiguous: lookup returns `false` and no usable handle, while both typed
component handles remain distinct and valid.

### Make sparse removal real removal

Removing an entry from `SparseSet<TData>` must clear membership and return the
removed value while preserving every other index/value association. Compact
or reuse released dense capacity: repeated remove/insert cycles must not grow
the dense storage according to historical insert count. Putting an existing
index overwrites it without increasing `Count`.

### Enforce versioned entity lifetime

Default, out-of-range, and destroyed entity handles are safely invalid.
Destroying a live entity must clear all of its components before invalidating
its version and presence bit; destroying it again is a no-op. A stale handle
must report no component membership and attempts to add or get components
through it must be rejected rather than reaching stale storage.

For a live entity, removing a component it does not own is a no-op. Getting a
missing component and clearing a stale entity must reject with
`InvalidOperationException`; adding through `Component.Invalid` must reject
with `ArgumentException` without damaging the entity. `Clear` removes all
owned components and query membership while leaving the entity itself live.

Destroyed entity slots must be reused before extending the entity index
domain. `EntityCount` is the allocated-index high-water mark, not a live count,
so reusing a released slot does not increase it. When several slots are
released, all of them must be consumed before a new index is allocated; their
relative reuse order is unspecified. Destroy publishes a slot at most once,
and `Clear` never publishes its still-live slot.

A reused slot receives the nonzero generation established by destruction.
Every older handle to that index remains invalid, and no component value,
component-mask bit, or query membership may leak into the replacement. The
replacement must otherwise behave like a newly created entity, including
joining existing queries when components are added. Generation advancement
must never issue the reserved zero value to a live entity. If a slot exhausts
generation `uint.MaxValue`, destruction retires that slot permanently at zero
rather than allowing any older generation to alias a future entity; later
creation extends the high-water domain after consuming other reusable slots.

Query iteration must yield each currently live matching entity exactly once,
honor all include/exclude masks, skip destroyed entities, and continue across
empty 64-entity presence words.

Calling `GetEnumerator` starts a stable query pass. That pass snapshots its
include/exclude filters, candidate presence, and candidate generations.
Filter changes, component registrations, new entities, and reused slot
generations made afterward affect only later enumerators. A captured candidate
that is destroyed before it is visited is skipped. Entity validity requires
both the matching nonzero generation and a live presence bit; a fabricated
handle using the current version of an absent slot is still invalid.

### Preserve canonical bounded chunks

World and tile coordinate conversion uses floor semantics. A negative
coordinate just outside the world remains negative instead of truncating into
chunk `(0, 0)`. Chunk creation rejects negative and past-world chunk
coordinates, returns the canonical existing chunk for repeated coordinates,
and records the current update tick on creation and `KeepAlive`.
World-position creation performs the world-to-tile-to-chunk conversion exactly
once. World, tile, and chunk creation entrypoints for the same positive
location must converge on one canonical entity.

Visible-chunk iteration must derive the view bottom from
`Main.screenPosition.Y + Main.screenHeight`, not the horizontal origin. The
creation event runs only after the canonical dictionary entry, `ChunkInfo`, and
initial keep-alive tick are observable. For a partial chunk at the right or
bottom world edge, `TileRectangle`, normalized `Rectangle`, and
`WorldRectangle` must be clamped to the remaining world extent.

`IterateAllChunks` captures a stable handle snapshot when it is called.
Chunks created afterward are not added to that pass, and unloading or mutating
the canonical dictionary does not invalidate or rewrite the captured sequence.

Chunk lookup validates that a mapped entity is still live, still owns
`ChunkInfo`, and still names the requested encoded coordinate. A stale or
corrupt mapping is pruned and treated as absent so later creation can rebuild a
fresh canonical chunk.

Chunk creation is transactional across `OnChunkCreated`. Invoke every creation
subscriber once and isolate individual subscriber exceptions. A throwing
subscriber does not prevent later subscribers or invalidate an otherwise
canonical creation. After notification, return `true` only if the same live,
initialized entity is still the canonical mapping. If an observer unloads the
system or destroys/replaces that entity, return `false` with an invalid output;
do not publish a stale handle or remove a newer replacement.

### Teardown chunks atomically

Idle cleanup destroys a chunk only after at least
`60 * TimeSystem.LogicFramerate` unsigned ticks have elapsed. A recent chunk
or a chunk with a nonzero `ValuableComponentCount` survives. Elapsed-time
logic must work when the unsigned update counter wraps.

Both idle cleanup and `Unload` must, for every destroyed chunk:

- remove the canonical dictionary entry before notifying observers;
- raise `OnChunkDestroyed` exactly once;
- clear/destroy the backing entity exactly once; and
- tolerate observers inspecting the now-absent mapping.

Destroying chunks while traversing the entity query or unloading all chunks
must not throw because a collection changed or because the canonical
dictionary was nulled too early.

Observer failure must not strand a removed-but-live entity or stop cleanup of
later chunks. Invoke each `OnChunkDestroyed` subscriber once, isolate an
individual subscriber exception, and still destroy the backing entity; idle
cleanup and `Unload` do not propagate such observer exceptions. During idle
cleanup, an observer may recreate the just-removed coordinate; that new,
freshly kept-alive canonical chunk survives the old chunk's teardown. During
`Unload`, however, reentrant `TryGetOrCreateChunk` calls return `false` and an
invalid output instead of creating an entity that would escape world teardown.
Creation works normally again after the next `Load`.

An idle-destruction observer that creates a replacement chunk runs before the
old backing entity is destroyed, so that replacement cannot reuse the old
slot. Once normal cleanup has completed, later chunk creation may reuse the
released index, but it must expose a new generation and freshly initialized
`ChunkInfo`; the old chunk handle stays invalid.

## Public check

Run `python tools/smoke.py` (or `python3` where applicable) to compile the
five production files in the offline .NET 8 source projection. This public
check contains no behavioral
assertions. Private evaluation uses separate engine doubles and invokes the
production data-store and chunk methods directly. The full profile also
compiles submitted production sources into a verifier mod and runs
task-specific sentinels inside pinned tModLoader `2026.7.3.0` on a Terraria
`1.4.4.9` dedicated server.
