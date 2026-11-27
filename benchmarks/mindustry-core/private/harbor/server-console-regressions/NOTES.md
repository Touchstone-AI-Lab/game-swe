# Maintenance notes: server-console-regressions

## Upstream

- Repository: https://github.com/Anuken/Mindustry (GPL-3.0, `LICENSE` kept).
- Base: release tag `v159.7`, commit `c9686eb5d0ae5dd47ee02c40f99f7d5018ccbc8c`.
- Starter: the v159.7 tree with four upstream fixes reverted; the reference is v159.7
  as released (`solution/after` holds `ServerControl.java` and `Administration.java`).

| Report | Upstream fix | Reverted in the starter |
| --- | --- | --- |
| `pause on`/`off` toggle instead of setting | `40cd2fd27605029151a446d0d0bffb6a27fa355c` (PR #9696) | yes |
| `host` with `shuffle none` throws a NullPointerException | `adb7264bc4745894eaab3897232681f17f9a4450` (issue #10815) | yes |
| `pardon` leaves the kick on the player's address | `966a93ddfa576e56a28639966d864176580b4122` (issue #6930), `ServerControl` hunk only | yes |
| player records unreadable after a restart | `1beb1c073fc1170827f58da2352cd8ea9820ff50` (issue #11793), `Administration` hunk only | yes |

The `966a93ddf` commit also changed `Unloader.read`, and `1beb1c073` also changed a
power-node preview in `Block.java`; those unrelated hunks are not reverted. Each reverted defect shipped in a release before its fix (the
fixes first appeared in v136, v147, v150 and v156.1). No defect is injected.

## Defects

- `ServerControl` `pause`: sets the state from `state.isPaused()` instead of the argument.
- `ServerControl` `host`: dereferences the shuffled map without a null check when the
  shuffle mode is `none`.
- `ServerControl` `pardon`: resets `PlayerInfo.lastKicked` but leaves
  `Administration.kickedIPs` holding the player's last address.
- `Administration.PlayerInfo` is not `Serializable`; `JsonIO.json` refuses to deserialize
  classes that are neither `Serializable` nor `JsonSerializable`, so `player-data`
  written by `forceSave` cannot be read back (`Class deserialization not allowed`).

## Suite design

Ten cases: one sentinel, four targets, five preserved. The cases drive the real server
console through `ServerControl.handleCommandString`, capture its log output, and read
game state, `Administration` kick and ban records. The restart case writes the settings
to disk (`Administration.forceSave`, `Settings.forceSave`), reloads them
(`Settings.load`) and constructs a fresh `Administration` the way a starting server does.
Cases host the built-in `Ancient_Caldera` map from the pinned jar.
