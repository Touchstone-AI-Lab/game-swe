# Repair Starlight River ability state

The frozen Starlight River 0.2.9.4 source has interacting failures in player
ability persistence, infusion slots, clone ownership, delayed transitions,
join progress, and remote activation. Repair the existing production path; do
not replace it with a parallel ability system.

Work in these files:

- `Content/Abilities/Ability.cs`
- `Content/Abilities/AbilityHandler.cs`
- `Content/Abilities/ShardSet.cs`
- `Content/Abilities/InfusionItem.cs`
- `Content/Abilities/InfusionTier.cs`
- `Content/Packets/AbilityProgress.cs`
- `Content/Packets/StartAbility.cs`

Keep existing public type and method names. Keep the submission source-only;
do not add binaries, archives, build output, or dependencies.

## Required behavior

### Save deterministic progression without losing slots

Keep the existing `Shards`, `unlockedAbilities`, `infusions`, and
`InfusionLimit` tag keys. Save unique shard IDs in ascending order and unique
ability `FullName` values in ordinal order. Store independent item snapshots.

An infusion save has all three physical positions: use an air `Item` for an
empty position so a populated slot two cannot move to slot zero. Load both
this positional representation and legacy compact lists, whose entries occupy
leading slots. A missing infusion-limit tag defaults to one.

### Validate a complete load before committing

Accept at most 4,096 nonnegative shard IDs, 256 ability names, and three
infusion items. Deduplicate saved shards and ability names. Resolve an ability
only by exact name from the assembly containing `Ability`; ignore an unknown
name and continue, but reject a resolved non-ability, abstract type, or type
that cannot be constructed.

The infusion limit must be from zero through three. A non-air saved item must
clone to an equippable `InfusionItem`, occupy an unlocked slot, and not
duplicate another saved infusion's concrete item type or non-null
`AbilityType`. Build fresh shards, abilities, and positional items first. If
any bound, constructor, clone, type, limit, or item check fails, log the load
error and preserve the entire previous live state.

### Make infusion edits atomic and positional

`SetInfusion` rejects a physical slot outside zero through two. Installing an
item also requires a slot below the current clamped `InfusionLimit`, an
equippable item, and no duplicate concrete item or non-null ability family in
another slot. Replacement of the currently occupied slot is allowed even
when the limit is full. Removing with `null` is allowed from any physical
slot.

Clone and validate the incoming item before changing the slot. Set the clone's
reserved-player index and the infused ability's `User` to the receiving
handler. A failed clone or validation leaves the previous slot unchanged.

### Deep-copy player state without gameplay effects

`Clone` and `CopyClientState` create independent shard storage, ability
instances, and positional infusion items. New objects point at the destination
handler/player and retain progression, modifiers, stamina state, infusion
limit, and active/pending identity. Map active and pending abilities to the
corresponding destination instance. Copying must not invoke activation,
deactivation, exit, or reset hooks and must not consume stamina.

### Apply one validated transition per tick

Assigning or activating an ability queues a transition; `PreUpdate` commits it
once. Before a non-null transition, require that the handler owns the exact
unlocked or infused instance, has no current or pending activation, and can
pay a finite, nonnegative activation cost. Invalid or insufficient activation
does not send a start packet or player-control message.

At commit, call the previous ability's exit/reset hooks once, set the new
owner, consume cost once, clear its activation-cost bonus, and call its
activation hook once. Repeated assignment of the same current or pending
instance is a no-op. Explicit deactivation calls `OnDeactivate` once, then
queues the exit/reset transition. Cancelling an activation before its commit
has no hooks or cost.

Ownership can also disappear between ticks. `Lock<T>`, a successful load,
replacement/removal of an infusion, or an accepted progress snapshot may
replace the exact ability instance held by the active or pending transition.
At the next `PreUpdate`, discard a no-longer-owned pending activation without
hooks or cost. Retire a no-longer-owned active ability before any active update:
call its `OnDeactivate`, `OnExit`, and `Reset` hooks exactly once in that order,
clear both active and pending references, and do not charge stamina. Do not
silently transfer activation to a new instance of the same type; a separate
activation is required. Repeated ticks after retirement are no-ops.

Death interrupts this same transition lifecycle immediately: `UpdateDead`
must cancel an uncommitted start with no hooks or stamina cost, and retire a
committed active ability with `OnDeactivate`, `OnExit`, then `Reset` before it
returns. Clear both active and pending references. Repeated dead ticks must
not repeat hooks. If explicit deactivation already delivered `OnDeactivate`
but its queued exit/reset has not committed, death finishes the retirement
without delivering `OnDeactivate` twice. `OnRespawn` restores stamina but
must not reactivate an old queued or retired instance; a new activation after
respawn still works normally. Death of a copied handler does not alter the
source handler. No death cleanup sends an ability-start packet.

### Isolate reentrant and failing ability callbacks

Treat ability lifecycle and tick hooks as untrusted synchronous callbacks:
they may mutate the handler or throw. Catch and log each hook failure through
the existing mod logger; one bad ability must not abort the player tick or
prevent another already-snapshotted ability from running.

`OnActivate` observes its exact instance already installed as the active
ability. If it throws, make that activation fail atomically: clear active and
pending state, restore the pre-attempt stamina and activation-cost bonus, then
invoke `OnExit` and `Reset` once each for compensation without invoking
`OnDeactivate`. Log failures from those compensation hooks independently.
Discard any activation or deactivation request raised by the failed activation
or its compensation callbacks, so it cannot replay on a later tick.

A throwing `OnDeactivate` still queues one retirement. During retirement,
clear active state before `OnExit` and `Reset`; invoke and log both hooks
independently even if either throws, and never retry them on later ticks.
An otherwise valid activation requested synchronously from an `OnExit` or
`Reset` callback is queued for the next tick, never committed as a second
transition in the current tick. Death teardown is stricter: discard every
transition request raised by its deactivate/exit/reset callbacks.

At each `PreUpdate`, snapshot the fixed-update set before the first ability
callback. The set contains each exact owned instance at most once, substitutes
an infusion ability for its matching base ability, and is ordered by ordinal
ability `FullName`. Bind snapshot owners before dispatch. An instance added by
a callback waits until the next tick; one removed before its turn is skipped.
Log a throwing `UpdateFixed` and continue later entries. After fixed callbacks,
reconcile ownership again before the active update, so a removed active
instance retires in the same tick and never receives `UpdateActive`.

If `UpdateActive` throws, log it and immediately retire that ability once with
the normal deactivate/exit/reset sequence. If it requests its own deactivation,
do not run `UpdateActiveEffects` or emit the player-control message later in
that tick. A client-only `UpdateActiveEffects` failure is visual: log it, keep
the gameplay ability active, and still emit the normal control message.
`PostDrawAbility` uses the same deterministic ownership-checked snapshot;
draw-time mutation or one throwing draw callback cannot invalidate enumeration
or draw an instance removed before its turn.

### Replicate canonical progress with sender authority

An `AbilityProgress` snapshot contains sorted unique shards and uses bit 7 for
`Dash`, bit 6 for `Whip`, and bit 5 for `HintAbility`; the lower five bits are
reserved. Receive rejects an invalid player, a server-side `Sender` different
from `fromWho`, null or oversized shards, negative or duplicate shard IDs, or
reserved mask bits without changing state or relaying.

On success, replace shards and those three managed unlocks transactionally,
while preserving other unlocked ability types. Fresh managed instances belong
to the receiving handler. A server relays the accepted packet once to all
clients except the actual `Sender`, without local re-execution.

### Validate remote starts before relaying

`StartAbility` validates the player range and, on a server, requires
`Sender == fromWho`. Resolve the exact `abTypeName` only from the `Ability`
assembly and require a concrete `Ability` type plus the player's exact
unlocked instance. Queue it only when the handler accepts the activation.
Unknown, non-ability, locked, unavailable, insufficient, duplicate, or
spoofed starts cause no mutation and no relay. A server relays an accepted
start once excluding `Sender`; a client applies an accepted server start
without relaying it.

## Public check

Run `python tools/smoke.py` (or `python3` where applicable) to compile the
seven production files in the offline .NET 8 source projection. It contains
no behavioral assertions.
Private evaluation invokes the production persistence, infusion, clone,
transition, progress, and start paths directly with separate engine/network
doubles. The full profile also compiles submitted production sources into a
verifier mod and runs task-specific sentinels inside pinned tModLoader
`2026.7.3.0` on a Terraria `1.4.4.9` dedicated server.
