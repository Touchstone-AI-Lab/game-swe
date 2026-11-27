# Exodus: bug reports against the Afterbirth+ release

You are working on **Exodus**, a Lua mod for **The Binding of Isaac: Rebirth with
Afterbirth and Afterbirth+**. The mod source is in `exodus/`.

## Problem

This release missed a batch of independent fixes. The reports below are observations
from players, not diagnoses. They do not necessarily share a cause.

> **[#EX-239]** Entering a secret room with Blue Moon can erase almost every wall and
> expose the void. The trinket may clear room obstacles, but the room boundary and its
> door must remain intact.

> **[#EX-251]** Broken Glasses forgets the current floor as soon as the trinket is
> dropped. Enemies or pickups that appear later on that same floor render normally,
> even though the broken-world effect is meant to persist until the next floor and
> reset there.

> **[#EX-266]** The Apocryphon no longer applies its room rewards to the player. On a
> first visit to a non-standard room, none of damage, tear delay, speed, shot speed,
> luck, or range changes, even though at least one of those stats should increase.

> **[#EX-296]** Starting a new floor grants a Book of Secrets mapping effect to every
> character. That automatic use belongs to James's floor setup only; a normal Isaac
> run without the item should not gain map, compass, or blue-map information.

> **[#EX-311]** Mutant Clover does not stack within a room. Activating it twice still
> gives only ten luck, while each activation in the current room should add another
> ten. The whole temporary stack should continue to reset on entering another room.

> **[#EX-318]** Anamnesis borrows the charge of whichever active item occupied the
> slot before it. Picking up a fresh Anamnesis after a fully charged active can make
> it immediately usable; dropping and later recovering it can likewise forget the
> charge it had earned. Its charge must belong to Anamnesis itself across active-item
> swaps, and a fresh copy must not inherit a full foreign charge.

> **[#EX-203]** Ritual Candle stops hurting nearby enemies on very high fire-rate
> builds. With all five candle flames lit and a tear delay of 2, an active vulnerable
> enemy standing next to the player can remain completely undamaged. At a tear delay
> of 4 the opposite timing problem is visible: the aura pulses every frame, roughly
> twice as often as the intended rounded interval.

> **[#EX-441]** Ominous Lantern now costs its charge just for being put away. Raising the
> lantern and then using the item again to lower it, without throwing, leaves the item empty:
> it cannot be raised again until its slow recharge (about ten seconds) has run. Lowering a
> lantern that was never thrown should leave it ready to raise again straight away. Throwing
> it must still empty it and start that recharge as before.

> **[#EX-463]** Unholy Mantle's burst no longer hurts enemies. When Isaac is hit while the
> mantle is charged, its costume disappears as before, but the enemies in the room take no
> damage. The burst should hit every vulnerable enemy in the room, once per floor.

> **[#EX-412]** Welcome Mat gets floor changes wrong. Arriving on a new floor now lays a mat
> under the character in the floor's first room, although nobody walked in through a door.
> The next room entered after that gets no mat at all, so its tears bonus is missing there;
> from the room after that, mats appear as usual. A mat belongs in every room entered after
> the first room of a floor, including the very next one, and never in the room where a new
> floor begins.

## Task

Diagnose and fix every report. Preserve behaviour outside the reported paths.

## Cross-report regression envelope

- Keep the scopes separate: Mutant Clover resets on room entry; Broken Glasses persists
  after its trinket is dropped but resets on the next floor; Anamnesis keeps its own
  charge over item swaps rather than borrowing the previous active item's charge.
- Blue Moon must leave secret-room walls and doors intact while removing eligible
  obstacles.
- Book of Secrets mapping at floor setup belongs to James only; ordinary Isaac must not
  receive it automatically. The Apocryphon's eligible first-visit room reward must still
  occur for the character who qualifies.
- Ritual Candle must hit nearby vulnerable active enemies at the high-fire-rate edge and
  retain the intended rounded pulse cadence at the slower edge.
- Do not use a single room/floor reset hook for all state: these reports intentionally
  require different transition boundaries.

## Notes

- The target runtime is the native Linux Steam build of Afterbirth+ `v1.06.T1`.
- This is an Afterbirth+ Lua mod, not a Repentance mod. Use APIs available in that
  runtime.
- Afterbirth+ embeds Lua 5.3.
- Do not replace the mod wholesale or add third-party code/assets.
- The grader runs the submitted mod in the real game in an isolated, offline verifier.
