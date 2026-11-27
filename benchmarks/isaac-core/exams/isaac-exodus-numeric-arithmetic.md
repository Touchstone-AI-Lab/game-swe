# Exodus: bug reports against the Afterbirth+ release

You are working on **Exodus**, a Lua mod for **The Binding of Isaac: Rebirth with
Afterbirth and Afterbirth+**. The mod source is in `exodus/`.

## Problem

This release missed a batch of independent fixes. The reports below are observations
from players, not diagnoses. They do not necessarily share a cause.

> **[#EX-191]** Tragic Mushroom mishandles the last half-heart case. A normal
> character entering the use with three red-heart containers and only half a red
> heart survives on that same half heart; the item is supposed to leave one full red
> heart after reducing the containers. The edge case is worse when the character
> already has only one red-heart container: using the item on half a heart kills them
> instead of filling that final container.

> **[#EX-203]** Ritual Candle stops hurting nearby enemies on very high fire-rate
> builds. With all five candle flames lit and a tear delay of 2, an active vulnerable
> enemy standing next to the player can remain completely undamaged. At a tear delay
> of 4 the opposite timing problem is visible: the aura pulses every frame, roughly
> twice as often as the intended rounded interval.

> **[#EX-217]** Cursed Metronome's first-time health conversion depends on how full
> the player's red-heart containers happen to be. A wounded player with six red-heart
> containers and two filled hearts is left with one filled heart, while the conversion
> should empty the red hearts consistently for that capacity.

> **[#EX-281]** Lil Rune's Jera form creates damaged enemies with invalid health.
> When a killed enemy is duplicated into two smaller copies, each copy keeps the
> original current health while its maximum is halved, leaving current health above
> the displayed maximum.

> **[#EX-303]** Tragic Mushroom only seems to remember that it has been used once.
> If it is found and used again in the same run, it consumes health again but the
> character's damage, speed, and range remain exactly at their first-use values. Each
> later use is meant to add a smaller, diminishing stat increase rather than no
> increase at all.

> **[#EX-266]** The Apocryphon no longer applies its room rewards to the player. On a
> first visit to a non-standard room, none of damage, tear delay, speed, shot speed,
> luck, or range changes, even though at least one of those stats should increase.

> **[#EX-427]** Lil Rune no longer takes on the power of runes. Using a rune while holding
> Lil Rune leaves the familiar unchanged: no transformation animation plays and none of the
> rune powers appear — for example, after Algiz it should destroy enemy shots that touch it,
> and after Jera it should split dying enemies.

> **[#EX-463]** Unholy Mantle's burst no longer hurts enemies. When Isaac is hit while the
> mantle is charged, its costume disappears as before, but the enemies in the room take no
> damage. The burst should hit every vulnerable enemy in the room, once per floor.

> **[#EX-452]** A new run started without closing the game inherits the previous run's stat
> changes. After using The Forbidden Fruit or Tragic Mushroom in one run, Isaac starts the next
> run with that run's boosted damage, speed and range; they only drop back to normal once he
> walks into another room. Every new run should start from the character's own stats.

## Task

Diagnose and fix every report. Preserve behaviour outside the reported paths.

## Cross-report regression envelope

- The numeric fixes have different bases and directions: Ritual Candle uses a rounded
  frame interval; Cursed Metronome uses red-heart capacity rather than filled hearts;
  Lil Rune copies must not exceed their new maximum health.
- Tragic Mushroom's half-heart refill must work both with multiple containers and with
  only the last container, without death. Later uses still add positive damage, speed,
  and range, with each gain smaller than the preceding gain.
- Keep the distinct arithmetic rules local to their mechanics. In particular, a broad
  health clamp or a shared stat-scale change must not mask one edge case by breaking
  another report's expected values.
- The Apocryphon's cache reward must remain active on the first eligible non-standard-room
  visit; numeric fixes must not leave the reward data correct but disconnected.

## Notes

- The target runtime is the native Linux Steam build of Afterbirth+ `v1.06.T1`.
- This is an Afterbirth+ Lua mod, not a Repentance mod. Use APIs available in that
  runtime.
- Afterbirth+ embeds Lua 5.3.
- Do not replace the mod wholesale or add third-party code/assets.
- The grader runs the submitted mod in the real game in an isolated, offline verifier.
