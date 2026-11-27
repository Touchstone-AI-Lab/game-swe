# Mutant Tanks release regressions

The frozen source tree is Mutant Tanks v9.3 at upstream commit
`c7ef30eea49abce235ef9ff50587aed7cd3c4d5a`. Server operators supplied the
following nine reports.

## Report 1: configuration subscribers lose nested context

Plugins compiled against `addons/sourcemod/scripting/include/mutant_tanks.inc`
subscribe to the documented eight-argument `MT_OnConfigsLoaded` forward. The
callback stream still arrives, but nested special-infected entries are reported
as ordinary entries: the final `special` flag is false and `specsection` is
empty. On initial load and
`sm_mt_reload`, preserve all eight arguments for the ordinary `General/Type
Range` entry and for both plugin-level and Tank-type `Health/Smoker Base Health`
entries nested under `Special`. The ordinary entry has a false special flag and
empty special-section name; both nested entries have a true flag and the exact
special-section name `Special`. Keep the current eight-argument API; do not
restore an old ten-argument API from an earlier Mutant Tanks version.

## Report 2: plugin-level SI health fallback loses precedence

A bot-controlled mutant Smoker selects a Tank type that omits its own `Health`
block. The plugin-level `Health` block supplies both generic and Smoker-specific
`Base Health` and `Extra Health` values, but the mutant now receives generic or
global defaults instead of the plugin-level Smoker values. The plugin-level
SI-specific values must win in this fallback path. An explicit Tank-type
SI-specific base and extra value must remain authoritative when present. Both
live `m_iHealth` and `m_iMaxHealth` after mutation must reflect the resolved base
plus extra health.

## Report 3: a Warp hit breaks an active pin

A mutant infected with a guaranteed on-hit Warp can relocate the hit victim
while that survivor is currently grabbed by a Smoker, pounced by a Hunter,
ridden by a Jockey, or pummelled by a Charger. The survivor argument passed to
the Warp-hit path must not be relocated in any of those four active states. An
otherwise eligible unpinned hit victim must still be warped to a different
living survivor by that guaranteed hit.

## Report 4: a four-stage Boss fails at its final form

A Boss configured with four health stages and four successor types evolves
through the early thresholds, then the repeating Boss timer raises an array
index exception at the final boundary. With health stages `800,600,400,200` and
Boss types `2,3,4,5`, a live type-1 Boss must advance in order through types 2,
3, 4, and 5 as its engine health crosses those thresholds. The final type-5
form must remain alive and valid across later timer ticks without a SourceMod
exception.

## Report 5: unequal reward stacks accumulate the wrong value

Two reward-enabled Tank types grant the same survivor both Damage Boost and
Ammo rewards. Type A grants a `1.5` damage multiplier and regenerates `10`
rounds per tick; type B grants `2.0` and `20`. Both reward categories allow a
second stack, and each reward lasts 12 seconds.

When the survivor kills A and then B, the already-active smaller values must
remain authoritative: a base 10-damage SMG hit deals 15 damage and the first
regeneration tick adds exactly 10 rounds to both the empty magazine and empty
reserve. The later larger values must not be added or substituted. In the
reverse B-then-A order, the later smaller values are additive: the same hit
deals 35 damage and the first regeneration tick adds exactly 30 rounds. This
reverse order is required; do not make all repeated rewards simply keep the
first value.

The active combined reward must survive a `bot_player_replace` handoff exactly
once. The incoming survivor keeps the same order-dependent damage and ammo
behavior, while the replaced survivor immediately returns to 10 damage and
receives no ammo regeneration. At expiry the incoming survivor must receive one
public `MT_OnRewardSurvivor(..., apply=false)` callback for the combined reward,
return to 10 damage, and stop regenerating ammo. Preserve normal first-reward,
replacement, and expiry behavior while repairing the unequal stack calculation.

## Report 6: Hypno shields are missing or duplicated

With the server's Graphics Level set to High or Max, `Hypno View=1` is a
spawn-time visual option: it must create exactly one shield parented to its
owning mutant even when `Ability Enabled=0`. Normal ability
activation must not create a second shield. Conversely, `Hypno View=0` must
never create a shield, while an enabled guaranteed Hypno hit must still apply
its gameplay effect. Creation may be deferred by a frame or short timer, but
must complete within one game-time second after `MT_OnPostTankSpawn`. It is
not required to complete inside that same forward call. This timing allowance
also applies to respawns and to the fresh Tank used before aggregate unload.

Shield ownership must also follow the Tank lifecycle. Removing a Tank must
remove its shield and invalidate the old entity reference; respawning must
create one new shield rather than reuse the old reference. Round reset and
unloading the primary ability aggregate must leave no orphan shields or
SourceMod exceptions.

## Report 7: `Panic Type=0` no longer uses its documented random fallback

For Panic mode 2, a zero `Panic Type` mask means "choose a random uncommon
infected," not "spawn nothing." With chance 100 and amount 1, activation must
create exactly one real `infected` entity whose model is one of the seven
supported uncommon models (CEDA, Jimmy Gibbs, Fallen Survivor, Clown, Mud Man,
Road Crew, or Riot Cop). An explicit `Panic Type=8` must still deterministically
create exactly one real `infected` entity total, and that entity must be a
Clown; explicit masks must retain their existing behavior.

## Report 8: a rainbow reward stops when survivor control changes

With Graphics Level set to High or Max, a survivor earns an active body-color
reward configured as `rainbow`. Its render color changes continuously before a
control handoff. When `bot_player_replace` transfers that survivor state from a
bot to a player, the replacement survivor must continue the active animation
and the old bot must return to the default neutral white render color
`(255, 255, 255)`. A later
`player_bot_replace` must transfer the same still-active animation back to the
idle bot and reset the replaced player to that same default white. Neither
direction may leave the reward visually frozen on the new owner or active on
both entities.

## Report 9: successful Acid and Ammo claw hits ignore their cooldowns

The Acid and Ammo abilities are both configured for guaranteed melee/claw hits.
A successful hit must start each ability's configured melee cooldown. Further
successful claw hits inside that window must not create another Acid projectile
or apply another Ammo drain; after the window expires, both effects must apply
again. A configured cooldown of zero must not suppress a later cross-second hit.
For Ammo Type 3 and Ammo Count 10, each accepted hit drains exactly 10 from both
the survivor's current primary magazine and its reserve ammo.

## Task

Diagnose and repair all nine regressions. Preserve the current public API,
plugin identity, ability aggregate loading and GPL attribution; avoid unrelated
changes.

Keep the submission source-only. Do not add `.smx` files, native libraries,
archives, symbolic links, Git metadata, game files, credential material, or
executable network-client helpers. Do not modify `/tests`.

Run the public compilation/package check after editing:

```bash
python3 tools/smoke.py
```

It contains no behavioral assertions. The private verifier recompiles the core
and both ability aggregates, then evaluates the reports in fresh boots of a
pinned headless L4D2 dedicated server through public APIs and observable engine
state. Scoring does not compare a reference diff or call private Mutant Tanks
helpers.
