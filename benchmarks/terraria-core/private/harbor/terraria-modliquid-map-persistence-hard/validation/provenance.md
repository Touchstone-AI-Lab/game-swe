# Provenance and review receipt

## Frozen source

- Repository: `https://github.com/Lion8cake/ModLiquidLib`
- Commit: `282498893150b53d2e52efe26be0813aa8c8e193`
- Mod version: ModLiquid Library 2025.12.0.0
- License: MIT, Copyright (c) 2026 Lion8cake
- Platform context: Terraria 1.4.4.9 and tModLoader 1.4.4 stable API

The starter production files and metadata preserve the frozen upstream content
with repository-required LF normalization. To keep the expanded starter
buildable against the stated contract, the existing nontransactional
`MapLoaderHooks` publication body is extracted into the new
`MapLiquidLoader.PublishEntries` seam and exposes a generation counter; the
hook still performs the same eager partial mutations. This is contract
scaffolding, not the reference repair. Original Git blob IDs are recorded
separately. The license is retained; assets, binaries, Git data, caches, and
build output are excluded.

## Real production path

`MapLoaderHooks.AddLiquidToFinishSetup` publishes `MapEntry` definitions into
tModLoader's color, name, lookup, reverse-owner, and name-callback registries.
`MapLiquidLoader.ModMapOption` then resolves per-cell custom-liquid options and
`UnloadModMap` tears that state down. `MapLiquidIO.WriteModFile` and
`ReadModFile` own the `.tlmap` sidecar lifecycle. `MapHelperHooks` injects both
runtime liquid lookup behavior and sidecar saves; `WorldMapHooks.InitaliseTLMap`
injects sidecar loads immediately after tModLoader's own map call.
`WriteModMap`/`ReadModMap` translate runtime content identity, while
`WriteMapData`, `WriteMapTile`, `ReadMapData`, and `ReadMapTile` are the real
sparse/RLE codec over `Main.Map`. The evaluator directly compiles and invokes
these six sources; doubles only expose external storage, loader, file, and IL
APIs.

## Historical grounding

Upstream commit `59ac922fd286e9348345c489ae8670ca97a3a5f8`, "Map stuff
(including .tlmap file stuff)", introduced this complete production sidecar
and its custom-liquid map integration. The frozen publisher mutates shared
tables in dictionary iteration order before validating later entries, unload
leaves dedicated-server mappings behind, runtime option selection can commit
against a reentrant registry change, and three hook methods emit after finding
only their first anchor. The frozen writer also discovers header types without
the payload's visibility predicate, while the decoder writes live map cells
before later validation can fail. The repair keeps the registry and file
formats while making their shared generation deterministic and transactional.

## Fairness and uniqueness

All 103 cases map to explicit prompt clauses. The prompt states registry
ordering, range and collision rules, publication/unload generation boundaries,
runtime callback transactions, sidecar generation binding, multi-anchor
preflight, scan order, visibility threshold, canonical header order and
discriminator values, count widths, continuation semantics, malformed-input
normalization, rollback, option fallback, coherent save and destination
snapshots, registry ambiguity, commit rollback, cloud/local behavior, and
exact IL-anchor cardinality. Boundary tests use real registry topology, format
thresholds, reentrant lifecycle races, and upstream hook shapes rather than
arbitrary puzzles. This task is distinct from prior tasks because it repairs a
custom content registry, world-map sidecar codec, transactional file load, and
all of their real hook integration as one generation.

## Revision history

Revision 2 was a substantial same-path redesign: save output is prepared from a
single map/registry generation, load commits are bound to one destination
generation and roll back engine write failures, and the real save/load hooks
must prove a unique tModLoader anchor before emitting. The oracle passes 74/74
and the frozen starter passes 33/74.

Revision 3 expands along the already-frozen production call graph, not by
adding parser trivia: it retains `MapEntry`, `MapLiquidLoader`, and
`MapLoaderHooks`; requires atomic deterministic publication and symmetric
teardown; makes `ModMapOption` a generation transaction; binds `.tlmap`
save/load to that same generation; and preflights every anchor in the three
map-hook methods before any emission. The oracle passes 103/103 and the starter
passes 38/103 in isolated local controls.
