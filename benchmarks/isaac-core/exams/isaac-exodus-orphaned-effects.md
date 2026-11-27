# Exodus: bug reports against the Afterbirth+ release

You are working on **Exodus**, a Lua mod for **The Binding of Isaac: Rebirth with
Afterbirth and Afterbirth+**. The mod source is in `exodus/`.

## Problem

This release missed a batch of independent fixes. The reports below are observations
from players, not diagnoses. They do not necessarily share a cause.

> **[#EX-203]** Ritual Candle stops hurting nearby enemies on very high fire-rate
> builds. With all five candle flames lit and a tear delay of 2, an active vulnerable
> enemy standing next to the player can remain completely undamaged. At a tear delay
> of 4 the opposite timing problem is visible: the aura pulses every frame, roughly
> twice as often as the intended rounded interval.

> **[#EX-247]** Rerolling or removing familiar items can leave their companions alive
> after the item is gone. This has been reproduced with Ritual Candle's five flames,
> both Sundial orbitals, Astro Baby, and Lil Rune. Every companion should disappear
> promptly once its owning collectible is no longer held.

> **[#EX-327]** Baseball Mitt's released baseballs lose their impact effect when they
> land after the catching stance has ended. The ball still hits, but the short
> baseball-hit poof is absent. A released ball must create that effect whenever it
> dies, even though the mitt is no longer raised.

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

> **[#EX-461]** Big Scissors' blood trail is gone. After Isaac is hurt while holding Big
> Scissors, the item's other effects still kick in, but he no longer leaves a trail of red
> creep behind him for the rest of the room.

> **[#EX-406]** In runs where Welcome Mat has been picked up, things that should appear in
> place start shooting across the room once the first mat has been laid. Baseball Mitt's
> impact poof, for example, streaks away the moment a released ball lands instead of popping
> where it hit. Other effects and pickups that Exodus spawns at rest are thrown the same way.
> The mat itself still lays down and still gives its tears bonus when the character stands
> on it.

## Task

Diagnose and fix every report. Preserve behaviour outside the reported paths.

## Cross-report regression envelope

- Distinguish effects that must finish after their source disappears from companions
  that must be removed when their owning collectible disappears. Existing gas, airborne
  lobs, and released baseballs have independent completion behavior; the five familiar
  variants do not outlive their items.
- A Headcase lob must still collide with the player after Headcase is removed, and Iron
  Lung gas must advance through its animation and cleanup without an emitter.
- Baseball impact effects must be tied to the released ball's end-of-life, not to whether
  the mitt is currently raised or still held.
- Forbidden Fruit's already-earned damage persists after the collectible is removed,
  unlike the familiar companions, which must be cleaned up when their item is gone.
- Preserve Ritual Candle's timing at both reported fire-delay extremes while making
  these owner-lifetime changes.

## Notes

- The target runtime is the native Linux Steam build of Afterbirth+ `v1.06.T1`.
- This is an Afterbirth+ Lua mod, not a Repentance mod. Use APIs available in that
  runtime.
- Afterbirth+ embeds Lua 5.3.
- Do not replace the mod wholesale or add third-party code/assets.
- The grader runs the submitted mod in the real game in an isolated, offline verifier.
