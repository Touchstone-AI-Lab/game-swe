# Maintenance notes: chatty-reload-ignores-chat-commands

## Upstream

- Repository: https://github.com/Brikster/Chatty, branch `v3` (MIT, `LICENSE`
  kept in the starter: "MIT License / Copyright (c) 2018 Ilya Andreev").
- Base commit: `c632a311cd8db35a1a3d39546a154d7c9091b331` (parent of the fix,
  "Accept CMI's colour codes").
- Fix: commit `3c62096c75e19cf9f385d4a30d956d4a9f2bcc10` "Pick up chat commands
  on a reload" (2026-08-10). No separate issue; the commit message records the
  maintainer's live-server verification (clean start, reload with no changes,
  rename, adding a command to a second chat).
- The starter is `git archive` of the base commit without `.github/` and
  `scripts/` (smoke-test JavaScript and a v2 fixture that do not take part in
  the build). `docs/` does not exist upstream.

## Defect

`Chatty.onEnable()` runs `initialize()`, then `registerChattyCommand()` (which
creates the sync `BukkitCommandManager`) and finally `registerChatCommands()`,
which walks `ChatRegistry.getChats()` once and registers `/<command>` (with
aliases) for every chat whose `chats.yml` entry has a `command:`. `/chatty
reload` calls `closeResources()` + `initialize()` only: the injector, the
configs and the chat registry are rebuilt, but the command manager is never
told about the new registry. An added command therefore stays unknown to
Bukkit's command map, a renamed command keeps its old name, and the handler
lambdas captured at start-up keep the `ChatCommandHandler` (and its
`ChatRegistry`) of the injector that the reload threw away. The `command:`
field ships empty, so a user who fills it in and reloads reads the feature as
missing.

## Reference fix

`solution/after/spigot/src/main/java/ru/brikster/chatty/Chatty.java` carries
the upstream main-source change only (the fix touches no tests). It keeps a
`chatCommandRoots` map of registered command name to aliases, registers the
`ChatCommandHandler` through the existing proxying-handler map under `"chat"`
(so the lambda no longer points at a stale injector), calls
`registerChatCommands()` from `initialize()` whenever the sync command manager
already exists (start-up still calls it explicitly after the manager is
created), and on each pass diffs the wanted registrations against the map:
entries whose aliases changed or that disappeared are removed with
`deleteRootCommand` (logged `Unregistered chat command /<name>`), missing ones
are registered, matching ones are left alone. Leaving matching registrations
alone is deliberate: cloud 1.8.4's `BukkitPluginRegistrationHandler` refuses an
alias that already sits in the command map and `unregisterRootCommand` removes
only `<name>` and `chatty:<name>` from `knownCommands`, not the aliases, so a
blanket delete-and-re-register would silently lose aliases. The base tests pass
with and without the fix (161/161 offline).

Known limitation of the reference (not asserted): `chatCommandRoots` is not
cleared in `onDisable`, so a plugin-manager disable/enable cycle would skip
re-registration. Paper 1.21.11 closes the plugin class loader on disable, so
such a cycle cannot be exercised on the live server anyway.

## Build

Gradle 8.8 wrapper, modules `api` and `spigot`, JDK 21 toolchain
(`org.gradle.java.installations.auto-download=false` is satisfied by the
image's JDK), `sourceCompatibility` 11, `compileOnly spigot-api 1.19-R0.1`.
The plugin jar is `spigot:shadowJar`, written to the root
`build/libs/Chatty-3.0.0-SNAPSHOT.jar`; `shadowJar` also resolves the dedicated
`sqliteDriver` configuration (embedded as `sqlite-jdbc.jardata`), so the
warm-up must run `shadowJar`, not `assemble`. Tests are JUnit 5 + Mockito
(no MockBukkit); reports land in `spigot/build/test-results/test/`.

Frozen paths are declared explicitly in the catalog (`build.frozen_paths`)
because the defaults are root-only: `api/build.gradle`, `spigot/build.gradle`,
`api/src/test`, `spigot/src/test` are added; `api/src/test` and
`gradle.properties` do not exist upstream and restore as "nothing".

Harness requirements for this task (all in the scratch pack's harness copy,
listed in `REPORT.md`):

1. `harness/verify.py` discovers JUnit reports with recursive globs
   (`**/build/test-results/**/*.xml`); already applied to the repository
   working tree for the sibling Chatty task.
2. `harness/verify.py` copies `tests/seed/<PluginName>/...` into the server's
   `plugins/` directory before the server starts (`seed_plugin_data`), and
   `scripts/materialize.py` emits `COPY seed /tests/seed` when `tests/seed`
   exists. This task ships `tests/seed/Chatty/chats.yml` so that chat commands
   exist at start-up (the shipped `chats.yml` declares none).
3. `rhenium_minecraft.catalog._validate_task` looks for `plugin.yml` at
   `<starter>/src/main/resources/`; Chatty's is at
   `<starter>/spigot/src/main/resources/plugin.yml` (same as the sibling task).

## Why the repository matters

The fix needs the solver to trace the two lifecycles (`onEnable` and `/chatty
reload`) through `initialize()`, notice that the sync command manager is
created after the first `initialize()` and survives reloads while the injector
does not, and reconcile Bukkit-level registrations with the rebuilt registry
without re-registering what did not change (which drops aliases in this
version of cloud) and without leaving the handler bound to the discarded
injector. Registering only what is new leaves renamed commands answering to
their old name; moving the registration into `initialize()` without keeping
the start-up call loses the commands present at start-up.

## Live-server design

No player is needed. The server starts with `tests/seed/Chatty/chats.yml`
(`local` → `/gcblocal` alias `gcbl`, `global` → `/gcbglobal`, and since 0.2.0
`gcbstaff` → `/gcbstaff`), so the
start-up registration path runs on the real enable. Later configurations are
written by the suite into `plugin.getDataFolder()/chats.yml` and picked up
through `/chatty reload` dispatched from a `GcbSenders.recording()` console
sender (the maintainer's own reproduction). Registration is observed through
`Bukkit.getCommandMap().getCommand(name)` (must be a
`PluginIdentifiableCommand` owned by Chatty) and by dispatching
`/<name> gcb message` from the recording sender: a chat command is
player-only, so a handled dispatch returns `true` and answers the sender (on
Paper 1.21.11 the reply is cloud's `... is not allowed to execute that command.
Must be of type Player`); an unregistered name makes `GcbCommands.dispatch`
return `false` with no reply.

Cases, in order: `plugin is enabled` (sentinel); `chat commands declared at
startup are registered` (preserved: `gcblocal`, `gcbl`, `gcbglobal`); `chat
commands survive a reload with an unchanged configuration` (preserved: reload
without touching the file); `chat command added in chats.yml is registered by
chatty reload` (target: chat `gcbadded` → `/gcbadd` alias `gcba`); `chat
registry lists the chat added in chats.yml` (preserved: `ChattyApi` shows
`gcbadded` with command `gcbadd`); `renamed chat command drops its old name
after chatty reload` (target: `global` → `/gcbworld`, `gcbglobal` must be
`null` in the command map, `gcblocal` untouched). The suite never asserts on
aliases of a renamed command because cloud 1.8.4 cannot take them back out of
the command map.

0.2.0 adds `removed chat command is unregistered by chatty reload` (target, last):
the suite rewrites `chats.yml` without the `gcbstaff` chat that was declared at
start-up and reloads; `/gcbstaff` must be `null` in the command map and no longer
dispatch, while `/gcblocal`, its alias and the renamed `/gcbworld` keep working.
On the starter the start-up registration is never revisited, so `/gcbstaff`
stays registered. A repair that only registers what is new (the target-negative)
fails this case and the rename case; the upstream reconciliation deletes both.
The case removes a chat declared at start-up rather than the chat added in case
3, because on the starter the added command was never registered and its absence
would prove nothing.

The 0.2.0 exam no longer names `Chatty.java`, the cloud command manager or the
`initialize()` path; it describes the edits, the reload and the commands the
server answers to. The solver has to find that chat commands are registered once
from `onEnable`, that `/chatty reload` rebuilds the injector and the chat registry
but never revisits the command map, and how to reconcile registrations without
re-registering unchanged ones (cloud 1.8.4 refuses an alias that is already in
the command map and `deleteRootCommand` leaves aliases behind).

## Merge review (0.2.0)

Considered and left out: the commit two before the fix, `ae83280`, is the fix of `chatty-bad-channel-disables-plugin`, so moving the base earlier would make two tasks share a defect; `c632a31` and the commits after the fix (`7b30403`, `087e964`) are features. `c3df433` ("Clear command state on disable so a re-enable registers again") is related but two days earlier, not adjacent, and needs a disable/enable cycle that Paper 1.21.11 cannot perform on a live server.
