# Mindustry v159.7: turrets, heat redirectors and shockwave towers misbehave

## Context

`mindustry/` is the source tree of Mindustry (<https://github.com/Anuken/Mindustry>,
GPL-3.0, see `mindustry/LICENSE`) exactly as our dedicated servers run it: release
**v159.7** with the game core in `core/src`, the dedicated-server launcher and console
in `server/src`, and the annotation definitions in `annotations/src`. Game assets,
the Gradle build scripts and the upstream test suite are not part of the tree.

Our server build compiles every Java file under `core/src` and `server/src`, plus
`annotations/src/main/java/mindustry/annotations/Annotations.java`, with
`javac --release 17` against the official v159.7 `server-release.jar`, and runs the
dedicated server with the compiled classes ahead of that jar. Code generated at build
time (the `mindustry.gen` package, including the entity classes generated from the
component templates in `core/src/mindustry/entities/comp`) and every asset (maps,
bundles, sprites) come from the official jar and are not regenerated, so changes have
to be made in ordinary sources. Keep your changes inside `mindustry/core/src` and
`mindustry/server/src`.

## Reports

Players report the following problems with defense and heat blocks.

- **Idle turrets fire two quick shots when they engage.** A turret that has been waiting
  without a target fires its first two shots much closer together than its reload time.
  A duo (reload 20 ticks) that idles for about four seconds fires its second shot only 14
  ticks after the first once an enemy wall comes into range; slow turrets such as
  Foreshadow and Scathe make the double shot very visible.
- **Disabled heat redirectors keep passing heat.** A heat redirector switched off by a
  processor (`control enabled redirector1 0`) keeps redirecting heat: sensing `@heat` on it
  and on the redirector behind it still shows the full 1000 heat of the heat source
  feeding it.
- **Shockwave towers hit bullets outside their range.** A shockwave tower destroys enemy
  bullets in a square around itself: bullets near the corners, well outside the range
  circle it displays (170 world units), are destroyed too.

## Expected behaviour

- After any idle period, consecutive shots of a turret are never closer together than its
  reload time (20 ticks for a duo with copper). An engaged turret keeps firing at its
  reload interval and keeps its exact average fire rate when that interval is not a whole
  number of ticks (a duo firing silicon, which reloads 1.5 times faster, fires every
  13⅓ ticks on average). A loaded turret still fires as soon as it has a target, and an
  idle turret that is fully loaded does not consume its coolant (the water in a waiting
  duo stays constant).
- A heat redirector or heat router that is disabled holds no heat (`@heat` is 0) and
  passes none on, so the blocks behind it receive no heat through it. Enabled redirectors
  keep passing heat along as before.
- A shockwave tower only affects hittable enemy bullets within its range circle: a
  bullet about 212 world units away from a tower with range 170 survives the wave, while
  a bullet 100 world units away is still destroyed.

## Evaluation

The verifier compiles your tree offline as described above and starts a real headless
v159.7 dedicated server with it, without network access. A trusted plugin inside that
server builds small test worlds and runs the full game simulation tick by tick: it counts
the shots of duos firing at enemy walls, measures the coolant they hold, reads heat values
through a processor, and places stationary enemy bullets around a powered shockwave
tower.
