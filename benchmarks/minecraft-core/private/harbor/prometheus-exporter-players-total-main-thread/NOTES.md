# Maintenance notes: prometheus-exporter-players-total-main-thread

## Upstream

- Repository: https://github.com/sladkoff/minecraft-prometheus-exporter (MIT,
  `LICENSE.md` kept in the starter; GitHub licence API and the file at the base
  commit both say MIT).
- Base commit: `e8647672998b36279970ea07c68e97a1af7daee3` (merge of PR #224,
  "build: configure Kotlin support"; parent of the fix).
- Fix: commit `e7de226014516d64fd8d04f4bac9d3a1e4145a0b` "fix lag when
  collecting counts for offline players and chunks total" (2024-02-26, shipped
  in 2.6.1). Related history: issue #24 "2% of server tick used by offline
  players metric".
- The starter is `git archive` of the base commit without `.github/`,
  `dashboards/` (Grafana JSON), `docker-compose.yml` and `renovate.json`, none of
  which take part in the build.

## Defect

`Metric.collect()` runs every collection on the common pool but, unless
`isAsyncCapable()` is overridden, wraps `doCollect()` in
`Bukkit.getScheduler().callSyncMethod(plugin, ...).get()`: the scrape thread
waits for the main thread to run the collection. `PlayersTotal.doCollect()`
calls `Bukkit.getOfflinePlayers()`, which lists the world's `playerdata` folder
and builds an `OfflinePlayer` per file, so every scrape charges that directory
listing to the tick and cannot finish while the main thread is busy.

## Reference fix

`solution/after/` carries the upstream main-source change minus a pure
package rename:

- `metrics/PlayersTotal.java` overrides `isAsyncCapable()` to `true` (the
  behaviour under test);
- `metrics/LoadedChunks.java` + new `collectors/LoadedChunksCollector.java`
  replace the per-scrape `world.getLoadedChunks()` array with an
  event-maintained counter (`ChunkLoadEvent`/`ChunkUnloadEvent`/
  `WorldUnloadEvent`). This part is a cost change that is still collected on
  the main thread; it has no deterministic observable behaviour and is only
  covered by the preserved family case (positive chunk count).
- The upstream commit also moved `TpsCollector` from `de.sldk.mc.tps` to
  `de.sldk.mc.collectors` together with its test. `src/test` is frozen at the
  base commit and `TpsCollectorTest` imports the old package, so the rename is
  not part of the reference and the exam tells the solver to keep the class.

## Build

Maven single module, no wrapper in the repository (`build.wrapper=false`,
`tool_version=3.9.11`); `paper-api 1.20.4-R0.1-SNAPSHOT` (provided),
`kotlin-maven-plugin` 1.9.22 compiles `src/main/kotlin` (the plugin main
class) and `src/main/java`, `maven-compiler-plugin` with `release 17`,
JUnit 5.10.2 + Mockito, `maven-assembly-plugin` jar-with-dependencies with
`appendAssemblyId=false`, so `package` produces
`target/minecraft-prometheus-exporter-2.6.1-SNAPSHOT.jar` (Jetty and the
Prometheus client shaded, `plugin.yml` `name: PrometheusExporter`,
`api-version: 1.16`). Surefire providers are resolved only while tests run, so
the image warm-up runs `dependency:go-offline test` online once, then proves
`-o clean test package`.

Harness requirements this task introduced (ported into the pack's
`scripts/materialize.py` and `harness/verify.py`):

- neither base image ships Maven, so `materialize.py` installs the pinned
  Apache Maven distribution named by `build.tool_version` (SHA-512 checked)
  into both images for a Maven task without a committed wrapper;
- `PathFileSizeTest$WhenPathIsFile.returnsFileSize` is a `@RepeatedTest(5)`
  and appears five times under one identity in the surefire XML. `verify.py`
  treats duplicated identities as unobserved and used to fail the whole unit
  layer whenever any duplicate appeared; it now only does so for duplicates
  inside the frozen set. The repeated test is therefore not one of the 27
  frozen `unit_cases` (32 executions, 27 observable identities).

## Why the repository matters

The solver must trace a scrape from `MetricsController` through
`MetricRegistry.collectMetrics()` into `Metric.collect()` to see that
`isAsyncCapable()` decides between the scrape thread and a scheduled
main-thread task, judge that `Bukkit.getOfflinePlayers()` is safe to read off
the main thread, and keep the count semantics. The fix itself is small; the
difficulty is in the diagnosis and in not breaking the metric contract or the
frozen `TpsCollector` package.

## Live-server design

- Sentinel `plugin is enabled`: plugin enabled, `config.yml` has a port, a
  `PlayersTotal` instance is registered and enabled.
- Preserved `scrape returns the expected metric families` (ticked): a
  background `HttpClient` GET of `http://<host>:<port>/metrics` while the main
  thread is free between ticks; asserts 200, text format, and samples for
  `mc_players_total`, `mc_players_online_total{world}`, `mc_tps`,
  `mc_jvm_memory{type="max"}` and a positive `mc_loaded_chunks_total{world}`
  (the harness force-loads the spawn chunks). The chunk value is not compared
  with `getLoadedChunks().length` because the reference's event counter may
  drift by a chunk around unload events.
- Preserved `players_total reports every known player` (ticked): writes three
  empty `playerdata/<uuid>.dat` files into the main world, computes
  `Bukkit.getOfflinePlayers().length` on the main thread, scrapes, and expects
  `mc_players_total` to equal it. Paper counts a playerdata file by name
  without reading it.
- Target `players_total is collected without the main thread` (synchronous,
  so the grader itself holds the main thread): looks up the registered
  `PlayersTotal` in `MetricRegistry` (reflection over its collection field),
  calls `collect()` and waits 3 s. Starter: the collection is queued through
  `callSyncMethod` and can never run while the case holds the main thread, so
  the wait times out (deterministic, not a race). Fix: the common pool finishes
  `getOfflinePlayers()` in milliseconds.
- Target `scrape completes while the main thread is busy` (synchronous): disables
  every enabled metric except `PlayersTotal` through the public
  `Metric.disable()`, scrapes with a 5 s request timeout while holding the
  main thread, then re-enables the paused metrics in `finally`. Starter: the
  scrape blocks on the players_total task (timeout). Fix: completes with
  `mc_players_total` in the body. Other metrics are paused because
  `Entities`, `Villagers`, `LoadedChunks`, `PlayersOnlineTotal`, the tick
  duration collectors and the JVM wrappers legitimately stay main-thread-bound.
- No player, no world creation; loopback HTTP works under `--network=none`.
- Preserved `world-state metrics are still collected on the main thread`
  (0.2.0, synchronous): calls `collect()` of the registered `Entities`,
  `Villagers`, `LoadedChunks` and `PlayersOnlineTotal` metrics while the grader
  holds the main thread and requires that none of the futures is done 1.5 s
  later. Holds on the starter and the reference (both keep these metrics behind
  `callSyncMethod`). It stops the shallow repair that makes every metric
  asynchronous (for example `Metric.isAsyncCapable()` returning `true` or
  `collect()` never using the scheduler), which passes both targets but reads
  Bukkit world state off the main thread.
- Preserved `a disabled metric is left out of the scrape` (0.2.0, ticked):
  `Tps.disable()` removes `mc_tps` from a scrape and `enable()` restores it, with
  `mc_players_total` still exported.

## Difficulty

The upstream repair is one method override, and the exam has to name the
`players_total` metric and its class because the grader collects that metric
directly. The 0.2.0 exam no longer describes how `Metric.collect()` chooses a
thread or which method decides it; the solver has to find that in
`Metric.collect()` itself. Beyond that the task cannot be made genuinely harder
within the authoring rules: the only other part of the upstream commit (the
event-maintained `LoadedChunks` counter) changes cost, not observable behaviour,
and the nearby upstream history holds no related player-free fix.
