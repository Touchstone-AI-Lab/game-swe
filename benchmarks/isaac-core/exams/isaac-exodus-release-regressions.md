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

> **[#EX-203]** Ritual Candle stops hurting nearby enemies on very high fire-rate
> builds. With all five candle flames lit and a tear delay of 2, an active vulnerable
> enemy standing next to the player can remain completely undamaged. At a tear delay
> of 4 the opposite timing problem is visible: the aura pulses every frame, roughly
> twice as often as the intended rounded interval.

> **[#EX-217]** Cursed Metronome's first-time health conversion depends on how full
> the player's red-heart containers happen to be. A wounded player with six red-heart
> containers and two filled hearts is left with one filled heart, while the conversion
> should empty the red hearts consistently for that capacity.

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

> **[#EX-247]** Rerolling or removing familiar items can leave their companions alive
> after the item is gone. This has been reproduced with Ritual Candle's five flames,
> both Sundial orbitals, Astro Baby, and Lil Rune. Every companion should disappear
> promptly once its owning collectible is no longer held.

> **[#EX-251]** Broken Glasses forgets the current floor as soon as the trinket is
> dropped. Enemies or pickups that appear later on that same floor render normally,
> even though the broken-world effect is meant to persist until the next floor and
> reset there.

> **[#EX-258]** Beehive makes fresh tears wobble at full strength immediately. During
> roughly their first twenty frames, successive velocity changes are about twice the
> intended size; young tears should use the gentler half-strength drift before the
> normal wobble takes over.

> **[#EX-266]** The Apocryphon no longer applies its room rewards to the player. On a
> first visit to a non-standard room, none of damage, tear delay, speed, shot speed,
> luck, or range changes, even though at least one of those stats should increase.

> **[#EX-274]** Deja Vu treats split tears as return candidates when they die. A split
> tear can produce both its normal child tears and an extra returning tear, which can
> then repeat the return chain. Split tears should be excluded from that mechanic.
> Ordinary eligible, non-split tears must continue to return normally.

> **[#EX-281]** Lil Rune's Jera form creates damaged enemies with invalid health.
> When a killed enemy is duplicated into two smaller copies, each copy keeps the
> original current health while its maximum is halved, leaving current health above
> the displayed maximum.

> **[#EX-289]** Lovely Fly can choose an inert shopkeeper as its mate when a real
> active enemy is also present. It then orbits the shopkeeper instead of the nearby
> combat target; non-active room decorations must not be eligible parents.

> **[#EX-296]** Starting a new floor grants a Book of Secrets mapping effect to every
> character. That automatic use belongs to James's floor setup only; a normal Isaac
> run without the item should not gain map, compass, or blue-map information.

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

## Task

Diagnose and fix every report. Preserve behaviour outside the reported paths.

## Notes

- The target runtime is the native Linux Steam build of Afterbirth+ `v1.06.T1`.
- This is an Afterbirth+ Lua mod, not a Repentance mod. Use APIs available in that
  runtime.
- Do not replace the mod wholesale or add third-party code/assets.
- The grader runs the submitted mod in the real game in an isolated, offline verifier.
