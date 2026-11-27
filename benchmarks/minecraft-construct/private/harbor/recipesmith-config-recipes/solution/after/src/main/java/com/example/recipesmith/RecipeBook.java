package com.example.recipesmith;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;
import org.bukkit.Bukkit;
import org.bukkit.NamespacedKey;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.inventory.Recipe;
import org.bukkit.inventory.ShapedRecipe;
import org.bukkit.inventory.ShapelessRecipe;

/** The recipes the plugin registered and the vanilla recipes it removed. */
public final class RecipeBook {

    /** What a reload did, for its reply. */
    public record Report(int loaded, List<String> skipped, int disabled, List<String> unknownVanilla) {
    }

    private final RecipesmithPlugin plugin;
    private final File file;
    private final Map<String, RecipeParser.Parsed> loaded = new TreeMap<>();
    /** Removed vanilla recipes by key, in the order they were removed, to be put back exactly. */
    private final Map<NamespacedKey, Recipe> removedVanilla = new LinkedHashMap<>();

    public RecipeBook(RecipesmithPlugin plugin) {
        this.plugin = plugin;
        this.file = new File(plugin.getDataFolder(), "recipes.yml");
    }

    public Map<String, RecipeParser.Parsed> loaded() {
        return loaded;
    }

    public String permission(Recipe recipe) {
        String id = recipe instanceof ShapedRecipe shaped ? shaped.getKey().getKey()
            : recipe instanceof ShapelessRecipe shapeless ? shapeless.getKey().getKey() : null;
        RecipeParser.Parsed parsed = id == null ? null : loaded.get(id);
        return parsed == null ? "" : parsed.permission();
    }

    /** Parses a key the way disabled-vanilla does: the namespace defaults to minecraft. */
    public static NamespacedKey key(String text) {
        return NamespacedKey.fromString(text.trim().toLowerCase(Locale.ROOT));
    }

    public static String display(String text) {
        NamespacedKey key = key(text);
        return key == null ? text : key.toString();
    }

    /** Unregisters everything the plugin changed on the server. */
    public void clear() {
        for (RecipeParser.Parsed parsed : loaded.values()) {
            Bukkit.removeRecipe(new NamespacedKey(plugin, parsed.id()));
        }
        loaded.clear();
        for (Recipe recipe : removedVanilla.values()) {
            Bukkit.addRecipe(recipe);
        }
        removedVanilla.clear();
        Bukkit.updateRecipes();
    }

    public Report reload() {
        clear();
        YamlConfiguration yaml = YamlConfiguration.loadConfiguration(file);
        RecipeParser parser = new RecipeParser(plugin);
        List<String> skipped = new ArrayList<>();
        ConfigurationSection recipes = yaml.getConfigurationSection("recipes");
        if (recipes != null) {
            for (String id : recipes.getKeys(false)) {
                try {
                    RecipeParser.Parsed parsed = parser.parse(id, recipes.getConfigurationSection(id));
                    if (Bukkit.addRecipe(parsed.recipe())) {
                        loaded.put(id, parsed);
                    } else {
                        skipped.add("Skipped " + id + ": the server refused the recipe.");
                    }
                } catch (RecipeException | IllegalArgumentException invalid) {
                    skipped.add("Skipped " + id + ": " + invalid.getMessage() + ".");
                }
            }
        }
        List<String> unknown = new ArrayList<>();
        for (String entry : yaml.getStringList("disabled-vanilla")) {
            if (!disableVanilla(entry)) {
                unknown.add("Unknown vanilla recipe: " + display(entry));
            }
        }
        Bukkit.updateRecipes();
        return new Report(loaded.size(), skipped, removedVanilla.size(), unknown);
    }

    public boolean isDisabled(NamespacedKey key) {
        return removedVanilla.containsKey(key);
    }

    /** Removes an existing minecraft recipe; false when there is no such vanilla recipe. */
    public boolean disableVanilla(String text) {
        NamespacedKey key = key(text);
        if (key == null || !key.getNamespace().equals(NamespacedKey.MINECRAFT) || removedVanilla.containsKey(key)) {
            return key != null && removedVanilla.containsKey(key);
        }
        Recipe recipe = Bukkit.getRecipe(key);
        if (recipe == null) {
            return false;
        }
        removedVanilla.put(key, recipe);
        Bukkit.removeRecipe(key);
        return true;
    }

    /** Puts a removed vanilla recipe back; false when it was not removed by the plugin. */
    public boolean enableVanilla(NamespacedKey key) {
        Recipe recipe = removedVanilla.remove(key);
        if (recipe == null) {
            return false;
        }
        Bukkit.addRecipe(recipe);
        return true;
    }

    /** Rewrites disabled-vanilla, keeping every other key of recipes.yml. */
    public void saveDisabled(List<String> keys) throws IOException {
        YamlConfiguration yaml = YamlConfiguration.loadConfiguration(file);
        yaml.set("disabled-vanilla", keys);
        yaml.save(file);
    }

    public List<String> disabledInFile() {
        List<String> keys = new ArrayList<>();
        for (String entry : YamlConfiguration.loadConfiguration(file).getStringList("disabled-vanilla")) {
            keys.add(display(entry));
        }
        return keys;
    }
}
