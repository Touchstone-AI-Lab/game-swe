package com.example.towncrier;

import java.util.Objects;
import org.bukkit.command.PluginCommand;
import org.bukkit.plugin.java.JavaPlugin;

public final class TownCrierPlugin extends JavaPlugin {

    private Crier crier;

    @Override
    public void onEnable() {
        AnnouncementStore store = new AnnouncementStore(this);
        store.writeDefaultIfMissing();
        crier = new Crier(this, store);

        LoadResult result = crier.reload();
        getLogger().info("Loaded " + result.groups().size() + " groups (" + result.disabledCount()
                + " disabled, " + result.skipped().size() + " invalid).");
        for (LoadResult.Skipped skipped : result.skipped()) {
            getLogger().warning("Skipped " + skipped.name() + ": " + skipped.reason() + ".");
        }

        PluginCommand command = Objects.requireNonNull(getCommand("crier"), "crier is missing from plugin.yml");
        command.setExecutor(new CrierCommand(crier));
    }

    @Override
    public void onDisable() {
        if (crier != null) {
            crier.stopAll();
            crier = null;
        }
    }
}
