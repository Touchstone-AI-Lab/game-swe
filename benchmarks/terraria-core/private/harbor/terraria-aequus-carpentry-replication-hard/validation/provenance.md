# Provenance and review receipt

## Frozen source

- Repository: `https://github.com/UriBuilder/AQMod`
- Commit: `f823418776e7dd54b0f370e3ff1b4befc2bc857d`
- Mod version: Aequus 2.7.3.3
- License: MIT for code, Copyright (c) 2022 Nathan Thomas
- Platform context: Terraria 1.4.4.9 and tModLoader 1.4.4 stable API

The starter production files and metadata preserve frozen upstream content
with repository-required LF normalization and no behavioral delta. Original
Git blob IDs are recorded separately. The package retains code and the
upstream license; assets, binaries, Git data, caches, and build output are
excluded.

## Real production path

`BuildChallengeSaveData` owns persistent completion identity and its wire
frame. `BuildBuffsData` owns saved and replicated build rectangles plus live
challenge scans. `CarpentrySystem` connects both stores to world lifecycle and
packets. `CarpentryPlayer` persists personal claims and participates in
ModPlayer cloning. The evaluator compiles and invokes these production files;
doubles provide engine-owned types, registrations, scan callbacks, and packet
recording only.

## Historical grounding

Upstream commit `d305013bd40786760760b3a51d56b6aab19c61e8`, "fix carpenter
not completing challenges in mp", changes the retained completion and system
path. At the frozen revision, completion send still serializes saved-list
positions instead of global challenge IDs, world sync omits the completion
section, clone copies from its own empty destination, building load returns at
the first missing key, and the validation inner loop increments the outer
index. The repair coordinates those interacting responsibilities rather than
inventing an unrelated feature.

## Fairness and uniqueness

All 87 cases map to explicit prompt clauses. Bounds, canonical ordering,
identity, rollback, overflow-safe rectangle validity, lifecycle, authority,
registry generations, unloaded-content retention, reentrancy, global budgets,
cloning, and live player buff rules are stated. Tests use visible fake
challenges and deterministic scan results; no UI, rendering, random world
state, or hidden content names are required. This task is distinct from the
earlier codecs, tile entity, entity store, geometry, and quest tasks because it
repairs one world/player carpentry replication feature across persistent,
authoritative, and gameplay state.

## Revision history

Revision 3 is a substantial same-path redesign: stable full-name ownership now
survives registry reorder and content unload, all persistence/wire/gameplay
operations share explicit canonical registry generations, whole-frame location
budgets are bounded, and engine callbacks cannot mix or clobber snapshots. The
oracle passes 87/87 and the frozen starter 12/87.
