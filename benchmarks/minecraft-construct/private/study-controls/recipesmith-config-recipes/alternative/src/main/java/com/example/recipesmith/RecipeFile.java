package com.example.recipesmith;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Consumer;
import java.util.logging.Level;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.plugin.java.JavaPlugin;

/** Reads and rewrites {@code plugins/Recipesmith/recipes.yml}. */
final class RecipeFile {
    static final String FILE_NAME = "recipes.yml";
    static final String RECIPES = "recipes";
    static final String DISABLED_VANILLA = "disabled-vanilla";

    /**
     * Keys are read literally: a recipe id containing a dot must stay one key (and fail the id
     * check) rather than become a nested section, so the path separator is a character that
     * cannot appear in a YAML key written by hand.
     */
    private static final char PATH_SEPARATOR = '\0';

    private final JavaPlugin plugin;
    private final File file;

    RecipeFile(JavaPlugin plugin) {
        this.plugin = plugin;
        this.file = new File(plugin.getDataFolder(), FILE_NAME);
    }

    /** Writes the bundled default file when the data folder has none. */
    void createDefaultIfMissing() {
        if (!file.exists()) {
            plugin.saveResource(FILE_NAME, false);
        }
    }

    /** Reads the file; a missing or unreadable file reads as an empty configuration. */
    YamlConfiguration readOrEmpty() {
        try {
            return read();
        } catch (IOException | InvalidConfigurationException failure) {
            plugin.getLogger().log(Level.WARNING, "Could not read " + file + "; no recipes are loaded", failure);
            return newConfiguration();
        }
    }

    /**
     * Rewrites the {@code disabled-vanilla} list, keeping the recipes and every other key of the
     * file as it is on disk.
     */
    void updateDisabledVanilla(Consumer<List<Object>> change) {
        YamlConfiguration config;
        try {
            config = read();
        } catch (IOException | InvalidConfigurationException failure) {
            plugin.getLogger().log(Level.WARNING, "Could not read " + file + "; it was not rewritten", failure);
            return;
        }
        List<Object> entries = new ArrayList<>(rawDisabledVanilla(config));
        change.accept(entries);
        config.set(DISABLED_VANILLA, entries);
        try {
            config.save(file);
        } catch (IOException failure) {
            plugin.getLogger().log(Level.SEVERE, "Could not write " + file, failure);
        }
    }

    /** The {@code disabled-vanilla} entries as written, skipping empty items. */
    static List<String> disabledVanilla(YamlConfiguration config) {
        List<String> entries = new ArrayList<>();
        for (Object entry : rawDisabledVanilla(config)) {
            if (entry != null) {
                entries.add(Values.text(entry));
            }
        }
        return entries;
    }

    private static List<?> rawDisabledVanilla(YamlConfiguration config) {
        Object raw = config.get(DISABLED_VANILLA);
        if (raw instanceof List<?> list) {
            return list;
        }
        return raw == null ? List.of() : List.of(raw);
    }

    private YamlConfiguration read() throws IOException, InvalidConfigurationException {
        YamlConfiguration config = newConfiguration();
        if (file.exists()) {
            config.load(file);
        }
        return config;
    }

    private static YamlConfiguration newConfiguration() {
        YamlConfiguration config = new YamlConfiguration();
        config.options().pathSeparator(PATH_SEPARATOR);
        return config;
    }
}
