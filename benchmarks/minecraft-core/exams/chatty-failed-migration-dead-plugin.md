# Chatty: a failed v2 configuration migration leaves an enabled but dead plugin

## Context

`plugin/` is the Chatty chat-management plugin (MIT) at an upstream commit. It
is a Gradle multi-module build: `api/` holds the public `ru.brikster.chatty.api`
types and `spigot/` the plugin itself (`spigot/src/main/resources/plugin.yml`,
`name: Chatty`). The shaded plugin jar is `build/libs/Chatty-3.0.0-SNAPSHOT.jar`,
produced by `./gradlew shadowJar`; the upstream JUnit tests run with
`./gradlew test`.

Chatty 3 keeps its configuration in several YAML files under `plugins/Chatty/`
(`settings.yml`, `chats.yml`, `moderation.yml`, `pm.yml`, ...). Chatty 2 used a
single `plugins/Chatty/config.yml`. When the plugin enables and finds that
legacy file, it moves the whole data folder aside to a sibling folder
`Chatty_old_<timestamp>`, generates the v3 files with their defaults, migrates
the legacy values into them (`MIGRATION.md` in the repository describes the
mapping), lists anything the owner should review in the console, and switches to
the migrated configuration. `/chatty reload` re-reads the v3 files and answers
`Plugin successfully reloaded!`.

v3 validates some values that v2 accepted: in `moderation.yml`, `caps.length`
must be at least `1` and `caps.percent` between `0` and `100`. The advertisement
patterns in `moderation.yml` are regular expressions.

## Symptom

Put a v2 `config.yml` whose `moderation.advertisement.patterns.ip` value is not
a valid regular expression (for example an unclosed character class) into an
otherwise empty `plugins/Chatty/` and start the server:

```text
[WARN]: [Chatty] Found legacy "config.yml" file in plugin directory. "Chatty" folder was renamed to "Chatty_old_1790057011580".
[INFO]: [Chatty] Migrating legacy Chatty v2 configuration...
[INFO]: [Chatty] Legacy configuration migrated. Please review the following:
...
[ERROR]: [Chatty] Failed to migrate legacy configuration — using defaults
ru.brikster.chatty.shaded.com.google.inject.CreationException: Unable to create injector, see the following errors:
...
Caused by: java.util.regex.PatternSyntaxException: Unclosed character class near index 21
[INFO]: Done (17.459s)! For help, type "help"
```

The server comes up and `plugins` lists Chatty as enabled, but the message
"using defaults" is not true. The plugin formats no chat and reacts to no player
joining, its notifications never run, and `plugins/Chatty/` still contains the
half-migrated v3 files with the broken pattern, so every `/chatty reload` fails
again:

```text
> chatty reload
[ERROR]: [Chatty] Error while reloading Chatty
ru.brikster.chatty.shaded.com.google.inject.CreationException: Unable to create injector, see the following errors:
...
Error while reloading plugin: CreationException. See console for more details.
```

Only `/chatty` (the info line) still answers. The operator is left with an
"enabled" plugin that processes nothing and cannot be reloaded, and is not told
where the v2 file went or what to do. Separately, v2 caps limits that v3 does not
accept (a length of `0`, a percent above `100`) are copied into the migrated
`moderation.yml` unchanged.

## Task

Repair the plugin so that a v2 configuration whose migration fails does not
leave a dead plugin behind:

- When the migrated configuration cannot be loaded, the half-migrated v3 files
  are moved out of `plugins/Chatty/` into a sibling folder named
  `Chatty_failed_migration_<timestamp>` (next to `Chatty_old_<timestamp>`), and
  the plugin starts again so that `plugins/Chatty/` holds a freshly generated
  default configuration (including `moderation.yml`).
- After that recovery the plugin is fully working on the running server: its
  listeners for `AsyncPlayerChatEvent` and `PlayerJoinEvent` are registered
  (visible through the events' `HandlerList`s as listeners owned by Chatty),
  `ChattyApi.instance().getChats()` contains the shipped `local` and `global`
  chats, and `/chatty reload` succeeds (it answers `Plugin successfully
  reloaded!` and does not report an error) and leaves those listeners
  registered.
- The failure is reported through the plugin logger at WARNING or SEVERE level:
  one message names the `Chatty_old_<timestamp>` backup folder and tells the
  operator to fix the reported problem, move its `config.yml` back and restart;
  one message names the quarantine folder the half-migrated files were moved to;
  and one message says the plugin started with a default configuration instead
  (it must contain the phrase `started with a default configuration`). A
  teardown or clean-up step that fails while recovering must not stop the
  recovery.
- The migration writes caps limits that v3 accepts: a v2 `caps.length` below `1`
  becomes `1` and a v2 `caps.percent` outside `0`..`100` becomes the nearest
  bound, in the migrated `moderation.yml` (in the quarantine folder when the
  migration fails), and each adjusted value is listed in the migration notes in
  the console by its name (`caps.length`, `caps.percent`).
- Everything else stays as it is: the legacy folder is still moved aside to
  `Chatty_old_<timestamp>` and keeps its `config.yml` exactly as the owner wrote
  it (no `config.yml` is left in `plugins/Chatty/`), a v2 configuration that
  migrates cleanly still takes effect, `/chatty` still answers a console sender,
  and the rest of the plugin's behaviour is unchanged.

Keep the change inside `plugin/spigot/src/main/java` (you may also touch
`plugin/api/src/main/java` if you need to). The build files (`build.gradle`,
`settings.gradle`, `api/build.gradle`, `spigot/build.gradle`), the Gradle
wrapper and the existing tests under `plugin/spigot/src/test` are frozen: the
verifier restores them from the starter before building, and every existing
upstream test must keep passing.

## Evaluation

The verifier builds the plugin offline with the repository's Gradle wrapper
(`shadowJar`), runs the upstream JUnit suite (`test`), and then loads the built
jar into a real Paper 1.21.11 dedicated server without players. Before the
server starts, `plugins/Chatty/config.yml` is a v2 configuration whose
advertisement ip pattern is an invalid regular expression and whose caps limits
are `length: 0` and `percent: 150`, so the migration fails while the plugin
enables. The grader then inspects the folders next to the plugin's data folder
and their contents, the server's `logs/latest.log`, the `HandlerList`s of
`AsyncPlayerChatEvent` and `PlayerJoinEvent`, `ChattyApi.instance().getChats()`,
and dispatches `/chatty` and `/chatty reload` from a console sender, checking the
replies.
