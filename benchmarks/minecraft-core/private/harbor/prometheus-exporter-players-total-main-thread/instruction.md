# Harbor workspace

Complete this task in `/app/plugin`; the repository's build files, dependency declarations and upstream tests are frozen and restored by the verifier.

# PrometheusExporter: every `/metrics` scrape waits for the main thread because of `players_total`

## Context

`plugin/` is the minecraft-prometheus-exporter Paper plugin (MIT) at an upstream
commit. It starts an embedded HTTP server on the `host` and `port` from
`plugins/PrometheusExporter/config.yml` (default `localhost:9940`) and answers
Prometheus scrapes of `/metrics` in the Prometheus text format. Each metric
family can be switched on and off in `config.yml`; at run time every metric is a
`de.sldk.mc.metrics.Metric` held by `de.sldk.mc.MetricRegistry`, with
`enable()`, `disable()`, `isEnabled()` and `collect()` (which returns a
`CompletableFuture` that completes once the metric's value is up to date). A
scrape collects every enabled metric and then renders the result.

Most metrics read world, chunk or entity state through the Bukkit API, which is
only safe on the server's main thread, so their collection runs there and a
scrape waits for it.

## Symptom

Server owners report that the exporter costs them tick time on every scrape and
that scrapes stall whenever the server is busy. Profiling points at the
`mc_players_total` gauge (the number of players the server has ever seen,
`Bukkit.getOfflinePlayers().length`, which lists the world's `playerdata`
folder): it is computed on the main thread for every scrape although it reads no
world state. With every other metric that needs the main thread switched off, a
scrape still cannot finish until the current tick ends, and collecting the
`players_total` metric while the main thread is blocked never completes.

## Task

Repair the plugin so that:

- Collecting the `players_total` metric (the `de.sldk.mc.metrics.PlayersTotal`
  instance registered in `MetricRegistry`) needs no main-thread work: its
  `collect()`, called while the main thread is blocked, completes within a few
  seconds.
- With every other registered metric disabled through `Metric.disable()`, a
  `/metrics` scrape completes while the main thread is busy and contains
  `mc_players_total`.
- `mc_players_total` keeps reporting the number of players known to the server
  (`Bukkit.getOfflinePlayers().length`), including players whose `playerdata`
  file appeared just before the scrape.
- Metrics that read world, chunk or entity state keep being collected on the
  main thread: `collect()` of the registered `Entities`, `Villagers`,
  `LoadedChunks` and `PlayersOnlineTotal` metrics, called while the main thread
  is blocked, does not complete until the main thread is free again.
- A normal scrape keeps returning the default metric families:
  `mc_players_total`, `mc_players_online_total{world=...}`,
  `mc_loaded_chunks_total{world=...}` (positive for a world with loaded
  chunks), `mc_tps` and `mc_jvm_memory{type=...}`.
- A metric disabled through `Metric.disable()` is left out of the scrape and
  appears again after `Metric.enable()`.

`MetricRegistry` must keep holding the registered `Metric` instances, the
classes named above must remain the ones behind their metric families, and
`Metric.enable()`, `disable()`, `isEnabled()` and `collect()` must keep their
contract: the verifier reaches the plugin through them.

Keep the change inside `plugin/src/main`. `pom.xml` and the existing tests under
`plugin/src/test` are frozen: the verifier restores them from the starter before
building, and every existing upstream test must keep compiling and passing
(`de.sldk.mc.tps.TpsCollectorTest` imports `de.sldk.mc.tps.TpsCollector`, so that
class must stay where it is).

## Evaluation

The verifier builds the plugin offline with Maven (`package`), runs the upstream
JUnit suite, and then loads the built jar into a real Paper 1.21.11 dedicated
server without players. From inside the server process it scrapes the embedded
endpoint, adds `playerdata` files before a scrape, disables and re-enables
metrics, and calls `collect()` of registered metrics and scrapes `/metrics`
while it holds the main thread.
