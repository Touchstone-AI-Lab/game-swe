package com.example.blocktrail;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.logging.Level;
import java.util.regex.Pattern;
import org.bukkit.Bukkit;
import org.bukkit.block.data.BlockData;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;

/** The /trail command. */
public final class TrailCommand implements CommandExecutor {

    private static final String USAGE = "Usage: /trail <lookup|player|rollback|purge|reload>";
    private static final Pattern COORDINATE = Pattern.compile("^-?[0-9]{1,9}$");
    private static final Pattern NUMBER = Pattern.compile("^[0-9]{1,9}$");

    private final BlockTrailPlugin plugin;

    public TrailCommand(BlockTrailPlugin plugin) {
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
                case "lookup" -> lookup(sender, rest);
                case "player" -> player(sender, rest);
                case "rollback" -> rollback(sender, rest);
                case "purge" -> purge(sender, rest);
                case "reload" -> reload(sender, rest);
                default -> sender.sendMessage(USAGE);
            }
        } catch (TrailException rejected) {
            sender.sendMessage(rejected.getMessage());
        } catch (IOException failure) {
            plugin.getLogger().log(Level.SEVERE, "Could not write changes.log", failure);
        }
        return true;
    }

    private static void arity(String[] args, int min, int max, String usage) throws TrailException {
        if (args.length < min || args.length > max) {
            throw new TrailException(usage);
        }
    }

    private static void permission(CommandSender sender, String permission) throws TrailException {
        if (!sender.hasPermission(permission)) {
            throw new TrailException("You do not have permission to do that.");
        }
    }

    private static World world(String name) throws TrailException {
        World world = Bukkit.getWorld(name);
        if (world == null) {
            throw new TrailException("Unknown world: " + name);
        }
        return world;
    }

    private static int[] coordinates(String[] args, int offset) throws TrailException {
        int[] values = new int[3];
        for (int i = 0; i < 3; i++) {
            String raw = args[offset + i];
            if (!COORDINATE.matcher(raw).matches()) {
                throw new TrailException("Invalid coordinates.");
            }
            values[i] = Integer.parseInt(raw);
        }
        return values;
    }

    private static int positive(String raw, String message) throws TrailException {
        if (!NUMBER.matcher(raw).matches() || Integer.parseInt(raw) < 1) {
            throw new TrailException(message + raw);
        }
        return Integer.parseInt(raw);
    }

    private static List<Change> newestFirst(List<Change> changes) {
        List<Change> sorted = new ArrayList<>(changes);
        sorted.sort(Comparator.comparingLong(Change::id).reversed());
        return sorted;
    }

    private void lookup(CommandSender sender, String[] args) throws TrailException {
        arity(args, 4, 4, "Usage: /trail lookup <world> <x> <y> <z>");
        permission(sender, "blocktrail.lookup");
        World world = world(args[0]);
        int[] at = coordinates(args, 1);
        String where = world.getName() + " " + at[0] + " " + at[1] + " " + at[2];
        List<Change> found = new ArrayList<>();
        for (Change change : plugin.store().all()) {
            if (change.at(world.getName(), at[0], at[1], at[2])) {
                found.add(change);
            }
        }
        if (found.isEmpty()) {
            sender.sendMessage("No changes at " + where + ".");
            return;
        }
        sender.sendMessage("Changes at " + where + ":");
        for (Change change : newestFirst(found)) {
            sender.sendMessage(change.describeAtBlock());
        }
    }

    private void player(CommandSender sender, String[] args) throws TrailException {
        arity(args, 1, 2, "Usage: /trail player <actor> [page]");
        permission(sender, "blocktrail.lookup");
        String actor = args[0];
        int page = args.length == 2 ? positive(args[1], "Invalid page: ") : 1;
        List<Change> found = new ArrayList<>();
        for (Change change : plugin.store().all()) {
            if (change.actor().equalsIgnoreCase(actor)) {
                found.add(change);
            }
        }
        if (found.isEmpty()) {
            sender.sendMessage("No changes by " + actor + ".");
            return;
        }
        int size = plugin.settings().pageSize();
        int last = (found.size() + size - 1) / size;
        if (page > last) {
            throw new TrailException("Page " + page + " does not exist; last page is " + last + ".");
        }
        List<Change> sorted = newestFirst(found);
        sender.sendMessage("Changes by " + actor + " (page " + page + "/" + last + "):");
        for (Change change : sorted.subList((page - 1) * size, Math.min(sorted.size(), page * size))) {
            sender.sendMessage(change.describeForActor());
        }
    }

    private void rollback(CommandSender sender, String[] args) throws TrailException, IOException {
        arity(args, 7, 7, "Usage: /trail rollback <actor> <world> <x> <y> <z> <radius> <seconds>");
        permission(sender, "blocktrail.rollback");
        String actor = args[0];
        World world = world(args[1]);
        int[] centre = coordinates(args, 2);
        int max = plugin.settings().maxRadius();
        String rawRadius = args[5];
        if (!NUMBER.matcher(rawRadius).matches() || Integer.parseInt(rawRadius) > max) {
            throw new TrailException("Radius must be a whole number from 0 to " + max + ".");
        }
        int radius = Integer.parseInt(rawRadius);
        int seconds = positive(args[6], "Invalid time: ");
        long cutoff = System.currentTimeMillis() - seconds * 1000L;
        List<Change> candidates = new ArrayList<>();
        for (Change change : plugin.store().all()) {
            if (!change.rolledBack() && change.actor().equalsIgnoreCase(actor)
                && change.world().equals(world.getName()) && change.time() >= cutoff
                && Math.abs(change.x() - centre[0]) <= radius && Math.abs(change.y() - centre[1]) <= radius
                && Math.abs(change.z() - centre[2]) <= radius) {
                candidates.add(change);
            }
        }
        if (candidates.isEmpty()) {
            sender.sendMessage("Nothing to roll back for " + actor + ".");
            return;
        }
        int restored = 0;
        int skipped = 0;
        for (Change change : newestFirst(candidates)) {
            Block block = world.getBlockAt(change.x(), change.y(), change.z());
            if (block.getType() == change.to()
                && (change.toData() == null || block.getBlockData().getAsString().equals(change.toData()))) {
                block.setType(change.from(), false);
                if (change.fromData() != null) {
                    BlockData original = Bukkit.createBlockData(change.fromData());
                    block.setBlockData(original, false);
                }
                plugin.store().markRolledBack(change);
                restored++;
            } else {
                skipped++;
            }
        }
        sender.sendMessage("Rollback of " + actor + ": " + restored + " restored, " + skipped + " skipped.");
    }

    private void purge(CommandSender sender, String[] args) throws TrailException, IOException {
        arity(args, 1, 1, "Usage: /trail purge <seconds>");
        permission(sender, "blocktrail.admin");
        int seconds = positive(args[0], "Invalid time: ");
        int removed = plugin.store().purgeBefore(System.currentTimeMillis() - seconds * 1000L);
        sender.sendMessage("Purge complete: " + removed + " removed, " + plugin.store().size() + " kept.");
    }

    private void reload(CommandSender sender, String[] args) throws TrailException, IOException {
        arity(args, 0, 0, "Usage: /trail reload");
        permission(sender, "blocktrail.admin");
        plugin.reloadTrail();
        sender.sendMessage("BlockTrail reloaded (changes: " + plugin.store().size() + ").");
    }
}
