package com.example.coinledger;

import org.bukkit.command.PluginCommand;
import org.bukkit.plugin.java.JavaPlugin;

public final class CoinLedgerPlugin extends JavaPlugin {

    @Override
    public void onEnable() {
        saveDefaultConfig();
        Ledger ledger = new Ledger(getDataFolder().toPath(), getLogger());
        ledger.reload();

        PluginCommand command = getCommand("ledger");
        if (command == null) {
            throw new IllegalStateException("The ledger command is missing from plugin.yml");
        }
        command.setExecutor(new LedgerCommand(ledger));
    }

    @Override
    public void onDisable() {
        // Every change is already on disk when its command returns.
    }
}
