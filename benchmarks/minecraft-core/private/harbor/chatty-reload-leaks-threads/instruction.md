# Harbor workspace

Complete this task in `/app/plugin`; the repository's build files, dependency declarations and upstream tests are frozen and restored by the verifier.

# Chatty: every /chatty reload leaks the notification ticker and bStats threads

## Context

`plugin/` is the Chatty chat-management plugin (MIT) at an upstream commit. It
is a Gradle multi-module build: `api/` holds the public `ru.brikster.chatty.api`
types and `spigot/` the plugin itself (`spigot/src/main/resources/plugin.yml`,
`name: Chatty`). The shaded plugin jar is `build/libs/Chatty-3.0.0-SNAPSHOT.jar`,
produced by `./gradlew shadowJar`; the upstream JUnit tests run with
`./gradlew test`.

Chatty rebuilds its whole runtime from the YAML files in `plugins/Chatty/` on
every `/chatty reload` (console permission `chatty.command.reload`, answer
`Plugin successfully reloaded!`), exactly as it builds it when the plugin
enables. Its periodic notifications (`notifications.yml`) are driven once per
second by a notification ticker, the object bound to
`ru.brikster.chatty.notification.NotificationTicker` in the plugin's Guice
injector; each registered `ru.brikster.chatty.notification.Notification` counts
those ticks. With `send-metrics: true` in `settings.yml` (the default) and
`enabled: true` in `plugins/bStats/config.yml`, the plugin reports to bStats
(`org.bstats`, shaded and relocated), which runs its own daemon thread named
`bStats-Metrics`. With cross-server chat enabled in `proxy.yml`, the plugin also
holds a Redisson client with its own connection pool and Netty threads.

## Symptom

Run `/chatty reload` from the console a few times. Every call answers
`Plugin successfully reloaded!` and the plugin keeps working, so nothing looks
wrong. A thread dump (`jstack`) tells another story: each reload leaves one more
idle `pool-<n>-thread-1` thread behind, parked in
`ScheduledThreadPoolExecutor$DelayedWorkQueue.take`, and with bStats enabled one
more `bStats-Metrics` thread. Across three reloads the plugin-owned threads grow
from 4 to 6 on Paper 1.21.11 and never go away until the server stops; on a
server with cross-server chat, a whole Redisson connection pool is abandoned per
reload as well. Switching `send-metrics` off and reloading does not stop bStats
either: the `bStats-Metrics` thread of the previous configuration keeps running.

There is a second, smaller defect: calling `cancelTicking()` on a notification
ticker that never started ticking throws a `NullPointerException`. The plugin
does that when it tears its configuration down before the ticker was started
(for example when a legacy configuration is migrated while the plugin enables).

## Task

Repair the plugin so that a reload releases everything the previous
configuration owned:

- After any number of `/chatty reload` calls the set of live plugin-owned
  threads does not grow. Once a reload has settled (allow a few seconds), the
  threads of the replaced ticker and of the replaced bStats instance are gone.
  The grader identifies plugin-owned threads by name: the JDK default
  `pool-<n>-thread-<m>` pattern, `bStats-Metrics`, and any thread whose name
  contains `notification`, `ticker` or `metrics` (case-insensitive). If you give
  a thread of the plugin a name, use one of those words.
- The notification ticker that a reload replaces stops for good: its
  notifications stop advancing and every `java.util.concurrent.ExecutorService`
  it holds is shut down (`isShutdown()` is true) once the reload has completed.
- `cancelTicking()` on a ticker that never started ticking returns normally.
- bStats follows the configuration: with `send-metrics: true` and bStats enabled,
  a reload leaves a live `bStats-Metrics` thread (metrics are re-created for the
  new configuration, not dropped); after `send-metrics` is switched to `false`
  and the plugin is reloaded, no `bStats-Metrics` thread remains.
- With cross-server chat enabled, the Redisson client of the configuration being
  replaced is shut down too. The grader runs without Redis and cannot observe
  this, but it is part of the repair.
- Everything else behaves exactly as before: a reload still answers
  `Plugin successfully reloaded!` and still picks up changed configuration (a
  channel added to `notifications.yml` is registered with the new ticker),
  notifications keep ticking after a reload, and every upstream unit test keeps
  passing.

Keep the change inside `plugin/spigot/src/main/java` (you may also touch
`plugin/api/src/main/java` if you need to). The build files (`build.gradle`,
`settings.gradle`, `api/build.gradle`, `spigot/build.gradle`), the Gradle
wrapper and the existing tests under `plugin/spigot/src/test` are frozen: the
verifier restores them from the starter before building.

## Evaluation

The verifier builds the plugin offline with the repository's Gradle wrapper
(`shadowJar`), runs the upstream JUnit suite (`test`), and then loads the built
jar into a real Paper 1.21.11 dedicated server without players. From a console
sender it reloads the plugin after editing `plugins/Chatty/notifications.yml`,
`plugins/Chatty/settings.yml` (`send-metrics`) and `plugins/bStats/config.yml`,
waits a few seconds after every reload, and compares the live plugin-owned
threads before and after three consecutive reloads. It keeps a reference to the
ticker instance a reload replaces and inspects its executors and tick counters,
checks that a notification registered by a reload keeps advancing, and creates a
fresh instance of the class bound to `NotificationTicker` to call
`cancelTicking()` on it before `startTicking()`.

The grader compiles against your jar and reaches the plugin's objects through
reflection, so keep these as they are: the `NotificationTicker` interface and its
binding in the plugin's injector, the `Chatty` field that holds the plugin's
(relocated) Guice `Injector`, the ticker's collection of registered
notifications, each notification's `name` field and the `tick` counter that every
notification inherits from `Notification`. The ticker implementation must stay
constructible through a constructor whose parameters the plugin's injector can
provide (the current no-argument constructor is fine). Paper closes a plugin's
class loader on disable, so the grader never disables and re-enables the plugin.
