# Terraria task 08 design: Starlight River ability state

## Candidate and provenance

- Upstream: `https://github.com/ProjectStarlight/StarlightRiver`
- Frozen revision: `d367416dcadfe68a541a5821a0c4be86b42db219`
- Upstream version: Starlight River 0.2.9.4
- License: GPL-3.0 for code; retain source and `LICENSE.txt` only
- Platform: Terraria 1.4.4.9 and the tModLoader 1.4.4 stable API
- Production path: an `AbilityHandler` owns persistent shards, unlocked ability
  instances, positional infusions, stamina, active transitions, join progress,
  and remote activation packets.

The history contains the dedicated commits `77bf60a7ab82f26e9585ba11f885305495775da2`
("ABILITIES SYNC"), `92e0f3dfd2513fc77ca644d61e8431b6e55965ef`
("misc. sync improvements and fixes"),
`ac6e18fcc1c581b929027590cab38385bca2b5b9`
("fix for fresh characters having unlocked abilities"), and
`e8957da9f931da0f7c63b01acda851bc46793d1e`
("Infusion right click fix"). The frozen implementation still compacts sparse
infusion slots on save, catches a whole load after partial mutation, indexes an
unchecked infusion slot, performs transition hooks before the queued state is
committed, and trusts packet-declared player/type identity.

## Operator reports to preserve in the task contract

1. Save output is deterministic and independent: shard IDs and ability type
   names are unique and sorted, while all three infusion positions survive
   round trips instead of being compacted.
2. Load is bounded and transactional. It accepts legacy compact infusion data,
   ignores unknown ability types individually, rejects impossible counts, and
   never leaves a half-loaded handler after a bad item or type constructor.
3. Infusion edits validate the slot and unlocked limit, allow removal and
   same-slot replacement, prohibit duplicate ability/item families across
   other slots, clone before commit, and leave state unchanged on failure.
4. `Clone` and `CopyClientState` create independent shards, ability instances,
   and infusion items with correct owners. Copying must not fire gameplay
   hooks or consume stamina.
5. Active-ability changes are one queued transition per tick: old exit/reset,
   new owner/cost/activation, and explicit deactivation hooks occur exactly
   once. Duplicate assignments are no-ops; nonfinite/negative costs and
   insufficient stamina cannot create or subsidize an activation.
6. Ability-progress packets snapshot canonical data, include every built-in
   unlock, validate player/sender identity, bounds, duplicate shards, and mask
   bits, then replace replicated progress transactionally and relay only an
   accepted frame.
7. Start-ability packets validate player/sender identity, resolve only known
   ability types from the ability assembly, require an unlocked available
   instance on the server, reject duplicates without charging again, and
   relay only an accepted transition.

## Expected repair shape

The retained production files are:

- `Content/Abilities/Ability.cs`
- `Content/Abilities/AbilityHandler.cs`
- `Content/Abilities/ShardSet.cs`
- `Content/Abilities/InfusionItem.cs`
- `Content/Abilities/InfusionTier.cs`
- `Content/Packets/AbilityProgress.cs`
- `Content/Packets/StartAbility.cs`

The repair coordinates save compatibility, defensive collection parsing,
clone ownership, a delayed transition state machine, and two authoritative
packet paths without changing public type or method names.

## Evaluation boundary

The evaluator compiles the seven production files in a .NET 8 projection. Test
doubles provide Terraria players/items, TagCompound, NetEasy delivery context,
graphics/input placeholders, three concrete abilities, and packet recording.
Private cases invoke production persistence, infusion, clone, tick-transition,
progress receive, and start receive paths. Public smoke is compile-only.

## Difficulty and fairness review

This is hard because the same logical state appears as reflection-resolved
types, owned runtime objects, save tags, a bit mask, queued current/next
instances, and remote player indices. Locally plausible fixes commonly lose
infusion positions, alias clone state, double-charge a queued activation, or
validate after mutating live data.

The prompt will state the ordering, bounds, legacy rule, mask mapping,
transaction boundary, ownership, hook timing, and authority rules. Tests use
visible fake abilities/items and deterministic delivery metadata; no UI,
rendering, real network, random world, or hidden mod content is involved.

## Design and implementation verdict

Accepted and locally audited. The 57 named contracts cover seven independent
behavior groups and match the executable case list one-for-one. The frozen
starter passes 13/57 cases while the oracle passes 57/57; both source
projections compile with zero warnings and zero errors. It is a historically
grounded progression and multiplayer path from a prominent released content
mod and is independent from the previous codec, tile-entity, entity-store,
geometry, quest, map, and carpentry tasks.

## Contract correction (2026-09-22)

One case equated "no activation hook during clone" with a cloned test counter
being zero, incorrectly rejecting a faithful copy of prior counter state. The
original oracle also constructed fresh abilities, indirectly invoking their
`Reset` hook despite the prompt's no-hook rule. The verifier now records hook
invocations directly; the oracle copies ability instances without invoking
constructors or gameplay hooks. The oracle passes 57/57 under the corrected
test.

## Revision: ownership loss during queued and active ability lifetimes

The initial contract did not cover a narrower real lifecycle gap. The existing
production methods `Lock<T>`, `LoadData`, `SetInfusion`, and
`ReplaceReplicatedProgress` can remove or replace an owned ability instance
while `AbilityHandler` still references it as the active or queued ability. Merely checking ownership when an activation is
first queued does not repair that later loss. A stale active instance can
continue its effects after its unlock or infusion has gone away; a stale
queued instance can be charged or activated on the next tick.

The revised task requires one consistent ownership reconciliation at the next
`PreUpdate`: discard uncommitted stale starts without hooks or cost, and retire
stale active instances with one deactivate/exit/reset sequence before active
updates. It must not silently transfer activation to a replacement instance
of the same type. This is a single player-state invariant across existing
upstream lifecycle paths, not an extra algorithm or a test-only input.

The repair belongs in `AbilityHandler` and is observable through its existing
public methods and packet receive path. New cases exercise lock, successful
load, infusion removal/replacement, and accepted progress replacement, with
both queued and active states. Broken starter and oracle will be checked
against the same named cases. A fresh independent strict attempt is required
for this revision.

The revised controls are 13/63 for the broken starter and 63/63 for the
oracle.

## Revision 2 design brief: death interrupts queued ability lifetime

`AbilityHandler.UpdateDead` is a retained tModLoader player hook. In the
frozen source it sets `ActiveAbility = null`, which merely queues a normal
transition. During dead ticks no later `PreUpdate` is guaranteed; the active
ability and its effects can remain live, or a previously queued start can
commit after respawn. This is the same active/pending lifecycle already under
repair, now interrupted by a base-game death event rather than lost ownership.

The repair belongs in `AbilityHandler.cs`. On death, cancel an uncommitted
start without charging stamina or invoking gameplay hooks; retire a committed
active ability immediately with one deactivate/exit/reset sequence, clear
active and pending references, and make repeated dead ticks idempotent. If a
normal `RequestDeactivate` already delivered `OnDeactivate` but had not yet
committed exit/reset, death must finish that retirement without calling the
deactivation hook twice. Respawn restores stamina but never resurrects the
old queued/active instance; a fresh activation remains possible. Preserve
clone independence and the existing packet authority behavior. No new API,
wire format, or verifier-only seam is introduced.

The evaluator will exercise the real `UpdateDead`, `OnRespawn`, `PreUpdate`,
and ability hooks through the existing source projection. Every case maps to
the new public clause and checks observable state, stamina, and hook counts.
This is a coherent lifecycle extension comparable to accepted L4D2 hard
event teardown scenarios; it is not a new unrelated algorithm. Audit prompt,
starter/oracle controls, case map, and package mirror before one fresh strict
calibration attempt.

The frozen starter passed 13/69 and the oracle passed 69/69.

## Revision 3: reentrant and failing ability callbacks

The 69-case contract assumes every mod-defined hook returns normally and leaves
the collections it is enumerating unchanged. That assumption is unsafe on the
real production seam: activation, retirement, fixed, active, visual, and draw
hooks are virtual callbacks, and each can synchronously unlock, lock, replace,
or deactivate abilities. One exception currently aborts the player tick;
collection mutation can invalidate enumeration; and cleanup callbacks can
overwrite an in-flight transition or resurrect an ability during death.

Revision 3 makes the existing tick a callback-safe transaction. `OnActivate`
sees committed active state but rolls stamina, bonus, and transition state back
if it throws, followed by one best-effort exit/reset compensation. Retirement
isolates failures from deactivate, exit, and reset independently. Cleanup-time
activation is deferred to the next tick, while death discards callback-raised
requests. Fixed and draw stages use deterministic start-of-stage snapshots,
skip exact instances removed before their turn, defer new instances, and
continue after logged failures. Ownership is reconciled again before active
update; gameplay update failure retires immediately, while visual failure is
logged without destroying gameplay state.

These requirements stay in the retained `AbilityHandler` lifecycle and use
ordinary virtual-hook behavior rather than verifier-only APIs. Revision 3 has
84 named cases across 11 groups. The oracle passes 84/84 and the frozen
starter 14/84.
