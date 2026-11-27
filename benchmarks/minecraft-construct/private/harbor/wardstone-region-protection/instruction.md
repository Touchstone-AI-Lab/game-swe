# Harbor workspace

Write this plugin in `/app/plugin`; the skeleton's `pom.xml` and anything under `src/test` are frozen and restored by the verifier.

# Write a plugin: Wardstone, cuboid region protection

You are writing a **new** Paper plugin. The skeleton at `/app/plugin` holds:

- `pom.xml`: the frozen Maven build. It compiles `src/main/java` with Java 21 against the
  Paper API 1.21.11 (the exact API of the server that grades you) and packages
  `src/main/resources` into `target/Wardstone.jar`. No other library is available.
- `src/main/resources/plugin.yml`: plugin name `Wardstone`, the main class and
  `api-version: '1.21'`. Add the command and the permissions described below.
- `src/main/java/com/example/wardstone/WardstonePlugin.java`: an empty main class.

Keep the plugin name and the main class `com.example.wardstone.WardstonePlugin`. Everything
else is yours to write: add classes under `src/main/java` and resources under
`src/main/resources`.

## How the plugin is built and graded

- The verifier restores `pom.xml` (and removes anything under `src/test`), then builds offline
  with `mvn -o -DskipTests package`. You can run the same build yourself where Maven and its
  cache are available.
- The jar is loaded into a real Paper 1.21.11 dedicated server with no players and no network,
  and with an empty data folder `plugins/Wardstone/`. The server has one world, `world`, a flat
  world whose top layer is grass blocks at y = -60. Private cases then run one after another in
  that single server session. If the plugin fails to enable, no case can be graded.
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
- The grader calls `BlockBreakEvent`, `BlockPlaceEvent`, `EntityExplodeEvent`,
  `BlockExplodeEvent`, `BlockBurnEvent` and `BlockIgniteEvent` through the plugin manager, on
  real blocks of `world`, with player stand-ins as the players, and then reads whether the event
  was cancelled, what is left in an explosion's block list and what the player was told.
- Replies are compared line by line. The grader records every message a sender or player
  stand-in receives, turns it into plain text (colour and formatting are dropped; a message
  with line breaks counts as several lines), trims each line and compares the sequence exactly
  with the lines this document specifies. Send nothing else. Colours are fine if they are real
  formatting, not literal `&` codes.
- Every file change is written to disk before the command that caused it returns.

## Regions

1. **A region** has a name, a world, two corners, a priority (a whole number, default 0), a
   set of owners, a set of members and a set of flags. Region names match
   `^[a-z0-9_-]{2,24}$` after being lower-cased: names are case-insensitive and stored,
   shown and saved in lower case. The region is the cuboid between the two corners, **every
   bound inclusive**: it contains a block when its x, y and z each lie between the smaller and
   the larger corner value, both included. Owners and members are player names matching
   `^[A-Za-z0-9_]{3,16}$`, case-insensitive, stored and shown in lower case.
2. **Flags.** Four flags exist: `block-break`, `block-place`, `explosion` and `fire`. A region
   either sets a flag to `allow` or `deny`, or does not set it.
3. **Resolution.** For a block and a flag, look at the regions that contain the block and set
   that flag. If there are none, the flag is allowed. Otherwise only the highest priority among
   them counts: the flag is denied if at least one region at that priority denies it, and
   allowed otherwise. The **deciding region** of a denial is the alphabetically first region
   name among the denying regions at that priority.
4. **Building.** A `BlockBreakEvent` (at the broken block) or `BlockPlaceEvent` (at the placed
   block) whose `block-break` or `block-place` flag is denied is cancelled, and the player is
   sent `You cannot break blocks in <region>.` or `You cannot place blocks in <region>.` naming
   the deciding region. It is not cancelled, and nothing is sent, when the player has the
   permission `wardstone.bypass` or is an owner or a member of the deciding region (by name,
   case-insensitively). Membership in a lower-priority overlapping region does not exempt the
   player from a denial decided by a higher-priority region.
5. **Explosions.** For an `EntityExplodeEvent` or a `BlockExplodeEvent`, every block of the
   block list whose `explosion` flag is denied is removed from the list; the event itself is
   not cancelled and the other blocks stay in the list.
6. **Fire.** A `BlockBurnEvent` whose block has the `fire` flag denied is cancelled. A
   `BlockIgniteEvent` at a block with `fire` denied is cancelled when its cause is `SPREAD`,
   `LAVA` or `LIGHTNING`; other causes (a player's flint and steel, for example) are not
   affected by this flag. A `BlockFromToEvent` is cancelled when its destination has
   `block-place` denied. Resolution uses the destination, so flow out of a protected source to
   an allowed destination is not cancelled.
7. **Default configuration.** When `plugins/Wardstone/config.yml` does not exist at enable, write
   it with `max-region-volume: 1000000` (comments are free). A region whose block count
   (`dx × dy × dz`, each side counted inclusively) is above this value cannot be defined.

## Persistence

8. After every change, `plugins/Wardstone/regions.yml` holds every region under the key
   `regions`, with the corners normalised so that `min` holds the smaller and `max` the larger
   value on each axis, and the owners, members and flags as shown here (lists sorted
   alphabetically; a region without flags has an empty `flags` section):

   ```yaml
   regions:
     spawn:
       world: world
       min: {x: 0, y: -64, z: 0}
       max: {x: 10, y: -50, z: 10}
       priority: 0
       owners: [alice]
       members: []
       flags:
         block-break: deny
   ```

9. `/ward reload` re-reads `config.yml` and `regions.yml` from disk (a missing `regions.yml`
   means no regions) and replies `Wardstone reloaded (regions: <n>).` Regions whose world is not
   loaded are kept but protect nothing.

## Commands

10. One command, `/ward`, with case-insensitive subcommands, all needing the permission
    `wardstone.admin`. Register `wardstone.admin` and `wardstone.bypass` in `plugin.yml` with
    default `op`. Validation order: an unknown subcommand, or none, gets the general usage
    line; a wrong number of arguments gets the subcommand's usage line; then the permission is
    checked (`You do not have permission to do that.`); then the arguments are validated from
    left to right; the first failure is the only reply. A region argument that is not a valid
    name gets `Invalid region name: <argument>`, a valid name with no region
    `Unknown region: <name>` (lower case).

    | Subcommand | Success reply |
    | --- | --- |
    | `define <region> <world> <x1> <y1> <z1> <x2> <y2> <z2>` | `Defined region <name> in <world> (<dx> x <dy> x <dz> = <volume> blocks).` |
    | `delete <region>` | `Deleted region <name>.` |
    | `priority <region> <priority>` | `Priority of <name> set to <priority>.` |
    | `flag <region> <flag> <allow\|deny\|clear>` | `Flag <flag> of <name> set to <value>.` or, for `clear`, `Flag <flag> of <name> cleared.` |
    | `addowner <region> <player>` | `Added <player> as owner of <name>.` |
    | `removeowner <region> <player>` | `Removed <player> from the owners of <name>.` |
    | `addmember <region> <player>` | `Added <player> as member of <name>.` |
    | `removemember <region> <player>` | `Removed <player> from the members of <name>.` |
    | `info <region>` | four lines, see requirement 11 |
    | `at <world> <x> <y> <z>` | `Regions at <world> <x> <y> <z>: <name> (priority <p>), …` |
    | `list` | `<n> regions: <a>, <b>, …` sorted by name, or `No regions.` |
    | `reload` | requirement 9 |

    Other replies, in the order the checks apply:
    - `define`: `Region <name> already exists.`; `Unknown world: <argument>`; coordinates are
      whole numbers (optional minus sign and digits), otherwise `Invalid coordinates.`;
      `Region too large: <volume> blocks (maximum <max>).`
    - `priority`: `Invalid priority: <argument>` for anything but a whole number.
    - `flag`: `Unknown flag: <argument> (flags: block-break, block-place, explosion, fire)`,
      then `Invalid flag value: <argument> (use allow, deny or clear)`. Flag names and values
      are case-insensitive.
    - owners and members: `Invalid player name: <argument>`; `<player> is already an owner of
      <name>.`, `<player> is not an owner of <name>.`, `<player> is already a member of
      <name>.`, `<player> is not a member of <name>.`
    - `at`: `Unknown world: <argument>`, `Invalid coordinates.`; with no region there:
      `No regions at <world> <x> <y> <z>.` Regions are listed by priority, highest first, then
      by name.

    The usage lines are:

    ```text
    Usage: /ward <define|delete|priority|flag|addowner|removeowner|addmember|removemember|info|at|list|reload>
    Usage: /ward define <region> <world> <x1> <y1> <z1> <x2> <y2> <z2>
    Usage: /ward delete <region>
    Usage: /ward priority <region> <priority>
    Usage: /ward flag <region> <flag> <allow|deny|clear>
    Usage: /ward addowner <region> <player>
    Usage: /ward removeowner <region> <player>
    Usage: /ward addmember <region> <player>
    Usage: /ward removemember <region> <player>
    Usage: /ward info <region>
    Usage: /ward at <world> <x> <y> <z>
    Usage: /ward list
    Usage: /ward reload
    ```

11. **Info** replies with exactly four lines:

    ```text
    Region <name> in <world> from <minx> <miny> <minz> to <maxx> <maxy> <maxz>, priority <p>
    Owners: <sorted names joined by ", ", or none>
    Members: <sorted names joined by ", ", or none>
    Flags: <flag>=<value> pairs sorted by flag name and joined by ", ", or none
    ```

The hidden cases run against the real server and cover the default configuration, the command
and permission declarations, defining regions (sizes, validation, the volume limit and the
saved file), inclusive bounds, break and place denials with their messages, owner, member and
bypass exemptions, membership against a higher-priority overlapping denial, priorities and
equal-priority conflicts, explosion block lists, fire, flag
editing, owners and members, info, at, list, delete, reload from a file the grader writes
itself, permission checks with limited senders, protected fluid destinations and the usage lines.
