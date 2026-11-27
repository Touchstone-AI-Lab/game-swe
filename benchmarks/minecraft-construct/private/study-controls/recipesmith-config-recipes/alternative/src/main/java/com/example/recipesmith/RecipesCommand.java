package com.example.recipesmith;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import net.kyori.adventure.text.Component;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabExecutor;

/** {@code /recipes <reload|list|disable|enable>}. */
final class RecipesCommand implements TabExecutor {
    static final String PERMISSION = "recipesmith.admin";

    private static final String GENERAL_USAGE = "Usage: /recipes <reload|list|disable|enable>";
    private static final String NO_PERMISSION = "You do not have permission to do that.";

    private enum Subcommand {
        RELOAD("reload", 0, "Usage: /recipes reload"),
        LIST("list", 0, "Usage: /recipes list"),
        DISABLE("disable", 1, "Usage: /recipes disable <key>"),
        ENABLE("enable", 1, "Usage: /recipes enable <key>");

        private final String label;
        private final int arguments;
        private final String usage;

        Subcommand(String label, int arguments, String usage) {
            this.label = label;
            this.arguments = arguments;
            this.usage = usage;
        }

        static Subcommand byLabel(String label) {
            String lower = label.toLowerCase(Locale.ROOT);
            for (Subcommand subcommand : values()) {
                if (subcommand.label.equals(lower)) {
                    return subcommand;
                }
            }
            return null;
        }
    }

    private final RecipeRegistry registry;

    RecipesCommand(RecipeRegistry registry) {
        this.registry = registry;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        for (String line : reply(sender, args)) {
            sender.sendMessage(Component.text(line));
        }
        return true;
    }

    private List<String> reply(CommandSender sender, String[] args) {
        Subcommand subcommand = args.length == 0 ? null : Subcommand.byLabel(args[0]);
        if (subcommand == null) {
            return List.of(GENERAL_USAGE);
        }
        if (args.length != subcommand.arguments + 1) {
            return List.of(subcommand.usage);
        }
        if (!sender.hasPermission(PERMISSION)) {
            return List.of(NO_PERMISSION);
        }
        return switch (subcommand) {
            case RELOAD -> registry.reload().lines();
            case LIST -> list();
            case DISABLE -> List.of(registry.disable(args[1]));
            case ENABLE -> List.of(registry.enable(args[1]));
        };
    }

    private List<String> list() {
        var recipes = registry.loadedRecipes();
        if (recipes.isEmpty()) {
            return List.of("No recipes.");
        }
        List<String> lines = new ArrayList<>(recipes.size() + 1);
        lines.add("Recipes (" + recipes.size() + "):");
        for (LoadedRecipe recipe : recipes) {
            lines.add(recipe.describe());
        }
        return lines;
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (!sender.hasPermission(PERMISSION)) {
            return List.of();
        }
        if (args.length == 1) {
            List<String> labels = new ArrayList<>();
            for (Subcommand subcommand : Subcommand.values()) {
                labels.add(subcommand.label);
            }
            return matching(labels, args[0]);
        }
        if (args.length == 2 && Subcommand.byLabel(args[0]) == Subcommand.ENABLE) {
            return matching(registry.disabledVanillaKeys(), args[1]);
        }
        return List.of();
    }

    private static List<String> matching(List<String> options, String prefix) {
        String lower = prefix.toLowerCase(Locale.ROOT);
        return options.stream().filter(option -> option.startsWith(lower)).toList();
    }
}
