package com.example.towncrier;

import java.io.IOException;
import java.util.Arrays;
import java.util.Locale;
import java.util.logging.Level;
import java.util.regex.Pattern;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;

/** The /crier command. */
public final class CrierCommand implements CommandExecutor {

    private static final String USAGE =
        "Usage: /crier <list|now|pause|resume|add|remove|interval|preview|reload>";
    private static final Pattern NUMBER = Pattern.compile("^[0-9]{1,9}$");

    private final TownCrierPlugin plugin;

    public CrierCommand(TownCrierPlugin plugin) {
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
                case "list" -> list(sender, rest);
                case "now" -> now(sender, rest);
                case "pause" -> pause(sender, rest);
                case "resume" -> resume(sender, rest);
                case "add" -> add(sender, rest);
                case "remove" -> remove(sender, rest);
                case "interval" -> interval(sender, rest);
                case "preview" -> preview(sender, rest);
                case "reload" -> reload(sender, rest);
                default -> sender.sendMessage(USAGE);
            }
        } catch (CrierException rejected) {
            sender.sendMessage(rejected.getMessage());
        } catch (IOException failure) {
            plugin.getLogger().log(Level.SEVERE, "Could not save announcements.yml", failure);
        }
        return true;
    }

    private Announcer announcer() {
        return plugin.announcer();
    }

    private static void check(CommandSender sender, String[] args, int min, int max, String usage)
        throws CrierException {
        if (args.length < min || args.length > max) {
            throw new CrierException(usage);
        }
        if (!sender.hasPermission("towncrier.admin")) {
            throw new CrierException("You do not have permission to do that.");
        }
    }

    private Group group(String name) throws CrierException {
        Group group = announcer().group(name);
        if (group == null) {
            throw new CrierException("Unknown group: " + name);
        }
        return group;
    }

    private static int index(Group group, String raw) throws CrierException {
        if (!NUMBER.matcher(raw).matches()) {
            throw new CrierException("Invalid index: " + raw);
        }
        int index = Integer.parseInt(raw);
        if (index < 1 || index > group.messages().size()) {
            throw new CrierException("Invalid index: " + raw);
        }
        return index;
    }

    private void list(CommandSender sender, String[] args) throws CrierException {
        check(sender, args, 0, 0, "Usage: /crier list");
        if (announcer().groups().isEmpty()) {
            sender.sendMessage("No groups.");
            return;
        }
        sender.sendMessage("Groups:");
        for (Group group : announcer().groups()) {
            sender.sendMessage(group.name() + ": " + group.messages().size() + " messages every " + group.interval()
                + "s, " + group.order() + ", " + group.state());
        }
    }

    private void now(CommandSender sender, String[] args) throws CrierException {
        check(sender, args, 1, 1, "Usage: /crier now <group>");
        Group group = group(args[0]);
        int index = announcer().announce(group);
        sender.sendMessage("Announced " + group.name() + " #" + index + ".");
    }

    private void pause(CommandSender sender, String[] args) throws CrierException {
        check(sender, args, 1, 1, "Usage: /crier pause <group>");
        Group group = group(args[0]);
        if (!group.enabled()) {
            throw new CrierException(group.name() + " is disabled.");
        }
        if (group.paused()) {
            throw new CrierException(group.name() + " is already paused.");
        }
        group.pauseTimer();
        group.paused(true);
        sender.sendMessage("Paused " + group.name() + ".");
    }

    private void resume(CommandSender sender, String[] args) throws CrierException {
        check(sender, args, 1, 1, "Usage: /crier resume <group>");
        Group group = group(args[0]);
        if (!group.enabled()) {
            throw new CrierException(group.name() + " is disabled.");
        }
        if (!group.paused()) {
            throw new CrierException(group.name() + " is not paused.");
        }
        group.paused(false);
        announcer().start(group);
        sender.sendMessage("Resumed " + group.name() + ".");
    }

    private void add(CommandSender sender, String[] args) throws CrierException, IOException {
        check(sender, args, 2, Integer.MAX_VALUE, "Usage: /crier add <group> <text...>");
        Group group = group(args[0]);
        group.addMessage(String.join(" ", Arrays.copyOfRange(args, 1, args.length)));
        announcer().save(group);
        sender.sendMessage("Added message #" + group.messages().size() + " to " + group.name() + ".");
    }

    private void remove(CommandSender sender, String[] args) throws CrierException, IOException {
        check(sender, args, 2, 2, "Usage: /crier remove <group> <index>");
        Group group = group(args[0]);
        int index = index(group, args[1]);
        if (group.messages().size() == 1) {
            throw new CrierException("Cannot remove the last message of " + group.name() + ".");
        }
        group.removeMessage(index - 1);
        announcer().save(group);
        sender.sendMessage("Removed message #" + index + " from " + group.name() + ".");
    }

    private void interval(CommandSender sender, String[] args) throws CrierException, IOException {
        check(sender, args, 2, 2, "Usage: /crier interval <group> <seconds>");
        Group group = group(args[0]);
        if (!NUMBER.matcher(args[1]).matches() || Integer.parseInt(args[1]) < 1) {
            throw new CrierException("Invalid interval: " + args[1]);
        }
        group.interval(Integer.parseInt(args[1]));
        announcer().save(group);
        announcer().start(group);
        sender.sendMessage("Interval of " + group.name() + " set to " + group.interval() + "s.");
    }

    private void preview(CommandSender sender, String[] args) throws CrierException {
        check(sender, args, 2, 2, "Usage: /crier preview <group> <index>");
        Group group = group(args[0]);
        int index = index(group, args[1]);
        sender.sendMessage(announcer().render(group, index - 1));
    }

    private void reload(CommandSender sender, String[] args) throws CrierException {
        check(sender, args, 0, 0, "Usage: /crier reload");
        Announcer.LoadReport report = announcer().load();
        sender.sendMessage("Loaded " + report.valid() + " groups (" + report.disabled() + " disabled, "
            + report.skipped().size() + " invalid).");
        for (String line : report.skipped()) {
            sender.sendMessage(line);
        }
    }
}
