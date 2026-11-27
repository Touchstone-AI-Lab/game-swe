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

> **[#EX-289]** Lovely Fly can choose an inert shopkeeper as its mate when a real
> active enemy is also present. It then orbits the shopkeeper instead of the nearby
> combat target; non-active room decorations must not be eligible parents.

> **[#EX-327]** Baseball Mitt's released baseballs lose their impact effect when they
> land after the catching stance has ended. The ball still hits, but the short
> baseball-hit poof is absent. A released ball must create that effect whenever it
> dies, even though the mitt is no longer raised.

> **[#EX-342]** Headcase's arcing blood shots become harmless if Headcase dies just
> after the stomp launches them. Shots already in flight can overlap the player on
> landing without dealing damage. Their collision must continue to be processed
> after the firing Headcase is gone.

> **[#EX-274]** Deja Vu treats split tears as return candidates when they die. A split
> tear can produce both its normal child tears and an extra returning tear, which can
> then repeat the return chain. Split tears should be excluded from that mechanic.
> Ordinary eligible, non-split tears must continue to return normally.

> **[#EX-427]** Lil Rune no longer takes on the power of runes. Using a rune while holding
> Lil Rune leaves the familiar unchanged: no transformation animation plays and none of the
> rune powers appear — for example, after Algiz it should destroy enemy shots that touch it,
> and after Jera it should split dying enemies.

> **[#EX-463]** Unholy Mantle's burst no longer hurts enemies. When Isaac is hit while the
> mantle is charged, its costume disappears as before, but the enemies in the room take no
> damage. The burst should hit every vulnerable enemy in the room, once per floor.

> **[#EX-469]** Balls returned by Baseball Mitt have lost their punch. They no longer bounce
> off walls or confuse enemies, they hit no harder than an ordinary tear, and when several
> shots were caught only one ball comes back.

## Task

Diagnose and fix every report. Preserve behaviour outside the reported paths.

## Cross-report regression envelope

- Grid Worm must constrain a new tear immediately, choose the initial axis from the
  firing direction, rebound cleanly from a wall, and preserve its later turn cadence.
- Do not conflate source lifetime with projectile lifetime: a launched Headcase lob
  still deals damage after its shooter dies, and a released baseball still creates its
  hit effect after the stance ends.
- Target eligibility is separate from proximity: Lovely Fly must choose an active
  combat enemy over a nearby inert shopkeeper when both are present.
- Deja Vu excludes split tears from return chains while ordinary eligible tears continue
  to return.
- Keep ordinary tears unaffected by the Grid Worm constraint when its trinket is absent.

## Notes

- The target runtime is the native Linux Steam build of Afterbirth+ `v1.06.T1`.
- This is an Afterbirth+ Lua mod, not a Repentance mod. Use APIs available in that
  runtime.
- Afterbirth+ embeds Lua 5.3.
- Do not replace the mod wholesale or add third-party code/assets.
- The grader runs the submitted mod in the real game in an isolated, offline verifier.
