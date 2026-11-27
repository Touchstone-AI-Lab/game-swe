package com.example.coinledger;

import java.io.IOException;
import java.util.logging.Level;
import org.bukkit.command.PluginCommand;
import org.bukkit.plugin.java.JavaPlugin;

public final class CoinLedgerPlugin extends JavaPlugin {

    private Ledger ledger;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        ledger = new Ledger(new LedgerStore(getDataFolder()), LedgerSettings.from(getConfig()), getLogger());
        try {
            ledger.reload(LedgerSettings.from(getConfig()));
        } catch (IOException failure) {
            getLogger().log(Level.SEVERE, "Could not read the ledger files", failure);
        }
        PluginCommand command = getCommand("ledger");
        if (command != null) {
            command.setExecutor(new LedgerCommand(this));
        }
    }

    @Override
    public void onDisable() {
        if (ledger != null) {
            try {
                ledger.store().save();
            } catch (IOException failure) {
                getLogger().log(Level.SEVERE, "Could not save the ledger", failure);
            }
        }
    }

    Ledger ledger() {
        return ledger;
    }

    /** Re-reads config.yml, accounts.yml and audit.log. */
    void reloadLedger() throws IOException {
        reloadConfig();
        ledger.reload(LedgerSettings.from(getConfig()));
    }
}
