# Harbor workspace

Complete this task in `/app/mindustry`; the verifier compiles its Java sources against the pinned Mindustry v159.7 dedicated server.

# Mindustry v159.7: dedicated server console regressions

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

Server operators report the following problems with the dedicated server console.

- **`pause` toggles instead of setting a state.** On a running game, `pause on` pauses
  it, but typing `pause on` again resumes the game; `pause off` on a running game
  pauses it.
- **`host` crashes when map shuffling is off.** After `shuffle none`, a plain `host`
  (without a map name) fails with

  ```text
  java.lang.NullPointerException: Cannot invoke "mindustry.maps.Map.plainName()" because ... is null
  ```

  and takes the whole server down.
- **Pardoned players still cannot rejoin.** A player who was kicked for 30 minutes and
  then pardoned with `pardon <ID>` is still refused when reconnecting from the same
  address until the original kick expires.
- **Player records vanish after a restart.** Bans by ID, known names and addresses, kick
  history and admin flags are all gone after the server restarts: `bans` lists no ID bans,
  `info` and `search` know nobody, and the startup log shows an error about reading the
  stored `player-data`.

## Expected behaviour

- On a running game `pause on` always leaves the game paused and `pause off` always
  leaves it running, however often they are repeated. Without a running game `pause`
  still refuses with `Cannot pause without a game running.`
- `host` without a map name while the shuffle mode is `none` does not throw: nothing is
  hosted, the server stays stopped (no game, no open server socket) and the console keeps
  working; a following `host <map name>` (for example `host Ancient_Caldera`) hosts that
  map as usual. `host <map name>`, `stop`, `status` and `shuffle` (which reports the
  current mode as `Shuffle mode current set to '<mode>'.`) keep working.
- `pardon <ID>` removes every pending kick of that player, both the one on the ID and the
  one recorded for the player's last known address, so that
  `netServer.admins.getKickTime(id, address)`, which the server checks for joining
  players, is no longer in the future. `pardon` with an unknown ID still answers
  `That ID can't be found.`
- Player records written by the server (names, addresses, ID bans, kicks, admin status)
  are read back when the server starts again, so an ID banned before a restart is still
  banned afterwards and its last known name is still known. Banning, listing and
  unbanning addresses within one session keeps working (`ban ip <address>`, `bans`,
  `unban <address>` answering `Unbanned player: <address>`).

## Evaluation

The verifier compiles your tree offline as described above and starts a real headless
v159.7 dedicated server with it, without network access. A trusted plugin inside that
server runs console commands (`status`, `host`, `stop`, `pause`, `shuffle`, `ban`,
`bans`, `unban`, `pardon`), inspects the resulting game state, kick records and ban
lists, and simulates a restart by writing the server settings to disk and reading the
player records back the way a freshly started server does.
