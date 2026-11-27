package com.example.blocktrail;

import org.bukkit.command.PluginCommand;
import org.bukkit.plugin.java.JavaPlugin;

public final class BlockTrailPlugin extends JavaPlugin {

    private volatile Settings settings;
    private ChangeStore store;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        reloadSettings();
        store = new ChangeStore(getDataFolder().toPath().resolve("changes.log"), getLogger());
        store.load();

        getServer().getPluginManager().registerEvents(new ChangeListener(store, this::settings), this);

        PluginCommand trail = getCommand("trail");
        if (trail == null) {
            throw new IllegalStateException("plugin.yml does not declare the trail command");
        }
        TrailCommand executor = new TrailCommand(this, store, this::settings);
        trail.setExecutor(executor);
        trail.setTabCompleter(executor);
    }

    @Override
    public void onDisable() {
    }

    /** Re-reads {@code config.yml} from disk. */
    void reloadSettings() {
        reloadConfig();
        settings = Settings.from(getConfig());
    }

    Settings settings() {
        return settings;
    }
}
