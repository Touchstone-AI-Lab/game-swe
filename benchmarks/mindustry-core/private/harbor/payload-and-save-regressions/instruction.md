# Harbor workspace

Complete this task in `/app/mindustry`; the verifier compiles its Java sources against the pinned Mindustry v159.7 dedicated server.

# Mindustry v159.7: payload and world save regressions

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

Players report the following problems with payloads and saved worlds.

- **Payloads come off derelict payload conveyors after loading.** A block payload lying on
  a derelict payload conveyor is no longer on that conveyor once the world is saved and
  loaded again: the payload ends up at the map origin (0, 0) and stays there. Payloads on
  conveyors of a real team are not affected.
- **Worlds with long build queues cannot be loaded.** A world in which a builder unit (for
  example a poly) has 1200 queued build plans saves without complaint, but loading that
  save fails with `Queue too long: 1200`, so the world is lost.
- **Carried derelict blocks cannot be set down near a core.** A unit that picked up a
  derelict block (for example a mega carrying a derelict copper wall) cannot set it down
  anywhere inside a core's protected area, even next to its own team's core, although the
  same unit puts down its own team's blocks there without trouble.

## Expected behaviour

- A payload on a derelict payload conveyor stays on its conveyor through a save and load:
  afterwards it is still the same block and lies within the conveyor's footprint, exactly
  as on a team conveyor. Team payload conveyors still pass payloads on to the next
  conveyor and keep their payload through a save.
- Saves load no matter how many build plans a unit has queued, and the unit comes back
  with all of its plans (1200 plans stay 1200 plans). Short queues keep working.
- A unit can set down a carried derelict block inside a core's protected area wherever
  the block could otherwise stand, and it appears there as a derelict block. Own-team
  blocks can still be set down near the team's core, derelict blocks can still be set
  down far from any core, and a block of another active team (for example a crux wall
  carried by a sharded unit) still cannot be set down inside a core's protected area.

## Evaluation

The verifier compiles your tree offline as described above and starts a real headless
v159.7 dedicated server with it, without network access. A trusted plugin inside that
server builds small test worlds with payload conveyors, builder units and
payload-carrying units, saves and reloads them, and has units try to set down the blocks
they carry, checking where payloads, units, plans and blocks end up.
