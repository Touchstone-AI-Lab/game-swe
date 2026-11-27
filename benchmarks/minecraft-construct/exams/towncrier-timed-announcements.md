---
difficulty: hard
estimated_minutes: 240
domains:
  - scheduler
  - broadcasting
  - configuration
  - commands
---

# Write a plugin: TownCrier, timed server announcements

You are writing a **new** Paper plugin. The skeleton at `/app/plugin` holds:

- `pom.xml`: the frozen Maven build. It compiles `src/main/java` with Java 21 against the
  Paper API 1.21.11 (the exact API of the server that grades you, Adventure and MiniMessage
  included) and packages `src/main/resources` into `target/TownCrier.jar`. No other library
  is available.
- `src/main/resources/plugin.yml`: plugin name `TownCrier`, the main class and
  `api-version: '1.21'`. Add the command and the permission described below.
- `src/main/java/com/example/towncrier/TownCrierPlugin.java`: an empty main class.

Keep the plugin name and the main class `com.example.towncrier.TownCrierPlugin`. Everything
else is yours to write: add classes under `src/main/java` and resources under
`src/main/resources`.

## How the plugin is built and graded

- The verifier restores `pom.xml` (and removes anything under `src/test`), then builds offline
  with `mvn -o -DskipTests package`. You can run the same build yourself where Maven and its
  cache are available.
- The jar is loaded into a real Paper 1.21.11 dedicated server with no players and no network
  (`max-players` is 1), and with an empty data folder `plugins/TownCrier/`. Private cases then
  run one after another in that single server session. If the plugin fails to enable, no case
  can be graded.
- The grader runs commands on the main server thread by looking the command up in the server's
  command map and calling `Command#execute`, with its own senders:
  - a console-like sender that has every permission;
  - senders that hold only the permissions a case grants them (they are not players).

  Declare the command in `plugin.yml` and handle it with a Bukkit `CommandExecutor` (not the
  Brigadier lifecycle API). Do not give the command a `permission:` key: the plugin checks
  the permission itself and answers with the message below.
- The grader receives announcements through receivers that it subscribes to permissions with
  `PluginManager#subscribeToPermission`, which is where `Server#broadcast(Component, String)`
  finds its recipients: one receiver holds only `bukkit.broadcast.user`, another holds
  `bukkit.broadcast.user` and `towncrier.staff`. It counts and reads what they receive while
  the server ticks, so timing is measured in server ticks (20 ticks per second), never in wall
  clock time.
- Replies and announcements are compared line by line. The grader turns every message a sender
  or receiver gets into plain text (colour and formatting are dropped; a message with line
  breaks counts as several lines), trims each line and compares exactly with the lines this
  document specifies. Send nothing else to the sender.
- Every file change is written to disk before the command that caused it returns.

## Announcement groups

1. **The file.** Announcements live in `plugins/TownCrier/announcements.yml`. When the file does
   not exist at enable, write it with exactly these values (comments and key order are free):

   ```yaml
   prefix: "<gray>[<gold>Crier</gold>]</gray> "
   groups:
     tips:
       enabled: true
       interval: 300
       order: sequential
       permission: ""
       messages:
         - "Use <yellow>/spawn</yellow> to return to spawn."
         - "Be kind to other players!"
   ```

2. **Group keys.** Every key under `groups` is a group. `interval` is required: whole seconds,
   at least 1. `enabled` defaults to `true`, `order` to `sequential` (the other allowed value is
   `shuffle`), `permission` to the empty string. `messages` is a list of strings with at least
   one entry. `prefix` (top level) defaults to the empty string.
3. **Invalid groups.** On enable and on reload every group is checked in this order, and the
   first failure makes it invalid with that reason:

   | Check | Reason |
   | --- | --- |
   | the name matches `^[a-z0-9_-]{1,32}$` | `invalid name` |
   | `interval` is a whole number of at least 1 | `interval must be a whole number of at least 1` |
   | `order` is `sequential` or `shuffle` | `order must be sequential or shuffle` |
   | `messages` has at least one entry | `no messages` |

   An invalid group does not exist for the plugin: it is never scheduled, never listed, and
   commands answer `Unknown group: <name>` for it. The other groups still load.
4. **Rendering.** An announcement is the prefix followed by the message, with these
   placeholders replaced first: `{group}` (the group name), `{index}` (the 1-based position of
   the message in the group's list), `{count}` (the number of messages in the group),
   `{online}` (online players) and `{max}` (the server's maximum players). The result is parsed
   with MiniMessage, so `<red>Red</red>` shows as `Red` in plain text.
5. **Delivery.** Each announcement is exactly one call of `Server#broadcast(Component, String)`
   (or `Bukkit.broadcast`) with the group's permission, or `bukkit.broadcast.user` when the
   group's permission is empty.
6. **Timers.** Every enabled, valid group that is not paused has its own repeating timer on the
   Bukkit scheduler: its first announcement comes `interval × 20` ticks after the group was
   started, then one every `interval × 20` ticks. Pausing stores the exact ticks remaining until
   the next announcement; resume uses that remainder once, then returns to the full interval.
   Changing the interval starts a full interval at the new rate. Enable and reload start a full
   interval. Disabled groups (`enabled: false`) never announce by themselves. Pausing or
   resuming one group must not cancel, reschedule or advance another group's timer or position.
7. **Order.** A `sequential` group announces its messages in list order and starts over after
   the last one. A `shuffle` group announces in cycles of `count` announcements; each cycle is a
   random order in which every message appears exactly once.
8. **Position.** Each group remembers which message comes next. The position goes back to the
   start of a new cycle on enable, on reload, and when `add` or `remove` changes the group's
   messages. Pausing, resuming and changing the interval keep it. `/crier now` announces the
   next message exactly like the timer does and moves the position on.
9. **Pause state** is kept in memory only; a reload resumes every group.

## Commands

10. One command, `/crier`, with case-insensitive subcommands, all needing the permission
    `towncrier.admin` (register it in `plugin.yml` with default `op`; also register
    `towncrier.staff` with default `op`). Validation order: an unknown subcommand, or none,
    gets the general usage line; a wrong number of arguments gets the subcommand's usage line;
    then the permission is checked (`You do not have permission to do that.`); then the group
    (`Unknown group: <argument>`); then the other arguments. The first failure is the only
    reply.

    | Subcommand | Reply |
    | --- | --- |
    | `list` | `Groups:` then one line per valid group, sorted by name: `<name>: <count> messages every <interval>s, <order>, <state>` with state `running`, `paused` or `disabled`; with no valid group `No groups.` |
    | `now <group>` | announces the group's next message (any state) and replies `Announced <group> #<index>.` |
    | `pause <group>` | `Paused <group>.`, or `<group> is already paused.`, or `<group> is disabled.` |
    | `resume <group>` | `Resumed <group>.` (the timer restarts), or `<group> is not paused.`, or `<group> is disabled.` |
    | `add <group> <text…>` | appends the words joined by single spaces as a new message: `Added message #<n> to <group>.` |
    | `remove <group> <index>` | `Removed message #<index> from <group>.`; an index that is not a whole number from 1 to the count gets `Invalid index: <argument>`; removing the only message gets `Cannot remove the last message of <group>.` |
    | `interval <group> <seconds>` | `Interval of <group> set to <seconds>s.`; anything but a whole number of at least 1 gets `Invalid interval: <argument>` |
    | `preview <group> <index>` | sends the rendered announcement of that message to the sender only, as the only reply; a bad index gets `Invalid index: <argument>` |
    | `reload` | see requirement 12 |

    `add` takes one or more words after the group; the others take exactly the arguments shown.
    The usage lines are:

    ```text
    Usage: /crier <list|now|pause|resume|add|remove|interval|preview|reload>
    Usage: /crier list
    Usage: /crier now <group>
    Usage: /crier pause <group>
    Usage: /crier resume <group>
    Usage: /crier add <group> <text...>
    Usage: /crier remove <group> <index>
    Usage: /crier interval <group> <seconds>
    Usage: /crier preview <group> <index>
    Usage: /crier reload
    ```

11. **Saving.** `add`, `remove` and `interval` rewrite `announcements.yml` with the change
    applied and everything else (the prefix, the other groups and their keys) kept.
12. **Reload** cancels every timer, re-reads `announcements.yml`, clears every pause, restarts the
    groups and replies `Loaded <valid> groups (<disabled> disabled, <invalid> invalid).`
    (`<valid>` counts every valid group, disabled ones included), followed by one line per
    invalid group in file order: `Skipped <name>: <reason>.` A reload never leaves an old timer
    running.

The hidden cases run against the real server and cover the default file, the command and
permission declarations, rendering and placeholders, the exact moments and order of timed
announcements, pause/resume while another group's timer and message position continue,
permission-gated delivery, disabled and shuffled groups, `now`, pause and resume, repeated reloads,
invalid groups, editing and saving the file,
unknown groups, permission checks with limited senders and the usage lines.
