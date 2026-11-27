package com.example.recipesmith;

import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.inventory.Recipe;

/** A validated recipe entry together with the Bukkit recipe built from it. */
record LoadedRecipe(String id, RecipeKind kind, Material result, int amount, NamespacedKey key, Recipe recipe) {

    /** The {@code list} line: {@code <id>: <type> -> <amount> <result>}. */
    String describe() {
        return id + ": " + kind.configName() + " -> " + amount + " " + Values.materialKey(result);
    }
}
