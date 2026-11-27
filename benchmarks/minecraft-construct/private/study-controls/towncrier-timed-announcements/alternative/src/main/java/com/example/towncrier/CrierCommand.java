package com.example.towncrier;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.OptionalLong;
import java.util.regex.Pattern;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;

/**
 * Handles {@code /crier}. Validation order: subcommand, argument count, permission, group,
 * remaining arguments; the first failure is the only reply.
 */
final class CrierCommand implements CommandExecutor {

    static final String ADMIN_PERMISSION = "towncrier.admin";

    private static final String GENERAL_USAGE =
            "Usage: /crier <list|now|pause|resume|add|remove|interval|preview|reload>";
    private static final String NO_PERMISSION = "You do not have permission to do that.";
    private static final Pattern DIGITS = Pattern.compile("[0-9]+");

    private enum Subcommand {
        LIST(0, 0, "Usage: /crier list"),
        NOW(1, 1, "Usage: /crier now <group>"),
        PAUSE(1, 1, "Usage: /crier pause <group>"),
        RESUME(1, 1, "Usage: /crier resume <group>"),
        ADD(2, Integer.MAX_VALUE, "Usage: /crier add <group> <text...>"),
        REMOVE(2, 2, "Usage: /crier remove <group> <index>"),
        INTERVAL(2, 2, "Usage: /crier interval <group> <seconds>"),
        PREVIEW(2, 2, "Usage: /crier preview <group> <index>"),
        RELOAD(0, 0, "Usage: /crier reload");

        private final int minArgs;
        private final int maxArgs;
        private final String usage;

        Subcommand(int minArgs, int maxArgs, String usage) {
            this.minArgs = minArgs;
            this.maxArgs = maxArgs;
            this.usage = usage;
        }

        boolean accepts(int argumentCount) {
            return argumentCount >= minArgs && argumentCount <= maxArgs;
        }

        /** Every subcommand except {@code list} and {@code reload} starts with a group name. */
        boolean takesGroup() {
            return minArgs > 0;
        }

        static Subcommand lookup(String name) {
            String key = name.toLowerCase(Locale.ROOT);
            for (Subcommand subcommand : values()) {
                if (subcommand.name().toLowerCase(Locale.ROOT).equals(key)) {
                    return subcommand;
                }
            }
            return null;
        }
    }

    private final Crier crier;

    CrierCommand(Crier crier) {
        this.crier = crier;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] rawArgs) {
        // Empty tokens come from repeated spaces; they are not words.
        String[] args = Arrays.stream(rawArgs).filter(arg -> !arg.isEmpty()).toArray(String[]::new);
        Subcommand subcommand = args.length == 0 ? null : Subcommand.lookup(args[0]);
        if (subcommand == null) {
            sender.sendMessage(GENERAL_USAGE);
            return true;
        }
        String[] params = Arrays.copyOfRange(args, 1, args.length);
        if (!subcommand.accepts(params.length)) {
            sender.sendMessage(subcommand.usage);
            return true;
        }
        if (!sender.hasPermission(ADMIN_PERMISSION)) {
            sender.sendMessage(NO_PERMISSION);
            return true;
        }
        if (!subcommand.takesGroup()) {
            switch (subcommand) {
                case LIST -> list(sender);
                case RELOAD -> reload(sender);
                default -> throw new IllegalStateException("Unhandled subcommand " + subcommand);
            }
            return true;
        }
        AnnouncementGroup group = crier.group(params[0]).orElse(null);
        if (group == null) {
            sender.sendMessage("Unknown group: " + params[0]);
            return true;
        }
        switch (subcommand) {
            case NOW -> now(sender, group);
            case PAUSE -> pause(sender, group);
            case RESUME -> resume(sender, group);
            case ADD -> add(sender, group, Arrays.copyOfRange(params, 1, params.length));
            case REMOVE -> remove(sender, group, params[1]);
            case INTERVAL -> interval(sender, group, params[1]);
            case PREVIEW -> preview(sender, group, params[1]);
            default -> throw new IllegalStateException("Unhandled subcommand " + subcommand);
        }
        return true;
    }

    private void list(CommandSender sender) {
        if (crier.groups().isEmpty()) {
            sender.sendMessage("No groups.");
            return;
        }
        List<String> lines = new ArrayList<>();
        lines.add("Groups:");
        for (AnnouncementGroup group : crier.groups()) {
            lines.add(group.name() + ": " + group.messageCount() + " messages every "
                    + group.intervalSeconds() + "s, " + group.order().key() + ", " + state(group));
        }
        lines.forEach(sender::sendMessage);
    }

    private static String state(AnnouncementGroup group) {
        if (!group.enabled()) {
            return "disabled";
        }
        return group.paused() ? "paused" : "running";
    }

    private void reload(CommandSender sender) {
        LoadResult result = crier.reload();
        sender.sendMessage("Loaded " + result.groups().size() + " groups (" + result.disabledCount()
                + " disabled, " + result.skipped().size() + " invalid).");
        for (LoadResult.Skipped skipped : result.skipped()) {
            sender.sendMessage("Skipped " + skipped.name() + ": " + skipped.reason() + ".");
        }
    }

    private void now(CommandSender sender, AnnouncementGroup group) {
        int index = crier.announceNext(group);
        sender.sendMessage("Announced " + group.name() + " #" + index + ".");
    }

    private void pause(CommandSender sender, AnnouncementGroup group) {
        String name = group.name();
        sender.sendMessage(switch (crier.pause(group)) {
            case DONE -> "Paused " + name + ".";
            case UNCHANGED -> name + " is already paused.";
            case DISABLED -> name + " is disabled.";
        });
    }

    private void resume(CommandSender sender, AnnouncementGroup group) {
        String name = group.name();
        sender.sendMessage(switch (crier.resume(group)) {
            case DONE -> "Resumed " + name + ".";
            case UNCHANGED -> name + " is not paused.";
            case DISABLED -> name + " is disabled.";
        });
    }

    private void add(CommandSender sender, AnnouncementGroup group, String[] words) {
        int count = crier.addMessage(group, String.join(" ", words));
        sender.sendMessage("Added message #" + count + " to " + group.name() + ".");
    }

    private void remove(CommandSender sender, AnnouncementGroup group, String argument) {
        OptionalLong index = messageIndex(argument, group);
        if (index.isEmpty()) {
            sender.sendMessage("Invalid index: " + argument);
            return;
        }
        if (group.messageCount() == 1) {
            sender.sendMessage("Cannot remove the last message of " + group.name() + ".");
            return;
        }
        crier.removeMessage(group, (int) index.getAsLong());
        sender.sendMessage("Removed message #" + index.getAsLong() + " from " + group.name() + ".");
    }

    private void interval(CommandSender sender, AnnouncementGroup group, String argument) {
        OptionalLong seconds = wholeNumber(argument);
        if (seconds.isEmpty() || seconds.getAsLong() < 1) {
            sender.sendMessage("Invalid interval: " + argument);
            return;
        }
        crier.setInterval(group, seconds.getAsLong());
        sender.sendMessage("Interval of " + group.name() + " set to " + seconds.getAsLong() + "s.");
    }

    private void preview(CommandSender sender, AnnouncementGroup group, String argument) {
        OptionalLong index = messageIndex(argument, group);
        if (index.isEmpty()) {
            sender.sendMessage("Invalid index: " + argument);
            return;
        }
        sender.sendMessage(crier.render(group, (int) index.getAsLong() - 1));
    }

    /** A 1-based message position of the group, or empty when the argument is not one. */
    private static OptionalLong messageIndex(String argument, AnnouncementGroup group) {
        OptionalLong index = wholeNumber(argument);
        if (index.isEmpty() || index.getAsLong() < 1 || index.getAsLong() > group.messageCount()) {
            return OptionalLong.empty();
        }
        return index;
    }

    /** Plain decimal digits only (no sign, no decimals) that fit in a long. */
    private static OptionalLong wholeNumber(String argument) {
        if (!DIGITS.matcher(argument).matches()) {
            return OptionalLong.empty();
        }
        try {
            return OptionalLong.of(Long.parseLong(argument));
        } catch (NumberFormatException overflow) {
            return OptionalLong.empty();
        }
    }
}
