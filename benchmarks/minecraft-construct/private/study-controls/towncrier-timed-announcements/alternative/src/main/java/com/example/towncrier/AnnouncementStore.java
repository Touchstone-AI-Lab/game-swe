package com.example.towncrier;

import java.io.File;
import java.io.IOException;
import java.math.BigInteger;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.OptionalLong;
import java.util.logging.Level;
import java.util.regex.Pattern;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.plugin.java.JavaPlugin;

/**
 * Reads, validates and rewrites {@code plugins/TownCrier/announcements.yml}.
 *
 * <p>The document read by the last {@link #load()} is kept in memory so that an edit rewrites
 * the file with only the changed key replaced and everything else (the prefix, other groups,
 * invalid groups, unknown keys) preserved.
 */
final class AnnouncementStore {

    static final String FILE_NAME = "announcements.yml";

    static final String REASON_NAME = "invalid name";
    static final String REASON_INTERVAL = "interval must be a whole number of at least 1";
    static final String REASON_ORDER = "order must be sequential or shuffle";
    static final String REASON_MESSAGES = "no messages";

    private static final String KEY_PREFIX = "prefix";
    private static final String KEY_GROUPS = "groups";
    private static final String KEY_ENABLED = "enabled";
    private static final String KEY_INTERVAL = "interval";
    private static final String KEY_ORDER = "order";
    private static final String KEY_PERMISSION = "permission";
    private static final String KEY_MESSAGES = "messages";

    /**
     * YAML keys are used literally. With Bukkit's default '.' separator a key such as
     * {@code bad.name} would silently turn into nested sections instead of one invalid group.
     */
    private static final char PATH_SEPARATOR = '\u0000';

    /** Keeps every saved message on one line instead of folding long strings. */
    private static final int YAML_WIDTH = 1 << 20;

    private static final Pattern GROUP_NAME = Pattern.compile("[a-z0-9_-]{1,32}");

    private final JavaPlugin plugin;
    private final File file;
    private YamlConfiguration document = emptyDocument();

    AnnouncementStore(JavaPlugin plugin) {
        this.plugin = plugin;
        this.file = new File(plugin.getDataFolder(), FILE_NAME);
    }

    /** Writes the bundled default file when none exists yet. */
    void writeDefaultIfMissing() {
        if (!file.exists()) {
            plugin.saveResource(FILE_NAME, false);
        }
    }

    /** Re-reads the file and validates every group in file order. */
    LoadResult load() {
        YamlConfiguration loaded = emptyDocument();
        if (file.exists()) {
            try {
                loaded.load(file);
            } catch (IOException | InvalidConfigurationException | RuntimeException e) {
                plugin.getLogger().log(Level.SEVERE, "Could not read " + FILE_NAME + "; no group is loaded", e);
                loaded = emptyDocument();
            }
        }
        document = loaded;

        String prefix = loaded.getString(KEY_PREFIX, "");
        List<GroupDefinition> groups = new ArrayList<>();
        List<LoadResult.Skipped> skipped = new ArrayList<>();
        ConfigurationSection groupsSection = loaded.getConfigurationSection(KEY_GROUPS);
        if (groupsSection != null) {
            for (String name : groupsSection.getKeys(false)) {
                ConfigurationSection section = groupsSection.getConfigurationSection(name);
                String reason = firstFailure(name, section);
                if (reason != null) {
                    skipped.add(new LoadResult.Skipped(name, reason));
                } else {
                    groups.add(toDefinition(name, section));
                }
            }
        }
        return new LoadResult(prefix, groups, skipped);
    }

    /** Rewrites the file with the group's current message list. */
    void saveMessages(AnnouncementGroup group) {
        groupSection(group.name()).set(KEY_MESSAGES, new ArrayList<>(group.messages()));
        save();
    }

    /** Rewrites the file with the group's current interval. */
    void saveInterval(AnnouncementGroup group) {
        long seconds = group.intervalSeconds();
        Object value = seconds <= Integer.MAX_VALUE ? Integer.valueOf((int) seconds) : Long.valueOf(seconds);
        groupSection(group.name()).set(KEY_INTERVAL, value);
        save();
    }

    private void save() {
        try {
            document.save(file);
        } catch (IOException e) {
            plugin.getLogger().log(Level.SEVERE, "Could not write " + file, e);
        }
    }

    private ConfigurationSection groupSection(String name) {
        ConfigurationSection groups = document.getConfigurationSection(KEY_GROUPS);
        ConfigurationSection section = groups == null ? null : groups.getConfigurationSection(name);
        if (section == null) {
            throw new IllegalStateException("Group " + name + " is not part of the loaded document");
        }
        return section;
    }

    /** Returns the reason of the first failed check, or {@code null} when the group is valid. */
    private static String firstFailure(String name, ConfigurationSection section) {
        if (!GROUP_NAME.matcher(name).matches()) {
            return REASON_NAME;
        }
        if (section == null) {
            return REASON_INTERVAL;
        }
        OptionalLong interval = wholeNumber(section.get(KEY_INTERVAL));
        if (interval.isEmpty() || interval.getAsLong() < 1) {
            return REASON_INTERVAL;
        }
        if (order(section).isEmpty()) {
            return REASON_ORDER;
        }
        if (section.getStringList(KEY_MESSAGES).isEmpty()) {
            return REASON_MESSAGES;
        }
        return null;
    }

    private static GroupDefinition toDefinition(String name, ConfigurationSection section) {
        return new GroupDefinition(
                name,
                section.getBoolean(KEY_ENABLED, true),
                wholeNumber(section.get(KEY_INTERVAL)).orElseThrow(),
                order(section).orElseThrow(),
                section.getString(KEY_PERMISSION, ""),
                section.getStringList(KEY_MESSAGES));
    }

    private static Optional<GroupOrder> order(ConfigurationSection section) {
        Object raw = section.get(KEY_ORDER);
        if (raw == null) {
            return Optional.of(GroupOrder.SEQUENTIAL);
        }
        return raw instanceof String text ? GroupOrder.fromKey(text) : Optional.empty();
    }

    /** Accepts YAML integers only; decimals, strings and other values are not whole numbers. */
    private static OptionalLong wholeNumber(Object raw) {
        if (raw instanceof Integer || raw instanceof Long || raw instanceof Short || raw instanceof Byte) {
            return OptionalLong.of(((Number) raw).longValue());
        }
        if (raw instanceof BigInteger big && big.bitLength() < Long.SIZE) {
            return OptionalLong.of(big.longValue());
        }
        return OptionalLong.empty();
    }

    private static YamlConfiguration emptyDocument() {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.options().pathSeparator(PATH_SEPARATOR).width(YAML_WIDTH);
        return yaml;
    }
}
