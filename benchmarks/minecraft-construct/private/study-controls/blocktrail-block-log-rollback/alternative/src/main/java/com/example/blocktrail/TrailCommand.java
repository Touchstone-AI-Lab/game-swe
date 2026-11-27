package com.example.blocktrail;

import java.math.BigInteger;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.function.Supplier;
import java.util.regex.Pattern;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.Server;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabExecutor;

/** {@code /trail lookup|player|rollback|purge|reload}. */
final class TrailCommand implements TabExecutor {

    static final String PERMISSION_LOOKUP = "blocktrail.lookup";
    static final String PERMISSION_ROLLBACK = "blocktrail.rollback";
    static final String PERMISSION_ADMIN = "blocktrail.admin";

    private static final String GENERAL_USAGE = "Usage: /trail <lookup|player|rollback|purge|reload>";
    private static final String NO_PERMISSION = "You do not have permission to do that.";
    private static final String INVALID_COORDINATES = "Invalid coordinates.";
    private static final Pattern WHOLE = Pattern.compile("-?[0-9]+");
    private static final BigInteger THOUSAND = BigInteger.valueOf(1000);

    private enum Sub {
        LOOKUP("lookup", 4, 4, PERMISSION_LOOKUP, "Usage: /trail lookup <world> <x> <y> <z>"),
        PLAYER("player", 1, 2, PERMISSION_LOOKUP, "Usage: /trail player <actor> [page]"),
        ROLLBACK("rollback", 7, 7, PERMISSION_ROLLBACK,
                "Usage: /trail rollback <actor> <world> <x> <y> <z> <radius> <seconds>"),
        PURGE("purge", 1, 1, PERMISSION_ADMIN, "Usage: /trail purge <seconds>"),
        RELOAD("reload", 0, 0, PERMISSION_ADMIN, "Usage: /trail reload");

        private final String name;
        private final int minArgs;
        private final int maxArgs;
        private final String permission;
        private final String usage;

        Sub(String name, int minArgs, int maxArgs, String permission, String usage) {
            this.name = name;
            this.minArgs = minArgs;
            this.maxArgs = maxArgs;
            this.permission = permission;
            this.usage = usage;
        }

        static Sub find(String name) {
            String normalized = name.toLowerCase(Locale.ROOT);
            for (Sub sub : values()) {
                if (sub.name.equals(normalized)) {
                    return sub;
                }
            }
            return null;
        }
    }

    private final BlockTrailPlugin plugin;
    private final ChangeStore store;
    private final Supplier<Settings> settings;

    TrailCommand(BlockTrailPlugin plugin, ChangeStore store, Supplier<Settings> settings) {
        this.plugin = plugin;
        this.store = store;
        this.settings = settings;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        for (String line : run(sender, args)) {
            sender.sendMessage(line);
        }
        return true;
    }

    private List<String> run(CommandSender sender, String[] args) {
        if (args.length == 0) {
            return List.of(GENERAL_USAGE);
        }
        Sub sub = Sub.find(args[0]);
        if (sub == null) {
            return List.of(GENERAL_USAGE);
        }
        int count = args.length - 1;
        if (count < sub.minArgs || count > sub.maxArgs) {
            return List.of(sub.usage);
        }
        if (!sender.hasPermission(sub.permission)) {
            return List.of(NO_PERMISSION);
        }
        return switch (sub) {
            case LOOKUP -> lookup(args);
            case PLAYER -> player(args);
            case ROLLBACK -> rollback(args);
            case PURGE -> purge(args);
            case RELOAD -> reload();
        };
    }

    private List<String> lookup(String[] args) {
        World world = server().getWorld(args[1]);
        if (world == null) {
            return List.of("Unknown world: " + args[1]);
        }
        int[] block = coordinates(args[2], args[3], args[4]);
        if (block == null) {
            return List.of(INVALID_COORDINATES);
        }
        String place = world.getName() + " " + block[0] + " " + block[1] + " " + block[2];
        List<String> lines = new ArrayList<>();
        for (Change change : store.newestFirst()) {
            if (change.isAt(world.getName(), block[0], block[1], block[2])) {
                lines.add(change.describe());
            }
        }
        if (lines.isEmpty()) {
            return List.of("No changes at " + place + ".");
        }
        lines.add(0, "Changes at " + place + ":");
        return lines;
    }

    private List<String> player(String[] args) {
        String actor = args[1];
        BigInteger page = BigInteger.ONE;
        if (args.length == 3) {
            page = whole(args[2]);
            if (page == null || page.signum() < 1) {
                return List.of("Invalid page: " + args[2]);
            }
        }
        List<Change> matches = new ArrayList<>();
        for (Change change : store.newestFirst()) {
            if (change.actor().equalsIgnoreCase(actor)) {
                matches.add(change);
            }
        }
        if (matches.isEmpty()) {
            return List.of("No changes by " + actor + ".");
        }
        int pageSize = settings.get().pageSize();
        int last = (matches.size() + pageSize - 1) / pageSize;
        if (page.compareTo(BigInteger.valueOf(last)) > 0) {
            return List.of("Page " + page + " does not exist; last page is " + last + ".");
        }
        int number = page.intValueExact();
        int start = (number - 1) * pageSize;
        int end = Math.min(start + pageSize, matches.size());
        List<String> lines = new ArrayList<>();
        lines.add("Changes by " + actor + " (page " + number + "/" + last + "):");
        for (Change change : matches.subList(start, end)) {
            lines.add(change.describeWithoutActor());
        }
        return lines;
    }

    private List<String> rollback(String[] args) {
        String actor = args[1];
        World world = server().getWorld(args[2]);
        if (world == null) {
            return List.of("Unknown world: " + args[2]);
        }
        int[] centre = coordinates(args[3], args[4], args[5]);
        if (centre == null) {
            return List.of(INVALID_COORDINATES);
        }
        int maxRadius = settings.get().maxRadius();
        BigInteger radiusValue = whole(args[6]);
        if (radiusValue == null || radiusValue.signum() < 0
                || radiusValue.compareTo(BigInteger.valueOf(maxRadius)) > 0) {
            return List.of("Radius must be a whole number from 0 to " + maxRadius + ".");
        }
        long radius = radiusValue.longValueExact();
        BigInteger seconds = whole(args[7]);
        if (seconds == null || seconds.signum() < 1) {
            return List.of("Invalid time: " + args[7]);
        }
        long cutoff = cutoff(seconds);

        List<Change> qualifying = new ArrayList<>();
        for (Change change : store.newestFirst()) {
            if (!change.rolledBack()
                    && change.actor().equalsIgnoreCase(actor)
                    && change.world().equalsIgnoreCase(world.getName())
                    && Math.abs((long) change.x() - centre[0]) <= radius
                    && Math.abs((long) change.y() - centre[1]) <= radius
                    && Math.abs((long) change.z() - centre[2]) <= radius
                    && change.time() >= cutoff) {
                qualifying.add(change);
            }
        }
        if (qualifying.isEmpty()) {
            return List.of("Nothing to roll back for " + actor + ".");
        }
        List<Change> restored = new ArrayList<>();
        int skipped = 0;
        for (Change change : qualifying) {
            if (restore(world, change)) {
                restored.add(change);
            } else {
                skipped++;
            }
        }
        store.markRolledBack(restored);
        return List.of("Rollback of " + actor + ": " + restored.size() + " restored, "
                + skipped + " skipped.");
    }

    /** Sets the block back to {@code from} when it still holds {@code to}; fires no events. */
    private static boolean restore(World world, Change change) {
        Material from = Materials.fromKey(change.from());
        if (from == null || !from.isBlock()) {
            return false;
        }
        if (change.y() < world.getMinHeight() || change.y() >= world.getMaxHeight()) {
            return false;
        }
        Block block = world.getBlockAt(change.x(), change.y(), change.z());
        if (!Materials.key(block.getType()).equals(change.to())) {
            return false;
        }
        if (change.toData() != null
                && !block.getBlockData().getAsString().equals(change.toData())) {
            return false;
        }
        if (change.fromData() == null) {
            block.setType(from, false);
        } else {
            block.setBlockData(Bukkit.createBlockData(change.fromData()), false);
        }
        return true;
    }

    private List<String> purge(String[] args) {
        BigInteger seconds = whole(args[1]);
        if (seconds == null || seconds.signum() < 1) {
            return List.of("Invalid time: " + args[1]);
        }
        int removed = store.purgeBefore(cutoff(seconds));
        return List.of("Purge complete: " + removed + " removed, " + store.size() + " kept.");
    }

    private List<String> reload() {
        plugin.reloadSettings();
        store.load();
        return List.of("BlockTrail reloaded (changes: " + store.size() + ").");
    }

    private Server server() {
        return plugin.getServer();
    }

    /** Now minus {@code seconds × 1000}, clamped to the range of a millisecond timestamp. */
    private static long cutoff(BigInteger seconds) {
        BigInteger value = BigInteger.valueOf(System.currentTimeMillis())
                .subtract(seconds.multiply(THOUSAND));
        if (value.compareTo(BigInteger.valueOf(Long.MIN_VALUE)) < 0) {
            return Long.MIN_VALUE;
        }
        return value.longValueExact();
    }

    /** Parses an optional minus sign followed by digits, or returns {@code null}. */
    private static BigInteger whole(String text) {
        if (!WHOLE.matcher(text).matches()) {
            return null;
        }
        return new BigInteger(text);
    }

    /** Parses three block coordinates, or returns {@code null} if any is not a whole number. */
    private static int[] coordinates(String x, String y, String z) {
        String[] texts = {x, y, z};
        int[] values = new int[3];
        for (int i = 0; i < 3; i++) {
            BigInteger value = whole(texts[i]);
            if (value == null || value.bitLength() > 31) {
                return null;
            }
            values[i] = value.intValueExact();
        }
        return values;
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        List<String> options = new ArrayList<>();
        if (args.length == 1) {
            for (Sub sub : Sub.values()) {
                options.add(sub.name);
            }
        } else if (args.length >= 2) {
            Sub sub = Sub.find(args[0]);
            boolean worldSlot = (sub == Sub.LOOKUP && args.length == 2)
                    || (sub == Sub.ROLLBACK && args.length == 3);
            if (worldSlot) {
                for (World world : server().getWorlds()) {
                    options.add(world.getName());
                }
            }
        }
        String prefix = args.length == 0 ? "" : args[args.length - 1].toLowerCase(Locale.ROOT);
        options.removeIf(option -> !option.toLowerCase(Locale.ROOT).startsWith(prefix));
        return options;
    }
}
