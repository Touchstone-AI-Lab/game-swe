---
difficulty: hard
estimated_minutes: 240
domains:
  - events
  - world-state
  - persistence
  - rollback
---

# Write a plugin: BlockTrail, a block change log with rollback

You are writing a **new** Paper plugin. The skeleton at `/app/plugin` holds:

- `pom.xml`: the frozen Maven build. It compiles `src/main/java` with Java 21 against the
  Paper API 1.21.11 (the exact API of the server that grades you) and packages
  `src/main/resources` into `target/BlockTrail.jar`. No other library is available.
- `src/main/resources/plugin.yml`: plugin name `BlockTrail`, the main class and
  `api-version: '1.21'`. Add the command and the permissions described below.
- `src/main/java/com/example/blocktrail/BlockTrailPlugin.java`: an empty main class.

Keep the plugin name and the main class `com.example.blocktrail.BlockTrailPlugin`. Everything
else is yours to write: add classes under `src/main/java` and resources under
`src/main/resources`.

## How the plugin is built and graded

- The verifier restores `pom.xml` (and removes anything under `src/test`), then builds offline
  with `mvn -o -DskipTests package`. You can run the same build yourself where Maven and its
  cache are available.
- The jar is loaded into a real Paper 1.21.11 dedicated server with no players and no network,
  and with an empty data folder `plugins/BlockTrail/`. The server has one world, `world`, a
  flat world whose top layer is grass blocks at y = -60 with air above. Private cases then run
  one after another in that single server session. If the plugin fails to enable, no case can
  be graded.
- The grader runs commands on the main server thread by looking the command up in the server's
  command map and calling `Command#execute`, with its own senders:
  - a console-like sender that has every permission;
  - senders that hold only the permissions a case grants them (they are not players);
  - player stand-ins that implement `Player` but support only `getName`, `getUniqueId`,
    `hasPermission`, `isOp` (always false), `sendMessage`, `sendPlainMessage`,
    `sendRichMessage` and `getServer`. Any other `Player` method throws.

  Declare the command in `plugin.yml` and handle it with a Bukkit `CommandExecutor` (not the
  Brigadier lifecycle API). Do not give the command a `permission:` key: the plugin checks
  permissions itself and answers with the message below.
- The grader drives the world the way the server does. It calls `BlockBreakEvent`,
  `BlockPlaceEvent` and `EntityExplodeEvent` through the plugin manager on real blocks of
  `world`, with player stand-ins as the players. For a break or an explosion it sets the
  affected blocks to air after the event unless the event was cancelled; for a place the block
  already holds the placed material when the event is called, as on a real server. The grader
  also primes real TNT and lets it explode.
- Replies are compared line by line. The grader records every message the sender receives,
  turns it into plain text (colour and formatting are dropped; a message with line breaks
  counts as several lines), trims each line and compares the sequence exactly with the lines
  this document specifies. Send nothing else to the sender. Colours are fine if they are real
  formatting, not literal `&` codes.
- Every file change is written to disk before the event handler or command that caused it
  returns.

## Recording changes

1. **Only changes that happen.** Listen at `EventPriority.MONITOR` and ignore cancelled events:
   a change whose event is cancelled, by any plugin at any priority or before it is called, is
   never recorded.
2. **What a change is.** Each change has an id, a time, an actor, an action, a world, block
   coordinates `x y z`, a `from` material and a `to` material:

   | Event | Action | Actor | `from` | `to` |
   | --- | --- | --- | --- | --- |
   | `BlockBreakEvent` | `break` | the player's `getName()` | the block's material | `air` |
   | `BlockPlaceEvent` | `place` | the player's `getName()` | `getBlockReplacedState()` material | `getBlockPlaced()` material |
   | `EntityExplodeEvent` | `explode` | `#` + the exploding entity's type key, e.g. `#tnt` | the block's material | `air` |

   Also record the complete before and after `BlockData#getAsString()` values for every change.
   Material alone is not enough: rollback must preserve properties such as stair facing, shape,
   half and waterlogging.

   An explosion records one change for every block of its final `blockList()` that is not air,
   in list order. Materials are written as their lower-case key without namespace
   (`Material#getKey().getKey()`, e.g. `stone`, `oak_planks`, `grass_block`). The time is
   `System.currentTimeMillis()` when the change is recorded.
3. **Ids.** Ids count up from 1 in recording order and are never reused. After a reload the
   next id is one more than the highest id in `changes.log` (1 when it holds no change).
4. **Filters.** A change is not recorded when its material (`from` for a break or an explosion,
   `to` for a place) is listed in `ignored-materials` (Bukkit `Material` names,
   case-insensitive), or when `worlds` is not empty and does not list the change's world.

## Configuration

5. When `plugins/BlockTrail/config.yml` does not exist at enable, write it with exactly these
   values (comments and key order are free):

   ```yaml
   ignored-materials:
     - SHORT_GRASS
     - TALL_GRASS
     - FIRE
   worlds: []
   page-size: 5
   max-radius: 32
   ```

## The change log file

6. Every new change is appended to `plugins/BlockTrail/changes.log` as one line (UTF-8,
   `\n` line ends) of twelve fields separated by `;`:

   ```text
   <id>;<time>;<actor>;<action>;<world>;<x>;<y>;<z>;<from>;<to>;<from-block-data>;<to-block-data>
   ```

   Block data fields are Bukkit `BlockData#getAsString()` values; air is `minecraft:air` and
   values cannot contain `;`. When a change is rolled back, `undo;<id>` is appended. Reload reads
   both kinds of line and continues to accept legacy ten-field changes with material-only
   rollback semantics; blank, malformed and unknown undo lines are ignored.

## Commands

7. One command, `/trail`, with case-insensitive subcommands. Validation order: an unknown
   subcommand, or none, gets the general usage line; a wrong number of arguments gets the
   subcommand's usage line; then the permission is checked; then the arguments are validated
   from left to right; the first failure is the only reply.

   | Subcommand | Permission (default `op`) |
   | --- | --- |
   | `lookup <world> <x> <y> <z>` | `blocktrail.lookup` |
   | `player <actor> [page]` | `blocktrail.lookup` |
   | `rollback <actor> <world> <x> <y> <z> <radius> <seconds>` | `blocktrail.rollback` |
   | `purge <seconds>` | `blocktrail.admin` |
   | `reload` | `blocktrail.admin` |

   Register the three permissions in `plugin.yml` with default `op`. A sender without the
   permission gets `You do not have permission to do that.` The usage lines are:

   ```text
   Usage: /trail <lookup|player|rollback|purge|reload>
   Usage: /trail lookup <world> <x> <y> <z>
   Usage: /trail player <actor> [page]
   Usage: /trail rollback <actor> <world> <x> <y> <z> <radius> <seconds>
   Usage: /trail purge <seconds>
   Usage: /trail reload
   ```

8. **Arguments.** A world that is not loaded gets `Unknown world: <argument>`. Coordinates are
   whole numbers (an optional minus sign and digits); if any of the three is not, the reply is
   `Invalid coordinates.` A page must be a whole number of at least 1, otherwise
   `Invalid page: <argument>`. The radius must be a whole number from 0 to `max-radius`,
   otherwise `Radius must be a whole number from 0 to <max-radius>.` Seconds must be a whole
   number of at least 1, otherwise `Invalid time: <argument>`. Actors are matched
   case-insensitively and echoed in replies exactly as typed.
9. **Change lines.** A change is described as `#<id> <actor> broke <from>`,
   `#<id> <actor> placed <to> over <from>` or `#<id> <actor> exploded <from>`, followed by
   ` (rolled back)` once it has been rolled back.
10. **Lookup** lists every recorded change at that block, newest (highest id) first, after the
    header `Changes at <world> <x> <y> <z>:`. With none it replies
    `No changes at <world> <x> <y> <z>.`
11. **Player** lists the actor's changes newest first, `page-size` per page (the page defaults
    to 1), after the header `Changes by <actor> (page <page>/<last>):`. Each line is the change
    line without the actor, with ` at <world> <x> <y> <z>` before the rolled-back suffix, for
    example `#12 broke stone at world 10 -59 4 (rolled back)`. With no change by the actor:
    `No changes by <actor>.`; past the last page: `Page <page> does not exist; last page is
    <last>.`
12. **Rollback** takes the actor's changes that are in that world, within `radius` of the
    centre on every axis (`|dx|`, `|dy|` and `|dz|` at most `radius`), recorded within the last
    `seconds` seconds (time at least now minus `seconds × 1000`) and not rolled back yet. It
   processes them newest first: a new-format change qualifies only when the current material
   and full block data equal its recorded `to` state; a legacy line checks only its material.
   A qualifying block is restored to its recorded `from` material and block data, then marked
   rolled back (append the `undo` line); otherwise it is skipped and stays unmarked. This
   preserves stair facing, shape, half and waterlogging, and protects later data-only changes
   from being overwritten. Restoring blocks fires no events and records nothing. The actor,
   world, radius, age, rollback-mark and block-state filters all apply
    together; a nearby change by another actor, or an older change by the requested actor, must
    remain untouched. The reply is `Rollback of <actor>: <restored> restored, <skipped>
    skipped.`, or `Nothing to roll back for <actor>.` when no change qualified.
13. **Purge** deletes every change recorded more than `seconds` seconds ago (time before now
    minus `seconds × 1000`) and rewrites `changes.log` to hold the remaining change lines in id
    order followed by one `undo;<id>` line for each remaining rolled-back change, in id order.
    The reply is `Purge complete: <removed> removed, <kept> kept.`
14. **Reload** re-reads `config.yml` and `changes.log` from disk (a missing `changes.log` means
    no changes) and replies `BlockTrail reloaded (changes: <n>).`

The hidden cases run against the real server and cover the default configuration, the command
and permission declarations, recording of breaks, places and explosions (including cancelled
events, ignored materials and the world filter), the exact log lines, lookups and paging,
rollbacks by actor, area and time (including skipped blocks, ordering and marks), exact block-data
restoration and stale-state skips, a real TNT explosion rolled back block for block, a rollback
combining actor/radius/time filters, purge,
reload from a log the grader writes itself, permission checks with limited senders and the usage
lines.
