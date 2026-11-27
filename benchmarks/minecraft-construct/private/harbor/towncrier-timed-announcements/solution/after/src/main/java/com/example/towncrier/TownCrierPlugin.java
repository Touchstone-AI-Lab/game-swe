package com.example.towncrier;

import java.io.File;
import org.bukkit.command.PluginCommand;
import org.bukkit.plugin.java.JavaPlugin;

public final class TownCrierPlugin extends JavaPlugin {

    private Announcer announcer;

    @Override
    public void onEnable() {
        if (!new File(getDataFolder(), "announcements.yml").exists()) {
            saveResource("announcements.yml", false);
        }
        announcer = new Announcer(this);
        Announcer.LoadReport report = announcer.load();
        for (String skipped : report.skipped()) {
            getLogger().warning(skipped);
        }
        PluginCommand command = getCommand("crier");
        if (command != null) {
            command.setExecutor(new CrierCommand(this));
        }
    }

    @Override
    public void onDisable() {
        if (announcer != null) {
            announcer.stop();
        }
    }

    Announcer announcer() {
        return announcer;
    }
}
