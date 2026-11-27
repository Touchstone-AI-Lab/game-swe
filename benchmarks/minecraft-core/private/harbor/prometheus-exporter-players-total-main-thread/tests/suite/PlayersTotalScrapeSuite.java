import de.sldk.mc.MetricRegistry;
import de.sldk.mc.metrics.Entities;
import de.sldk.mc.metrics.LoadedChunks;
import de.sldk.mc.metrics.Metric;
import de.sldk.mc.metrics.PlayersOnlineTotal;
import de.sldk.mc.metrics.Tps;
import de.sldk.mc.metrics.Villagers;
import de.sldk.mc.metrics.PlayersTotal;
import io.gamecodebench.harness.GcbAssert;
import io.gamecodebench.harness.GcbCase;
import io.gamecodebench.harness.GcbScript;
import io.gamecodebench.harness.GcbSuite;
import io.gamecodebench.harness.GcbWorlds;
import org.bukkit.Bukkit;
import org.bukkit.plugin.Plugin;

import java.lang.reflect.Field;
import java.lang.reflect.Modifier;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.http.HttpTimeoutException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

/** Live-server grader: players_total must be collected off the main thread. */
public final class PlayersTotalScrapeSuite implements GcbSuite {

    private static final String PLUGIN_NAME = "PrometheusExporter";
    private static final Duration SCRAPE_TIMEOUT = Duration.ofSeconds(5);
    private static final int KNOWN_PLAYERS_ADDED = 3;

    private CompletableFuture<HttpResponse<String>> pendingScrape;
    private int expectedKnownPlayers;

    private static Plugin plugin() {
        Plugin plugin = Bukkit.getPluginManager().getPlugin(PLUGIN_NAME);
        GcbAssert.notNull(plugin, PLUGIN_NAME + " must be loaded");
        GcbAssert.isTrue(plugin.isEnabled(), PLUGIN_NAME + " must be enabled");
        return plugin;
    }

    /** host/port as the plugin reads them: config.yml values fall back to the plugin's own defaults. */
    private static URI metricsUri(Plugin plugin) {
        String host = plugin.getConfig().getString("host");
        int port = plugin.getConfig().getInt("port");
        GcbAssert.isTrue(host != null && !host.isBlank(), "config.yml must declare the metrics host");
        GcbAssert.isTrue(port > 0, "config.yml must declare the metrics port");
        return URI.create("http://" + host + ":" + port + "/metrics");
    }

    private static CompletableFuture<HttpResponse<String>> scrapeAsync(Plugin plugin) {
        HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build();
        HttpRequest request = HttpRequest.newBuilder(metricsUri(plugin)).timeout(SCRAPE_TIMEOUT).GET().build();
        return client.sendAsync(request, HttpResponse.BodyHandlers.ofString());
    }

    /**
     * The sample line for {@code name}, or null. A bare name matches its unlabelled
     * sample or any labelled child; a name with a label prefix such as
     * {@code mc_x{world="w"} matches the children whose label list starts with it.
     */
    private static String sampleLine(String body, String name) {
        boolean labelled = name.contains("{");
        for (String line : body.split("\n")) {
            if (labelled ? line.startsWith(name) : (line.startsWith(name + " ") || line.startsWith(name + "{"))) {
                return line.trim();
            }
        }
        return null;
    }

    private static double sampleValue(String body, String name) {
        String line = sampleLine(body, name);
        GcbAssert.notNull(line, "the scrape must contain a sample for " + name);
        String[] parts = line.split("\\s+");
        return Double.parseDouble(parts[parts.length - 1]);
    }

    /** Every Metric instance the plugin registered in MetricRegistry. */
    private static List<Metric> registeredMetrics() throws Exception {
        MetricRegistry registry = MetricRegistry.getInstance();
        List<Metric> found = new ArrayList<>();
        for (Field field : MetricRegistry.class.getDeclaredFields()) {
            if (Modifier.isStatic(field.getModifiers())) {
                continue;
            }
            field.setAccessible(true);
            Object value = field.get(registry);
            if (value instanceof Iterable<?> items) {
                for (Object item : items) {
                    if (item instanceof Metric metric) {
                        found.add(metric);
                    }
                }
            }
        }
        GcbAssert.isFalse(found.isEmpty(), "MetricRegistry must hold the registered Metric instances");
        return found;
    }

    private static Metric registered(Class<? extends Metric> type) throws Exception {
        for (Metric metric : registeredMetrics()) {
            if (type.isInstance(metric)) {
                return metric;
            }
        }
        GcbAssert.fail("no " + type.getSimpleName() + " instance is registered in MetricRegistry");
        return null;
    }

    private static Metric registeredPlayersTotal() throws Exception {
        for (Metric metric : registeredMetrics()) {
            if (metric instanceof PlayersTotal) {
                return metric;
            }
        }
        GcbAssert.fail("no PlayersTotal instance is registered in MetricRegistry");
        return null;
    }

    @GcbCase(value = "plugin is enabled", order = 0)
    public void pluginIsEnabled() throws Exception {
        Plugin plugin = plugin();
        GcbAssert.notNull(metricsUri(plugin), "the metrics endpoint must be configured");
        GcbAssert.isTrue(registeredPlayersTotal().isEnabled(), "players_total must be enabled by default");
    }

    @GcbCase(value = "scrape returns the expected metric families", order = 1, ticks = 400)
    public void scrapeReturnsDefaultFamilies(GcbScript script) {
        script.step(() -> pendingScrape = scrapeAsync(plugin()));
        script.waitUntil(() -> pendingScrape.isDone(), "the /metrics scrape to complete");
        script.step(() -> {
            HttpResponse<String> response = pendingScrape.get();
            GcbAssert.equals(200, response.statusCode(), "/metrics must answer 200");
            String contentType = response.headers().firstValue("Content-Type").orElse("");
            GcbAssert.isTrue(contentType.startsWith("text/plain"), "the scrape must use the Prometheus text format, got " + contentType);
            String body = response.body();
            String mainWorld = GcbWorlds.main().getName();
            GcbAssert.notNull(sampleLine(body, "mc_players_total"), "mc_players_total must be exported");
            GcbAssert.notNull(sampleLine(body, "mc_players_online_total{world=\"" + mainWorld + "\""),
                    "mc_players_online_total must be exported for " + mainWorld);
            GcbAssert.notNull(sampleLine(body, "mc_tps"), "mc_tps must be exported");
            GcbAssert.notNull(sampleLine(body, "mc_jvm_memory{type=\"max\""), "mc_jvm_memory must be exported");
            double loadedChunks = sampleValue(body, "mc_loaded_chunks_total{world=\"" + mainWorld + "\"");
            GcbAssert.isTrue(loadedChunks > 0,
                    "mc_loaded_chunks_total for " + mainWorld + " must be positive while its spawn chunks are loaded, got " + loadedChunks);
        });
    }

    @GcbCase(value = "players_total reports every known player", order = 2, ticks = 400)
    public void playersTotalCountsKnownPlayers(GcbScript script) {
        script.step(() -> {
            Path playerdata = GcbWorlds.main().getWorldFolder().toPath().resolve("playerdata");
            Files.createDirectories(playerdata);
            for (int i = 0; i < KNOWN_PLAYERS_ADDED; i++) {
                UUID id = UUID.nameUUIDFromBytes(("gcb-known-player-" + i).getBytes(StandardCharsets.UTF_8));
                Files.write(playerdata.resolve(id + ".dat"), new byte[0]);
            }
            expectedKnownPlayers = Bukkit.getOfflinePlayers().length;
            GcbAssert.isTrue(expectedKnownPlayers >= KNOWN_PLAYERS_ADDED,
                    "the server must know the added playerdata files, saw " + expectedKnownPlayers);
            pendingScrape = scrapeAsync(plugin());
        });
        script.waitUntil(() -> pendingScrape.isDone(), "the /metrics scrape to complete");
        script.step(() -> {
            HttpResponse<String> response = pendingScrape.get();
            GcbAssert.equals(200, response.statusCode(), "/metrics must answer 200");
            GcbAssert.equals(expectedKnownPlayers, sampleValue(response.body(), "mc_players_total"),
                    "mc_players_total must equal the number of players known to the server");
        });
    }

    @GcbCase(value = "players_total is collected without the main thread", order = 3)
    public void playersTotalCollectsOffMainThread() throws Exception {
        plugin();
        GcbAssert.isTrue(Bukkit.isPrimaryThread(), "the grader must hold the main thread during this case");
        Metric playersTotal = registeredPlayersTotal();
        GcbAssert.isTrue(playersTotal.isEnabled(), "players_total must be enabled");
        CompletableFuture<Void> collection = playersTotal.collect();
        try {
            collection.get(3, TimeUnit.SECONDS);
        } catch (TimeoutException timeout) {
            GcbAssert.fail("PlayersTotal.collect() did not complete within 3 s while the main thread was busy: "
                    + "the collection waits for a main-thread task");
        }
    }

    @GcbCase(value = "scrape completes while the main thread is busy", order = 4)
    public void scrapeCompletesWhileMainThreadBusy() throws Exception {
        Plugin plugin = plugin();
        GcbAssert.isTrue(Bukkit.isPrimaryThread(), "the grader must hold the main thread during this case");
        List<Metric> paused = new ArrayList<>();
        for (Metric metric : registeredMetrics()) {
            if (metric.isEnabled() && !(metric instanceof PlayersTotal)) {
                metric.disable();
                paused.add(metric);
            }
        }
        try {
            GcbAssert.isTrue(registeredPlayersTotal().isEnabled(), "players_total must stay enabled");
            CompletableFuture<HttpResponse<String>> scrape = scrapeAsync(plugin);
            HttpResponse<String> response;
            try {
                response = scrape.get(SCRAPE_TIMEOUT.toSeconds() + 2, TimeUnit.SECONDS);
            } catch (TimeoutException timeout) {
                response = null;
            } catch (ExecutionException failure) {
                if (!(failure.getCause() instanceof HttpTimeoutException)) {
                    throw failure;
                }
                response = null;
            }
            if (response == null) {
                GcbAssert.fail("a /metrics scrape with only players_total enabled did not complete within "
                        + SCRAPE_TIMEOUT.toSeconds() + " s while the main thread was busy");
                return;
            }
            GcbAssert.equals(200, response.statusCode(), "/metrics must answer 200");
            GcbAssert.notNull(sampleLine(response.body(), "mc_players_total"),
                    "the scrape must contain mc_players_total");
        } finally {
            for (Metric metric : paused) {
                metric.enable();
            }
        }
    }

    @GcbCase(value = "world-state metrics are still collected on the main thread", order = 5)
    public void worldStateMetricsStayOnMainThread() throws Exception {
        plugin();
        GcbAssert.isTrue(Bukkit.isPrimaryThread(), "the grader must hold the main thread during this case");
        List<Class<? extends Metric>> types = List.of(Entities.class, Villagers.class, LoadedChunks.class,
                PlayersOnlineTotal.class);
        List<CompletableFuture<Void>> collections = new ArrayList<>();
        for (Class<? extends Metric> type : types) {
            Metric metric = registered(type);
            GcbAssert.isTrue(metric.isEnabled(), type.getSimpleName() + " must be enabled by default");
            collections.add(metric.collect());
        }
        Thread.sleep(1500);
        for (int i = 0; i < types.size(); i++) {
            GcbAssert.isFalse(collections.get(i).isDone(),
                    types.get(i).getSimpleName() + ".collect() completed while the main thread was busy: a metric "
                            + "that reads world, chunk or entity state must be collected on the main thread");
        }
    }

    @GcbCase(value = "a disabled metric is left out of the scrape", order = 6, ticks = 600)
    public void disabledMetricIsLeftOut(GcbScript script) {
        Metric[] tps = new Metric[1];
        script.step(() -> {
            tps[0] = registered(Tps.class);
            GcbAssert.isTrue(tps[0].isEnabled(), "tps must be enabled by default");
            tps[0].disable();
            GcbAssert.isFalse(tps[0].isEnabled(), "Metric.disable() must disable the metric");
            pendingScrape = scrapeAsync(plugin());
        });
        script.waitUntil(() -> pendingScrape.isDone(), "the /metrics scrape to complete");
        script.step(() -> {
            HttpResponse<String> response = pendingScrape.get();
            tps[0].enable();
            GcbAssert.equals(200, response.statusCode(), "/metrics must answer 200");
            GcbAssert.isTrue(sampleLine(response.body(), "mc_tps") == null,
                    "a disabled metric must not appear in the scrape");
            GcbAssert.notNull(sampleLine(response.body(), "mc_players_total"),
                    "mc_players_total must still be exported");
            GcbAssert.isTrue(tps[0].isEnabled(), "Metric.enable() must enable the metric again");
            pendingScrape = scrapeAsync(plugin());
        });
        script.waitUntil(() -> pendingScrape.isDone(), "the second /metrics scrape to complete");
        script.step(() -> GcbAssert.notNull(sampleLine(pendingScrape.get().body(), "mc_tps"),
                "a re-enabled metric must appear in the scrape again"));
    }
}
