# Maintenance notes: chatty-failed-migration-dead-plugin

## Upstream

- Repository: https://github.com/Brikster/Chatty, branch `v3` (MIT, `LICENSE`
  kept in the starter: "MIT License / Copyright (c) 2018 Ilya Andreev").
- Base commit: `b620b36c62fabfaebfbe22a7e305108e77355629` (parent of the fix,
  "Migrate the v2 locale to a v3 language").
- Fix: commit `4072f98bebeb66c2232a7fcb2c0de2af05f35b9f` "Stop a failed v2
  migration from leaving a dead plugin behind" (2026-08-08). No separate
  issue; the commit message records the maintainer's reproduction on a real
  Paper server (an invalid regex in the v2 advertisement ip pattern) and notes
  that disabling the plugin from inside `onEnable` crashed the server in
  `initPostWorld`, which is why the fix recovers instead of disabling.
- The starter is `git archive` of the base commit without `.github/` and
  `scripts/` (smoke-test JavaScript and a v2 fixture that do not take part in
  the build). `docs/` does not exist upstream.

## Defect

`Chatty.onEnable()` detects a legacy `config.yml`, renames the data folder to
`Chatty_old_<ts>`, reads the v2 map, calls `initialize()` (defaults), then
`V2ConfigMigrator.migrate()` overwrites the migrated keys in the generated v3
files, `closeResources()` tears the running configuration down (listeners
unregistered, ticker cancelled, SQLite pool closed) and `initialize()` runs
again. When the second `initialize()` throws — `ModerationConfig` compiles the
advertisement patterns into `java.util.regex.Pattern` while okaeri loads
`moderation.yml`, so the invalid regex surfaces as a Guice
`CreationException` from `Guice.createInjector` — the `catch (Throwable)`
only logs "Failed to migrate legacy configuration — using defaults" and
`registerChattyCommand()` runs. Nothing is rebuilt: the `injector` field
still points at the closed first injector, no listener is registered, the
ticker is cancelled, and `plugins/Chatty` keeps the half-migrated files. The
plugin reports enabled, handles no event, and every `/chatty reload` fails on
the same files. The migrator also copied `caps.length`/`caps.percent`
verbatim, which v3's validation annotations would reject.

## Reference fix

`solution/after/` carries the upstream main-source change only (the upstream
commit also added a migrator unit test, which is not in the frozen set; the
54 base tests pass with and without the fix). `Chatty.java`: the failed
`Files.move` of the data folder is reported and the plugin disabled instead
of throwing through `@SneakyThrows`; the migration catch logs a SEVERE message
naming `Chatty_old_<ts>` with the instruction to fix, move `config.yml` back
and restart, then `startWithDefaultConfiguration()` closes resources
(ignoring errors), moves the data folder to
`Chatty_failed_migration_<ts>` (WARNING naming it), calls `initialize()`
again and logs "Chatty started with a default configuration instead."; if
even that fails, a SEVERE message says the plugin is loaded but will not
process chat. `closeResources()` and `unregisterAllCommands()` become
null-safe so `onDisable` works after a partial start. `V2ConfigMigrator`:
`copyClampedInt` clamps `caps.length` to `>= 1` and `caps.percent` to
`0..100` and adds a migration note. Since 0.2.0 the clamp is graded: the seed
carries `length: 0` and `percent: 150`, and the migrated `moderation.yml` (in the
quarantine folder) must hold `1` and `100`, with both names in the migration notes.
The base loader accepts the out-of-range values at load time (checked on the real
server in 0.1.0), so the clamp is only visible in the migrated file and the notes,
not as a load failure.

## Build

Gradle 8.8 wrapper, modules `api` and `spigot`, JDK 21 toolchain
(`org.gradle.java.installations.auto-download=false` is satisfied by the
image's JDK), `sourceCompatibility` 11, `compileOnly spigot-api 1.19-R0.1`.
The plugin jar is `spigot:shadowJar`, written to the root
`build/libs/Chatty-3.0.0-SNAPSHOT.jar`; `shadowJar` also resolves the
dedicated `sqliteDriver` configuration (embedded as `sqlite-jdbc.jardata`), so
the warm-up must run `shadowJar`, not `assemble`. Tests are JUnit 5 + Mockito
(no MockBukkit); reports land in `spigot/build/test-results/test/` and are
collected by the verifier's recursive JUnit glob.

Frozen paths are declared explicitly in the catalog (`build.frozen_paths`)
because the defaults are root-only: `api/build.gradle`, `spigot/build.gradle`,
`api/src/test`, `spigot/src/test` are added; `api/src/test` and
`gradle.properties` do not exist upstream and restore as "nothing".

Harness requirements: the verifier's `tests/seed/<PluginName>/...` support
(`seed_plugin_data` in `harness/verify.py`, `COPY seed /tests/seed` emitted
by `scripts/materialize.py`). This task ships `tests/seed/Chatty/config.yml`,
the failing v2 configuration, so the migration runs on the real enable.

## Why the repository matters

The solver has to follow the enable-time lifecycle through two `initialize()`
calls, notice that `closeResources()` has already run when the second one
throws (so "using defaults" is a lie: the first configuration is gone), work
out that the half-migrated files must be taken out of the data folder before
`initialize()` can regenerate defaults, keep the v2 backup untouched so the
operator can retry, and make the teardown tolerant of a partially built state.
Wiping the broken output instead of quarantining it loses what the operator
needs to diagnose; retrying `initialize()` on the same folder fails the same
way; disabling the plugin from `onEnable` crashes Paper's `initPostWorld`
(documented upstream); tidying the backup folder away breaks the documented
retry path.

## Live-server design

No player is needed. The server starts with `tests/seed/Chatty/config.yml`
(v2, invalid ip regex) already in `plugins/Chatty`, so the failing migration
happens on the real `onEnable`; every case then observes the resulting state
without any disable/enable cycle (Paper closes the plugin classloader on
disable). Observations: sibling folders of `plugin.getDataFolder()` matched
by prefix (`Chatty_old_`, `Chatty_failed_migration_`) and their files; the
server's own `logs/latest.log` (Paper's file appender flushes each record,
and the enable-time lines are written seconds before the first case);
`AsyncPlayerChatEvent.getHandlerList()` / `PlayerJoinEvent.getHandlerList()`
filtered to listeners whose plugin is Chatty; `ChattyApi.instance().getChats()`;
`/chatty` and `/chatty reload` dispatched from a `GcbSenders.recording()`
console sender (Chatty uses the native Adventure platform on Paper, so the
recording proxy sees the replies).

Cases, in order: `plugin is enabled` (sentinel: enabled, `/chatty` owned by
Chatty in the command map); `legacy configuration is moved aside before
migrating` (preserved: exactly one `Chatty_old_*` sibling holding the seeded
`config.yml`, none left in the data folder — holds on the starter); `info
command answers from the console` (preserved: `/chatty` summary — holds on the
starter because the info handler only needs the stale injector's audience
provider); `chat pipeline is live after a failed migration` (target: Chatty
listeners on `AsyncPlayerChatEvent` and `PlayerJoinEvent` — none on the
starter after `closeResources()`); `failed migration is quarantined and
reported` (target: exactly one `Chatty_failed_migration_*` sibling containing
`moderation.yml`, a regenerated `plugins/Chatty/moderation.yml`, and WARN/ERROR
log lines naming the backup folder, the quarantine folder and the phrase
`started with a default configuration` — the starter has no quarantine
folder); `chatty reload works after a failed migration` (target: success
reply, no error reply, `local`/`global` in the registry, listeners still
registered — the starter answers `Error while reloading plugin:
CreationException`). The target cases run last; the reload is the only
mutation and comes at the very end. Only one seed exists per task image, so
the valid-v2 migration path is not exercised on the live server; it stays
covered by the frozen `V2ConfigMigratorTest` unit cases.

## 0.2.0 changes

The exam no longer walks through `onEnable` (folder rename, the two
`initialize()` calls, `closeResources()` in between); it shows the console and
states the recovery contract. The seed adds out-of-range caps limits, the
preserved backup case also checks that the backup `config.yml` keeps them as
written (a repair that clamps the owner's file in place fails it), and the new
target `migrated caps limits are clamped to the v3 range` (order 5, before the
reload) reads the quarantined `moderation.yml` with Bukkit's `YamlConfiguration`
and the server log for the two setting names. A repair that quarantines and
restarts correctly but leaves `copyInt` alone fails only that target.

## Merge review (0.2.0)

Considered and left out: the previous commit `b620b36` is merged into `chatty-v2-migration-null-spy-format` (whose reference ends at this task's base), and the next commit `18a9094` (a `$` in a moderation replacement cancels every chat message) can only be reproduced with a player's chat event, which the authoring rules exclude for targets. The caps clamp, part of `4072f98` itself, is graded since 0.2.0.
