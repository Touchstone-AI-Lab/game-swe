# Terraria task 07 design: Aequus carpentry replication

## Candidate and provenance

- Upstream: `https://github.com/UriBuilder/AQMod`
- Frozen revision: `f823418776e7dd54b0f370e3ff1b4befc2bc857d`
- Upstream version: Aequus 2.7.3.3
- License: MIT for code; retained package contains code and license only
- Platform: Terraria 1.4.4.9 and the tModLoader 1.4.4 stable API
- Production path: carpenter challenge completion and building-buff rectangles
  persist in world/player tags, clone with players, travel through world sync,
  and are updated through client/server packets.

Upstream commit `d305013bd40786760760b3a51d56b6aab19c61e8` is titled
"fix carpenter not completing challenges in mp" and changes two retained
files. The frozen path still writes positions in a player's completion list
as though they were global challenge IDs, clears clone destinations before
copying from themselves, stops loading building data at the first absent key,
and has an inner validation loop that increments the outer index.

## Operator reports to preserve in the task contract

1. Completed challenge names remain stable, first-seen, and unique in saves;
   unknown mod names survive local persistence but are omitted from network
   frames until their content is registered again.
2. Completion network frames contain unique ascending global challenge IDs,
   not positions in the saved subset. Receive validates bounded counts,
   range, and duplicates into temporary state and rolls back on any failure.
3. Building-buff save/load clears stale state once, continues across missing
   challenge keys, copies tag lists, retains nonempty valid rectangles, and
   does not erase live state merely because the world was saved.
4. Building validation scans every step with the correct loop variable,
   removes failed/throwing locations without stalling, keeps later locations,
   and rejects unknown challenge IDs or nonpositive rectangles.
5. Building network send is deterministic by challenge ID, writes a count
   matching exactly the nonempty groups emitted, and snapshots data so caller
   mutation cannot change the frame halfway through.
6. Building network receive bounds groups and per-group locations, rejects
   duplicate/unknown IDs, invalid or overlapping rectangles, truncation, and
   integer abuse transactionally, then replaces state exactly once.
7. World sync writes/reads completions followed by buildings in the provided
   stream; completion/reset and add/remove packets are emitted only for valid
   state changes with correct client/server quiet behavior. Player clone and
   client-state copy produce independent completion lists from the source.
8. Completion and building receivers require canonical ascending IDs;
   persistence and replication reject coordinate-overflow rectangles and
   stale groups. The real player update path treats challenge type zero as
   valid, ignores corrupt groups, and grants intersecting positive buffs only
   through the owner/tenth-tick/no-danger gate.

## Expected repair shape

The retained production files are:

- `Common/Carpentry/BuildChallengeSaveData.cs`
- `Common/Carpentry/BuildBuffsData.cs`
- `Common/Carpentry/CarpentrySystem.cs`
- `Common/Carpentry/CarpentryPlayer.cs`

The repair coordinates stable identity, bounded binary parsing, rectangle
invariants, world lifecycle, packet authority, and deep-copy semantics without
changing public method signatures.

## Evaluation boundary

The evaluator compiles the four production files in a .NET 8 projection.
Test doubles provide Terraria rectangles/players, TagCompound, ModSystem,
packet recording, challenge registration, and scan callbacks. Private cases
execute the production persistence, scan, clone, world-sync, and packet paths.
Public smoke is compile-only.

## Difficulty and fairness review

This is hard because one logical feature has three identities (full name,
global type, subset position), two stores (world/player), two binary payloads,
and client/server request versus broadcast semantics. The most dangerous bugs
look locally plausible and only appear with sparse registries, missing mods,
partial streams, later challenge keys, or cloning.

The prompt states ordering, bounds, rollback, rectangle validity, lifecycle,
and authority rules. Tests use visible fake challenges and deterministic scan
results; no UI, world rendering, randomness, or hidden content names are used.

## Design and implementation verdict

Accepted and locally audited. The strengthened revision has 58 named contracts
across eight behavior groups, with a one-to-one match between rubric, contract
map, and executable cases. The frozen starter passes 11/58 while the oracle
passes 58/58; both projections compile with zero warnings and zero errors. It
is a historically grounded multiplayer and gameplay path from a substantial
released mod and is independent from the prior codec, quest, entity, geometry,
tile-entity, and compressed-I/O tasks.

## Revision 2: persistence audit and canonical receive

A maintainer review exposed an omission in the oracle itself:
`CarpentrySystem.SaveWorldData` saved buildings but not `CompletedBounties`,
although world loading read both stores. Revision 2 fixes the production oracle
and adds an end-to-end world save/load case, rather than counting this omission
as task difficulty. It also states and tests the
canonical building-frame invariant already followed by `NetSend`: emitted
groups are nonempty, so `NetReceive` rejects a declared empty group. The
frozen starter is 11/60 and the corrected oracle 60/60.

## Revision 3: stable identities and reentrant registry transactions

Revision 3 addresses a harder production invariant behind the same four files:
`BuildChallenge.Type` is a loader-session index, while world/player persistence
must remain owned by `FullName`. Building geometry and
selected bounties now follow stable names across registry reordering, unloaded
building groups survive local resaves as dormant state, and returning content
reactivates at its new type without leaking dormant groups onto the wire.

Every ID/name mapping captures one canonical registry generation. Completion,
building, world, and buff paths fail closed on malformed registries; receive
transactions reject mid-read generation changes; and whole-world operations
use one generation for both sections. Output is prepared before the first
caller-writer callback. Save-time scans no longer mutate live state, explicit
trim does not clobber reentrant scan mutations, and buff application snapshots
all groups before the first engine callback. The building frame is also capped
at 4,096 rectangles globally, not merely per group.

These are coordinated state-machine requirements across the same four real
production files, not unrelated format trivia. The public prompt states the
canonical-registry definition, stable-name ownership, dormant lifecycle,
failure classes, reentrancy rule, and budget. Revision 3 has 87 named contracts
across 12 groups; the oracle passes 87/87, the frozen starter passes 12/87, and
both public projections compile without warnings or errors. A fresh strict
calibration is required.
