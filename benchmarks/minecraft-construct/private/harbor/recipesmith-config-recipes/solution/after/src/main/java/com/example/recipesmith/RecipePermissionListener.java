package com.example.recipesmith;

import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.PrepareItemCraftEvent;

/** Hides a permission-gated recipe from players who cannot craft it. */
public final class RecipePermissionListener implements Listener {

    private final RecipesmithPlugin plugin;

    public RecipePermissionListener(RecipesmithPlugin plugin) {
        this.plugin = plugin;
    }

    @EventHandler
    public void onPrepare(PrepareItemCraftEvent event) {
        String permission = plugin.book().permission(event.getRecipe());
        if (!permission.isEmpty() && !event.getView().getPlayer().hasPermission(permission)) {
            event.getInventory().setResult(null);
        }
    }
}
