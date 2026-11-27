# Terraria task 09 design: Fargo's Souls toggle presets

## Candidate and provenance

- Upstream: `https://github.com/Fargowilta/FargowiltasSouls`
- Frozen revision: `226fadeadbe3422785a7708ba2cdf53bd8548c00`
- Upstream version: Fargo's Souls Mod 1.7.3.7
- License: MIT
- Platform: Terraria 1.4.4.9 and the tModLoader 1.4.4 stable API
- Production path: global accessory-effect definitions are materialized into
  per-player toggle backends, persisted in three preference slots, restored
  for a selected player, and queried by runtime accessory effects.

The feature is grounded in the dedicated toggler reimplementation commit
`fa9a7e066d317b9113d88b77de370f6f99fe2cf0`, the loading and ordering repair
`a438fc26ef496a65ce201d4acf24d9b58c2928b8`, the guarded lookup repair
`bc1dcf7912482aa0d487007b8d82d7a8198f07e8`, custom-preset work at
`8709a672fe8f25b6001b00a633e396b5746f8980`, and effect defaults at
`236335c6ff99815f1d7cee5d28c38f9f96193f75`.

## Operator reports to preserve in the task contract

1. The global registry has an explicit load/unload lifecycle and atomically
   rejects null, headerless, duplicate-object, and duplicate-identity entries.
2. Each backend materializes a fresh dictionary and fresh toggle objects with
   per-effect defaults; initialization is idempotent and performs no preference
   I/O on a dedicated server.
3. The three preference slots load independently by exact ordinal `FullName`,
   survive malformed sibling slots, ignore unknown identities, and become
   canonical ordered snapshots.
4. Client save writes every slot before one flush, clears stale null slots,
   and records unique non-null effects by exact ordered identity; server save
   is a no-op.
5. Player restore targets the supplied backend rather than `Main.LocalPlayer`,
   begins from registered defaults, applies persisted full identities, and
   replaces the synchronization snapshot exactly once.
6. One-based custom-preset actions are bounded to slots 1 through 3, remain
   inert on a dedicated server, preserve stored snapshots and the prior
   `disabledToggles` list reference, and report success only for real actions.
7. Runtime lookup resolves equivalent effects by exact `FullName`, returns
   safe defaults for null or missing effects, warns once for a missing set,
   and applies Mutant Presence suppression only to affected/minion effects
   unless checks are explicitly skipped.

## Expected repair shape

The retained production files are:

- `Core/Toggler/Toggle.cs`
- `Core/Toggler/ToggleLoader.cs`
- `Core/Toggler/ToggleBackend.cs`
- `Core/Toggler/SoulCheck.cs`

The repair separates immutable registry definitions from mutable player
state, gives persisted identities a stable namespace, and coordinates
preference, player, preset-action, and runtime lookup behavior without
changing public type or method names.

## Evaluation boundary

The evaluator compiles the four production files in a .NET 8 source
projection. Test doubles provide Terraria players, preferences, localization,
chat parsing, mod-content lookup, and representative effects. Private cases
invoke the production lifecycle, materialization, preference I/O, restore,
preset, and lookup paths. Public smoke is compile-only.

## Difficulty and fairness review

This is hard because the same effect has object identity, short name, stable
full identity, a global definition, three durable preset representations, and
one mutable value per player. Locally plausible fixes often retain shared
toggle objects, clear only populated disk slots, target the wrong player, or
restore a temporary preset without preserving the persistent list reference.

The task is fair: lifecycle, identity, ordering, bounds, server behavior,
snapshot ownership, warning behavior, and suppression flags are stated in the
prompt. Tests use visible effects and preferences; no UI timing, random world
state, assets, or hidden identity is required.

## Design and implementation verdict

Accepted and locally audited. The 55 named contracts cover seven independent
behavior groups and match the executable case list one-for-one. The frozen
starter passes 19/55 cases while the oracle passes 55/55; both source
projections compile with zero warnings and zero errors. The task is a coherent
real-player state isolation and persistence repair, not a collection of
unrelated algorithms.

## Contract correction (2026-09-22)

Five registry tests required `ArgumentNullException` or
`InvalidOperationException` even though the public contract only required
rejected registration and no state change. The corrected tests observe registry
state after a return or an exception, with no hidden exception-class policy.

## Revision: built-in presets must respect backend ownership

The normal built-in preset methods `SomeEffects` and `MinimalEffects` remain
in the retained upstream `ToggleBackend.cs`. Both first call backend-local
`SetAll` but then route their named choices through `Main.LocalPlayer`.
Invoking either method on another player's backend therefore splits one
preset across two players. `SomeEffects` also routes the registered `Pet`
family through the same wrong player. This is the same player-local ownership
defect as `LoadPlayerToggles` and `SetAll`, now exercised through the two
production preset entry points rather than an artificial helper.

The revised public contract names both methods, preserves their visible
choices, and says that absent registry entries are ignored without warning or
insertion. The expected patch redirects all named and `Pet` choices to this
backend's existing toggle objects, while leaving custom-preset storage and
preference I/O untouched. New checks compare a nonlocal backend with
`Main.LocalPlayer`, exercise a sparse registry and `Pet` effect, and verify
custom storage remains independent. A fresh strict attempt is required for
this revision.

The revised starter passes 20/60 and the oracle passes 60/60.

## Revision 2: immutable definitions and live registry rebase

The 60-case repair still treats the global registry as permanently frozen once
a player backend initializes. That assumption is not enforced by the retained
API: `ToggleLoader.Load`, `Unload`, and `RegisterToggle` remain live production
entry points, while effect metadata is supplied by overridable properties and
the registry collections and definition objects are globally visible. An
initialized player can therefore retain removed object keys, miss new defaults,
or let a same-name foreign object change Mutant Presence policy.

Revision 2 turns registration into an immutable definition snapshot and every
successful loader mutation into a new generation. On the next real backend or
runtime entry, each initialized backend atomically rebases a start-generation
snapshot: current booleans survive by exact stable identity, new entries use
their registered defaults, removed entries disappear, and non-null custom
presets are rebound, filtered, deduplicated, and sorted. Rebase neither touches
preferences nor rewrites persistent `disabledToggles`, and separate players
retain independent toggle objects and values.

Identity getters remain mod-defined callback code. If an alias throws, runtime
lookup is safe. If resolving a preset identity reentrantly registers another
definition, the candidate dictionary and presets are discarded together and
the next public entry retries the newer complete generation. Suppression flags
come from the registered snapshot, preventing an equivalent caller alias from
bypassing or imposing policy. All behavior stays in `Toggle`, `ToggleLoader`,
`ToggleBackend`, and `SoulCheck`; no synthetic synchronization API is required.

Revision 2 has 82 named cases across ten groups. The oracle passes 82/82 and
the frozen starter 25/82.
