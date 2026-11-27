# Exodus: bug reports against the Afterbirth+ release

You are working on **Exodus**, a Lua mod for **The Binding of Isaac: Rebirth with
Afterbirth and Afterbirth+**. The mod source is in `exodus/`.

## Problem

This release missed a batch of independent fixes. The reports below are observations
from players, not diagnoses. They do not necessarily share a cause.

> **[#EX-226]** Grid Worm does not constrain a newly fired tear immediately. A tear
> fired diagonally can spend its opening frames travelling diagonally before the
> trinket's horizontal/vertical pattern takes over. When it finally snaps, its first
> direction can disagree with the direction the character is facing. Tears that hit a
> wall also invert their velocity without leaving the collision tile, so they can
> oscillate in place instead of rebounding cleanly. Keep the existing later random-turn
> cadence; fixing the opening direction must not make those periodic turns start sooner.

> **[#EX-239]** Entering a secret room with Blue Moon can erase almost every wall and
> expose the void. The trinket may clear room obstacles, but the room boundary and its
> door must remain intact.

> **[#EX-251]** Broken Glasses forgets the current floor as soon as the trinket is
> dropped. Enemies or pickups that appear later on that same floor render normally,
> even though the broken-world effect is meant to persist until the next floor and
> reset there.

> **[#EX-258]** Beehive makes fresh tears wobble at full strength immediately. During
> roughly their first twenty frames, successive velocity changes are about twice the
> intended size; young tears should use the gentler half-strength drift before the
> normal wobble takes over.

> **[#EX-184]** The Forbidden Fruit's earned damage disappears if the item is removed
> or rerolled. Using it increases damage while it is held, but the run immediately
> drops back to its old damage value when the item leaves the inventory.

> **[#EX-441]** Ominous Lantern now costs its charge just for being put away. Raising the
> lantern and then using the item again to lower it, without throwing, leaves the item empty:
> it cannot be raised again until its slow recharge (about ten seconds) has run. Lowering a
> lantern that was never thrown should leave it ready to raise again straight away. Throwing
> it must still empty it and start that recharge as before.

> **[#EX-461]** Big Scissors' blood trail is gone. After Isaac is hurt while holding Big
> Scissors, the item's other effects still kick in, but he no longer leaves a trail of red
> creep behind him for the rest of the room.

> **[#EX-436]** Child's Leash has no effect on Exodus's orbiting familiars. While the trinket
> is held, Sundial's sun and shadow, Hungry Hippo and Robo-Baby 3.6.0 keep circling at their
> full distance instead of being pulled in to half of it. They must orbit at half their
> usual distance while Child's Leash is held, and return to their usual distance once it is
> dropped.

## Task

Diagnose and fix every report. Preserve behaviour outside the reported paths.

## Cross-report regression envelope

- Grid Worm has three separate timing boundaries: a new tear is constrained at once,
  its initial axis follows the firing direction, and later random turns retain their
  existing cadence. A wall hit must rebound instead of oscillating in place.
- Beehive's reduced wobble applies only to young tears; mature tears retain full wobble.
- Blue Moon may clear obstacles but must preserve secret-room walls and its door.
- Broken Glasses is floor-scoped, not item-scoped: dropping the trinket does not end the
  current-floor effect, and entering the next floor does.
- Forbidden Fruit is run-state rather than current-item state: its earned damage remains
  after item removal and must not be gated on continued possession.

## Notes

- The target runtime is the native Linux Steam build of Afterbirth+ `v1.06.T1`.
- This is an Afterbirth+ Lua mod, not a Repentance mod. Use APIs available in that
  runtime.
- Afterbirth+ embeds Lua 5.3.
- Do not replace the mod wholesale or add third-party code/assets.
- The grader runs the submitted mod in the real game in an isolated, offline verifier.
