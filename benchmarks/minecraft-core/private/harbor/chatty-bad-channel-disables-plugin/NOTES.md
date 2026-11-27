# Maintenance notes: chatty-bad-channel-disables-plugin

## Upstream

- Repository: https://github.com/Brikster/Chatty, branch `v3` (MIT, `LICENSE`
  kept in the starter: "MIT License / Copyright (c) 2018 Ilya Andreev").
- Base commit: `7ca46993b66212ba582a10f350674922ed84486c` (parent of the fix).
- Fix: commit `ae832809657a1d287ec8839029c01399e47888c5` "Do not let one bad
  notification channel disable the plugin" (2026-08-10). No separate issue; the
  commit message is the maintainer's reproduction.
- The starter is `git archive` of the base commit without `.github/` and
  `scripts/` (smoke-test JavaScript and a v2 fixture that do not take part in
  the build). `docs/` does not exist upstream.

## Defect

`ConfigsLoader` is member-injected by Guice from `Chatty.initialize()`; its
`@Inject` methods construct every chat and notification channel. The
`ActionbarNotification` constructor checks `stay <= period` with
`Preconditions.checkArgument`, so an action bar channel whose `stay` exceeds
its `period` throws `IllegalArgumentException` inside `injector.injectMembers`,
which Guice wraps in a `ProvisionException`. `onEnable` is `@SneakyThrows`, so
the plugin fails to enable (Paper disables it), and `/chatty reload` has
already run `closeResources()` before `initialize()` throws, so the reload
answers `Error while reloading plugin: ProvisionException` and leaves no
working configuration behind. Channels after the bad one in the same section
are never built because the `forEach` is aborted. The trace names neither the
file nor the channel. `period`/`stay` themselves are `@Positive`-validated by
okaeri at config load, so a negative or zero number fails earlier and
differently; the number the fix handles is `stay > period`.

## Reference fix

`solution/after/spigot/src/main/java/ru/brikster/chatty/guice/ConfigsLoader.java`
carries the upstream main-source change only: each title, chat and action bar
channel is built through `addChannel(ticker, logger, type, id, supplier)`, which
catches `Throwable`, logs `Skipping the "<id>" <type> notification from
notifications.yml: <reason>` at `WARNING` through a Guice-injected
`java.util.logging.Logger`, and carries on with the next channel. The upstream
commit also added `spigot/src/test/java/.../convert/SupportedFormatsTest.java`,
which is unrelated to the fix (it pins MiniMessage syntax support); the base
tests stay frozen and pass with and without the fix (checked: 138/138 offline).

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

Two harness/plugin adjustments are needed for this multi-module layout:

1. `harness/verify.py` discovers JUnit reports with recursive globs
   (`**/build/test-results/**/*.xml`, `**/target/surefire-reports/*.xml`)
   instead of root-only ones. Without it the 138 unit cases are "missing"
   and every run is incomplete. The patch is in the scratch pack's harness copy
   and in `REPORT.md`.
2. `rhenium_minecraft.catalog._validate_task` looks for
   `plugin.yml` at `<starter>/src/main/resources/`; Chatty's is at
   `<starter>/spigot/src/main/resources/plugin.yml`. The lookup must also try
   `<module>/src/main/resources` (or every `*/src/main/resources`). Until that
   lands, `MinecraftCatalog.load` rejects the pack with "starter lacks
   src/main/resources/plugin.yml"; the rest of the validation passes with that
   lookup patched (see `REPORT.md`).

## Why the repository matters

The exam gives only the operator's view: a `notifications.yml` typo stops the
plugin from enabling, `/chatty reload` fails with a `ProvisionException` that
names neither file nor channel, and the plugin is dead afterwards. The solver has
to follow that failure from `/chatty reload` through `Chatty.initialize()` and
`injector.injectMembers(new ConfigsLoader())` to the constructor that rejects the
number, see that `closeResources()` has already torn the old configuration down
when the injection throws (listeners unregistered, ticker cancelled), and decide
where a per-channel failure can be contained without skipping the channels after
it or aborting the other sections. Plausible shallow repairs and what stops them:

- a catch around the whole `injectMembers` call keeps the plugin alive but drops
  every channel after the bad one and names nothing (`reload survives ...`,
  `skipped channel ...`, `every offending channel ...`);
- a catch around a section's `forEach` loses the rest of that section;
- clamping `stay` to `period` registers the offending channel instead of
  skipping it;
- logging only the exception message never names the channel.

## Live-server design

No player is needed. The harness offers no way to start the server with a broken
file and still grade (a plugin that fails to enable makes the live layer
incomplete), so every configuration under test is written by the suite into
`plugin.getDataFolder()/notifications.yml` and picked up through `/chatty reload`
from a `GcbSenders.recording()` console sender (the maintainer's own
reproduction). `/chatty reload` runs the same `initialize()` as `onEnable`.

- A `PluginManager.disablePlugin` + `enablePlugin` cycle was tried for the
  start-up symptom and rejected: Paper 1.21.11 closes the plugin's jar
  classloader on disable, so `enablePlugin` fails for every submission with a
  "zip file closed" error.

Registered channels are read through the plugin's own objects: the private
`Chatty.injector` field (found by its relocated `Injector` type), then
`Injector.getInstance(NotificationTicker.class)` and the ticker's notification
collection, taking each `Notification`'s `name` field; progress is the `tick`
counter inherited from `Notification` (a chat channel with a 600 s period is used
because an action bar channel's own counter resets every second). Listeners are
read from the `HandlerList`s of Paper's `AsyncChatEvent`, `AsyncPlayerChatEvent`
and `PlayerJoinEvent`, filtered to Chatty. Console warnings are captured with a
`java.util.logging.Handler` on the root, server and plugin loggers and formatted
with `SimpleFormatter.formatMessage` so `{0}` parameters are substituted.

Cases: `plugin is enabled` (sentinel); preserved, in order: `default configuration
reloads cleanly` (file removed, defaults regenerated, `donate` and three `default`
channels registered), `valid notifications.yml loads every channel` (includes
`stay == period`, which catches an off-by-one "fix"), `chats stay registered after
a reload` (public `ChattyApi`), `info command answers from the console`,
`notifications tick after a clean reload` (ticked, 80-tick wait); targets, after
every preserved case because on the starter they leave the plugin without a
working configuration: `reload survives an action bar channel whose stay exceeds
its period` (success message, `gcb_healthy` after `gcb_broken` registered,
`gcb_broken` not, three `default` channels), `skipped channel is reported by name`,
`every offending channel is skipped and reported` (offending channels first and
last in the list, both named, the channel between them registered), `chat keeps
being handled after a reload with an offending channel` (chat and join listeners,
shipped chats), `notifications keep ticking after a reload with an offending
channel` (ticked).

## Merge review (0.2.0)

Considered and left out: the toast fixes `22af1f9` and `9316fb8` two and one commits before the base (advancement layout of the toast feature added in `6a576dc`; a different defect family, and the intermediate `7ca4699` also refactors main sources), and the next commits `c632a31` (CMI colour codes, a feature) and `3c62096`, which is the fix of `chatty-reload-ignores-chat-commands`. The task keeps `ae83280` alone.
