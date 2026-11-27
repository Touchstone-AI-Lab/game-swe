# Terraria task 03 design: Terraria Overhaul entity-backed chunk lifetime

## Candidate and provenance

- Upstream: `https://github.com/Mirsario/TerrariaOverhaul`
- Frozen revision: `55c23fbde42f6fcb9eb266992475a040d14c2b84`
- Upstream version: Terraria Overhaul 5.0.0.38
- License: GNU GPL v3, Copyright (c) 2020-2026 Mirsario & Contributors
- Platform: Terraria 1.4.4.9 and the tModLoader 1.4.4 stable API
- Production path: the mod's data store owns versioned entity handles,
  dynamically registered component masks and queries; the chunk system stores
  each live world chunk as one of those entities and destroys idle chunks from
  the normal `ModSystem.PostUpdateEverything` lifecycle.

The revision was chosen from upstream history, not from an isolated utility.
Commits `98915aa96d1ff8b4fb0f41bd1332b36fa8c88d52`,
`1bf023a1b3b5f8ab8f97a9d4f6acfb7bd0c68141`, and the frozen
`55c23fbde42f6fcb9eb266992475a040d14c2b84` all modify this exact execution
path: idle chunk unloading, entity destruction, component mutation, main-thread
ownership, and query behavior.

## Operator reports to preserve in the task contract

1. The reserved invalid component handle must remain invalid; every registered
   component receives a stable, valid, unique handle.
2. Crossing either the 64- or 128-component boundary must preserve every
   entity and query mask bit. Existing `With` and `Without` filters must still
   select the same entities after the mask arrays grow.
3. Removing a component must remove exactly that sparse-set entry. Later
   insertion must reuse released dense capacity without changing another
   entity's value or allowing stale data to appear through `Has` or `Get`.
4. Entity destruction clears all of its components before invalidating its
   version. A stale or default handle reports invalid and cannot mutate or
   alias a later entity.
5. A query iterator must yield each currently live matching entity once,
   exclude non-matching and destroyed entities, and terminate cleanly across
   empty 64-entity mask words.
6. Chunk creation is bounded by the world, canonical per chunk coordinate,
   and refreshes keep-alive state. Negative world/tile coordinates must not be
   truncated into chunk `(0, 0)`.
7. Idle cleanup and mod unload destroy each chunk once, remove it from the
   canonical dictionary, and raise one destruction event. Reentrant observers
   may inspect the now-removed chunk without causing a second destruction or a
   collection-modified/null-reference failure.
8. Chunks with valuable components or a recent keep-alive tick survive idle
   cleanup, including the unsigned update-counter wrap boundary.
9. Component operations distinguish live, missing, invalid, and stale state:
   missing removal is a no-op; missing get, stale clear, and invalid dynamic
   handles reject deterministically; clearing a live entity removes query
   membership without destroying the entity.
10. Visible chunk iteration uses the vertical screen origin for its bottom
    edge. Creation observers see an initialized canonical chunk, and partial
    edge-chunk rectangles are clamped to the real world extent.

## Expected repair shape

The retained production files are:

- `Core/Data/DataStorage.cs`
- `Core/Data/SparseSet.cs`
- `Core/Data/Entities.cs`
- `Core/Chunks/Chunks.cs`
- `Utilities/BitMasks.cs`

The frozen snapshot contains the real upstream implementation. A correct
repair is expected to preserve its public/internal surface while fixing mask
repacking, sparse removal, entity teardown, query validity, coordinate
flooring, and chunk teardown ordering. The files are deliberately not replaced
by a benchmark-only data store.

## Evaluation boundary

The evaluator compiles all five production files directly in a .NET 8 source
projection. Small deterministic doubles provide only engine-owned XNA,
Terraria, and tModLoader types plus Overhaul types outside this retained slice.
Private checks call the real `DataStorage`, `SparseSet`, query iterator, and
`Chunks` methods. Public smoke checks compile the same production files using
an independent copy of the projection stubs and contain no behavioral oracle.

Cases are organized around component registration/growth, sparse mutation,
entity lifetime and operations, query iteration, coordinate/canonical creation,
visible and edge-chunk iteration, idle cleanup, and unload/reentrancy. Test-only
reflection is used only to reset or inspect private static state; it does not
substitute for production behavior.

## Difficulty and fairness review

This is a hard task because three representations must stay consistent:
sparse component values, per-entity bit masks, and versioned entity presence
masks. The chunk layer then mutates those structures while iterating them and
emits reentrant lifecycle events. Boundary failures occur only after 64/128
registrations, across update-counter wrap, or during teardown, so a local
happy-path edit is insufficient. Revision 2 also exposes the source's actual
`IterateVisibleChunks` axis typo and requires consistent rejection/no-op
semantics across the component facade, sparse store, and versioned masks.

The task remains fair. The prompt states every ownership, boundary, and event
ordering invariant that is scored. All algorithms and affected files are
visible, ordinary C# collection/versioning rules explain the failures, and no
assertion depends on rendering, game assets, timing noise, or an undocumented
tModLoader callback. The repair is comparable to accepted hard tasks because
it requires cross-file state reasoning and negative controls, not because it
contains unrelated requirements.

## Revision history and design verdict

Accepted for implementation. The path is mature production infrastructure,
the failures form one entity-backed chunk-lifetime problem, and the evaluator
can execute the real algorithms without redistributing Terraria binaries.

Revision 2 contains 42 cases in nine behavior groups; its design, oracle, and
controls are complete, while exact-revision calibration is deferred until the
requested ten-task authoring pass is finished.

## Revision 3: exception-safe, reentrant chunk teardown

A remaining production-lifecycle gap is visible in `Chunks.DestroyChunk`: the canonical mapping is removed,
then a multicast `OnChunkDestroyed` event is invoked, and only afterward is
the backing entity destroyed. A throwing subscriber can therefore leave a
live, unmapped entity and abort cleanup of later chunks. During `Unload`, an
observer can also request a new chunk after its predecessor is removed; the
system then nulls the dictionary without destroying that new entity.

The revised contract keeps the established event order but requires
per-subscriber exception isolation and eventual entity destruction. Idle
cleanup may recreate a coordinate, whose new entity must survive; world
`Unload` must reject reentrant creation until a subsequent `Load`. These are
one coherent lifetime/ownership invariant on the same `Chunks` production
path, not a separate algorithm. New tests observe two subscribers, multiple
chunks, old versus recreated entity identity, and post-reload creation.
They use only public `Chunks` methods and documented C# event behavior. A
new starter/oracle control and independent strict calibration attempt are
required for this revision.

The revised controls are 21/46 on the frozen starter and 46/46 on the
oracle.

## Revision 4 design brief: generational entity-slot reuse

The prior teardown revision still leaves a production-scale lifetime problem
in `DataStorage.CreateEntity`: every destroyed entity permanently consumes a
new index. Chunk churn therefore grows the version, presence, component-mask,
and every sparse component index domain according to historical creations,
even though destroyed handles already carry generations specifically suited
to safe slot reuse.

This revision makes entity allocation a generational free-slot lifecycle.
`DestroyEntity` clears components and presence before publishing a slot for
reuse, publishes it exactly once, and advances the generation without ever
issuing reserved version zero to a live entity. A slot that exhausts
`uint.MaxValue` is retired at the invalid zero generation instead of wrapping
to an older live generation. `CreateEntity` consumes released slots before
extending the high-water index domain. Reuse must not leak presence bits,
component masks, or sparse values; old handles remain invalid and reject all
operations, while the replacement participates normally in existing queries.
`Clear` keeps a live entity and therefore never releases its slot. When
several slots are released, all must be reused before the high-water
`EntityCount` grows; no arbitrary free-list ordering is required.

This crosses the retained real ECS and chunk layers rather than adding a
standalone allocator. A chunk removed by normal cleanup may later receive a
reused backing index, but the new version and freshly initialized `ChunkInfo`
must distinguish it from the stale chunk entity. Existing reentrant teardown
ordering remains unchanged: an observer-created replacement during the old
destroy event cannot reuse the still-live old slot.

The evaluator will extend the existing entity/query/chunk harness with churn,
multiple-release, stale-handle, mask-leak, clear-versus-destroy, and chunk
recreation cases. Every assertion follows from this public contract and
visible generational handle fields. This is a substantial storage-lifetime
repair comparable to accepted server lifecycle work: it requires coordinating
allocation, versions, sparse components, masks, queries, and chunk identity.
The revised controls are 23/57 on the frozen starter and 57/57 on the oracle.

## Revision 5 design brief: load-order capacity and lifecycle snapshots

This revision returns to the retained production code and extends only defects
that arise on normal mod-loading and world-lifecycle paths.

First, tModLoader registers component types before ordinary world entities are
created. `DataStorage.CreateComponent` previously advanced
`componentMasksPerEntity` only when the entity-mask backing array was already
nonempty. Registering the 64th or 128th component during normal load therefore
left the declared width at one word; the first later entity could not store a
high component, and queries created during registration could not retain high
include/exclude bits. Four bounded cases register fixed type sets before any
entity exists, then exercise later entity and query behavior across both mask
boundaries. This is not an artificial stress loop: it matches the actual
component-registration-before-world-allocation order.

The component registry also indexed `Type.Name` with last-writer-wins
semantics. Closed generic component types share the same simple name, so a
later registration silently redirected string lookup to an unrelated type.
Revision 5 preserves typed handles but makes ambiguous simple names explicitly
unresolvable. A unique-name control prevents a solution from disabling the
registry wholesale.

Second, an active query iterator retained live spans into global filters and
read global presence/version arrays as it advanced. Mask-array growth could
invalidate those spans; a later filter mutation changed a pass already in
progress; and an entity created or a slot generation reused after
`GetEnumerator` could be substituted into an earlier pass. The revised public
contract defines `GetEnumerator` as the snapshot boundary for filters,
candidate presence, and candidate generations. It still validates each
candidate at visitation, so destruction before yield is omitted. Entity
validity now also requires a presence bit, closing the related absent-current-
version alias. Six independent cases cover growth, filter mutation, later
creation, generation reuse, destruction, and absent-slot validity.

Third, `TryGetOrCreateChunkAtWorldPosition` converted world coordinates to a
chunk coordinate and then passed that value to the tile entrypoint, which
divided it by 64 a second time. Positive positions outside chunk zero therefore
created the wrong canonical entry. Three cases establish the world, tile, and
chunk entrypoint equivalence in both axes.

Finally, chunk creation and enumeration had no ownership boundary comparable
to the already-repaired destruction path. `OnChunkCreated` was invoked as one
multicast delegate, allowing an early exception to suppress later subscribers;
an observer could unload the system or destroy the new backing entity while
the outer call still returned `true` and a stale handle. `TryGetChunk` also
trusted stale dictionary entries, and `IterateAllChunks` exposed the live
dictionary value view. Revision 5 treats creation as a transaction: isolate
subscribers, revalidate the same live canonical entity afterward, fail with an
invalid output if ownership was lost, and never remove a newer replacement.
Lookup prunes stale/corrupt mappings so a fresh generation can be rebuilt.
All-chunk iteration captures an immediate handle snapshot that is stable across
later creation and unload. Six cases exercise subscriber failure, reentrant
unload, direct entity destruction, stale rebuild, later creation, and unload.

The revision adds 21 cases in six new behavior groups, for 78 cases in 16
groups total. The oracle passes 78/78 and the frozen starter passes 25/78. All
new assertions are stated in the public prompt, use retained production APIs,
and run in isolated processes.
