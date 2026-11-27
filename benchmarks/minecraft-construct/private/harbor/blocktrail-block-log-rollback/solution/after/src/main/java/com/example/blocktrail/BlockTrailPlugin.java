package com.example.blocktrail;

import java.io.IOException;
import java.util.logging.Level;
import org.bukkit.Material;
import org.bukkit.block.Block;
import org.bukkit.command.PluginCommand;
import org.bukkit.plugin.java.JavaPlugin;

public final class BlockTrailPlugin extends JavaPlugin {

    private TrailStore store;
    private TrailSettings settings;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        store = new TrailStore(getDataFolder());
        try {
            reloadTrail();
        } catch (IOException failure) {
            getLogger().log(Level.SEVERE, "Could not read changes.log", failure);
        }
        getServer().getPluginManager().registerEvents(new TrailListener(this), this);
        PluginCommand command = getCommand("trail");
        if (command != null) {
            command.setExecutor(new TrailCommand(this));
        }
    }

    TrailStore store() {
        return store;
    }

    TrailSettings settings() {
        return settings;
    }

    void reloadTrail() throws IOException {
        reloadConfig();
        settings = TrailSettings.from(getConfig());
        store.load();
    }

    /** Records one change unless it is filtered out; {@code material} is the material the filters look at. */
    void record(String actor, Action action, Block block, Material from, Material to, Material material,
                String fromData, String toData) {
        String world = block.getWorld().getName();
        if (!settings.records(world, material)) {
            return;
        }
        Change change = new Change(store.nextId(), System.currentTimeMillis(), actor, action, world,
            block.getX(), block.getY(), block.getZ(), from, to, fromData, toData);
        try {
            store.add(change);
        } catch (IOException failure) {
            getLogger().log(Level.SEVERE, "Could not write changes.log", failure);
        }
    }
}
