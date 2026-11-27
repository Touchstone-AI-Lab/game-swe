package com.example.coinledger;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.logging.Logger;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;

/**
 * The values of {@code config.yml}. Money values are whole cents; an empty
 * {@code feeAccount} means there is no fee account.
 */
record Settings(String currency, long startingBalance, long maxBalance, int transferFeePercent,
                String feeAccount, int historyPageSize) {

    static final Settings DEFAULTS = new Settings("coins", 10_000L, 100_000_000L, 2, "treasury", 5);

    boolean hasFeeAccount() {
        return !feeAccount.isEmpty();
    }

    String format(long cents) {
        return Money.format(cents, currency);
    }

    /**
     * Reads {@code config.yml}. A missing file, a missing key or an out-of-range value falls
     * back to the default for that key (with a warning for invalid values).
     */
    static Settings load(Path file, Logger logger) {
        YamlConfiguration yaml = new YamlConfiguration();
        if (Files.isRegularFile(file)) {
            try {
                yaml.load(file.toFile());
            } catch (IOException | InvalidConfigurationException e) {
                logger.warning("Cannot read " + file.getFileName() + ", using defaults: "
                        + e.getMessage());
            }
        }
        Reader reader = new Reader(yaml, logger);
        return new Settings(
                reader.currency(),
                reader.cents("starting-balance", DEFAULTS.startingBalance()),
                reader.cents("max-balance", DEFAULTS.maxBalance()),
                (int) reader.whole("transfer-fee-percent", 0, 100, DEFAULTS.transferFeePercent()),
                reader.feeAccount(),
                (int) reader.whole("history-page-size", 1, Integer.MAX_VALUE,
                        DEFAULTS.historyPageSize()));
    }

    private record Reader(YamlConfiguration yaml, Logger logger) {

        String currency() {
            Object value = yaml.get("currency");
            if (value == null || value instanceof ConfigurationSection) {
                return DEFAULTS.currency();
            }
            return value.toString();
        }

        long cents(String key, long fallback) {
            Object value = yaml.get(key);
            if (value == null) {
                return fallback;
            }
            Long cents = Money.settingCents(value);
            if (cents == null) {
                return invalid(key, value, fallback);
            }
            return cents;
        }

        long whole(String key, long min, long max, long fallback) {
            Object value = yaml.get(key);
            if (value == null) {
                return fallback;
            }
            Long number = Money.wholeNumber(value);
            if (number == null || number < min || number > max) {
                return invalid(key, value, fallback);
            }
            return number;
        }

        String feeAccount() {
            Object value = yaml.get("fee-account");
            if (value == null || value instanceof ConfigurationSection) {
                return DEFAULTS.feeAccount();
            }
            String name = value.toString().trim();
            if (name.isEmpty()) {
                return "";
            }
            if (!Account.isValidName(name)) {
                logger.warning("Invalid fee-account '" + name + "', using '"
                        + DEFAULTS.feeAccount() + "'.");
                return DEFAULTS.feeAccount();
            }
            return Account.normalize(name);
        }

        private long invalid(String key, Object value, long fallback) {
            logger.warning("Invalid " + key + " '" + value + "', using the default.");
            return fallback;
        }
    }
}
