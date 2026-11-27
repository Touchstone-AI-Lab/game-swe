package com.example.recipesmith;

import java.io.File;
import org.bukkit.command.PluginCommand;
import org.bukkit.plugin.java.JavaPlugin;

public final class RecipesmithPlugin extends JavaPlugin {

    private RecipeBook book;

    @Override
    public void onEnable() {
        if (!new File(getDataFolder(), "recipes.yml").exists()) {
            saveResource("recipes.yml", false);
        }
        book = new RecipeBook(this);
        getServer().getPluginManager().registerEvents(new RecipePermissionListener(this), this);
        RecipeBook.Report report = book.reload();
        report.skipped().forEach(line -> getLogger().warning(line));
        report.unknownVanilla().forEach(line -> getLogger().warning(line));
        PluginCommand command = getCommand("recipes");
        if (command != null) {
            command.setExecutor(new RecipesCommand(this));
        }
    }

    @Override
    public void onDisable() {
        if (book != null) {
            book.clear();
        }
    }

    RecipeBook book() {
        return book;
    }
}
