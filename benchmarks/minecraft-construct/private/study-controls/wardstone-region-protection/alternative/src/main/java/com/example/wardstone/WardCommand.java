package com.example.wardstone;

import java.math.BigInteger;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.StringJoiner;
import java.util.regex.Pattern;
import org.bukkit.World;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;

/**
 * The {@code /ward} command. Checks run in a fixed order: the subcommand, the
 * argument count, the {@code wardstone.admin} permission, then each argument from
 * left to right. The first failing check produces the only reply.
 */
final class WardCommand implements CommandExecutor {
    static final String ADMIN_PERMISSION = "wardstone.admin";

    private static final String NO_PERMISSION = "You do not have permission to do that.";
    private static final String INVALID_COORDINATES = "Invalid coordinates.";
    private static final Pattern WHOLE_NUMBER = Pattern.compile("-?[0-9]+");

    private enum Subcommand {
        DEFINE("<region> <world> <x1> <y1> <z1> <x2> <y2> <z2>"),
        DELETE("<region>"),
        PRIORITY("<region> <priority>"),
        FLAG("<region> <flag> <allow|deny|clear>"),
        ADDOWNER("<region> <player>"),
        REMOVEOWNER("<region> <player>"),
        ADDMEMBER("<region> <player>"),
        REMOVEMEMBER("<region> <player>"),
        INFO("<region>"),
        AT("<world> <x> <y> <z>"),
        LIST(""),
        RELOAD("");

        private final String parameters;
        private final int arity;

        Subcommand(String parameters) {
            this.parameters = parameters;
            this.arity = parameters.isEmpty() ? 0 : parameters.split(" ").length;
        }

        String label() {
            return name().toLowerCase(Locale.ROOT);
        }

        String usage() {
            return "Usage: /ward " + label() + (parameters.isEmpty() ? "" : " " + parameters);
        }

        static Subcommand byLabel(String text) {
            String wanted = text.toLowerCase(Locale.ROOT);
            for (Subcommand subcommand : values()) {
                if (subcommand.label().equals(wanted)) {
                    return subcommand;
                }
            }
            return null;
        }

        static String generalUsage() {
            StringJoiner labels = new StringJoiner("|", "Usage: /ward <", ">");
            for (Subcommand subcommand : values()) {
                labels.add(subcommand.label());
            }
            return labels.toString();
        }
    }

    /** A validation failure; its message is the whole reply. */
    private static final class Rejection extends Exception {
        private static final long serialVersionUID = 1L;

        Rejection(String reply) {
            super(reply, null, false, false);
        }
    }

    private final WardstonePlugin plugin;
    private final RegionRegistry registry;

    WardCommand(WardstonePlugin plugin, RegionRegistry registry) {
        this.plugin = plugin;
        this.registry = registry;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        for (String line : reply(sender, args)) {
            sender.sendMessage(line);
        }
        return true;
    }

    private List<String> reply(CommandSender sender, String[] args) {
        Subcommand subcommand = args.length == 0 ? null : Subcommand.byLabel(args[0]);
        if (subcommand == null) {
            return List.of(Subcommand.generalUsage());
        }
        if (args.length != subcommand.arity + 1) {
            return List.of(subcommand.usage());
        }
        if (!sender.hasPermission(ADMIN_PERMISSION)) {
            return List.of(NO_PERMISSION);
        }
        try {
            return switch (subcommand) {
                case DEFINE -> define(args);
                case DELETE -> delete(args);
                case PRIORITY -> priority(args);
                case FLAG -> flag(args);
                case ADDOWNER -> addPlayer(args, Role.OWNER);
                case REMOVEOWNER -> removePlayer(args, Role.OWNER);
                case ADDMEMBER -> addPlayer(args, Role.MEMBER);
                case REMOVEMEMBER -> removePlayer(args, Role.MEMBER);
                case INFO -> info(args);
                case AT -> at(args);
                case LIST -> list();
                case RELOAD -> reload();
            };
        } catch (Rejection rejection) {
            return List.of(rejection.getMessage());
        }
    }

    private List<String> define(String[] args) throws Rejection {
        String name = regionName(args[1]);
        if (registry.get(name) != null) {
            throw new Rejection("Region " + name + " already exists.");
        }
        World world = world(args[2]);
        int x1 = coordinate(args[3]);
        int y1 = coordinate(args[4]);
        int z1 = coordinate(args[5]);
        int x2 = coordinate(args[6]);
        int y2 = coordinate(args[7]);
        int z2 = coordinate(args[8]);
        Region region = new Region(name, world.getName(), x1, y1, z1, x2, y2, z2);
        BigInteger volume = region.volume();
        long maximum = plugin.maxRegionVolume();
        if (volume.compareTo(BigInteger.valueOf(maximum)) > 0) {
            throw new Rejection("Region too large: " + volume + " blocks (maximum " + maximum + ").");
        }
        registry.put(region);
        plugin.saveRegions();
        return List.of("Defined region " + name + " in " + world.getName() + " (" + region.sizeX() + " x "
                + region.sizeY() + " x " + region.sizeZ() + " = " + volume + " blocks).");
    }

    private List<String> delete(String[] args) throws Rejection {
        Region region = existingRegion(args[1]);
        registry.remove(region.name());
        plugin.saveRegions();
        return List.of("Deleted region " + region.name() + ".");
    }

    private List<String> priority(String[] args) throws Rejection {
        Region region = existingRegion(args[1]);
        Integer priority = wholeNumber(args[2]);
        if (priority == null) {
            throw new Rejection("Invalid priority: " + args[2]);
        }
        region.setPriority(priority);
        plugin.saveRegions();
        return List.of("Priority of " + region.name() + " set to " + priority + ".");
    }

    private List<String> flag(String[] args) throws Rejection {
        Region region = existingRegion(args[1]);
        Flag flag = Flag.fromId(args[2]);
        if (flag == null) {
            throw new Rejection("Unknown flag: " + args[2] + " (flags: " + flagNames() + ")");
        }
        if (args[3].equalsIgnoreCase("clear")) {
            region.clearFlag(flag);
            plugin.saveRegions();
            return List.of("Flag " + flag.id() + " of " + region.name() + " cleared.");
        }
        FlagValue value = FlagValue.fromId(args[3]);
        if (value == null) {
            throw new Rejection("Invalid flag value: " + args[3] + " (use allow, deny or clear)");
        }
        region.setFlag(flag, value);
        plugin.saveRegions();
        return List.of("Flag " + flag.id() + " of " + region.name() + " set to " + value.id() + ".");
    }

    private List<String> addPlayer(String[] args, Role role) throws Rejection {
        Region region = existingRegion(args[1]);
        String player = playerName(args[2]);
        if (!region.addPlayer(role, player)) {
            throw new Rejection(player + " is already " + article(role) + " of " + region.name() + ".");
        }
        plugin.saveRegions();
        return List.of("Added " + player + " as " + noun(role) + " of " + region.name() + ".");
    }

    private List<String> removePlayer(String[] args, Role role) throws Rejection {
        Region region = existingRegion(args[1]);
        String player = playerName(args[2]);
        if (!region.removePlayer(role, player)) {
            throw new Rejection(player + " is not " + article(role) + " of " + region.name() + ".");
        }
        plugin.saveRegions();
        return List.of("Removed " + player + " from the " + noun(role) + "s of " + region.name() + ".");
    }

    private List<String> info(String[] args) throws Rejection {
        Region region = existingRegion(args[1]);
        List<String> flags = new ArrayList<>();
        for (Map.Entry<Flag, FlagValue> entry : region.flags().entrySet()) {
            flags.add(entry.getKey().id() + "=" + entry.getValue().id());
        }
        return List.of(
                "Region " + region.name() + " in " + region.world()
                        + " from " + region.minX() + " " + region.minY() + " " + region.minZ()
                        + " to " + region.maxX() + " " + region.maxY() + " " + region.maxZ()
                        + ", priority " + region.priority(),
                "Owners: " + joinedOrNone(region.players(Role.OWNER)),
                "Members: " + joinedOrNone(region.players(Role.MEMBER)),
                "Flags: " + joinedOrNone(flags));
    }

    private List<String> at(String[] args) throws Rejection {
        World world = world(args[1]);
        int x = coordinate(args[2]);
        int y = coordinate(args[3]);
        int z = coordinate(args[4]);
        String place = world.getName() + " " + x + " " + y + " " + z;
        List<Region> regions = registry.regionsAt(world.getName(), x, y, z);
        if (regions.isEmpty()) {
            return List.of("No regions at " + place + ".");
        }
        StringJoiner found = new StringJoiner(", ");
        for (Region region : regions) {
            found.add(region.name() + " (priority " + region.priority() + ")");
        }
        return List.of("Regions at " + place + ": " + found);
    }

    private List<String> list() {
        if (registry.size() == 0) {
            return List.of("No regions.");
        }
        StringJoiner names = new StringJoiner(", ");
        for (Region region : registry.all()) {
            names.add(region.name());
        }
        return List.of(registry.size() + " regions: " + names);
    }

    private List<String> reload() {
        int count = plugin.reloadFromDisk();
        return List.of("Wardstone reloaded (regions: " + count + ").");
    }

    private static String regionName(String argument) throws Rejection {
        String name = Names.region(argument);
        if (name == null) {
            throw new Rejection("Invalid region name: " + argument);
        }
        return name;
    }

    private Region existingRegion(String argument) throws Rejection {
        String name = regionName(argument);
        Region region = registry.get(name);
        if (region == null) {
            throw new Rejection("Unknown region: " + name);
        }
        return region;
    }

    private static String playerName(String argument) throws Rejection {
        String player = Names.player(argument);
        if (player == null) {
            throw new Rejection("Invalid player name: " + argument);
        }
        return player;
    }

    private World world(String argument) throws Rejection {
        World world = plugin.getServer().getWorld(argument);
        if (world == null) {
            throw new Rejection("Unknown world: " + argument);
        }
        return world;
    }

    private static int coordinate(String argument) throws Rejection {
        Integer value = wholeNumber(argument);
        if (value == null) {
            throw new Rejection(INVALID_COORDINATES);
        }
        return value;
    }

    /** An optional minus sign and ASCII digits that fit in an {@code int}, or {@code null}. */
    private static Integer wholeNumber(String argument) {
        if (!WHOLE_NUMBER.matcher(argument).matches()) {
            return null;
        }
        try {
            return Integer.parseInt(argument);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    private static String flagNames() {
        StringJoiner names = new StringJoiner(", ");
        for (Flag flag : Flag.values()) {
            names.add(flag.id());
        }
        return names.toString();
    }

    private static String noun(Role role) {
        return role == Role.OWNER ? "owner" : "member";
    }

    private static String article(Role role) {
        return role == Role.OWNER ? "an owner" : "a member";
    }

    private static String joinedOrNone(Collection<String> values) {
        return values.isEmpty() ? "none" : String.join(", ", values);
    }
}
