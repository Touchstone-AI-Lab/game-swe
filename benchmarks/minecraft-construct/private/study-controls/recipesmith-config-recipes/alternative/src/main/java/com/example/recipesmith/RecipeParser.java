package com.example.recipesmith;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
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

/**
 * Validates one entry of the {@code recipes} section and builds its Bukkit recipe. Checks run in
 * the documented order and the first failure is reported.
 */
final class RecipeParser {
    private static final Pattern ID_PATTERN = Pattern.compile("[a-z0-9_]{1,32}");
    private static final int MIN_AMOUNT = 1;
    private static final int MAX_AMOUNT = 64;
    private static final int MAX_SHAPE_SIZE = 3;
    private static final int MAX_SHAPELESS_INGREDIENTS = 9;
    private static final char EMPTY_SLOT = ' ';

    private final Plugin plugin;
    private final MiniMessage miniMessage = MiniMessage.miniMessage();

    RecipeParser(Plugin plugin) {
        this.plugin = plugin;
    }

    LoadedRecipe parse(String id, Object entry) throws InvalidRecipeException {
        if (!ID_PATTERN.matcher(id).matches()) {
            throw new InvalidRecipeException("invalid id");
        }
        ConfigurationSection section = entry instanceof ConfigurationSection s ? s : null;

        Object rawType = value(section, "type");
        RecipeKind kind = rawType == null ? null : RecipeKind.fromConfigName(Values.text(rawType));
        if (kind == null) {
            throw new InvalidRecipeException("unknown type " + Values.written(rawType));
        }

        ConfigurationSection result = subsection(section, "result");
        Object rawMaterial = value(result, "material");
        Material resultMaterial = rawMaterial == null ? null : Values.itemMaterial(Values.text(rawMaterial));
        if (resultMaterial == null) {
            throw new InvalidRecipeException("unknown result material " + Values.written(rawMaterial));
        }
        int amount = amount(value(result, "amount"));

        NamespacedKey key = new NamespacedKey(plugin, id);
        Object rawGroup = value(section, "group");
        String group = rawGroup == null ? null : Values.text(rawGroup);

        ItemStack item = resultItem(resultMaterial, amount, result);

        Recipe recipe = switch (kind) {
            case SHAPED -> shaped(section, key, group, item);
            case SHAPELESS -> shapeless(section, key, group, item);
            case STONECUTTING -> stonecutting(section, key, group, item);
            case SMELTING, SMOKING, BLASTING, CAMPFIRE -> cooking(kind, section, key, group, item);
        };
        return new LoadedRecipe(id, kind, resultMaterial, amount, key, recipe);
    }

    private static int amount(Object raw) throws InvalidRecipeException {
        if (raw == null) {
            return MIN_AMOUNT;
        }
        Long value = Values.wholeNumber(raw);
        if (value == null || value < MIN_AMOUNT || value > MAX_AMOUNT) {
            throw new InvalidRecipeException("amount must be between 1 and 64");
        }
        return value.intValue();
    }

    private Recipe shaped(ConfigurationSection section, NamespacedKey key, String group, ItemStack result)
            throws InvalidRecipeException {
        List<String> rows = shapeRows(value(section, "shape"));
        if (rows == null) {
            throw new InvalidRecipeException("invalid shape");
        }

        Set<Character> symbols = new LinkedHashSet<>();
        for (String row : rows) {
            for (int i = 0; i < row.length(); i++) {
                char symbol = row.charAt(i);
                if (symbol != EMPTY_SLOT) {
                    symbols.add(symbol);
                }
            }
        }

        Map<String, Object> ingredients = new LinkedHashMap<>();
        ConfigurationSection ingredientSection = subsection(section, "ingredients");
        if (ingredientSection != null) {
            for (String symbolKey : ingredientSection.getKeys(false)) {
                ingredients.put(symbolKey, ingredientSection.get(symbolKey));
            }
        }

        for (char symbol : symbols) {
            Object ingredient = ingredients.get(String.valueOf(symbol));
            if (ingredient == null || (ingredient instanceof List<?> list && list.isEmpty())) {
                throw new InvalidRecipeException("no ingredient for " + symbol);
            }
        }
        for (String symbolKey : ingredients.keySet()) {
            if (symbolKey.length() != 1 || !symbols.contains(symbolKey.charAt(0))) {
                throw new InvalidRecipeException("unused ingredient " + symbolKey);
            }
        }

        Map<Character, RecipeChoice> choices = new LinkedHashMap<>();
        for (Map.Entry<String, Object> ingredient : ingredients.entrySet()) {
            choices.put(ingredient.getKey().charAt(0), ingredient(ingredient.getValue()));
        }

        ShapedRecipe recipe = new ShapedRecipe(key, result);
        recipe.shape(rows.toArray(String[]::new));
        choices.forEach(recipe::setIngredient);
        if (group != null) {
            recipe.setGroup(group);
        }
        return recipe;
    }

    /** The rows of a valid shape, or {@code null} when the shape is invalid. */
    private static List<String> shapeRows(Object raw) {
        if (!(raw instanceof List<?> list) || list.isEmpty() || list.size() > MAX_SHAPE_SIZE) {
            return null;
        }
        List<String> rows = new ArrayList<>(list.size());
        boolean hasSlot = false;
        for (Object element : list) {
            if (!(element instanceof String || element instanceof Number
                    || element instanceof Character || element instanceof Boolean)) {
                return null;
            }
            String row = Values.text(element);
            if (row.isEmpty() || row.length() > MAX_SHAPE_SIZE
                    || (!rows.isEmpty() && row.length() != rows.get(0).length())) {
                return null;
            }
            hasSlot |= row.chars().anyMatch(c -> c != EMPTY_SLOT);
            rows.add(row);
        }
        return hasSlot ? rows : null;
    }

    private Recipe shapeless(ConfigurationSection section, NamespacedKey key, String group, ItemStack result)
            throws InvalidRecipeException {
        Object raw = value(section, "ingredients");
        List<?> ingredients = raw instanceof List<?> list ? list : List.of();
        if (ingredients.isEmpty() || ingredients.size() > MAX_SHAPELESS_INGREDIENTS) {
            throw new InvalidRecipeException("shapeless recipes need 1 to 9 ingredients");
        }
        List<RecipeChoice> choices = new ArrayList<>(ingredients.size());
        for (Object ingredient : ingredients) {
            choices.add(ingredient(ingredient));
        }

        ShapelessRecipe recipe = new ShapelessRecipe(key, result);
        choices.forEach(recipe::addIngredient);
        if (group != null) {
            recipe.setGroup(group);
        }
        return recipe;
    }

    private Recipe cooking(RecipeKind kind, ConfigurationSection section, NamespacedKey key, String group,
            ItemStack result) throws InvalidRecipeException {
        RecipeChoice input = ingredient(value(section, "input"));

        float experience = 0.0f;
        Object rawExperience = value(section, "experience");
        if (rawExperience != null) {
            if (!(rawExperience instanceof Number number)) {
                throw new InvalidRecipeException("invalid experience");
            }
            double value = number.doubleValue();
            if (!Double.isFinite(value) || value < 0 || !Float.isFinite((float) value)) {
                throw new InvalidRecipeException("invalid experience");
            }
            experience = (float) value;
        }

        int cookingTime = kind.defaultCookingTime();
        Object rawCookingTime = value(section, "cooking-time");
        if (rawCookingTime != null) {
            Long value = Values.wholeNumber(rawCookingTime);
            if (value == null || value < 1 || value > Integer.MAX_VALUE) {
                throw new InvalidRecipeException("invalid cooking time");
            }
            cookingTime = value.intValue();
        }

        CookingRecipe<?> recipe = switch (kind) {
            case SMELTING -> new FurnaceRecipe(key, result, input, experience, cookingTime);
            case SMOKING -> new SmokingRecipe(key, result, input, experience, cookingTime);
            case BLASTING -> new BlastingRecipe(key, result, input, experience, cookingTime);
            case CAMPFIRE -> new CampfireRecipe(key, result, input, experience, cookingTime);
            default -> throw new IllegalArgumentException("not a cooking type: " + kind);
        };
        if (group != null) {
            recipe.setGroup(group);
        }
        return recipe;
    }

    private Recipe stonecutting(ConfigurationSection section, NamespacedKey key, String group, ItemStack result)
            throws InvalidRecipeException {
        StonecuttingRecipe recipe = new StonecuttingRecipe(key, result, ingredient(value(section, "input")));
        if (group != null) {
            recipe.setGroup(group);
        }
        return recipe;
    }

    /**
     * Parses an ingredient: a material name, a list of material names, or an item tag written
     * {@code #namespace:key}. Materials are checked in order and the first bad one is reported.
     */
    private static RecipeChoice ingredient(Object raw) throws InvalidRecipeException {
        List<Material> materials = new ArrayList<>();
        if (raw instanceof List<?> list) {
            if (list.isEmpty()) {
                throw new InvalidRecipeException("unknown material " + Values.MISSING);
            }
            for (Object element : list) {
                collect(element, materials);
            }
        } else {
            collect(raw, materials);
        }
        return new RecipeChoice.MaterialChoice(materials);
    }

    private static void collect(Object raw, List<Material> materials) throws InvalidRecipeException {
        if (raw == null) {
            throw new InvalidRecipeException("unknown material " + Values.MISSING);
        }
        String written = Values.text(raw);
        if (written.startsWith("#")) {
            materials.addAll(tagValues(written));
            return;
        }
        Material material = Values.itemMaterial(written);
        if (material == null) {
            throw new InvalidRecipeException("unknown material " + written);
        }
        materials.add(material);
    }

    private static Set<Material> tagValues(String written) throws InvalidRecipeException {
        NamespacedKey tagKey = Values.parseKey(written.substring(1));
        Tag<Material> tag = tagKey == null ? null : Bukkit.getTag(Tag.REGISTRY_ITEMS, tagKey, Material.class);
        if (tag == null) {
            throw new InvalidRecipeException("unknown tag " + written);
        }
        Set<Material> values = new LinkedHashSet<>();
        for (Material material : tag.getValues()) {
            if (!material.isAir() && material.isItem()) {
                values.add(material);
            }
        }
        if (values.isEmpty()) {
            throw new InvalidRecipeException("unknown tag " + written);
        }
        return values;
    }

    private ItemStack resultItem(Material material, int amount, ConfigurationSection result) {
        ItemStack item = new ItemStack(material, amount);
        Object rawName = value(result, "name");
        Object rawLore = value(result, "lore");
        if (rawName == null && rawLore == null) {
            return item;
        }
        ItemMeta meta = item.getItemMeta();
        if (meta == null) {
            return item;
        }
        if (rawName != null) {
            meta.displayName(miniMessage(Values.text(rawName)));
        }
        if (rawLore != null) {
            List<Component> lore = new ArrayList<>();
            if (rawLore instanceof List<?> lines) {
                for (Object line : lines) {
                    lore.add(miniMessage(line == null ? "" : Values.text(line)));
                }
            } else {
                lore.add(miniMessage(Values.text(rawLore)));
            }
            if (!lore.isEmpty()) {
                meta.lore(lore);
            }
        }
        item.setItemMeta(meta);
        return item;
    }

    private Component miniMessage(String text) {
        try {
            return miniMessage.deserialize(text);
        } catch (RuntimeException malformed) {
            return Component.text(text);
        }
    }

    private static Object value(ConfigurationSection section, String key) {
        return section == null ? null : section.get(key);
    }

    private static ConfigurationSection subsection(ConfigurationSection section, String key) {
        return value(section, key) instanceof ConfigurationSection child ? child : null;
    }
}
