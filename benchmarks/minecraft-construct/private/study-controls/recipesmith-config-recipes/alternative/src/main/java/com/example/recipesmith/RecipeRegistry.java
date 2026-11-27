package com.example.recipesmith;

import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.SortedMap;
import java.util.TreeMap;
import java.util.logging.Level;
import org.bukkit.Bukkit;
import org.bukkit.NamespacedKey;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.inventory.Recipe;
import org.bukkit.plugin.java.JavaPlugin;

/**
 * Owns the server-side state of the plugin: the custom recipes it registered and the vanilla
 * recipes it removed (kept so exactly those recipes can be put back).
 */
final class RecipeRegistry {
    private final JavaPlugin plugin;
    private final RecipeFile file;
    private final RecipeParser parser;
    private final SortedMap<String, LoadedRecipe> loaded = new TreeMap<>();
    private final Map<NamespacedKey, Recipe> removedVanilla = new LinkedHashMap<>();

    RecipeRegistry(JavaPlugin plugin, RecipeFile file, RecipeParser parser) {
        this.plugin = plugin;
        this.file = file;
        this.parser = parser;
    }

    /** Undoes every change, re-reads the file and applies it again. */
    ReloadReport reload() {
        unregisterCustomRecipes();
        restoreVanillaRecipes();

        YamlConfiguration config = file.readOrEmpty();
        List<ReloadReport.Skip> skipped = new ArrayList<>();
        ConfigurationSection recipes = config.getConfigurationSection(RecipeFile.RECIPES);
        if (recipes != null) {
            for (String id : recipes.getKeys(false)) {
                try {
                    register(parser.parse(id, recipes.get(id)));
                } catch (InvalidRecipeException invalid) {
                    skipped.add(new ReloadReport.Skip(id, invalid.reason()));
                } catch (RuntimeException unexpected) {
                    plugin.getLogger().log(Level.WARNING, "Could not build recipe " + id, unexpected);
                    skipped.add(new ReloadReport.Skip(id, "the recipe could not be built"));
                }
            }
        }

        List<String> unknownVanilla = new ArrayList<>();
        for (String entry : RecipeFile.disabledVanilla(config)) {
            NamespacedKey key = Values.parseKey(entry);
            if (key != null && removedVanilla.containsKey(key)) {
                continue;
            }
            if (!removeVanilla(key)) {
                unknownVanilla.add(key == null ? entry : key.toString());
            }
        }

        Bukkit.updateRecipes();
        return new ReloadReport(loaded.size(), skipped, removedVanilla.size(), unknownVanilla);
    }

    /** The loaded recipes sorted by id. */
    Collection<LoadedRecipe> loadedRecipes() {
        return List.copyOf(loaded.values());
    }

    /** The vanilla recipes the plugin currently keeps removed, in {@code namespace:key} form. */
    List<String> disabledVanillaKeys() {
        return removedVanilla.keySet().stream().map(NamespacedKey::toString).toList();
    }

    /** Handles {@code /recipes disable <key>} and returns the reply line. */
    String disable(String raw) {
        NamespacedKey key = Values.parseKey(raw);
        String shown = key == null ? raw : key.toString();
        if (key != null && removedVanilla.containsKey(key)) {
            return shown + " is already disabled.";
        }
        if (!removeVanilla(key)) {
            return "Unknown vanilla recipe: " + shown;
        }
        Bukkit.updateRecipes();
        file.updateDisabledVanilla(entries -> {
            if (entries.stream().noneMatch(entry -> key.equals(entryKey(entry)))) {
                entries.add(shown);
            }
        });
        return "Disabled " + shown + ".";
    }

    /** Handles {@code /recipes enable <key>} and returns the reply line. */
    String enable(String raw) {
        NamespacedKey key = Values.parseKey(raw);
        String shown = key == null ? raw : key.toString();
        Recipe recipe = key == null ? null : removedVanilla.remove(key);
        if (recipe == null) {
            return shown + " is not disabled.";
        }
        restore(key, recipe);
        Bukkit.updateRecipes();
        file.updateDisabledVanilla(entries -> entries.removeIf(entry -> key.equals(entryKey(entry))));
        return "Enabled " + shown + ".";
    }

    /** Leaves the server as it was before the plugin changed it. */
    void shutdown() {
        unregisterCustomRecipes();
        restoreVanillaRecipes();
        try {
            Bukkit.updateRecipes();
        } catch (RuntimeException ignored) {
            // The server may already be stopping; nothing is left to resend to.
        }
    }

    private void register(LoadedRecipe recipe) throws InvalidRecipeException {
        boolean added;
        try {
            added = Bukkit.addRecipe(recipe.recipe(), false);
        } catch (RuntimeException failure) {
            plugin.getLogger().log(Level.WARNING, "The server rejected recipe " + recipe.key(), failure);
            added = false;
        }
        if (!added) {
            throw new InvalidRecipeException("the server rejected the recipe");
        }
        loaded.put(recipe.id(), recipe);
    }

    private void unregisterCustomRecipes() {
        for (LoadedRecipe recipe : loaded.values()) {
            Bukkit.removeRecipe(recipe.key(), false);
        }
        loaded.clear();
    }

    /** Removes an existing {@code minecraft} recipe and keeps it; false when there is none. */
    private boolean removeVanilla(NamespacedKey key) {
        if (key == null || !NamespacedKey.MINECRAFT.equals(key.getNamespace())) {
            return false;
        }
        Recipe recipe = Bukkit.getRecipe(key);
        if (recipe == null || !Bukkit.removeRecipe(key, false)) {
            return false;
        }
        removedVanilla.put(key, recipe);
        return true;
    }

    private void restoreVanillaRecipes() {
        removedVanilla.forEach(this::restore);
        removedVanilla.clear();
    }

    private void restore(NamespacedKey key, Recipe recipe) {
        if (Bukkit.getRecipe(key) != null) {
            return;
        }
        try {
            Bukkit.addRecipe(recipe, false);
        } catch (RuntimeException failure) {
            plugin.getLogger().log(Level.WARNING, "Could not put back vanilla recipe " + key, failure);
        }
    }

    private static NamespacedKey entryKey(Object entry) {
        return entry == null ? null : Values.parseKey(Values.text(entry));
    }
}
