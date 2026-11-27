# Provenance and review receipt

## Frozen source

- Repository: `https://github.com/Mirsario/TerrariaOverhaul`
- Commit: `55c23fbde42f6fcb9eb266992475a040d14c2b84`
- Mod version: Terraria Overhaul 5.0.0.38
- License: GPL-3.0, Copyright (c) 2020-2026 Mirsario & Contributors
- Platform context: Terraria 1.4.4.9 and tModLoader 1.4.4 stable API

The retained production files are byte-identical to the listed upstream blobs;
there is no injected starter delta. License and build metadata are retained.
No assets, Git metadata, package caches, binaries, or build output are part of
the task.

## Real production path

`DataStorage` allocates component handles, per-entity masks, query masks,
versioned entity records, and sparse values. `Entities` is the normal facade.
`Chunks` creates a `DataEntity` with `ChunkInfo` for each live world chunk and
destroys idle chunks in `PostUpdateEverything`. `SparseSet` and `BitMask` are
the production storage primitives called by those paths. Private cases compile
and invoke these exact five files; doubles supply engine-owned types only.

## Historical grounding

Upstream commits `98915aa96d1ff8b4fb0f41bd1332b36fa8c88d52`,
`1bf023a1b3b5f8ab8f97a9d4f6acfb7bd0c68141`, and the frozen revision changed
idle chunk unloading, entity destruction, component ownership, and query
tests in this same path. The task asks for maintainable completion of those
invariants at real capacity, lifetime, reentrancy, and wrap boundaries.

Revision 2 also covers ordinary operations already exposed by `DataEntity`
(`Remove`, `Get`, `Clear`, and `AddByHandle`) and repairs a directly visible
frozen-source defect in `Chunks.IterateVisibleChunks`: its bottom coordinate
was computed from `Main.screenPosition.X` rather than `Y`. Creation-event and
partial-edge checks preserve the initialization and rectangle logic adjacent
to that runtime path.

## Fairness and uniqueness

All 78 assertions map to explicit prompt clauses in `case-contracts.tsv`.
Capacity reuse is observed through the existing `SparseSet.Dense` property;
the last-generation setup directly exercises the retained internal version
array in the same compiled source projection, but no private-only API is
required of the repair. This task differs substantively from compressed binary I/O and
the Enchanted Tree transaction: it evaluates an ECS-like storage engine and
the world-chunk lifecycle built directly on it. The Python verifier shell is
shared infrastructure; the prompt, production path, C# cases, and oracle are
independently authored.

## Revision history

Revision 3 adds explicit exception-safe and reentrant chunk-teardown behavior.

Revision 4 adds a generational free-slot lifecycle to the same production data
store. Eleven new cases require destroyed slots to be published once, reused
before high-water growth, retired instead of wrapped when their generation is
exhausted, cleared of sparse and mask state, and safely reintroduced to
existing queries. Two of those cases
exercise real chunk cleanup: normal recreation receives fresh `ChunkInfo`,
while observer-time replacement cannot reuse an entity whose destruction event
is still running. The frozen starter passes 23/57 and the oracle passes 57/57.

Revision 5 adds 21 cases grounded in four visible defects on the same retained
path: mask width did not advance when components were registered before the
first entity; active query iterators observed mutable global filters,
presence, and generations; the world creation entrypoint divided coordinates
twice; and chunk creation/iteration exposed callback and dictionary mutations
without a transaction or snapshot boundary. The prompt defines the exact
snapshot, ambiguity, observer, and stale-mapping semantics. The oracle passes
78/78 and the frozen starter passes 25/78.
