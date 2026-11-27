package com.example.wardstone;

import java.io.IOException;
import java.util.Objects;
import java.util.logging.Level;
import org.bukkit.command.PluginCommand;
import org.bukkit.plugin.java.JavaPlugin;

public final class WardstonePlugin extends JavaPlugin {
    static final String CONFIG_MAX_VOLUME = "max-region-volume";
    static final long DEFAULT_MAX_VOLUME = 1_000_000L;

    private final RegionRegistry registry = new RegionRegistry();
    private RegionStorage storage;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        storage = new RegionStorage(getDataFolder().toPath().resolve("regions.yml"), getLogger());
        registry.replaceAll(storage.load());

        PluginCommand ward = Objects.requireNonNull(getCommand("ward"), "command ward missing from plugin.yml");
        ward.setExecutor(new WardCommand(this, registry));
        getServer().getPluginManager().registerEvents(new ProtectionListener(registry), this);
    }

    @Override
    public void onDisable() {
        // Every change is already on disk: regions.yml is written after each one.
    }

    /** The largest block count a region may have, from {@code config.yml}. */
    long maxRegionVolume() {
        return getConfig().getLong(CONFIG_MAX_VOLUME, DEFAULT_MAX_VOLUME);
    }

    /** Re-reads {@code config.yml} and {@code regions.yml}; returns the region count. */
    int reloadFromDisk() {
        reloadConfig();
        registry.replaceAll(storage.load());
        return registry.size();
    }

    /** Writes every region to {@code regions.yml} before returning. */
    void saveRegions() {
        try {
            storage.save(registry.all());
        } catch (IOException e) {
            getLogger().log(Level.SEVERE, "Could not write regions.yml", e);
        }
    }
}
