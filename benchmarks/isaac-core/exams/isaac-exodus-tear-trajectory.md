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

> **[#EX-226]** Grid Worm does not constrain a newly fired tear immediately. A tear
> fired diagonally can spend its opening frames travelling diagonally before the
> trinket's horizontal/vertical pattern takes over. When it finally snaps, its first
> direction can disagree with the direction the character is facing. Tears that hit a
> wall also invert their velocity without leaving the collision tile, so they can
> oscillate in place instead of rebounding cleanly. Keep the existing later random-turn
> cadence; fixing the opening direction must not make those periodic turns start sooner.

> **[#EX-258]** Beehive makes fresh tears wobble at full strength immediately. During
> roughly their first twenty frames, successive velocity changes are about twice the
> intended size; young tears should use the gentler half-strength drift before the
> normal wobble takes over.

> **[#EX-274]** Deja Vu treats split tears as return candidates when they die. A split
> tear can produce both its normal child tears and an extra returning tear, which can
> then repeat the return chain. Split tears should be excluded from that mechanic.
> Ordinary eligible, non-split tears must continue to return normally.

> **[#EX-327]** Baseball Mitt's released baseballs lose their impact effect when they
> land after the catching stance has ended. The ball still hits, but the short
> baseball-hit poof is absent. A released ball must create that effect whenever it
> dies, even though the mitt is no longer raised.

> **[#EX-289]** Lovely Fly can choose an inert shopkeeper as its mate when a real
> active enemy is also present. It then orbits the shopkeeper instead of the nearby
> combat target; non-active room decorations must not be eligible parents.

> **[#EX-441]** Ominous Lantern now costs its charge just for being put away. Raising the
> lantern and then using the item again to lower it, without throwing, leaves the item empty:
> it cannot be raised again until its slow recharge (about ten seconds) has run. Lowering a
> lantern that was never thrown should leave it ready to raise again straight away. Throwing
> it must still empty it and start that recharge as before.

> **[#EX-461]** Big Scissors' blood trail is gone. After Isaac is hurt while holding Big
> Scissors, the item's other effects still kick in, but he no longer leaves a trail of red
> creep behind him for the rest of the room.

> **[#EX-469]** Balls returned by Baseball Mitt have lost their punch. They no longer bounce
> off walls or confuse enemies, they hit no harder than an ordinary tear, and when several
> shots were caught only one ball comes back.

## Task

Diagnose and fix every report. Preserve behaviour outside the reported paths.

## Cross-report regression envelope

- Grid Worm's opening correction must not reset the later random-turn clock; a wall
  rebound must escape the collision tile rather than oscillate there.
- Ritual Candle must damage a nearby vulnerable active enemy at very high fire rate and
  must not pulse every frame at the slower reported cadence.
- Beehive's young-tear wobble is half-strength only during the opening period; mature
  tears retain the full wobble.
- Deja Vu must suppress split-tear return chains without suppressing ordinary eligible
  returns. Baseball Mitt's impact effect is tied to the released ball even after the
  stance ends.
- Lovely Fly must select an active combat target rather than an inert shopkeeper that
  happens to be closer.

## Notes

- The target runtime is the native Linux Steam build of Afterbirth+ `v1.06.T1`.
- This is an Afterbirth+ Lua mod, not a Repentance mod. Use APIs available in that
  runtime.
- Afterbirth+ embeds Lua 5.3.
- Do not replace the mod wholesale or add third-party code/assets.
- The grader runs the submitted mod in the real game in an isolated, offline verifier.
