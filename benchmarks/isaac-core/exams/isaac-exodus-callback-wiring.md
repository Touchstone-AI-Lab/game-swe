# Exodus: bug reports against the Afterbirth+ release

You are working on **Exodus**, a Lua mod for **The Binding of Isaac: Rebirth with
Afterbirth and Afterbirth+**. The mod source is in `exodus/`.

## Problem

This release missed a batch of independent fixes. The reports below are observations
from players, not diagnoses. They do not necessarily share a cause.

> **[#EX-217]** Cursed Metronome's first-time health conversion depends on how full
> the player's red-heart containers happen to be. A wounded player with six red-heart
> containers and two filled hearts is left with one filled heart, while the conversion
> should empty the red hearts consistently for that capacity.

> **[#EX-266]** The Apocryphon no longer applies its room rewards to the player. On a
> first visit to a non-standard room, none of damage, tear delay, speed, shot speed,
> luck, or range changes, even though at least one of those stats should increase.

> **[#EX-318]** Anamnesis borrows the charge of whichever active item occupied the
> slot before it. Picking up a fresh Anamnesis after a fully charged active can make
> it immediately usable; dropping and later recovering it can likewise forget the
> charge it had earned. Its charge must belong to Anamnesis itself across active-item
> swaps, and a fresh copy must not inherit a full foreign charge.

> **[#EX-335]** Iron Lung gas can become a permanent frozen cloud. If the Iron Lung
> that emitted it dies before the cloud finishes, the cloud stops progressing and
> never reaches its fade-out. Existing gas must finish its own animation and cleanup
> without requiring an Iron Lung to remain alive.

> **[#EX-342]** Headcase's arcing blood shots become harmless if Headcase dies just
> after the stomp launches them. Shots already in flight can overlap the player on
> landing without dealing damage. Their collision must continue to be processed
> after the firing Headcase is gone.

> **[#EX-184]** The Forbidden Fruit's earned damage disappears if the item is removed
> or rerolled. Using it increases damage while it is held, but the run immediately
> drops back to its old damage value when the item leaves the inventory.

> **[#EX-427]** Lil Rune no longer takes on the power of runes. Using a rune while holding
> Lil Rune leaves the familiar unchanged: no transformation animation plays and none of the
> rune powers appear — for example, after Algiz it should destroy enemy shots that touch it,
> and after Jera it should split dying enemies.

> **[#EX-465]** Birdbath does nothing when used: no bath appears next to Isaac.

> **[#EX-467]** Paper Cut no longer makes cards hurt. Using a card while holding Paper Cut
> should cut every vulnerable enemy in the room, but they take no damage at all.

## Task

Diagnose and fix every report. Preserve behaviour outside the reported paths.

## Cross-report regression envelope

- Cache-driven rewards must occur on the first eligible non-standard-room visit, while
  floor setup must grant automatic mapping to James only; ordinary Isaac must not inherit
  that character-specific effect.
- A fresh Anamnesis must not inherit another active item's charge, and its own partial
  charge must remain intact after swapping away and back.
- Cursed Metronome's first conversion is capacity-based; changing the callback wiring
  must not make the result depend on the player's current red-heart fill.
- Separate child-entity lifetime from owner lifetime: existing gas and launched lobs must
  keep progressing after their source dies, while Forbidden Fruit's earned damage must
  remain after its collectible is removed.
- These cases have opposite ownership rules. Do not solve orphaned children by globally
  cleaning up all owner-linked state, or preserve item-owned companions after their item
  disappears.

## Notes

- The target runtime is the native Linux Steam build of Afterbirth+ `v1.06.T1`.
- This is an Afterbirth+ Lua mod, not a Repentance mod. Use APIs available in that
  runtime.
- Afterbirth+ embeds Lua 5.3.
- Do not replace the mod wholesale or add third-party code/assets.
- The grader runs the submitted mod in the real game in an isolated, offline verifier.
