# Provenance and review receipt

## Frozen source

- Repository: `https://github.com/Fargowilta/FargowiltasSouls`
- Commit: `226fadeadbe3422785a7708ba2cdf53bd8548c00`
- Mod version: Fargo's Souls Mod 1.7.3.7
- License: MIT
- Platform context: Terraria 1.4.4.9 and tModLoader 1.4.4 stable API

The starter retains the four frozen upstream production files byte-for-byte,
plus the upstream build metadata and license. The package contains source and
license only; assets, referenced DLLs, Git data, caches, and build output are
excluded.

## Real production path

`ToggleLoader` owns the global accessory-effect definitions registered during
mod loading. Every `FargoSoulsPlayer` owns a `ToggleBackend`; that backend
hydrates custom presets from tModLoader `Preferences`, restores disabled
effects, supplies the toggler UI's bulk and custom-preset actions, and creates
the state snapshot later sent by player synchronization. `SoulCheck` is the
runtime extension path used by accessory effects to query and update those
toggles. The evaluator invokes these production files; doubles supply only
engine-owned boundaries and representative effect definitions.

## Historical grounding

Upstream history includes `fa9a7e066d317b9113d88b77de370f6f99fe2cf0`
("Toggler Reimplemented full Toggler functionality, including presets"),
`a438fc26ef496a65ce201d4acf24d9b58c2928b8` (loading and ordering fixes),
`bc1dcf7912482aa0d487007b8d82d7a8198f07e8` (guarded toggle checks),
`8709a672fe8f25b6001b00a633e396b5746f8980` (custom-preset save work), and
`236335c6ff99815f1d7cee5d28c38f9f96193f75` (effect defaults). At the frozen
revision, backends alias the global dictionary and toggle objects, persisted
keys use collision-prone short names, player restore and `SetAll` route
through `Main.LocalPlayer`, null slots leave stale preference keys, and lookup
helpers still have unsafe null paths.

## Fairness and uniqueness

All 82 cases map to explicit prompt clauses. The prompt states lifecycle,
identity, ordering, slot bounds, default restoration, target ownership,
snapshot replacement, dedicated-server boundaries, and Mutant Presence
semantics. The tests use visible preferences and effect flags; no UI timing,
random world state, hidden type names, or unmentioned wire format is involved.
This task is distinct from the other Terraria tasks because it repairs the
boundary between immutable global definitions, mutable per-player values,
durable user presets, built-in preset application, and runtime effect queries.
The revised built-in-preset cases invoke the two existing production methods
with a nonlocal backend and sparse registry; they do not add synthetic seams.

## Revision history

Revision 2 extends the same four production files with immutable registered
definition metadata and live registry-generation reconciliation. Initialized
player backends atomically preserve values by stable identity, add captured
defaults, remove missing effects, rebind all preset slots, and publish only
current objects. Virtual identity resolution is an explicit untrusted callback:
an exception or reentrant registry change discards the whole candidate and is
retried on the next entry. Runtime suppression uses canonical registered flags,
not caller aliases. These rules are public and require no verifier-only seam.
The oracle passes all 82 cases and the frozen starter passes 25/82.
