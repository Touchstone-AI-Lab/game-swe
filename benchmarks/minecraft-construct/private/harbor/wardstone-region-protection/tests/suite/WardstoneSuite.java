package gcbtest.wardstone;

import io.gamecodebench.harness.GcbAssert;
import io.gamecodebench.harness.GcbCase;
import io.gamecodebench.harness.GcbSuite;
import io.gamecodebench.harness.GcbWorlds;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Set;
import org.bukkit.Bukkit;
import org.bukkit.ExplosionResult;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.BlockState;
import org.bukkit.command.PluginCommand;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Creeper;
import org.bukkit.entity.Entity;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockBurnEvent;
import org.bukkit.event.block.BlockFromToEvent;
import org.bukkit.event.block.BlockExplodeEvent;
import org.bukkit.event.block.BlockIgniteEvent;
import org.bukkit.event.block.BlockIgniteEvent.IgniteCause;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.entity.EntityExplodeEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;
import org.bukkit.permissions.Permission;
import org.bukkit.permissions.PermissionDefault;
import org.bukkit.plugin.java.JavaPlugin;

/** Hidden live-server cases for the Wardstone construct task. */
public final class WardstoneSuite implements GcbSuite {

    private static final String DENIED = "You do not have permission to do that.";
    private static final String USAGE = "Usage: /ward <define|delete|priority|flag|addowner|removeowner|addmember"
        + "|removemember|info|at|list|reload>";

    @Override
    public void onEnable(JavaPlugin grader) {
    }

    // --- helpers -------------------------------------------------------------------------

    private static World world() {
        return GcbWorlds.main();
    }

    private static Block block(int x, int y, int z) {
        Block block = world().getBlockAt(x, y, z);
        block.getChunk().setForceLoaded(true);
        return block;
    }

    private static List<String> ward(String arguments) {
        return Actor.console().run("ward " + arguments);
    }

    private static void expect(String arguments, String... expected) {
        Kit.lines(ward(arguments), "/ward " + arguments, expected);
    }

    /** Defines a region from x1..x2 and z1..z2 over the whole height -64..-50 and returns its reply. */
    private static void define(String name, int x1, int z1, int x2, int z2) {
        List<String> reply = ward("define " + name + " world " + x1 + " -64 " + z1 + " " + x2 + " -50 " + z2);
        GcbAssert.isTrue(reply.size() == 1 && reply.get(0).startsWith("Defined region " + name + " in world ("),
            "define " + name + ": " + reply);
    }

    private static void flag(String region, String flag, String value) {
        expect("flag " + region + " " + flag + " " + value, "Flag " + flag + " of " + region + " set to " + value + ".");
    }

    /** Breaks a stone block at the location as a player; returns the event. */
    private static BlockBreakEvent breakAt(Actor player, int x, int y, int z) {
        Block block = block(x, y, z);
        block.setType(Material.STONE, false);
        player.clear();
        BlockBreakEvent event = new BlockBreakEvent(block, player.player());
        Bukkit.getPluginManager().callEvent(event);
        return event;
    }

    private static BlockPlaceEvent placeAt(Actor player, int x, int y, int z) {
        Block block = block(x, y, z);
        block.setType(Material.AIR, false);
        BlockState replaced = block.getState();
        block.setType(Material.STONE, false);
        player.clear();
        BlockPlaceEvent event = new BlockPlaceEvent(block, replaced, block.getRelative(BlockFace.DOWN),
            new ItemStack(Material.STONE), player.player(), true, EquipmentSlot.HAND);
        Bukkit.getPluginManager().callEvent(event);
        return event;
    }

    private static void denied(Actor player, BlockBreakEvent event, String region) {
        GcbAssert.isTrue(event.isCancelled(), player.name() + " may not break at " + where(event.getBlock()));
        GcbAssert.equals(List.of("You cannot break blocks in " + region + "."), player.lines(), "message to " + player.name());
    }

    private static void allowed(Actor player, BlockBreakEvent event) {
        GcbAssert.isFalse(event.isCancelled(), player.name() + " may break at " + where(event.getBlock()));
        GcbAssert.equals(List.of(), player.lines(), "no message to " + player.name());
    }

    private static String where(Block block) {
        return block.getX() + " " + block.getY() + " " + block.getZ();
    }

    private static List<String> locations(List<Block> blocks) {
        List<String> names = new ArrayList<>();
        blocks.forEach(block -> names.add(where(block)));
        return names;
    }

    private static Set<String> keys(ConfigurationSection section) {
        return section == null ? Set.of() : section.getKeys(false);
    }

    // --- cases ---------------------------------------------------------------------------

    @GcbCase(value = "Wardstone is enabled", order = 0)
    public void sentinel() {
        GcbAssert.isTrue(Kit.plugin().isEnabled(), "Wardstone is enabled");
        GcbAssert.equals("Wardstone", Kit.plugin().getName(), "plugin name");
    }

    @GcbCase(value = "default config.yml is written on first enable", order = 1)
    public void defaultConfig() {
        GcbAssert.equals(1000000L, Kit.yaml("config.yml").getLong("max-region-volume"), "max-region-volume");
    }

    @GcbCase(value = "plugin.yml declares the ward command and permissions", order = 2)
    public void declarations() {
        PluginCommand command = Bukkit.getPluginCommand("ward");
        GcbAssert.notNull(command, "/ward is a plugin command");
        GcbAssert.equals("Wardstone", command.getPlugin().getName(), "/ward belongs to Wardstone");
        GcbAssert.isNull(command.getPermission(), "/ward has no permission key");
        for (String name : List.of("wardstone.admin", "wardstone.bypass")) {
            Permission permission = Bukkit.getPluginManager().getPermission(name);
            GcbAssert.notNull(permission, name + " is registered");
            GcbAssert.equals(PermissionDefault.OP, permission.getDefault(), name + " default");
        }
    }

    @GcbCase(value = "define creates a region and reports its size", order = 3)
    public void defineRegion() {
        expect("define Spawn world 0 -64 0 10 -50 10", "Defined region spawn in world (11 x 15 x 11 = 1815 blocks).");
        expect("info SPAWN", "Region spawn in world from 0 -64 0 to 10 -50 10, priority 0", "Owners: none",
            "Members: none", "Flags: none");
        expect("list", "1 regions: spawn");
    }

    @GcbCase(value = "define validates its arguments", order = 4)
    public void defineValidation() {
        expect("define x world 0 0 0 1 1 1", "Invalid region name: x");
        expect("define bad!name world 0 0 0 1 1 1", "Invalid region name: bad!name");
        expect("define abcdefghijklmnopqrstuvwxy world 0 0 0 1 1 1", "Invalid region name: abcdefghijklmnopqrstuvwxy");
        expect("define x nowhere 0 0 0 1 1 z", "Invalid region name: x");
        expect("define spawn nowhere 0 0 0 1 1 1", "Region spawn already exists.");
        expect("define other nowhere 0 0 0 1 1 1", "Unknown world: nowhere");
        expect("define other world 0 0 0 1 1 z", "Invalid coordinates.");
        expect("define other world 0 0 0 1.5 1 1", "Invalid coordinates.");
        expect("list", "1 regions: spawn");
    }

    @GcbCase(value = "define rejects regions above the maximum volume", order = 5)
    public void maximumVolume() {
        expect("define big world 0 -64 0 999 -64 1000", "Region too large: 1001000 blocks (maximum 1000000).");
        expect("define exact world 0 -64 0 999 -64 999", "Defined region exact in world (1000 x 1 x 1000 = 1000000 blocks).");
        expect("delete exact", "Deleted region exact.");
        try {
            Kit.write("config.yml", "max-region-volume: 100\n");
            expect("reload", "Wardstone reloaded (regions: 1).");
            expect("define small world 0 0 0 4 4 4", "Region too large: 125 blocks (maximum 100).");
            expect("define small world 0 0 0 4 3 4", "Defined region small in world (5 x 4 x 5 = 100 blocks).");
            expect("delete small", "Deleted region small.");
        } finally {
            Kit.write("config.yml", "max-region-volume: 1000000\n");
            expect("reload", "Wardstone reloaded (regions: 1).");
        }
    }

    @GcbCase(value = "regions.yml stores normalised corners and sorted lists", order = 6)
    public void regionsFile() {
        expect("define Market world 30 -50 40 20 -60 30", "Defined region market in world (11 x 11 x 11 = 1331 blocks).");
        expect("addowner market Zed_1", "Added zed_1 as owner of market.");
        expect("addowner market alice", "Added alice as owner of market.");
        expect("addmember market Bob", "Added bob as member of market.");
        flag("market", "block-place", "deny");
        flag("market", "explosion", "allow");
        expect("priority market 7", "Priority of market set to 7.");
        YamlConfiguration yaml = Kit.yaml("regions.yml");
        String base = "regions.market.";
        GcbAssert.equals("world", yaml.getString(base + "world"), "world");
        GcbAssert.equals(List.of(20, -60, 30), List.of(yaml.getInt(base + "min.x"), yaml.getInt(base + "min.y"),
            yaml.getInt(base + "min.z")), "min corner");
        GcbAssert.equals(List.of(30, -50, 40), List.of(yaml.getInt(base + "max.x"), yaml.getInt(base + "max.y"),
            yaml.getInt(base + "max.z")), "max corner");
        GcbAssert.equals(7, yaml.getInt(base + "priority"), "priority");
        GcbAssert.equals(List.of("alice", "zed_1"), yaml.getStringList(base + "owners"), "owners, sorted");
        GcbAssert.equals(List.of("bob"), yaml.getStringList(base + "members"), "members");
        GcbAssert.equals(Set.of("block-place", "explosion"), keys(yaml.getConfigurationSection(base + "flags")), "flags");
        GcbAssert.equals("deny", yaml.getString(base + "flags.block-place"), "block-place");
        GcbAssert.equals("allow", yaml.getString(base + "flags.explosion"), "explosion");
        GcbAssert.isTrue(yaml.contains("regions.spawn.world"), "the other region is saved too");
        GcbAssert.equals(Set.of(), keys(yaml.getConfigurationSection("regions.spawn.flags")), "spawn has no flags");
    }

    @GcbCase(value = "denied breaks are cancelled with a message", order = 7)
    public void deniedBreak() {
        define("keep", 100, 100, 110, 110);
        flag("keep", "block-break", "deny");
        Actor alice = Actor.player("Alice");
        denied(alice, breakAt(alice, 105, -60, 105), "keep");
        BlockPlaceEvent place = placeAt(alice, 105, -59, 105);
        GcbAssert.isFalse(place.isCancelled(), "block-place is not set, so placing is allowed");
        GcbAssert.equals(List.of(), alice.lines(), "no message for an allowed place");
        allowed(alice, breakAt(alice, 150, -60, 150));
    }

    @GcbCase(value = "bounds are inclusive on every axis", order = 8)
    public void inclusiveBounds() {
        expect("define edges world 200 -63 200 205 -55 205", "Defined region edges in world (6 x 9 x 6 = 324 blocks).");
        flag("edges", "block-break", "deny");
        Actor gil = Actor.player("Gil");
        denied(gil, breakAt(gil, 200, -63, 200), "edges");
        denied(gil, breakAt(gil, 205, -55, 205), "edges");
        denied(gil, breakAt(gil, 200, -55, 205), "edges");
        denied(gil, breakAt(gil, 205, -63, 200), "edges");
        int[][] outside = {
            {199, -60, 202}, {206, -60, 202}, {202, -64, 202}, {202, -54, 202}, {202, -60, 199}, {202, -60, 206},
        };
        for (int[] at : outside) {
            allowed(gil, breakAt(gil, at[0], at[1], at[2]));
        }
    }

    @GcbCase(value = "denied places are cancelled with a message", order = 9)
    public void deniedPlace() {
        define("shop", 300, 300, 310, 310);
        flag("shop", "block-place", "deny");
        Actor bob = Actor.player("Bob");
        BlockPlaceEvent place = placeAt(bob, 305, -59, 305);
        GcbAssert.isTrue(place.isCancelled(), "placing in shop is cancelled");
        GcbAssert.equals(List.of("You cannot place blocks in shop."), bob.lines(), "message to Bob");
        allowed(bob, breakAt(bob, 305, -60, 305));
    }

    @GcbCase(value = "owners and members build in their own region", order = 10)
    public void ownersAndMembers() {
        define("guild", 400, 400, 410, 410);
        flag("guild", "block-break", "deny");
        flag("guild", "block-place", "deny");
        expect("addowner guild Carol", "Added carol as owner of guild.");
        expect("addmember guild dave", "Added dave as member of guild.");
        Actor carol = Actor.player("Carol");
        Actor dave = Actor.player("Dave");
        Actor erin = Actor.player("Erin");
        allowed(carol, breakAt(carol, 405, -60, 405));
        BlockPlaceEvent place = placeAt(dave, 405, -59, 405);
        GcbAssert.isFalse(place.isCancelled(), "a member may place");
        GcbAssert.equals(List.of(), dave.lines(), "no message to a member");
        denied(erin, breakAt(erin, 405, -60, 405), "guild");
        expect("removemember guild Dave", "Removed dave from the members of guild.");
        denied(dave, breakAt(dave, 405, -60, 405), "guild");
    }

    @GcbCase(value = "the bypass permission builds everywhere", order = 11)
    public void bypass() {
        define("fortress", 450, 450, 460, 460);
        flag("fortress", "block-break", "deny");
        flag("fortress", "block-place", "deny");
        Actor finn = Actor.player("Finn", "wardstone.bypass");
        allowed(finn, breakAt(finn, 455, -60, 455));
        BlockPlaceEvent place = placeAt(finn, 455, -59, 455);
        GcbAssert.isFalse(place.isCancelled(), "bypass may place");
        GcbAssert.equals(List.of(), finn.lines(), "no message with bypass");
        Actor gwen = Actor.player("Gwen");
        denied(gwen, breakAt(gwen, 455, -60, 455), "fortress");
    }

    @GcbCase(value = "the highest priority region decides", order = 12)
    public void priorities() {
        define("outer", 500, 500, 540, 540);
        define("inner", 510, 510, 520, 520);
        flag("outer", "block-break", "deny");
        flag("inner", "block-break", "allow");
        expect("priority inner 5", "Priority of inner set to 5.");
        Actor gus = Actor.player("Gus");
        allowed(gus, breakAt(gus, 515, -60, 515));
        denied(gus, breakAt(gus, 505, -60, 505), "outer");
        define("top", 512, 512, 518, 518);
        expect("priority top 10", "Priority of top set to 10.");
        flag("top", "block-place", "deny");
        allowed(gus, breakAt(gus, 515, -60, 515));
        expect("priority inner -1", "Priority of inner set to -1.");
        denied(gus, breakAt(gus, 515, -60, 515), "outer");
        expect("priority inner high", "Invalid priority: high");
    }

    @GcbCase(value = "deny wins between equal priorities and the first name decides", order = 13)
    public void equalPriorities() {
        define("zeta", 600, 600, 610, 610);
        define("beta", 600, 600, 610, 610);
        define("alpha", 600, 600, 610, 610);
        for (String region : List.of("zeta", "beta", "alpha")) {
            expect("priority " + region + " 3", "Priority of " + region + " set to 3.");
        }
        flag("zeta", "block-break", "deny");
        flag("beta", "block-break", "deny");
        flag("alpha", "block-break", "allow");
        Actor hank = Actor.player("Hank");
        denied(hank, breakAt(hank, 605, -60, 605), "beta");
        expect("addowner zeta Hank", "Added hank as owner of zeta.");
        denied(hank, breakAt(hank, 605, -60, 605), "beta");
        expect("addmember beta hank", "Added hank as member of beta.");
        allowed(hank, breakAt(hank, 605, -60, 605));
    }

    @GcbCase(value = "explosions keep blocks in protected regions", order = 14)
    public void explosions() {
        define("vault", 700, 700, 710, 710);
        define("open", 711, 700, 720, 710);
        flag("vault", "explosion", "deny");
        flag("open", "explosion", "allow");
        Block inVault = block(705, -60, 705);
        Block inOpen = block(715, -60, 705);
        Block outside = block(730, -60, 705);
        Block vaultEdge = block(710, -50, 710);
        Creeper creeper = world().spawn(block(725, -59, 725).getLocation(), Creeper.class);
        try {
            EntityExplodeEvent entity = new EntityExplodeEvent(creeper, creeper.getLocation(),
                new ArrayList<>(List.of(inVault, inOpen, outside, vaultEdge)), 1.0f, ExplosionResult.DESTROY);
            Bukkit.getPluginManager().callEvent(entity);
            GcbAssert.isFalse(entity.isCancelled(), "the entity explosion is not cancelled");
            GcbAssert.equals(locations(List.of(inOpen, outside)), locations(entity.blockList()),
                "blocks left in the entity explosion");
        } finally {
            creeper.remove();
        }
        Block source = block(725, -60, 705);
        BlockExplodeEvent blockEvent = new BlockExplodeEvent(source, source.getState(),
            new ArrayList<>(List.of(outside, inVault, inOpen)), 1.0f, ExplosionResult.DESTROY);
        Bukkit.getPluginManager().callEvent(blockEvent);
        GcbAssert.isFalse(blockEvent.isCancelled(), "the block explosion is not cancelled");
        GcbAssert.equals(locations(List.of(outside, inOpen)), locations(blockEvent.blockList()),
            "blocks left in the block explosion");
    }

    @GcbCase(value = "fire is blocked where the fire flag is denied", order = 15)
    public void fire() {
        define("hearth", 800, 800, 810, 810);
        flag("hearth", "fire", "deny");
        Block inside = block(805, -59, 805);
        Block outside = block(820, -59, 805);
        inside.setType(Material.OAK_PLANKS, false);
        outside.setType(Material.OAK_PLANKS, false);
        BlockBurnEvent burn = new BlockBurnEvent(inside, inside.getRelative(BlockFace.UP));
        Bukkit.getPluginManager().callEvent(burn);
        GcbAssert.isTrue(burn.isCancelled(), "burning inside hearth is cancelled");
        BlockBurnEvent burnOutside = new BlockBurnEvent(outside, outside.getRelative(BlockFace.UP));
        Bukkit.getPluginManager().callEvent(burnOutside);
        GcbAssert.isFalse(burnOutside.isCancelled(), "burning outside is allowed");
        for (IgniteCause cause : List.of(IgniteCause.SPREAD, IgniteCause.LAVA, IgniteCause.LIGHTNING)) {
            BlockIgniteEvent ignite = new BlockIgniteEvent(inside, cause, (Entity) null);
            Bukkit.getPluginManager().callEvent(ignite);
            GcbAssert.isTrue(ignite.isCancelled(), cause + " ignition inside hearth is cancelled");
            BlockIgniteEvent away = new BlockIgniteEvent(outside, cause, (Entity) null);
            Bukkit.getPluginManager().callEvent(away);
            GcbAssert.isFalse(away.isCancelled(), cause + " ignition outside is allowed");
        }
        BlockIgniteEvent flint = new BlockIgniteEvent(inside, IgniteCause.FLINT_AND_STEEL, (Entity) null);
        Bukkit.getPluginManager().callEvent(flint);
        GcbAssert.isFalse(flint.isCancelled(), "flint and steel is not governed by the fire flag");
    }

    @GcbCase(value = "flags can be changed and cleared", order = 16)
    public void changeFlags() {
        define("toggle", 850, 850, 860, 860);
        Actor ivy = Actor.player("Ivy");
        flag("toggle", "block-break", "deny");
        denied(ivy, breakAt(ivy, 855, -60, 855), "toggle");
        expect("flag toggle BLOCK-BREAK Allow", "Flag block-break of toggle set to allow.");
        allowed(ivy, breakAt(ivy, 855, -60, 855));
        expect("flag toggle block-break deny", "Flag block-break of toggle set to deny.");
        expect("flag toggle block-break clear", "Flag block-break of toggle cleared.");
        allowed(ivy, breakAt(ivy, 855, -60, 855));
        expect("info toggle", "Region toggle in world from 850 -64 850 to 860 -50 860, priority 0", "Owners: none",
            "Members: none", "Flags: none");
        GcbAssert.equals(Set.of(), keys(Kit.yaml("regions.yml").getConfigurationSection("regions.toggle.flags")),
            "the cleared flag is gone from regions.yml");
    }

    @GcbCase(value = "flag validates the flag and the value", order = 17)
    public void flagValidation() {
        define("checks", 870, 870, 875, 875);
        expect("flag checks pvp deny", "Unknown flag: pvp (flags: block-break, block-place, explosion, fire)");
        expect("flag checks pvp maybe", "Unknown flag: pvp (flags: block-break, block-place, explosion, fire)");
        expect("flag checks fire maybe", "Invalid flag value: maybe (use allow, deny or clear)");
        expect("flag ghost fire deny", "Unknown region: ghost");
        expect("flag Ghost! fire deny", "Invalid region name: Ghost!");
        expect("flag checks fire DENY", "Flag fire of checks set to deny.");
    }

    @GcbCase(value = "owners and members are managed by name", order = 18)
    public void people() {
        define("club", 880, 880, 885, 885);
        expect("addowner club Jill", "Added jill as owner of club.");
        expect("addowner club JILL", "jill is already an owner of club.");
        expect("addmember club jill", "Added jill as member of club.");
        expect("addmember club Jill", "jill is already a member of club.");
        expect("removeowner club jill", "Removed jill from the owners of club.");
        expect("removeowner club jill", "jill is not an owner of club.");
        expect("removemember club kurt", "kurt is not a member of club.");
        expect("addmember club ab", "Invalid player name: ab");
        expect("addmember ghost jill", "Unknown region: ghost");
        expect("info club", "Region club in world from 880 -64 880 to 885 -50 885, priority 0", "Owners: none",
            "Members: jill", "Flags: none");
    }

    @GcbCase(value = "info describes a region", order = 19)
    public void info() {
        expect("define Info-1 world 895 -60 899 890 -62 894", "Defined region info-1 in world (6 x 3 x 6 = 108 blocks).");
        expect("addowner info-1 zoe", "Added zoe as owner of info-1.");
        expect("addowner info-1 amy", "Added amy as owner of info-1.");
        expect("addmember info-1 max", "Added max as member of info-1.");
        expect("addmember info-1 ben", "Added ben as member of info-1.");
        flag("info-1", "fire", "allow");
        flag("info-1", "block-break", "deny");
        expect("priority info-1 -3", "Priority of info-1 set to -3.");
        expect("info INFO-1", "Region info-1 in world from 890 -62 894 to 895 -60 899, priority -3", "Owners: amy, zoe",
            "Members: ben, max", "Flags: block-break=deny, fire=allow");
    }

    @GcbCase(value = "at lists the regions at a block by priority", order = 20)
    public void at() {
        define("low", 900, 900, 910, 910);
        define("high", 900, 900, 910, 910);
        define("mid-b", 900, 900, 910, 910);
        define("mid-a", 905, 905, 910, 910);
        expect("priority low 1", "Priority of low set to 1.");
        expect("priority high 9", "Priority of high set to 9.");
        expect("priority mid-a 5", "Priority of mid-a set to 5.");
        expect("priority mid-b 5", "Priority of mid-b set to 5.");
        expect("at world 905 -60 905",
            "Regions at world 905 -60 905: high (priority 9), mid-a (priority 5), mid-b (priority 5), low (priority 1)");
        expect("at world 901 -60 901", "Regions at world 901 -60 901: high (priority 9), mid-b (priority 5), low (priority 1)");
        expect("at world 950 -60 950", "No regions at world 950 -60 950.");
        expect("at nowhere 1 2 3", "Unknown world: nowhere");
        expect("at world 1 x 3", "Invalid coordinates.");
    }

    @GcbCase(value = "delete removes a region and its protection", order = 21)
    public void delete() {
        define("gone", 960, 960, 965, 965);
        flag("gone", "block-break", "deny");
        Actor lily = Actor.player("Lily");
        denied(lily, breakAt(lily, 962, -60, 962), "gone");
        expect("delete GONE", "Deleted region gone.");
        allowed(lily, breakAt(lily, 962, -60, 962));
        expect("info gone", "Unknown region: gone");
        expect("delete gone", "Unknown region: gone");
        GcbAssert.isFalse(Kit.yaml("regions.yml").contains("regions.gone"), "regions.yml no longer holds gone");
    }

    @GcbCase(value = "reload reads regions from disk", order = 22)
    public void reloadFromDisk() {
        Kit.write("regions.yml", """
            regions:
              castle:
                world: world
                min: {x: 1000, y: -64, z: 1000}
                max: {x: 1010, y: -50, z: 1010}
                priority: 2
                owners: [mona]
                members: []
                flags:
                  block-break: deny
                  explosion: deny
              far:
                world: nowhere
                min: {x: 1000, y: -64, z: 1000}
                max: {x: 1010, y: -50, z: 1010}
                priority: 0
                owners: []
                members: []
                flags:
                  block-break: deny
            """);
        expect("reload", "Wardstone reloaded (regions: 2).");
        expect("list", "2 regions: castle, far");
        expect("info castle", "Region castle in world from 1000 -64 1000 to 1010 -50 1010, priority 2", "Owners: mona",
            "Members: none", "Flags: block-break=deny, explosion=deny");
        expect("info far", "Region far in nowhere from 1000 -64 1000 to 1010 -50 1010, priority 0", "Owners: none",
            "Members: none", "Flags: block-break=deny");
        Actor nora = Actor.player("Nora");
        denied(nora, breakAt(nora, 1005, -60, 1005), "castle");
        Actor mona = Actor.player("Mona");
        allowed(mona, breakAt(mona, 1005, -60, 1005));
        expect("at world 1005 -60 1005", "Regions at world 1005 -60 1005: castle (priority 2)");
        Kit.write("regions.yml", "regions: {}\n");
        expect("reload", "Wardstone reloaded (regions: 0).");
        expect("list", "No regions.");
        allowed(nora, breakAt(nora, 1005, -60, 1005));
    }

    @GcbCase(value = "permissions are enforced", order = 23)
    public void permissions() {
        define("guarded", 1100, 1100, 1105, 1105);
        byte[] before = Kit.bytes("regions.yml");
        Actor nobody = Actor.limited("nobody_23");
        for (String line : List.of("define other world 0 0 0 1 1 1", "delete guarded", "priority guarded 3",
                "flag guarded fire deny", "addowner guarded amy", "removeowner guarded amy", "addmember guarded amy",
                "removemember guarded amy", "info guarded", "at world 1 2 3", "list", "reload")) {
            Kit.lines(nobody.run("ward " + line), "/ward " + line + " without permission", DENIED);
        }
        GcbAssert.isTrue(Arrays.equals(before, Kit.bytes("regions.yml")), "denied commands change nothing");
        Actor bypass = Actor.limited("bypass_23", "wardstone.bypass");
        Kit.lines(bypass.run("ward list"), "wardstone.bypass is not wardstone.admin", DENIED);
        Actor admin = Actor.limited("admin_23", "wardstone.admin");
        Kit.lines(admin.run("ward list"), "wardstone.admin lists", "1 regions: guarded");
    }

    @GcbCase(value = "malformed commands show usage", order = 24)
    public void usage() {
        expect("", USAGE);
        expect("bogus", USAGE);
        expect("define a world 1 2 3 4 5", "Usage: /ward define <region> <world> <x1> <y1> <z1> <x2> <y2> <z2>");
        expect("delete", "Usage: /ward delete <region>");
        expect("priority a", "Usage: /ward priority <region> <priority>");
        expect("flag a b", "Usage: /ward flag <region> <flag> <allow|deny|clear>");
        expect("addowner a", "Usage: /ward addowner <region> <player>");
        expect("removeowner a b c", "Usage: /ward removeowner <region> <player>");
        expect("addmember a", "Usage: /ward addmember <region> <player>");
        expect("removemember", "Usage: /ward removemember <region> <player>");
        expect("info", "Usage: /ward info <region>");
        expect("at world 1 2", "Usage: /ward at <world> <x> <y> <z>");
        expect("list all", "Usage: /ward list");
        expect("reload now", "Usage: /ward reload");
        Kit.lines(Actor.limited("nobody_24").run("ward delete"), "usage comes before the permission check",
            "Usage: /ward delete <region>");
        expect("LIST", "1 regions: guarded");
    }

    @GcbCase(value = "membership in a lower-priority region does not override a higher denial", order = 25)
    public void membershipDoesNotOverrideHigherPriority() {
        define("outer", 1200, 1200, 1220, 1220);
        define("inner", 1205, 1205, 1215, 1215);
        expect("priority outer 1", "Priority of outer set to 1.");
        expect("priority inner 9", "Priority of inner set to 9.");
        flag("outer", "block-break", "deny");
        flag("inner", "block-break", "deny");
        expect("addmember outer Alex", "Added alex as member of outer.");

        Actor alex = Actor.player("Alex");
        denied(alex, breakAt(alex, 1210, -60, 1210), "inner");
    }

    @GcbCase(value = "liquid flow respects the destination block-place flag", order = 26)
    public void liquidFlowProtection() {
        define("flowguard", 1301, 1300, 1305, 1305);
        flag("flowguard", "block-place", "deny");
        Block source = block(1300, -60, 1302);
        source.setType(Material.WATER, false);
        BlockFromToEvent into = new BlockFromToEvent(source, BlockFace.EAST);
        Bukkit.getPluginManager().callEvent(into);
        GcbAssert.isTrue(into.isCancelled(), "flow into a protected destination is cancelled");

        Block reverseSource = block(1301, -60, 1302);
        reverseSource.setType(Material.WATER, false);
        BlockFromToEvent out = new BlockFromToEvent(reverseSource, BlockFace.WEST);
        Bukkit.getPluginManager().callEvent(out);
        GcbAssert.isFalse(out.isCancelled(), "a protected source does not block flow out to an allowed destination");
    }
}
