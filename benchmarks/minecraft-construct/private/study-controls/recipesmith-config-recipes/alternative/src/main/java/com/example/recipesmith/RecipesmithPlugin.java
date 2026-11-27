package com.example.recipesmith;

import java.util.Objects;
import org.bukkit.command.PluginCommand;
import org.bukkit.plugin.java.JavaPlugin;

public final class RecipesmithPlugin extends JavaPlugin {
    private RecipeRegistry registry;

    @Override
    public void onEnable() {
        RecipeFile recipeFile = new RecipeFile(this);
        recipeFile.createDefaultIfMissing();

        registry = new RecipeRegistry(this, recipeFile, new RecipeParser(this));
        for (String line : registry.reload().lines()) {
            getLogger().info(line);
        }

        PluginCommand command = Objects.requireNonNull(getCommand("recipes"), "command recipes");
        RecipesCommand handler = new RecipesCommand(registry);
        command.setExecutor(handler);
        command.setTabCompleter(handler);
    }

    @Override
    public void onDisable() {
        if (registry != null) {
            registry.shutdown();
            registry = null;
        }
    }
}
