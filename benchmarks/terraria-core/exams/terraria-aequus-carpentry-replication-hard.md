# Repair Aequus carpentry replication

The frozen Aequus 2.7.3.3 source has coupled failures in carpenter challenge
persistence, building validation, world synchronization, multiplayer authority,
and player-state cloning. Repair the existing production path; do not replace
it with a parallel carpentry system.

Work in these files:

- `Common/Carpentry/BuildChallengeSaveData.cs`
- `Common/Carpentry/BuildBuffsData.cs`
- `Common/Carpentry/CarpentrySystem.cs`
- `Common/Carpentry/CarpentryPlayer.cs`

Keep existing public method signatures and the misspelled public
`RecieveData` name. Keep the submission source-only; do not add binaries,
archives, build output, or dependencies.

## Required behavior

### Preserve challenge identity across save and wire formats

Saved completion names are stable, first-seen, and unique. World saving writes
the completed-name list as well as the building lists, so a world save/load
round trip restores both stores. Saving stores an
independent list; loading clears stale entries and canonicalizes duplicates.
Names for unloaded content survive local save/load.

Network completion frames contain unique registered challenge `Type` values
in ascending order, never positions in the saved-name subset. Omit unloaded
names from the frame without deleting them locally. On receive, bound the
count by the current registry, reject negative counts, duplicate or invalid
IDs, nonascending IDs, and truncation as `InvalidDataException`. Parse into
temporary state and replace the live list only after the whole frame is valid.
A present completion save key with a value other than a string list is
malformed: throw `InvalidDataException` without changing the live list.

### Bind transient IDs to one canonical registry generation

Every operation which maps a challenge `Type` to a `FullName`, building group,
selected bounty, or buff uses one captured registry generation. A canonical
registry has exactly `BuildChallengeCount` nonnull entries; entry `i` has
`Type == i`; and every `FullName` is nonempty and ordinal-unique. A generation
also captures entry object identity and `BuildBuffType`. Outbound save/wire
preparation that needs an invalid registry throws `InvalidOperationException`
before writing anything. Receive/load paths normalize it to
`InvalidDataException` and preserve live state; boolean mutators and gameplay
queries fail closed.

Completion, building, and whole-world receivers must reject a registry which
changes while bytes are being read. Whole-world save/send/receive uses the same
generation for both sections. Outbound frames are fully prepared before the
first caller-writer call, so a writer callback that mutates live state or the
registry cannot mix generations in the bytes already being emitted.

### Keep building persistence and validation coherent

Loading building rectangles clears stale world data once, continues past
missing challenge keys, and copies retained lists. A present matching building
key whose value is not a rectangle list is malformed and rolls the load back.
Building groups are owned by stable challenge `FullName`, even though the
public live dictionary is keyed by transient `Type`: registry reordering must
move geometry to the returning challenge's new type. Valid groups for unloaded
content survive local load/save by their `BuildingBuffs_{FullName}` key, remain
dormant and omitted from wire/gameplay, and reactivate when that name is
registered again. Direct live groups without recorded provenance bind to the
current canonical entry on first observation; unknown numeric IDs are skipped.

Saving copies nonempty lists after validation, skips stale challenge IDs and
invalid/overlapping rectangles, and must not erase live world state. Save-time
challenge scans filter only the saved snapshot; scan failures or exceptions do
not remove the live rectangle. Loading applies the same rectangle filter.
`ClearWorld` clears active and dormant building state as well as completions.

Accept a building only for a registered challenge, with positive width and
height, signed-coordinate edges that do not overflow, and when it does not
overlap an existing rectangle in that challenge.
During explicit trimming, evaluate every step for every location using fresh
scan results. Remove a location whose scan fails or throws, log scan
exceptions, and continue validating later locations without stalling. Scan
callbacks may reenter and mutate the target group or registry; if they do, the
trim must abandon its stale commit and preserve the callback's changes.

### Make building frames deterministic and transactional

Send exactly the nonempty registered groups in ascending challenge-ID order.
The group count must match the groups actually emitted, and output must use a
snapshot so collection mutation during the write cannot alter the frame.

Receive at most the registered number of groups, at most 4,096 locations per
group, and at most 4,096 locations across the entire frame. The sender enforces
the same global budget and fails before writing any bytes when its canonical
snapshot is too large. A group in the wire frame must be nonempty, matching
the sender's canonical nonempty-group format. Require groups in strictly
ascending challenge-ID order. Reject negative counts, duplicate or unknown
group IDs, nonpositive, overflowing, or
overlapping rectangles, and truncated fields as `InvalidDataException`.
Validate into temporary storage; on success replace the building store once,
and on failure preserve it exactly.

### Enforce world, packet, and clone authority

World sync writes and reads completions first, then buildings, through the
provided reader or writer. Failure in either receive section, a corrupt world
tag section, or a registry-generation change rolls back both stores. World tag
load parses both sections before either commit; world save prepares both
sections before touching the destination tag.

In multiplayer, a client completion is a request and does not mutate local
completion state. A server applies each valid completion once and broadcasts
only a real change. Reset clears authoritative state before broadcasting.
Building add/remove packets likewise follow successful state changes only;
`quiet` changes never echo. Single-player changes stay local.

`CarpentryPlayer.Clone` and `CopyClientState` copy the source selected bounty
and completion names into independent collections. A selected bounty is bound
to its stable full name, follows that name across registry reorder, may remain
dormant while its content is unloaded, and rebinds when it returns. A numeric
selection that never resolved to a canonical challenge is invalid and is not
saved or indexed.

### Apply building buffs through the live player path

Challenge type zero is a valid registered group. `CheckBuffBuildings` ignores
stale group IDs, null lists, invalid rectangles, nonpositive buff IDs, and
nonintersecting buildings. Each registered group grants its positive buff at
most once for 60 ticks when any valid rectangle intersects the player's tile
range. Geometry remains bound to the stable challenge across registry reorder.
Snapshot all applicable groups and captured buff IDs before the first
`AddBuff` call, so an engine callback which mutates building state does not
invalidate enumeration or alter later grants in the current check.
`PostUpdate` runs this check only for the local player, on every tenth update,
and while the danger gate is clear.

## Public check

Run `python3 tools/smoke.py` to compile the four production files in the
offline .NET 8 source projection. It contains no behavioral assertions.
Private evaluation invokes the production persistence, scan, clone,
world-sync, and packet paths directly with separate engine doubles. The full
profile also compiles submitted production sources into a verifier mod and
runs task-specific sentinels inside pinned tModLoader `2026.7.3.0` on a
Terraria `1.4.4.9` dedicated server.
