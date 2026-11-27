# Repair Fargo's Souls toggle presets

The frozen Fargo's Souls 1.7.3.7 source shares registered toggle objects
between players and persists presets by unstable short names. It also routes
backend operations through `Main.LocalPlayer`, retains stale configuration,
and exposes unsafe lookup boundaries. Repair the existing production toggle
path; do not add a parallel preset or toggle implementation.

Work in these files:

- `Core/Toggler/Toggle.cs`
- `Core/Toggler/ToggleLoader.cs`
- `Core/Toggler/ToggleBackend.cs`
- `Core/Toggler/SoulCheck.cs`

Keep the existing public type and method names. Keep the submission
source-only; do not add binaries, archives, build output, or dependencies.

## Required behavior

### Give the global registry an explicit lifecycle

`ToggleLoader.Load` creates fresh empty toggle and header collections, and
`Unload` releases both collections rather than retaining cleared global
objects. Reject a null toggle, null effect, effect without a `ToggleHeader`,
null header, the same effect twice, or two effects with the same ordinal
`FullName`. A rejected registration leaves the registry unchanged.

### Materialize player-local backend state

`TryLoad` remains idempotent. Materialize a fresh dictionary and a fresh
`Toggle` for every registered effect, preserving its `Mod` and
`DefaultToggle`; neither the registry nor another backend may share mutable
toggle state. An empty registry is valid. Dedicated-server initialization
must not load or save the client preference file.

For each of the three configured preset slots, read
`CustomPresetsOff1` through `CustomPresetsOff3` independently. Keys are exact
ordinal `AccessoryEffect.FullName` identities, not `Name`; ignore unknown
keys, canonicalize resolved effects by `FullName`, and do not let one malformed
slot prevent a later valid slot from loading. Do not rerun this work after a
backend has initialized.

### Freeze definitions and rebase live registry generations

A registered toggle is an immutable definition snapshot. Capture its exact
ordinal `FullName`, `Mod`, header, `DefaultToggle`, `MutantsPresenceAffects`,
and `MinionEffect` metadata rather than consulting those virtual properties
again while materializing players. Reject a null or empty stable identity.
Later mutation of the source effect metadata or the source `Toggle.Effect` and
`Toggle.Mod` fields must not rewrite the registered definition; a backend uses
the effect object that was the registry key and a fresh mutable toggle copied
from the captured definition.

Every successful toggle-registry `Load`, `Unload`, or `RegisterToggle` changes
the current definition generation; rejected registration does not. An
initialized backend remains idempotent while that generation is unchanged.
Before `TryLoad`, preference save, player restore, every built-in/custom preset
operation, `SetAll`, or runtime get/set uses it after a generation change,
atomically rebase that backend onto one start-of-operation registry snapshot.
The rebase performs no preference load/save and never mutates or replaces a
player's `disabledToggles` list.

On a successful rebase, create a fresh dictionary and fresh toggle objects.
Preserve each existing boolean by exact captured `FullName`; use the captured
default for a newly registered identity and drop removed identities. Rebind
each non-null custom-preset slot to current registry objects, dropping removed
identities and making the result unique and ordinally sorted; preserve null
slots. Backends remain mutually isolated, and the next player restore must
publish only current-generation effect objects in `TogglesToSync`.

Treat identity resolution as untrusted callback code. If it throws, or if the
registry generation changes while preset identities are being resolved, do
not commit any part of the candidate dictionary or presets. Keep the prior
coherent backend snapshot and retry the newer generation on the next public
entry. Runtime lookup/set of a foreign effect whose `FullName` throws is a safe
null/false/no-op and emits no warning. After an equivalent foreign effect is
resolved, Mutant Presence policy comes from the captured registered definition,
not from flags on the caller-supplied alias.

### Persist canonical, complete preset snapshots

On a client, `Save` writes all three preset keys before one preference flush.
A null slot writes an empty dictionary so stale disk data is cleared. Each
non-null slot is an independent snapshot containing unique, non-null effects
in ordinal `FullName` order, with `false` values. A dedicated-server save is a
no-op.

### Restore the requested player's state

`LoadPlayerToggles(modPlayer)` must operate on this backend and the supplied
player state, never on the global registry or `Main.LocalPlayer`. Start each
registered effect at its own `DefaultToggle`, then disable persisted effects
by exact ordinal `FullName`. Ignore unknown entries. Replace
`TogglesToSync` with one exact snapshot of the resulting registered state;
do not merge stale entries. An uninitialized backend is a no-op.

`SetAll` directly changes this backend's toggle objects. It must not redirect
through the local player's backend.

The built-in `SomeEffects` and `MinimalEffects` presets are likewise operations
on this backend, even when `Main.LocalPlayer` refers to a different player.
Keep their existing named choices: `SomeEffects` first enables registered
toggles, then disables its listed effects and registered effects whose `Name`
contains `Pet`; `MinimalEffects` first disables registered toggles, then
enables its listed effects. Resolve each listed choice against this backend's
registered toggles. Missing listed effects are simply absent, not warnings or
new entries. These built-in presets do not read/write preferences, mutate
custom-preset storage, or replace a player's `disabledToggles` list.

### Make custom preset actions bounded and non-destructive

Preset slots remain one-based and limited to 1 through 3. Invalid slots and
all dedicated-server preset actions are safe no-ops with no success message.
Saving captures the currently disabled registered effects in ordinal
`FullName` order and reports success without aliasing later toggle changes.

Loading a valid preset applies it through the local player's normal
`LoadPlayerToggles` path and updates its sync snapshot. It must not consume or
modify the stored preset, and any temporary use of `disabledToggles` must
restore the exact previous list reference. A valid but empty slot reports the
existing no-preset message without changing toggles or sync state.

### Keep toggle lookup boundaries safe

`GetToggle`, `GetToggleValue`, and `GetPlayerBoolValue` return null or false
for null or unregistered input rather than throwing. Resolve an equivalent
effect by exact `FullName` when object identity differs. `SetToggleValue`
updates that registered toggle or emits one existing warning for a non-null
missing effect without throwing.

Unless `skipChecks` is true, Mutant Presence suppresses effects whose
`MutantsPresenceAffects` or `MinionEffect` flag is true. It does not suppress
unaffected effects.

## Public check

Run `python tools/smoke.py` (or `python3` where applicable) to compile the
four production files in the offline .NET 8 source projection. It contains
no behavioral assertions.
Private evaluation invokes registry lifecycle, backend isolation, preference
I/O, player restore, preset actions, and lookup behavior directly with
separate engine doubles. The full profile also compiles submitted production
sources into a verifier mod and runs task-specific sentinels inside pinned
tModLoader `2026.7.3.0` on a Terraria `1.4.4.9` dedicated server.
