package com.example.coinledger;

import java.util.Locale;
import org.bukkit.configuration.file.FileConfiguration;

/** The values read from config.yml. */
public record LedgerSettings(
    String currency,
    long startingBalance,
    long maxBalance,
    int feePercent,
    String feeAccount,
    int pageSize) {

    public static LedgerSettings from(FileConfiguration config) {
        String currency = config.getString("currency", "coins");
        long starting = Money.fromConfig(config.get("starting-balance"), 10_000);
        long max = Money.fromConfig(config.get("max-balance"), 100_000_000);
        int percent = Math.max(0, Math.min(100, config.getInt("transfer-fee-percent", 2)));
        String feeAccount = config.getString("fee-account", "treasury").trim().toLowerCase(Locale.ROOT);
        int pageSize = Math.max(1, config.getInt("history-page-size", 5));
        return new LedgerSettings(currency, starting, max, percent, feeAccount, pageSize);
    }

    public boolean hasFeeAccount() {
        return !feeAccount.isEmpty();
    }

    /** The fee for a transfer of {@code amount} cents, rounded down to the cent. */
    public long feeFor(long amount) {
        return hasFeeAccount() ? amount * feePercent / 100 : 0;
    }

    public String format(long cents) {
        return Money.format(cents, currency);
    }
}
