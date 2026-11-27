# Maintenance notes: chatty-reload-leaks-threads

## Upstream

- Repository: https://github.com/Brikster/Chatty, branch `v3` (MIT, `LICENSE`
  kept in the starter: "MIT License / Copyright (c) 2018 Ilya Andreev", blob
  `c65e21c6` at the base).
- Base commit: `f98b81914293a3d48bb1b759e6c9e7d937164d4e` (parent of the fix).
- Fix: commit `c7ba4171e034bd2c200e1b9cf4aa1d61ea9883d3` "Release what
  /chatty reload used to abandon" (2026-08-08). No separate issue; the commit
  message carries the maintainer's `jstack` measurement (plugin-owned threads
  4 -> 6 across three reloads before, flat after) and names the
  `cancelTicking()` NPE on the failed-migration path.
- The starter is `git archive` of the base commit without `.github/` and
  `scripts/` (a smoke-test shell/JavaScript pair and a v2 fixture that do not
  take part in the build). `docs/` does not exist upstream.

## Defect

`Chatty.initialize()` builds a fresh Guice injector on every `/chatty reload`
(and in `onEnable`), so every reload creates fresh instances of everything the
module binds. Three of them own resources that `closeResources()` never
released:

1. `ScheduledExecutorNotificationTicker` (singleton per injector) creates a
   single-thread `ScheduledExecutorService` with the JDK default factory in its
   field initialiser. `cancelTicking()` only cancelled the scheduled future, so
   the executor's worker thread (`pool-<n>-thread-1`) stayed parked in
   `DelayedWorkQueue.take` forever: one more thread per reload. The same method
   dereferenced `future` unconditionally, so calling it before `startTicking()`
   (the failed-migration path in `onEnable`) threw a `NullPointerException`.
2. `MetricsSender.run()` constructed a new bStats `Metrics` on every
   `initialize()`; bStats 3.0.2 starts its `bStats-Metrics` daemon thread as
   soon as the instance is created with `enabled: true`, and the previous
   instance was never `shutdown()`.
3. `ProxyServiceImpl` (only with cross-server chat) kept the `RedissonClient`
   in a local variable, so `close()` could not shut it down and the connection
   pool with its Netty threads was abandoned per reload.

## Reference fix

`solution/after/` carries the upstream main-source change only (no test
change upstream): `ScheduledExecutorNotificationTicker.cancelTicking()` guards
the null future and calls `executor.shutdownNow()`; `MetricsSender` remembers
the active `Metrics` in a static field, `shutdownActive()` shuts it down before
a new one is built and `Chatty.closeResources()` calls it; `ProxyServiceImpl`
keeps the `RedissonClient` in a field and shuts it down in `close()`. The base
tests (82) stay frozen and pass with and without the fix (checked offline in
the verifier image, see `validation/controls.md`).

## Build

Gradle 8.8 wrapper, modules `api` and `spigot`, JDK 21 toolchain
(`org.gradle.java.installations.auto-download=false` is satisfied by the
image's JDK), `sourceCompatibility` 11, `compileOnly spigot-api 1.19-R0.1`.
The plugin jar is `spigot:shadowJar`, written to the root
`build/libs/Chatty-3.0.0-SNAPSHOT.jar`; `shadowJar` also resolves the dedicated
`sqliteDriver` configuration (embedded as `sqlite-jdbc.jardata`), so the
warm-up must run `shadowJar`, not `assemble` (`build.assemble: shadowJar`).
Tests are JUnit 5 + Mockito (no MockBukkit); reports land in
`spigot/build/test-results/test/`, which the verifier's recursive report
discovery picks up. `build.module` stays null (root `shadowJar test` builds
`api` + `spigot`).

Frozen paths are declared explicitly in the catalog (`build.frozen_paths`)
because the defaults are root-only: `api/build.gradle`, `spigot/build.gradle`,
`api/src/test`, `spigot/src/test` are added; `api/src/test` and
`gradle.properties` do not exist upstream and restore as "nothing".

## Why the repository matters

The reload path is spread over `Chatty.closeResources()`/`initialize()`, the
Guice module, the ticker and `MetricsSender`; the reload itself succeeds every
time, so the solver has to reason about object lifetimes across injectors: a
singleton-scoped ticker is still one instance per injector, `MetricsSender`
is re-created per injector so an instance field cannot remember the previous
`Metrics`, and cancelling a scheduled future is not the same as shutting down
the executor that owns the thread. Shutting the ticker's executor down alone
still leaks bStats; keeping the bStats instance across reloads without
re-creating it drops metrics for the new configuration; sharing one executor
across reloads and shutting it down kills ticking after the first reload.

## Live-server design

No player is needed. Threads are counted from `Thread.getAllStackTraces()` on
the main thread; the plugin's threads are identified by name (`pool-\d+-thread-\d+`,
`bStats-Metrics`, or a name containing `notification`, `ticker` or `metrics`,
case-insensitive; the exam states this rule so a renamed thread factory still
counts). bStats is disabled by the runtime's `plugins/bStats/config.yml`, so the
suite writes `enabled: true` into that file before the cases that need the
`bStats-Metrics` thread; the bStats submitter first fires after 3-6 minutes and
the container has no network, so nothing is ever sent.

The ticker and its notifications are reached through the private `Chatty`
injector field (typed by the relocated
`ru.brikster.chatty.shaded.com.google.inject.Injector`, stable because the
relocation lives in the frozen `spigot/build.gradle`), then
`Injector.getInstance(NotificationTicker.class)`, the ticker's `Collection`
fields, each notification's `name` field and the inherited `tick` counter.
Executors are every field of the ticker assignable to
`java.util.concurrent.ExecutorService`.

Cases (`tests/suite/ChattyReloadResourcesSuite.java`):

- `plugin is enabled` (sentinel).
- `reload picks up a changed notifications.yml` (preserved): a chat channel
  `gcb_reloaded` is written, `/chatty reload` answers with the success
  message, the channel is registered with the current ticker.
- `notifications keep ticking after a reload` (preserved, ticked): channel
  `gcb_ticking` with a 600 s period; its tick counter advances within 80 ticks
  after the reload.
- `bStats metrics stay scheduled after a reload` (preserved, ticked): bStats
  enabled, reload, at least one live `bStats-Metrics` thread 40 ticks later.
  Catches a "fix" that stops re-creating metrics.
- `previous ticker is stopped by a reload` (target, ticked): the ticker
  instance and its `gcb_previous` notification are captured, the ticker is
  observed ticking, a reload replaces it; 20 and 80 ticks later the old
  notification's counter is unchanged and every executor of the old ticker
  reports `isShutdown()`. Starter: executor not shut down.
- `cancelling a ticker that never started does not throw` (target): a fresh
  instance of the class bound to `NotificationTicker` is created through its
  constructor (parameters resolved from the plugin injector) and
  `cancelTicking()` must return normally. Starter: `NullPointerException`.
- `reloads do not leak ticker or bStats threads` (target, ticked): bStats
  enabled, one warm-up reload, 60 ticks, snapshot; three reloads 20 ticks
  apart, 80 ticks; the number of live plugin-owned threads must not have
  grown (new alive minus gone). Starter: +3 `pool-*` and +3 `bStats-Metrics`.

Observed on the real server (see `validation/controls.md`): the JVM's own JMX
`Notification Thread` matches the keyword rule and appears in every snapshot; it
is steady-state, so the delta ignores it. On the starter the leak case reports
`new [bStats-Metrics x3, pool-24/25/26-thread-1], gone []`; with the reference fix
the replaced threads are gone within the 80-tick settle.

Target cases run last. All reloads go through `GcbSenders.recording()` +
`GcbCommands.dispatch(sender, "chatty reload")`; the success message is read
from `sender.messages()`.

## 0.2.0 changes

The exam no longer names `closeResources()`, `ScheduledExecutorNotificationTicker`,
`MetricsSender` or the proxy service, and no longer explains which object owns
which thread; it gives the `jstack` symptom, the thread-name rule and the
reflection contract. New case:

- `turning metrics off stops the bStats thread on reload` (target, last): with
  bStats enabled and `send-metrics: true` a reload leaves a `bStats-Metrics`
  thread; the suite then rewrites `send-metrics: false` in
  `plugins/Chatty/settings.yml` (only that line), reloads, waits 80 ticks and
  requires that no `bStats-Metrics` thread is alive, then restores
  `send-metrics: true`. On the starter the previous `Metrics` is never shut
  down. Upstream shuts the active instance down in `closeResources()` and again at
  the start of `MetricsSender.run()`, independent of `send-metrics`; a repair that
  shuts the previous instance down only when it creates a new one (inside the
  `send-metrics` branch) passes the leak case and fails this one. The two bStats
  cases that need bStats on set `send-metrics: true` themselves, so the order of
  cases does not matter for them.

## Merge review (0.2.0)

Considered and left out: the commit before the base, `722be7a`, brings back per-chat commands (a feature), and the commit after the fix, `6d2bc6c`, repairs message formatting (a different family). The later reload-lifetime fixes are not adjacent (ten and more commits later): `c56f5a4` ("Keep /mute working after a reload") repairs the mute system, which was added after the base, and `c3df433` ("Clear command state on disable") needs a disable/enable cycle that Paper 1.21.11 cannot perform on a live server. The task keeps `c7ba417` alone.
