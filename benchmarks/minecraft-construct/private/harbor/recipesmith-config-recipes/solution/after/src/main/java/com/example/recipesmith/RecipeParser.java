package com.example.recipesmith;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Pattern;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.minimessage.MiniMessage;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.Tag;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.inventory.BlastingRecipe;
import org.bukkit.inventory.CampfireRecipe;
import org.bukkit.inventory.CookingRecipe;
import org.bukkit.inventory.FurnaceRecipe;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.Recipe;
import org.bukkit.inventory.RecipeChoice;
import org.bukkit.inventory.ShapedRecipe;
import org.bukkit.inventory.ShapelessRecipe;
import org.bukkit.inventory.SmokingRecipe;
import org.bukkit.inventory.StonecuttingRecipe;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.plugin.Plugin;

/** Turns one entry of recipes.yml into a Bukkit recipe, checking it in the documented order. */
public final class RecipeParser {

    /** A registered recipe with what /recipes list shows. */
    public record Parsed(String id, String type, Recipe recipe, ItemStack result, String permission) {
    }

    private static final Pattern ID = Pattern.compile("^[a-z0-9_]{1,32}$");
    private static final List<String> TYPES =
        List.of("shaped", "shapeless", "smelting", "smoking", "blasting", "campfire", "stonecutting");

    private final Plugin plugin;

    public RecipeParser(Plugin plugin) {
        this.plugin = plugin;
    }

    public Parsed parse(String id, ConfigurationSection entry) throws RecipeException {
        if (!ID.matcher(id).matches()) {
            throw new RecipeException("invalid id");
        }
        String type = entry == null ? null : entry.getString("type");
        if (type == null || !TYPES.contains(type)) {
            throw new RecipeException("unknown type " + (type == null ? "none" : type));
        }
        String permission = entry.getString("permission", "").trim();
        if (!permission.isEmpty() && !type.equals("shaped") && !type.equals("shapeless")) {
            throw new RecipeException("permission requires a crafting recipe");
        }
        ItemStack result = result(entry);
        NamespacedKey key = new NamespacedKey(plugin, id);
        Recipe recipe = switch (type) {
            case "shaped" -> shaped(key, result, entry);
            case "shapeless" -> shapeless(key, result, entry);
            case "stonecutting" -> new StonecuttingRecipe(key, result, choice(entry.get("input")));
            default -> cooking(type, key, result, entry);
        };
        String group = entry.getString("group");
        if (group != null) {
            if (recipe instanceof ShapedRecipe shaped) {
                shaped.setGroup(group);
            } else if (recipe instanceof ShapelessRecipe shapeless) {
                shapeless.setGroup(group);
            } else if (recipe instanceof CookingRecipe<?> cooking) {
                cooking.setGroup(group);
            } else if (recipe instanceof StonecuttingRecipe cutting) {
                cutting.setGroup(group);
            }
        }
        return new Parsed(id, type, recipe, result, permission);
    }

    private static ItemStack result(ConfigurationSection entry) throws RecipeException {
        String name = entry.getString("result.material");
        Material material = name == null ? null : Material.matchMaterial(name);
        if (material == null || !material.isItem() || material.isAir()) {
            throw new RecipeException("unknown result material " + (name == null ? "none" : name));
        }
        int amount = entry.getInt("result.amount", 1);
        if (!entry.isInt("result.amount") && entry.contains("result.amount")) {
            amount = 0;
        }
        if (amount < 1 || amount > 64) {
            throw new RecipeException("amount must be between 1 and 64");
        }
        ItemStack stack = new ItemStack(material, amount);
        String display = entry.getString("result.name");
        List<String> lore = entry.getStringList("result.lore");
        if (display != null || !lore.isEmpty()) {
            ItemMeta meta = stack.getItemMeta();
            MiniMessage mini = MiniMessage.miniMessage();
            if (display != null) {
                meta.displayName(mini.deserialize(display));
            }
            if (!lore.isEmpty()) {
                List<Component> lines = new ArrayList<>();
                lore.forEach(line -> lines.add(mini.deserialize(line)));
                meta.lore(lines);
            }
            stack.setItemMeta(meta);
        }
        return stack;
    }

    private static ShapedRecipe shaped(NamespacedKey key, ItemStack result, ConfigurationSection entry)
        throws RecipeException {
        List<String> shape = entry.getStringList("shape");
        if (shape.isEmpty() || shape.size() > 3) {
            throw new RecipeException("invalid shape");
        }
        int width = shape.get(0).length();
        boolean anything = false;
        for (String row : shape) {
            if (row.isEmpty() || row.length() > 3 || row.length() != width) {
                throw new RecipeException("invalid shape");
            }
            anything |= !row.isBlank();
        }
        if (!anything) {
            throw new RecipeException("invalid shape");
        }
        ConfigurationSection ingredients = entry.getConfigurationSection("ingredients");
        Set<String> keys = ingredients == null ? Set.of() : ingredients.getKeys(false);
        Set<Character> used = new LinkedHashSet<>();
        for (String row : shape) {
            for (char c : row.toCharArray()) {
                if (c != ' ') {
                    used.add(c);
                }
            }
        }
        for (char c : used) {
            if (!keys.contains(String.valueOf(c))) {
                throw new RecipeException("no ingredient for " + c);
            }
        }
        for (String ingredientKey : keys) {
            if (ingredientKey.length() != 1 || !used.contains(ingredientKey.charAt(0))) {
                throw new RecipeException("unused ingredient " + ingredientKey);
            }
        }
        ShapedRecipe recipe = new ShapedRecipe(key, result);
        recipe.shape(shape.toArray(String[]::new));
        for (String ingredientKey : keys) {
            recipe.setIngredient(ingredientKey.charAt(0), choice(ingredients.get(ingredientKey)));
        }
        return recipe;
    }

    private static ShapelessRecipe shapeless(NamespacedKey key, ItemStack result, ConfigurationSection entry)
        throws RecipeException {
        List<?> ingredients = entry.getList("ingredients", List.of());
        if (ingredients.isEmpty() || ingredients.size() > 9) {
            throw new RecipeException("shapeless recipes need 1 to 9 ingredients");
        }
        List<RecipeChoice> choices = new ArrayList<>();
        for (Object ingredient : ingredients) {
            choices.add(choice(ingredient));
        }
        ShapelessRecipe recipe = new ShapelessRecipe(key, result);
        choices.forEach(recipe::addIngredient);
        return recipe;
    }

    private static Recipe cooking(String type, NamespacedKey key, ItemStack result, ConfigurationSection entry)
        throws RecipeException {
        RecipeChoice input = choice(entry.get("input"));
        float experience = 0;
        if (entry.contains("experience")) {
            if (!entry.isDouble("experience") && !entry.isInt("experience") || entry.getDouble("experience") < 0) {
                throw new RecipeException("invalid experience");
            }
            experience = (float) entry.getDouble("experience");
        }
        int defaultTime = switch (type) {
            case "smelting" -> 200;
            case "campfire" -> 600;
            default -> 100;
        };
        int time = defaultTime;
        if (entry.contains("cooking-time")) {
            if (!entry.isInt("cooking-time") || entry.getInt("cooking-time") < 1) {
                throw new RecipeException("invalid cooking time");
            }
            time = entry.getInt("cooking-time");
        }
        return switch (type) {
            case "smelting" -> new FurnaceRecipe(key, result, input, experience, time);
            case "smoking" -> new SmokingRecipe(key, result, input, experience, time);
            case "blasting" -> new BlastingRecipe(key, result, input, experience, time);
            default -> new CampfireRecipe(key, result, input, experience, time);
        };
    }

    /** One ingredient: a material, a list of materials or an item tag. */
    private static RecipeChoice choice(Object value) throws RecipeException {
        List<Material> materials = new ArrayList<>();
        List<Object> parts = value instanceof List<?> list ? new ArrayList<>(list) : List.of(String.valueOf(value));
        if (value == null || parts.isEmpty()) {
            throw new RecipeException("unknown material " + (value == null ? "none" : "[]"));
        }
        for (Object part : parts) {
            String text = String.valueOf(part).trim();
            if (text.startsWith("#")) {
                NamespacedKey tagKey = NamespacedKey.fromString(text.substring(1).toLowerCase(Locale.ROOT));
                Tag<Material> tag = tagKey == null ? null : Bukkit.getTag(Tag.REGISTRY_ITEMS, tagKey, Material.class);
                if (tag == null) {
                    throw new RecipeException("unknown tag " + text);
                }
                materials.addAll(tag.getValues());
            } else {
                Material material = Material.matchMaterial(text);
                if (material == null || !material.isItem() || material.isAir()) {
                    throw new RecipeException("unknown material " + text);
                }
                materials.add(material);
            }
        }
        return new RecipeChoice.MaterialChoice(materials);
    }
}
