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

> **[#EX-251]** Broken Glasses forgets the current floor as soon as the trinket is
> dropped. Enemies or pickups that appear later on that same floor render normally,
> even though the broken-world effect is meant to persist until the next floor and
> reset there.

> **[#EX-266]** The Apocryphon no longer applies its room rewards to the player. On a
> first visit to a non-standard room, none of damage, tear delay, speed, shot speed,
> luck, or range changes, even though at least one of those stats should increase.

> **[#EX-274]** Deja Vu treats split tears as return candidates when they die. A split
> tear can produce both its normal child tears and an extra returning tear, which can
> then repeat the return chain. Split tears should be excluded from that mechanic.
> Ordinary eligible, non-split tears must continue to return normally.

> **[#EX-318]** Anamnesis borrows the charge of whichever active item occupied the
> slot before it. Picking up a fresh Anamnesis after a fully charged active can make
> it immediately usable; dropping and later recovering it can likewise forget the
> charge it had earned. Its charge must belong to Anamnesis itself across active-item
> swaps, and a fresh copy must not inherit a full foreign charge.

> **[#EX-342]** Headcase's arcing blood shots become harmless if Headcase dies just
> after the stomp launches them. Shots already in flight can overlap the player on
> landing without dealing damage. Their collision must continue to be processed
> after the firing Headcase is gone.

> **[#EX-289]** Lovely Fly can choose an inert shopkeeper as its mate when a real
> active enemy is also present. It then orbits the shopkeeper instead of the nearby
> combat target; non-active room decorations must not be eligible parents.

> **[#EX-427]** Lil Rune no longer takes on the power of runes. Using a rune while holding
> Lil Rune leaves the familiar unchanged: no transformation animation plays and none of the
> rune powers appear — for example, after Algiz it should destroy enemy shots that touch it,
> and after Jera it should split dying enemies.

> **[#EX-441]** Ominous Lantern now costs its charge just for being put away. Raising the
> lantern and then using the item again to lower it, without throwing, leaves the item empty:
> it cannot be raised again until its slow recharge (about ten seconds) has run. Lowering a
> lantern that was never thrown should leave it ready to raise again straight away. Throwing
> it must still empty it and start that recharge as before.

> **[#EX-465]** Birdbath does nothing when used: no bath appears next to Isaac.

## Task

Diagnose and fix every report. Preserve behaviour outside the reported paths.

## Cross-report regression envelope

- The reports span independent state scopes. Do not apply a global tear rewrite,
  cache reset, or owner cleanup to make one report pass if it changes another mechanic.
- Grid Worm's initial axis and heading correction must leave its later turn cadence
  intact; Deja Vu must exclude split tears without disabling returns for ordinary tears.
- Anamnesis starts without a borrowed charge and retains its own charge over a swap;
  Broken Glasses survives trinket removal for the current floor but resets on the next.
- The Apocryphon must still reward the eligible first non-standard-room visit, while
  Cursed Metronome's conversion is based on red-heart capacity rather than the current
  fill level. Launched Headcase shots must finish their collision after the shooter dies.
- Lovely Fly's target eligibility must exclude an inert shopkeeper even when it is the
  closest entity to the fly.

## Notes

- The target runtime is the native Linux Steam build of Afterbirth+ `v1.06.T1`.
- This is an Afterbirth+ Lua mod, not a Repentance mod. Use APIs available in that
  runtime.
- Afterbirth+ embeds Lua 5.3.
- Do not replace the mod wholesale or add third-party code/assets.
- The grader runs the submitted mod in the real game in an isolated, offline verifier.
