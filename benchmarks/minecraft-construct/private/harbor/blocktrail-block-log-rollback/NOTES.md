# Maintenance notes: blocktrail-block-log-rollback

## Task

Construct task: the model writes the whole BlockTrail plugin, a block change logger in the
style of CoreProtect: MONITOR-priority listeners for breaks, places and explosions, an
append-only `changes.log` with `undo` marks, lookups by block and by actor, rollback by actor,
area and time on real world blocks, purge and reload.

## Skeleton

Frozen `pom.xml` (as in the other construct tasks), minimal `plugin.yml`, empty
`BlockTrailPlugin`. The empty skeleton builds and enables; the `nop` control is complete and
fails every case but the sentinel.

## Reference

`solution/after/` (about 620 lines of Java): `Action`, `Change` (log line, parsing, the two
description formats), `TrailSettings`, `TrailStore` (id order, undo marks, purge rewrite),
`TrailListener`, `TrailCommand` and `BlockTrailPlugin`.

## Live-server design

- 25 cases in `tests/suite/BlockTrailSuite.java`, sentinel first.
- The grader drives the world as the server does: it sets a block, calls
  `BlockBreakEvent`/`BlockPlaceEvent`/`EntityExplodeEvent` through the plugin manager with a
  `Player` stand-in, and then applies (or, when cancelled, reverts) the change itself.
- `tests/suite/Canceller.java` is a second listener registered by the grader plugin at
  `HIGHEST`: it cancels chosen breaks and removes chosen blocks from explosion lists, so the case
  "cancelled changes are not recorded" needs the MONITOR priority the exam requires.
- `a real TNT explosion is recorded and rolled back` primes real TNT (fuse 10) in force-loaded
  chunks at x = z = 600, snapshots a 15 x 15 x 15 cube, and requires the rollback reply to count
  exactly the blocks the explosion changed and every block to be restored. The explosion is
  random; the assertions are not.
- Ids are derived from `changes.log` (highest id + 1), never hard-coded, except after the
  cases that write the log themselves and reload.
- The time-window, purge and reload cases write `changes.log` with times relative to "now"
  (one minute, one second, two hours ago) and reload; they run late because they replace the
  log.

## Pitfalls found while authoring

- `max-world-size` is 1024 in the benchmark server: block entities outside the border do not
  tick. Entity ticking (TNT) is unaffected, but the TNT case was moved inside the border anyway.
- `Material.FIRE` is not an item; the grader places fire with flint and steel in hand.

## Fairness review

- The exam states the MONITOR priority, the change fields, the id rule, the filters, the file
  format including `undo` lines, the reply formats and the rollback order and skip rule.
- Rollback restores with `setType(from, false)` in the reference; the exam only says "set back
  to `from`", and no case uses a block whose physics would differ.
