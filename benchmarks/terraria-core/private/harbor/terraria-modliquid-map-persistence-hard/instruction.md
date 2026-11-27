# Repair ModLiquid Library map persistence

The frozen ModLiquid Library 2025.12.0.0 source contains related failures in
custom-liquid map-registry publication and teardown, runtime option selection,
the `.tlmap` sidecar's header discovery, sparse/RLE validation, transactional
decode, local/cloud lifecycle, and the map IL hooks. Repair the existing
production code; do not replace it with a parallel registry or map format.

Work in `ModLoader/MapLiquidLoader.cs`, `Hooks/MapLoaderHooks.cs`,
`IO/MapLiquidIO.cs`, `Hooks/MapHelperHooks.cs`, and
`Hooks/WorldMapHooks.cs`. `ModLoader/MapEntry.cs` is the retained registry
entry model. Keep existing types and method signatures, and preserve the
existing on-disk field order. You may add private helpers. Keep the submission
source-only; do not add binaries, archives, build output, or dependencies.

## Required behavior

### Publish one coherent custom-liquid registry generation

`MapLiquidLoader.PublishEntries` receives the color and localized-name tables
that tModLoader is constructing. Both inputs are required and their counts
must match. Build the complete prospective custom-liquid registry before
changing either caller table or any global mapping. Visit custom liquid types
in ascending numeric order and retain each type's map-entry insertion order.
Each type must be in `[LiquidID.Count, LiquidLoader.LiquidCount)`, have a
nonnull, nonempty entry list, and every entry must have both a localized name
and a name callback.

The first option for a liquid is
`MapHelper.modPosition + originalColors.Count + priorCustomOptionCount`.
Every resulting map type must fit in `ushort` and must not collide with a tile
or wall old-type mapping or a name callback not owned by the preceding liquid
publication. On any validation, arithmetic, or collision failure,
throw `InvalidOperationException`: retain the original caller table references
and contents, `liquidLookup`, `entryToLiquid`, `MapLoader.nameFuncs`, and the
registry generation exactly as they were.

On success, replace the two caller tables with staged tables; preserve the
existing vanilla `[0, LiquidID.Count)` lookup prefix; publish a lookup base for
every custom liquid, a reverse owner for every option, and its matching name
callback; preserve unrelated name callbacks; remove callbacks owned only by
the preceding liquid generation; and advance `MapLiquidLoader.Generation`
exactly once. The published arrays and dictionaries must describe the same
generation.

`UnloadModMap` performs the inverse on clients and dedicated servers alike:
clear liquid definitions and reverse mappings, truncate the lookup to
`LiquidID.Count` while preserving its vanilla prefix, remove only liquid-owned
name callbacks, clear `initialized`, and advance the generation exactly once.
Do not leave dedicated-server-only stale state.

For a map type with no liquid owner, `ModMapOption` is a no-op. Otherwise,
snapshot the selected owner, its option list, lookup base, contiguous reverse
mapping, and generation; the incoming map type itself must be inside that
contiguous option range. Resolve the registered `ModLiquid`, then invoke its
`GetMapOption(i, j)` callback exactly once. Resolve the result from the
published lookup base, not from the incoming option's old type. An option at
or above the current option count throws `ArgumentOutOfRangeException`.
Before invoking the callback and again before assigning the `ref mapType`,
reject an owner, list identity/count, lookup, contiguous-range, or generation
change with `InvalidOperationException`. Every failure leaves the caller's
map type unchanged.

### Emit a deterministic, resolvable header

Include only map types from cells with type at or above
`MapHelper.modPosition` and `Light > 18`. Emit each old type once in ascending
numeric order. Return `false` and write no bytes when none exist; reject a
count larger than `ushort.MaxValue` before writing a partial header.

Preserve the existing tile-versus-nontile discriminator and the existing mod,
name, and option fields for tiles, custom liquids, walls, and missing content.
On load, accept only the canonical discriminator bytes zero and one, require
old types to remain in the mod-map range and appear in strictly ascending
order, and allow a zero-entry header only when it ends the stream. An option
outside that content's current option count falls back to zero. Missing content
maps to type zero. Duplicate definitions, malformed string framing, and a
zero-entry header followed by tile payload are malformed.

Treat the map and content registries as a coherent save snapshot. Capture the
dimensions, map object, and X-major cell values once before resolving header
entries; both the header and payload must describe those captured cells even
if resolution callbacks later mutate the live map. Copy the three old-type
registry mappings before resolving entries. One old type present in more than
one tile/liquid/wall registry is malformed. A registered entry must have a
nonempty mod/name identity, a lookup base in the mod-map range, at least one
option, and an old type representable by that base and option count.

Prepare the complete header and payload before transferring any bytes to the
supplied writer. A snapshot, registry, identity, option, or serialization
failure is `InvalidDataException` and leaves the writer's prior bytes and
position unchanged. The file wrapper performs no write or delete when this
preparation fails.

Bind each complete `.tlmap` save or load to one
`MapLiquidLoader.Generation`. Capture it before registry-dependent work and
verify it immediately before transferring prepared bytes or committing map
cells, including a zero-entry load. If a loader or content-resolution callback
publishes or unloads a registry generation in between, surface
`InvalidDataException`; the writer and file output remain untouched on save,
and the destination map remains untouched on load.

### Preserve sparse scan and run-length boundaries

Traverse the whole map in X-major/Y-minor order. Sparse skips include tile
zero, cross row/column boundaries, split into 255-byte chunks, and correctly
represent the final cell without inventing a record. A skip beyond the world
is malformed.

Equal visible entries retain the existing continuation/RLE representation.
Use exactly one count byte through 255 repeated cells, two bytes from 256
through 65,535, and four bytes from 65,536 upward. Preserve type, light, and
color. Adjacent distinct mod entries use the continuation flag without an
intervening skip byte.

### Validate completely before committing

Treat the sidecar as untrusted. Reject reserved flag bits, inconsistent or
non-minimal run-width flags, zero runs, missing type-table references,
truncated fields, runs beyond the world, a continuation beyond the final cell,
and trailing bytes. A missing type table is malformed as well. Surface every
malformed header or payload framing failure as `InvalidDataException`.

For a nontile header entry, resolve custom-liquid and wall identities before
choosing either. If both resolve, reject the ambiguous entry. Resolved content
must have at least one option, and its base lookup plus the selected (or
fallback-zero) option must remain in the mod-map `ushort` range.

Do not mutate `Main.Map` until the entire payload has been parsed and
validated. On success, commit each decoded cell exactly once; cells represented
only by skips remain untouched. On any header or payload failure, leave the
whole live map unchanged.

Capture the destination map object and dimensions before header resolution.
If either changes before commit, reject the stale load without mutating the old
or new map. The final commit is itself transactional: if any `SetTile` call
throws, restore every cell already written and also the failing target in case
the engine primitive mutated it before throwing. Surface
`InvalidDataException` and leave skipped cells untouched. Apply the same rules
through the file wrapper.

### Keep local and cloud sidecars coherent

Always change the supplied path extension to `.tlmap`. Write exactly once only
when visible mod-map data exists. Otherwise delete the local sidecar for a
local save, or ask the available cloud provider to delete the cloud sidecar.
If a cloud provider is unavailable, never fall through to deleting the same
path on the local filesystem. A missing read target performs no byte read.
Dispose read streams and apply the same transactional validation to file loads.

### Preflight every map hook before emitting IL

`MapLoaderHooks.AddLiquidToFinishSetup` must locate exactly one ordered
sequence that stores the color table local, constructs a
`List<LocalizedText>`, and stores the name table local. Prove uniqueness before
emitting anything, then forward both locals by reference to
`MapLiquidLoader.PublishEntries`.

`MapHelperHooks.AddLiquidMapEntrys` must likewise preflight both of its ordered
anchors: the exact `MapHelper.liquidPosition + mapIndex` store, followed by the
exact `Terraria.ModLoader.MapLoader.ModMapOption` call with the map-type local
by reference and arguments zero and one. Preserve all discovered locals and
delegate to the custom-liquid lookup and `ModMapOption` paths.

`MapHelperHooks.IncrimentLiquidMapEntries` must preflight all three ordered
anchors: the store to `MapHelper.liquidPosition`, the `Color` array copy, and
the later constant-four use of that same map-choice local. Its delegates reset
the vanilla lookup, record each copied liquid color's map type, and substitute
`LiquidID.Count`. For all three hooks, a missing, duplicated, reversed, or
wrong-owner anchor throws `InvalidOperationException` with no emitted IL.

### Integrate with exactly one sidecar save and load anchor

`MapHelperHooks.SaveTLMap` must locate exactly one sequence that loads the
path local, loads the cloud-save local, and calls tModLoader
`MapIO.WriteModFile`. Only after proving that cardinality, inject the same two
locals in the same order and delegate to `MapLiquidIO.WriteModFile`.

`WorldMapHooks.InitaliseTLMap` applies the equivalent rule to
`MapIO.ReadModFile` and `MapLiquidIO.ReadModFile`. A missing or duplicate
anchor is an `InvalidOperationException` and emits no partial IL. Do not match
a different owner or similarly named method.

## Public check

Run `python3 tools/smoke.py` to compile the production files in the offline
.NET 8 source projection. It contains no behavioral assertions. Private
evaluation uses separate map/loader/I/O/IL doubles and invokes the production
header, RLE, decoder, file wrapper, and hook methods directly. The full profile
also compiles submitted production sources into a verifier mod and runs
task-specific sentinels inside pinned tModLoader `2026.7.3.0` on a Terraria
`1.4.4.9` dedicated server. Client-only rendering and IL-hook execution remain
covered by the source projection rather than being claimed as live-engine
evidence.
