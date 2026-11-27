# Harbor workspace

Complete this task in `/app/plugin`; the repository's build files, dependency declarations and upstream tests are frozen and restored by the verifier.

# Chatty: `chatty reload` ignores chat commands added, renamed or removed in `chats.yml`

## Context

`plugin/` is the Chatty chat-management plugin (MIT) at an upstream commit. It
is a Gradle multi-module build: `api/` holds the public `ru.brikster.chatty.api`
types and `spigot/` the plugin itself (`spigot/src/main/resources/plugin.yml`,
`name: Chatty`). The shaded plugin jar is `build/libs/Chatty-3.0.0-SNAPSHOT.jar`,
produced by `./gradlew shadowJar`; the upstream JUnit tests run with
`./gradlew test`.

Chatty keeps its configuration in several YAML files under `plugins/Chatty/`.
`chats.yml` declares the chats; every chat may carry a `command:` (plus
`aliases:`) so that players can write into that chat with
`/<command> <message>` or switch to it with `/<command>`. Such a command is a
server command owned by Chatty: `Bukkit.getCommandMap().getCommand("<command>")`
returns a `PluginIdentifiableCommand` whose plugin is Chatty. Chat commands are
player-only: a console sender that runs one gets the plugin's reply that the
command must be executed by a player. `/chatty reload` re-reads every
configuration file and answers `Plugin successfully reloaded!`; the chat
registry (`ChattyApi.instance().getChats()`) then lists the chats of the edited
file.

## Symptom

Start the server with a `chats.yml` in which the `local` chat declares
`command: gcblocal` with alias `gcbl` and the `global` chat declares
`command: gcbglobal`. Both commands work. Now edit the file while the server is
running: add a third chat with `command: gcbadd`, rename the `global` command
to `gcbworld`, and run `/chatty reload` from the console. The reload answers
`Plugin successfully reloaded!` and the chat registry does list the new chat,
but the commands are unchanged:

```text
> gcbadd hello
Unknown or incomplete command. See below for error
gcbadd hello<--[HERE]
> gcbworld hello
Unknown or incomplete command. See below for error
gcbworld hello<--[HERE]
> gcbglobal hello
TerminalConsoleCommandSender is not allowed to execute that command. Must be of type Player
```

The added command is unknown and the renamed command still answers only to its
old name. Removing a chat (or its `command:`) from the file and reloading leaves
its command registered as well. Only a full server restart picks up the edited
commands. Chat commands that are present when the server starts do work and keep
working after a reload whose `chats.yml` did not change.

## Task

Repair the plugin so that `/chatty reload` applies the chat commands declared
in `chats.yml`:

- A chat command added to `chats.yml` is registered after the reload, aliases
  included: the command map returns a command owned by Chatty for the name and
  for each alias, and dispatching `/<name> <message>` is handled by the plugin's
  chat command (a console sender receives the usual player-only reply rather
  than "Unknown command").
- When a chat's command is renamed, the new name is registered as above and the
  old name is no longer registered:
  `Bukkit.getCommandMap().getCommand("<old>")` returns `null` after the reload.
- When a chat is removed from `chats.yml`, its command name is no longer
  registered after the reload (`getCommand` returns `null` and dispatching it
  finds no command). Removal and renaming are checked by the command's name;
  whether a dropped alias disappears is not evaluated.
- Chat commands declared at start-up keep working exactly as before, aliases
  included; a reload whose `chats.yml` did not change leaves them registered and
  working, and commands that an edit does not touch stay registered and working.
- The chat registry, `/chatty`, `/chatty reload` (including its success
  message) and the rest of the plugin behave exactly as before.

Keep the change inside `plugin/spigot/src/main/java` (you may also touch
`plugin/api/src/main/java` if you need to). The build files (`build.gradle`,
`settings.gradle`, `api/build.gradle`, `spigot/build.gradle`), the Gradle
wrapper and the existing tests under `plugin/spigot/src/test` are frozen: the
verifier restores them from the starter before building, and every existing
upstream test must keep passing.

## Evaluation

The verifier builds the plugin offline with the repository's Gradle wrapper
(`shadowJar`), runs the upstream JUnit suite (`test`), and then loads the built
jar into a real Paper 1.21.11 dedicated server without players. The server
starts with a `plugins/Chatty/chats.yml` whose `local` and `global` chats and a
third chat declare chat commands. The grader checks those commands in the
command map and dispatches them from a console sender, runs `/chatty reload`
with the file unchanged, then rewrites `chats.yml` in the plugin's data folder
to add a chat with a new command, in a later step to rename an existing command
and finally to remove a chat that was declared at start-up, runs
`/chatty reload` after each edit, and inspects
`Bukkit.getCommandMap()`, the console sender's replies and
`ChattyApi.instance().getChats()`.
