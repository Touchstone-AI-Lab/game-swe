# Exodus: bug reports against the Afterbirth+ release

You are working on **Exodus**, a Lua mod for **The Binding of Isaac: Rebirth with
Afterbirth and Afterbirth+**. The mod source is in `exodus/`.

## Problem

This release missed a batch of independent fixes. The reports below are observations
from players, not diagnoses. They do not necessarily share a cause.

> **[#EX-184]** The Forbidden Fruit's earned damage disappears if the item is removed
> or rerolled. Using it increases damage while it is held, but the run immediately
> drops back to its old damage value when the item leaves the inventory.

> **[#EX-191]** Tragic Mushroom mishandles the last half-heart case. A normal
> character entering the use with three red-heart containers and only half a red
> heart survives on that same half heart; the item is supposed to leave one full red
> heart after reducing the containers. The edge case is worse when the character
> already has only one red-heart container: using the item on half a heart kills them
> instead of filling that final container.

> **[#EX-303]** Tragic Mushroom only seems to remember that it has been used once.
> If it is found and used again in the same run, it consumes health again but the
> character's damage, speed, and range remain exactly at their first-use values. Each
> later use is meant to add a smaller, diminishing stat increase rather than no
> increase at all.

> **[#EX-311]** Mutant Clover does not stack within a room. Activating it twice still
> gives only ten luck, while each activation in the current room should add another
> ten. The whole temporary stack should continue to reset on entering another room.

> **[#EX-318]** Anamnesis borrows the charge of whichever active item occupied the
> slot before it. Picking up a fresh Anamnesis after a fully charged active can make
> it immediately usable; dropping and later recovering it can likewise forget the
> charge it had earned. Its charge must belong to Anamnesis itself across active-item
> swaps, and a fresh copy must not inherit a full foreign charge.

> **[#EX-217]** Cursed Metronome's first-time health conversion depends on how full
> the player's red-heart containers happen to be. A wounded player with six red-heart
> containers and two filled hearts is left with one filled heart, while the conversion
> should empty the red hearts consistently for that capacity.

> **[#EX-441]** Ominous Lantern now costs its charge just for being put away. Raising the
> lantern and then using the item again to lower it, without throwing, leaves the item empty:
> it cannot be raised again until its slow recharge (about ten seconds) has run. Lowering a
> lantern that was never thrown should leave it ready to raise again straight away. Throwing
> it must still empty it and start that recharge as before.

> **[#EX-465]** Birdbath does nothing when used: no bath appears next to Isaac.

> **[#EX-447]** Hurdle Heels' landing stomp no longer hurts enemies. An enemy standing right
> next to Isaac when he comes down from the jump takes no damage at all.

## Task

Diagnose and fix every report. Preserve behaviour outside the reported paths.

## Cross-report regression envelope

- Treat room-, floor-, run-, and item-owned state as distinct lifetimes. Clover's bonus
  accumulates per activation but ends on room entry; Broken Glasses' effect outlives the
  trinket only until the next floor; Forbidden Fruit's earned damage survives removal.
- Active-item charge must not leak between the item previously in the slot and Anamnesis:
  a fresh Anamnesis starts uncharged, while its own partial charge survives a swap away
  and back.
- Cursed Metronome's first conversion must depend on red-heart container capacity, not
  on how many of those hearts are currently filled.
- Tragic Mushroom must handle both half-heart edge cases without killing the player, and
  repeated uses must produce positive but diminishing gains in all three reported stats.
  A fix for repeat-use bookkeeping must not collapse the separate last-container rule.
- Keep each behavior independently valid when the corresponding collectible is removed
  or replaced; do not make current ownership a proxy for already-earned run state.

## Notes

- The target runtime is the native Linux Steam build of Afterbirth+ `v1.06.T1`.
- This is an Afterbirth+ Lua mod, not a Repentance mod. Use APIs available in that
  runtime.
- Afterbirth+ embeds Lua 5.3.
- Do not replace the mod wholesale or add third-party code/assets.
- The grader runs the submitted mod in the real game in an isolated, offline verifier.
