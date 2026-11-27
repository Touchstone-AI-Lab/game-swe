package de.sldk.mc.metrics;

import io.prometheus.client.Gauge;
import org.bukkit.Bukkit;
import org.bukkit.plugin.Plugin;

public class PlayersTotal extends Metric {

    private static final Gauge PLAYERS = Gauge.build()
            .name(prefix("players_total"))
            .help("Unique players (online + offline)")
            .create();

    public PlayersTotal(Plugin plugin) {
        super(plugin, PLAYERS);
    }

    @Override
    public void doCollect() {
        PLAYERS.set(Bukkit.getOfflinePlayers().length);
    }

    /**
     * {@link Bukkit#getOfflinePlayers()} lists the player data folder and the
     * online players. It reads no world, chunk or entity state, so it is
     * collected off the main thread and a scrape does not wait for the current
     * tick. It is still read on every collection, so player data written just
     * before a scrape is counted.
     */
    @Override
    protected boolean isAsyncCapable() {
        return true;
    }
}
