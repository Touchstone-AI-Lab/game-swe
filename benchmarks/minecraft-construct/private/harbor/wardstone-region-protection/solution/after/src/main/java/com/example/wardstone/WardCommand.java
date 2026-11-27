package com.example.wardstone;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.logging.Level;
import java.util.regex.Pattern;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;

/** The /ward command. */
public final class WardCommand implements CommandExecutor {

    private static final String USAGE = "Usage: /ward <define|delete|priority|flag|addowner|removeowner|addmember"
        + "|removemember|info|at|list|reload>";
    private static final Pattern REGION = Pattern.compile("^[a-z0-9_-]{2,24}$");
    private static final Pattern PLAYER = Pattern.compile("^[A-Za-z0-9_]{3,16}$");
    private static final Pattern INTEGER = Pattern.compile("^-?[0-9]{1,9}$");

    private final WardstonePlugin plugin;

    public WardCommand(WardstonePlugin plugin) {
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
                case "define" -> define(sender, rest);
                case "delete" -> delete(sender, rest);
                case "priority" -> priority(sender, rest);
                case "flag" -> flag(sender, rest);
                case "addowner" -> people(sender, rest, true, true);
                case "removeowner" -> people(sender, rest, true, false);
                case "addmember" -> people(sender, rest, false, true);
                case "removemember" -> people(sender, rest, false, false);
                case "info" -> info(sender, rest);
                case "at" -> at(sender, rest);
                case "list" -> list(sender, rest);
                case "reload" -> reload(sender, rest);
                default -> sender.sendMessage(USAGE);
            }
        } catch (WardException rejected) {
            sender.sendMessage(rejected.getMessage());
        } catch (IOException failure) {
            plugin.getLogger().log(Level.SEVERE, "Could not save regions.yml", failure);
        }
        return true;
    }

    private static void check(CommandSender sender, String[] args, int count, String usage) throws WardException {
        if (args.length != count) {
            throw new WardException(usage);
        }
        if (!sender.hasPermission("wardstone.admin")) {
            throw new WardException("You do not have permission to do that.");
        }
    }

    private static String regionName(String raw) throws WardException {
        String name = raw.toLowerCase(Locale.ROOT);
        if (!REGION.matcher(name).matches()) {
            throw new WardException("Invalid region name: " + raw);
        }
        return name;
    }

    private Region region(String raw) throws WardException {
        String name = regionName(raw);
        Region region = plugin.regions().get(name);
        if (region == null) {
            throw new WardException("Unknown region: " + name);
        }
        return region;
    }

    private static World world(String raw) throws WardException {
        World world = Bukkit.getWorld(raw);
        if (world == null) {
            throw new WardException("Unknown world: " + raw);
        }
        return world;
    }

    private static int[] coordinates(String[] args, int offset, int count) throws WardException {
        int[] values = new int[count];
        for (int i = 0; i < count; i++) {
            if (!INTEGER.matcher(args[offset + i]).matches()) {
                throw new WardException("Invalid coordinates.");
            }
            values[i] = Integer.parseInt(args[offset + i]);
        }
        return values;
    }

    private void save() throws IOException {
        plugin.regions().save();
    }

    private void define(CommandSender sender, String[] args) throws WardException, IOException {
        check(sender, args, 8, "Usage: /ward define <region> <world> <x1> <y1> <z1> <x2> <y2> <z2>");
        String name = regionName(args[0]);
        if (plugin.regions().get(name) != null) {
            throw new WardException("Region " + name + " already exists.");
        }
        World world = world(args[1]);
        int[] c = coordinates(args, 2, 6);
        Region region = new Region(name, world.getName(), c[0], c[1], c[2], c[3], c[4], c[5]);
        long max = plugin.getConfig().getLong("max-region-volume", 1_000_000L);
        if (region.volume() > max) {
            throw new WardException("Region too large: " + region.volume() + " blocks (maximum " + max + ").");
        }
        plugin.regions().add(region);
        save();
        sender.sendMessage("Defined region " + name + " in " + world.getName() + " (" + region.sizeX() + " x "
            + region.sizeY() + " x " + region.sizeZ() + " = " + region.volume() + " blocks).");
    }

    private void delete(CommandSender sender, String[] args) throws WardException, IOException {
        check(sender, args, 1, "Usage: /ward delete <region>");
        Region region = region(args[0]);
        plugin.regions().remove(region.name());
        save();
        sender.sendMessage("Deleted region " + region.name() + ".");
    }

    private void priority(CommandSender sender, String[] args) throws WardException, IOException {
        check(sender, args, 2, "Usage: /ward priority <region> <priority>");
        Region region = region(args[0]);
        if (!INTEGER.matcher(args[1]).matches()) {
            throw new WardException("Invalid priority: " + args[1]);
        }
        region.priority(Integer.parseInt(args[1]));
        save();
        sender.sendMessage("Priority of " + region.name() + " set to " + region.priority() + ".");
    }

    private void flag(CommandSender sender, String[] args) throws WardException, IOException {
        check(sender, args, 3, "Usage: /ward flag <region> <flag> <allow|deny|clear>");
        Region region = region(args[0]);
        Flag flag = Flag.fromKey(args[1]);
        if (flag == null) {
            throw new WardException("Unknown flag: " + args[1] + " (flags: block-break, block-place, explosion, fire)");
        }
        String value = args[2].toLowerCase(Locale.ROOT);
        switch (value) {
            case "allow", "deny" -> {
                region.flags().put(flag.key(), value.equals("allow"));
                save();
                sender.sendMessage("Flag " + flag.key() + " of " + region.name() + " set to " + value + ".");
            }
            case "clear" -> {
                region.flags().remove(flag.key());
                save();
                sender.sendMessage("Flag " + flag.key() + " of " + region.name() + " cleared.");
            }
            default -> throw new WardException("Invalid flag value: " + args[2] + " (use allow, deny or clear)");
        }
    }

    private void people(CommandSender sender, String[] args, boolean owners, boolean add)
        throws WardException, IOException {
        String sub = (add ? "add" : "remove") + (owners ? "owner" : "member");
        check(sender, args, 2, "Usage: /ward " + sub + " <region> <player>");
        Region region = region(args[0]);
        if (!PLAYER.matcher(args[1]).matches()) {
            throw new WardException("Invalid player name: " + args[1]);
        }
        String player = args[1].toLowerCase(Locale.ROOT);
        Set<String> set = owners ? region.owners() : region.members();
        String role = owners ? "an owner" : "a member";
        if (add) {
            if (!set.add(player)) {
                throw new WardException(player + " is already " + role + " of " + region.name() + ".");
            }
            save();
            sender.sendMessage("Added " + player + " as " + (owners ? "owner" : "member") + " of " + region.name() + ".");
        } else {
            if (!set.remove(player)) {
                throw new WardException(player + " is not " + role + " of " + region.name() + ".");
            }
            save();
            sender.sendMessage("Removed " + player + " from the " + (owners ? "owners" : "members") + " of "
                + region.name() + ".");
        }
    }

    private static String joined(Set<String> names) {
        return names.isEmpty() ? "none" : String.join(", ", names);
    }

    private void info(CommandSender sender, String[] args) throws WardException {
        check(sender, args, 1, "Usage: /ward info <region>");
        Region r = region(args[0]);
        sender.sendMessage("Region " + r.name() + " in " + r.world() + " from " + r.minX() + " " + r.minY() + " "
            + r.minZ() + " to " + r.maxX() + " " + r.maxY() + " " + r.maxZ() + ", priority " + r.priority());
        sender.sendMessage("Owners: " + joined(r.owners()));
        sender.sendMessage("Members: " + joined(r.members()));
        List<String> flags = new ArrayList<>();
        r.flags().forEach((key, allow) -> flags.add(key + "=" + (allow ? "allow" : "deny")));
        sender.sendMessage("Flags: " + (flags.isEmpty() ? "none" : String.join(", ", flags)));
    }

    private void at(CommandSender sender, String[] args) throws WardException {
        check(sender, args, 4, "Usage: /ward at <world> <x> <y> <z>");
        World world = world(args[0]);
        int[] c = coordinates(args, 1, 3);
        String where = world.getName() + " " + c[0] + " " + c[1] + " " + c[2];
        List<Region> found = plugin.regions().at(world.getName(), c[0], c[1], c[2]);
        if (found.isEmpty()) {
            sender.sendMessage("No regions at " + where + ".");
            return;
        }
        found.sort(Comparator.comparingInt((Region region) -> region.priority()).reversed()
            .thenComparing(Region::name));
        List<String> parts = new ArrayList<>();
        for (Region region : found) {
            parts.add(region.name() + " (priority " + region.priority() + ")");
        }
        sender.sendMessage("Regions at " + where + ": " + String.join(", ", parts));
    }

    private void list(CommandSender sender, String[] args) throws WardException {
        check(sender, args, 0, "Usage: /ward list");
        List<String> names = new ArrayList<>();
        plugin.regions().all().forEach(region -> names.add(region.name()));
        sender.sendMessage(names.isEmpty() ? "No regions." : names.size() + " regions: " + String.join(", ", names));
    }

    private void reload(CommandSender sender, String[] args) throws WardException {
        check(sender, args, 0, "Usage: /ward reload");
        plugin.reloadRegions();
        sender.sendMessage("Wardstone reloaded (regions: " + plugin.regions().all().size() + ").");
    }
}
