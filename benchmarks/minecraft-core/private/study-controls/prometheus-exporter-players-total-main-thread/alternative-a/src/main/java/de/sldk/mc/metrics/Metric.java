package de.sldk.mc.metrics;

import io.prometheus.client.Collector;
import io.prometheus.client.CollectorRegistry;
import org.bukkit.Bukkit;
import org.bukkit.plugin.Plugin;

import java.util.concurrent.CompletableFuture;
import java.util.logging.Logger;

public abstract class Metric {

    private final static String COMMON_PREFIX = "mc_";

    private final Plugin plugin;
    private final Collector collector;

    /* Toggled by enable()/disable() and read by collect() on scrape threads */
    private volatile boolean enabled = false;

    protected Metric(Plugin plugin, Collector collector) {
        this.plugin = plugin;
        this.collector = collector;
    }

    protected Plugin getPlugin() {
        return plugin;
    }

    /**
     * Brings the metric's value up to date.
     *
     * @return a future that completes once the value is up to date,
     * or right away if the metric is disabled
     */
    public CompletableFuture<Void> collect() {
        if (!enabled) {
            return CompletableFuture.completedFuture(null);
        }

        /* If metric is capable of async execution run it on a thread pool */
        if (isAsyncCapable()) {
            return CompletableFuture.runAsync(this::doCollectAndLog);
        }

        /*
         * Otherwise run the metric on the main thread. The scheduled task
         * completes the future itself, so no pool thread is parked while the
         * main thread is busy: a parked pool thread would hold up the
         * async-capable metrics queued behind it.
         */
        final CompletableFuture<Void> future = new CompletableFuture<>();
        try {
            Bukkit.getScheduler().runTask(plugin, () -> {
                try {
                    doCollectAndLog();
                } finally {
                    future.complete(null);
                }
            });
        } catch (RuntimeException e) {
            logException(e);
            future.completeExceptionally(e);
        }
        return future;
    }

    private void doCollectAndLog() {
        try {
            doCollect();
        }
        catch (Exception e) {
            logException(e);
        }
    }

    protected abstract void doCollect();

    /**
     * This method is called during the Metric collection
     * to determine if it is safe to do it async.
     * By default, all Metrics are sync unless this method
     * is overridden.
     */
    protected boolean isAsyncCapable() {
        return false;
    }

    private void logException(Exception e) {
        final Logger log = plugin.getLogger();
        final String className = getClass().getSimpleName();

        log.throwing(className, "collect", e);
    }

    protected static String prefix(String name) {
        return COMMON_PREFIX + name;
    }

    public void enable() {
        CollectorRegistry.defaultRegistry.register(collector);
        enabled = true;
    }

    public void disable() {
        CollectorRegistry.defaultRegistry.unregister(collector);
        enabled = false;
    }

    public boolean isEnabled() {
        return enabled;
    }
}
