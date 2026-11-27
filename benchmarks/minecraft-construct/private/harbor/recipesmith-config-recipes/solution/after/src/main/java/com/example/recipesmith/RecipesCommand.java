package com.example.recipesmith;

import java.io.IOException;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.logging.Level;
import org.bukkit.Bukkit;
import org.bukkit.NamespacedKey;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;

/** The /recipes command. */
public final class RecipesCommand implements CommandExecutor {

    private static final String USAGE = "Usage: /recipes <reload|list|disable|enable>";

    private final RecipesmithPlugin plugin;

    public RecipesCommand(RecipesmithPlugin plugin) {
        this.plugin = plugin;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (args.length == 0) {
            sender.sendMessage(USAGE);
            return true;
        }
        String[] rest = Arrays.copyOfRange(args, 1, args.length);
        try {
            switch (args[0].toLowerCase(Locale.ROOT)) {
                case "reload" -> reload(sender, rest);
                case "list" -> list(sender, rest);
                case "disable" -> disable(sender, rest);
                case "enable" -> enable(sender, rest);
                default -> sender.sendMessage(USAGE);
            }
        } catch (RecipeException rejected) {
            sender.sendMessage(rejected.getMessage());
        } catch (IOException failure) {
            plugin.getLogger().log(Level.SEVERE, "Could not save recipes.yml", failure);
        }
        return true;
    }

    private static void check(CommandSender sender, String[] args, int count, String usage) throws RecipeException {
        if (args.length != count) {
            throw new RecipeException(usage);
        }
        if (!sender.hasPermission("recipesmith.admin")) {
            throw new RecipeException("You do not have permission to do that.");
        }
    }

    private void reload(CommandSender sender, String[] args) throws RecipeException {
        check(sender, args, 0, "Usage: /recipes reload");
        RecipeBook.Report report = plugin.book().reload();
        sender.sendMessage("Loaded " + report.loaded() + " recipes, skipped " + report.skipped().size() + ", disabled "
            + report.disabled() + " vanilla recipes.");
        report.skipped().forEach(sender::sendMessage);
        report.unknownVanilla().forEach(sender::sendMessage);
    }

    private void list(CommandSender sender, String[] args) throws RecipeException {
        check(sender, args, 0, "Usage: /recipes list");
        if (plugin.book().loaded().isEmpty()) {
            sender.sendMessage("No recipes.");
            return;
        }
        sender.sendMessage("Recipes (" + plugin.book().loaded().size() + "):");
        for (RecipeParser.Parsed parsed : plugin.book().loaded().values()) {
            sender.sendMessage(parsed.id() + ": " + parsed.type() + " -> " + parsed.result().getAmount() + " "
                + parsed.result().getType().getKey().getKey());
        }
    }

    private void disable(CommandSender sender, String[] args) throws RecipeException, IOException {
        check(sender, args, 1, "Usage: /recipes disable <key>");
        String shown = RecipeBook.display(args[0]);
        NamespacedKey key = RecipeBook.key(args[0]);
        if (key != null && plugin.book().isDisabled(key)) {
            throw new RecipeException(shown + " is already disabled.");
        }
        if (!plugin.book().disableVanilla(args[0])) {
            throw new RecipeException("Unknown vanilla recipe: " + shown);
        }
        List<String> keys = plugin.book().disabledInFile();
        if (!keys.contains(shown)) {
            keys.add(shown);
        }
        plugin.book().saveDisabled(keys);
        Bukkit.updateRecipes();
        sender.sendMessage("Disabled " + shown + ".");
    }

    private void enable(CommandSender sender, String[] args) throws RecipeException, IOException {
        check(sender, args, 1, "Usage: /recipes enable <key>");
        String shown = RecipeBook.display(args[0]);
        NamespacedKey key = RecipeBook.key(args[0]);
        List<String> keys = plugin.book().disabledInFile();
        boolean listed = keys.remove(shown);
        boolean restored = key != null && plugin.book().enableVanilla(key);
        if (!listed && !restored) {
            throw new RecipeException(shown + " is not disabled.");
        }
        plugin.book().saveDisabled(keys);
        Bukkit.updateRecipes();
        sender.sendMessage("Enabled " + shown + ".");
    }
}
