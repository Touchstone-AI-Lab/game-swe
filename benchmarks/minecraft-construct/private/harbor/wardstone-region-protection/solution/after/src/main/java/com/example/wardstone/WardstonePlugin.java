package com.example.wardstone;

import org.bukkit.command.PluginCommand;
import org.bukkit.plugin.java.JavaPlugin;

public final class WardstonePlugin extends JavaPlugin {

    private RegionStore regions;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        regions = new RegionStore(getDataFolder());
        regions.load();
        getServer().getPluginManager().registerEvents(new ProtectionListener(this), this);
        PluginCommand command = getCommand("ward");
        if (command != null) {
            command.setExecutor(new WardCommand(this));
        }
    }

    RegionStore regions() {
        return regions;
    }

    void reloadRegions() {
        reloadConfig();
        regions.load();
    }
}
