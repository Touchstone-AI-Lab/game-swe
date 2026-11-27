# Terraria task 06 design: ModLiquid map persistence

## Candidate and provenance

- Upstream: `https://github.com/Lion8cake/ModLiquidLib`
- Frozen revision: `282498893150b53d2e52efe26be0813aa8c8e193`
- Upstream version: ModLiquid Library 2025.12.0.0
- License: MIT
- Platform: Terraria 1.4.4.9 and the tModLoader 1.4.4 stable API
- Production path: `IO/MapLiquidIO.cs` writes and reads the `.tlmap` sidecar
  used to persist visible mod tile, wall, and custom-liquid map entries.
- Expanded production path: `ModLoader/MapLiquidLoader.cs` and
  `Hooks/MapLoaderHooks.cs` publish and tear down the custom-liquid map
  registry used by that same sidecar, while `Hooks/MapHelperHooks.cs` applies
  its runtime option mapping.

Upstream commit `59ac922fd286e9348345c489ae8670ca97a3a5f8` introduced the
complete sidecar format. In the frozen implementation, header discovery and
payload discovery use different visibility predicates, so a world containing
only hidden entries still produces a sidecar and unused definitions. The
decoder also mutates the live map before a malformed stream is known valid.

## Operator reports to preserve in the task contract

1. Header entries include only visible persisted mod-map types (`Light > 18`),
   are unique and ascending by old type, reject an unrepresentable count, and
   produce no bytes when no mod data exists.
2. Tile, liquid, wall, and missing-content header entries round-trip through
   existing loader tables. Out-of-range style options fall back to option zero;
   duplicate old-type definitions are malformed.
3. Header decoding accepts only canonical boolean discriminator bytes, requires
   strictly ascending mod-range old types, rejects payload after a zero-entry
   header, and normalizes malformed string framing to `InvalidDataException`.
4. Sparse skip runs traverse the complete map in X-major/Y-minor order,
   preserve tile zero and row/column boundaries, split at byte 255, and neither
   invent nor omit a record at the final cell.
5. Equal visible map tiles use exact 1-, 2-, or 4-byte run counts at the
   255/256 and 65,535/65,536 boundaries. Adjacent distinct mod records use the
   continuation flag and preserve type, light, and color without byte bleed.
6. Decoding validates reserved flags, the presence of the type table, every
   run-width combination, zero counts, type references, EOF, run bounds, and
   continuation-at-world-end. Any malformed stream throws
   `InvalidDataException` and leaves the entire live map unchanged.
7. A valid decoded payload is committed exactly once after full validation;
   missing content maps to type zero, hidden/vanilla cells remain untouched,
   and trailing bytes are rejected rather than silently ignored.
8. File wrappers use the `.tlmap` extension, dispose readers, write only when
   data exists, delete the correct local/cloud sidecar when it does not, avoid
   a local delete for an unavailable cloud provider, and do no I/O for a
   missing read target.

## Expected repair shape

The retained production file is `IO/MapLiquidIO.cs`. The repair coordinates
header construction, binary run encoding, a validate-then-commit decoder, and
local/cloud file lifecycle while preserving existing method signatures and
the on-disk field order.

## Evaluation boundary

The evaluator directly compiles the production file in a .NET 8 source
projection. Test doubles provide only Terraria map storage, content-loader
registries, and local/cloud byte I/O. Private tests invoke the real header,
RLE, decoder, and file wrapper methods. Public smoke uses an independent stub
copy and has no behavioral assertions.

## Difficulty and fairness review

This is hard because the same cursor is advanced by sparse skips, RLE runs,
and the continuation bit, with three integer widths and two end-of-world
representations. Transactional decode requires separating parsing from map
mutation across header and payload failures. Cloud/local cleanup adds a
second state machine but remains part of the same `.tlmap` lifecycle.

The task is fair: the prompt states scan order, thresholds, flag semantics,
error type, rollback rule, option fallback, and file behavior. No assertion
depends on rendering, native hooks, random state, or undisclosed assets.

## Design and implementation verdict

Accepted and locally audited. The strengthened revision has 54 named contracts
across eight behavior groups, with a one-to-one match between rubric, contract
map, and executable cases. The frozen starter passes 29/54 while the oracle
passes 54/54; both projections compile with zero warnings and zero errors. It
is a real released-library persistence path, contains demonstrable frozen
bugs, and is independent from the earlier quest, entity, geometry,
tile-entity, and compressed-I/O tasks.

## Revision 2: coherent snapshots and fail-closed hook integration

The 54-case codec contract could be repaired as a largely self-contained
rewrite of one source file. Revision 2 extends the same production failure
chain instead of adding unrelated format features.

`WriteModMap` now has an explicit prepare/commit boundary. It must capture one
X-major map snapshot, resolve every visible type against one coherent registry
view, serialize from that snapshot, and transfer bytes to the caller only after
preparation succeeds. Registry collisions, invalid lookup bases/options, and
resolution failures therefore cannot leave a partial sidecar or cause the
header and payload to describe different map generations.

The load transaction captures the destination map object and dimensions before
header resolution. A registry callback that swaps worlds or changes geometry
invalidates the load before any tile is committed. If a real `SetTile` call
throws during the final commit, already written cells are restored and the
failure is normalized without touching skipped cells. The nontile
discriminator must also reject an identity that resolves simultaneously as a
custom liquid and a wall.

Finally, the retained upstream `MapHelperHooks.SaveTLMap` and
`WorldMapHooks.InitaliseTLMap` methods are part of the evaluated production
path. Each IL edit must locate exactly one tModLoader `MapIO` anchor before
emitting anything, forward the captured path/cloud arguments in order, and
fail closed when the target call is absent or ambiguous. These requirements
connect the codec to the actual save/load lifecycle and require coordinated
reasoning across three upstream files. They remain fair because the prompt
states the snapshot boundary, collision policy, rollback behavior, anchor
identity, and cardinality explicitly; the projection doubles only model the
external Terraria and MonoMod APIs used by those files.

Revision 2 has 74 named contracts across 12 behavior groups. The oracle passes
74/74, the frozen starter passes 33/74, and both public source projections
compile with zero warnings and zero errors.

## Revision 3: one registry generation across publication, runtime, and disk

Revision 3 follows the frozen production call graph outward rather than adding
more parser edge cases. It retains the real
`MapEntry`, `MapLiquidLoader`, and `MapLoaderHooks` files and connects their
state transitions to the already-retained `.tlmap` operations.

The registry publisher must validate and stage every liquid option before
replacing tModLoader's color/name tables, liquid lookup bases, reverse-owner
map, or name callbacks. Publication order is numeric liquid type followed by
entry insertion order. Range, null-entry, arithmetic, tile/wall ownership, and
foreign name-callback collisions are rejected without any observable mutation.
A successful publication or either client/dedicated-server unload advances a
single explicit generation and keeps only the callbacks owned by the current
liquid generation.

Runtime `ModMapOption` is a reentrant transaction over that state. It validates
the selected contiguous option topology, resolves the registered liquid, and
invokes its coordinate callback once, but commits the caller's `ref mapType`
only if the generation, owner, list identity/count, lookup base, and reverse
range are still identical. The sidecar writer and reader capture the same
generation and reject callback-driven republication before output or map
commit. This prevents a structurally valid sidecar from combining identities
from two registry generations.

The expanded hook surface adds six upstream IL anchors. The finish-setup hook
must uniquely locate the two registry-table locals. Runtime lookup injection
must prove both of its anchors, and liquid-count setup must prove all three of
its ordered anchors. Missing, duplicate, reversed, and wrong-owner shapes fail
before the first emitted instruction, complementing the existing one-anchor
save and load rules.

Revision 3 has 103 named contracts across 17 behavior groups. Every new case
maps to an explicit English prompt clause and an existing production state
transition. The oracle passes 103/103 and the buildable frozen starter passes
38/103 in isolated local controls.
