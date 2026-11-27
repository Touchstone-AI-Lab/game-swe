package gcbtest.blocktrail;

import io.gamecodebench.harness.GcbAssert;
import io.gamecodebench.harness.GcbCase;
import io.gamecodebench.harness.GcbScript;
import io.gamecodebench.harness.GcbSuite;
import io.gamecodebench.harness.GcbWorlds;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import org.bukkit.Bukkit;
import org.bukkit.ExplosionResult;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.BlockState;
import org.bukkit.command.PluginCommand;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Creeper;
import org.bukkit.entity.TNTPrimed;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.entity.EntityExplodeEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;
import org.bukkit.permissions.Permission;
import org.bukkit.permissions.PermissionDefault;
import org.bukkit.plugin.java.JavaPlugin;

/** Hidden live-server cases for the BlockTrail construct task. */
public final class BlockTrailSuite implements GcbSuite {

    private static final String DENIED = "You do not have permission to do that.";
    private static final String USAGE = "Usage: /trail <lookup|player|rollback|purge|reload>";
    private static final int Y = -59;
    private static final String DEFAULT_CONFIG = """
        ignored-materials:
          - SHORT_GRASS
          - TALL_GRASS
          - FIRE
        worlds: []
        page-size: 5
        max-radius: 32
        """;

    private final Canceller canceller = new Canceller();

    @Override
    public void onEnable(JavaPlugin grader) {
        Bukkit.getPluginManager().registerEvents(canceller, grader);
    }

    // --- helpers -------------------------------------------------------------------------

    private static World world() {
        return GcbWorlds.main();
    }

    /** A block of the flat world at y = -59 (air above the grass), its chunk kept loaded. */
    private static Block block(int x, int z) {
        return block(x, Y, z);
    }

    private static Block block(int x, int y, int z) {
        Block block = world().getBlockAt(x, y, z);
        block.getChunk().setForceLoaded(true);
        return block;
    }

    private static String at(Block block) {
        return "world " + block.getX() + " " + block.getY() + " " + block.getZ();
    }

    private static List<String> trail(String arguments) {
        return Actor.console().run("trail " + arguments);
    }

    private static void expect(String arguments, String... expected) {
        Kit.lines(trail(arguments), "/trail " + arguments, expected);
    }

    private static void lookup(Block block, String... changes) {
        if (changes.length == 0) {
            expect("lookup " + at(block), "No changes at " + at(block) + ".");
            return;
        }
        String[] expected = new String[changes.length + 1];
        expected[0] = "Changes at " + at(block) + ":";
        System.arraycopy(changes, 0, expected, 1, changes.length);
        expect("lookup " + at(block), expected);
    }

    /** Breaks the block as the server would: the event first, then air unless cancelled. */
    private static BlockBreakEvent breakAs(Actor player, Block block, Material material) {
        block.setType(material, false);
        BlockBreakEvent event = new BlockBreakEvent(block, player.player());
        Bukkit.getPluginManager().callEvent(event);
        if (!event.isCancelled()) {
            block.setType(Material.AIR, false);
        }
        return event;
    }

    /** Places the material as the server would: the block holds it when the event is called. */
    private static BlockPlaceEvent placeAs(Actor player, Block block, Material material, boolean preCancelled) {
        BlockState replaced = block.getState();
        block.setType(material, false);
        ItemStack hand = new ItemStack(material.isItem() ? material : Material.FLINT_AND_STEEL);
        BlockPlaceEvent event = new BlockPlaceEvent(block, replaced, block.getRelative(BlockFace.DOWN),
            hand, player.player(), true, EquipmentSlot.HAND);
        event.setCancelled(preCancelled);
        Bukkit.getPluginManager().callEvent(event);
        if (event.isCancelled()) {
            replaced.update(true, false);
        }
        return event;
    }

    private static BlockPlaceEvent placeAs(Actor player, Block block, Material material) {
        return placeAs(player, block, material, false);
    }

    /** The current twelve-field and backward-compatible ten-field change lines. */
    private static List<String> changeLines() {
        return Kit.lines("changes.log").stream()
            .filter(line -> (line.split(";", -1).length == 10 || line.split(";", -1).length == 12)
                && line.substring(0, line.indexOf(';')).matches("[0-9]+"))
            .toList();
    }

    /** The highest id in changes.log, or 0. */
    private static long lastId() {
        long max = 0;
        for (String line : changeLines()) {
            max = Math.max(max, Long.parseLong(line.substring(0, line.indexOf(';'))));
        }
        return max;
    }

    private static List<String> lastLines(int count) {
        List<String> lines = Kit.lines("changes.log");
        GcbAssert.isTrue(lines.size() >= count, "changes.log has at least " + count + " lines: " + lines);
        return lines.subList(lines.size() - count, lines.size());
    }

    private static void restoreDefaultConfig() {
        Kit.write("config.yml", DEFAULT_CONFIG);
        List<String> reply = trail("reload");
        GcbAssert.isTrue(reply.size() == 1 && reply.get(0).startsWith("BlockTrail reloaded (changes: "),
            "reload after restoring config.yml: " + reply);
    }

    private static String line(long id, long time, String actor, String action, Block block, String from, String to) {
        return id + ";" + time + ";" + actor + ";" + action + ";world;" + block.getX() + ";" + block.getY() + ";"
            + block.getZ() + ";" + from + ";" + to;
    }

    // --- cases ---------------------------------------------------------------------------

    @GcbCase(value = "BlockTrail is enabled", order = 0)
    public void sentinel() {
        GcbAssert.isTrue(Kit.plugin().isEnabled(), "BlockTrail is enabled");
        GcbAssert.equals("BlockTrail", Kit.plugin().getName(), "plugin name");
    }

    @GcbCase(value = "default config.yml is written on first enable", order = 1)
    public void defaultConfig() {
        YamlConfiguration yaml = Kit.yaml("config.yml");
        List<String> ignored = yaml.getStringList("ignored-materials").stream()
            .map(name -> name.trim().toUpperCase(Locale.ROOT)).toList();
        GcbAssert.equals(List.of("SHORT_GRASS", "TALL_GRASS", "FIRE"), ignored, "ignored-materials");
        GcbAssert.isTrue(yaml.isList("worlds") && yaml.getList("worlds").isEmpty(), "worlds is an empty list");
        GcbAssert.equals(5, yaml.getInt("page-size"), "page-size");
        GcbAssert.equals(32, yaml.getInt("max-radius"), "max-radius");
    }

    @GcbCase(value = "plugin.yml declares the trail command and permissions", order = 2)
    public void declarations() {
        PluginCommand command = Bukkit.getPluginCommand("trail");
        GcbAssert.notNull(command, "/trail is a plugin command");
        GcbAssert.equals("BlockTrail", command.getPlugin().getName(), "/trail belongs to BlockTrail");
        GcbAssert.isNull(command.getPermission(), "/trail has no permission key");
        for (String name : List.of("blocktrail.lookup", "blocktrail.rollback", "blocktrail.admin")) {
            Permission permission = Bukkit.getPluginManager().getPermission(name);
            GcbAssert.notNull(permission, name + " is registered");
            GcbAssert.equals(PermissionDefault.OP, permission.getDefault(), name + " default");
        }
    }

    @GcbCase(value = "a broken block is recorded and shown by lookup", order = 3)
    public void breakRecorded() {
        long id = lastId() + 1;
        Block block = block(1000, 0);
        BlockBreakEvent event = breakAs(Actor.player("Alice"), block, Material.STONE);
        GcbAssert.isFalse(event.isCancelled(), "BlockTrail does not cancel breaks");
        lookup(block, "#" + id + " Alice broke stone");
    }

    @GcbCase(value = "a placed block records the material it replaced", order = 4)
    public void placeRecorded() {
        long id = lastId() + 1;
        Actor bob = Actor.player("Bob");
        Block air = block(1016, 0);
        air.setType(Material.AIR, false);
        placeAs(bob, air, Material.OAK_PLANKS);
        Block grass = block(1016, 2);
        grass.setType(Material.SHORT_GRASS, false);
        placeAs(bob, grass, Material.DIRT);
        lookup(air, "#" + id + " Bob placed oak_planks over air");
        lookup(grass, "#" + (id + 1) + " Bob placed dirt over short_grass");
    }

    @GcbCase(value = "lookup lists every change at a block newest first", order = 5)
    public void lookupOrder() {
        long id = lastId() + 1;
        Block block = block(1032, 0);
        block.setType(Material.AIR, false);
        placeAs(Actor.player("Carl"), block, Material.COBBLESTONE);
        breakAs(Actor.player("Dana"), block, Material.COBBLESTONE);
        placeAs(Actor.player("Carl"), block, Material.GLASS);
        lookup(block,
            "#" + (id + 2) + " Carl placed glass over air",
            "#" + (id + 1) + " Dana broke cobblestone",
            "#" + id + " Carl placed cobblestone over air");
    }

    @GcbCase(value = "cancelled changes are not recorded", order = 6)
    public void cancelledChanges() {
        Actor erin = Actor.player("Erin");
        Block cancelledByPlugin = block(1048, 0);
        Block cancelledBefore = block(1048, 2);
        Block recorded = block(1048, 4);
        long id = lastId() + 1;
        canceller.cancelBreakAt(cancelledByPlugin.getLocation());
        try {
            GcbAssert.isTrue(breakAs(erin, cancelledByPlugin, Material.STONE).isCancelled(),
                "another plugin cancelled the break at HIGHEST");
        } finally {
            canceller.clear();
        }
        cancelledBefore.setType(Material.AIR, false);
        placeAs(erin, cancelledBefore, Material.STONE, true);
        breakAs(erin, recorded, Material.STONE);
        lookup(cancelledByPlugin);
        lookup(cancelledBefore);
        lookup(recorded, "#" + id + " Erin broke stone");
        GcbAssert.equals(Material.STONE, cancelledByPlugin.getType(), "the cancelled break left the block");
    }

    @GcbCase(value = "ignored materials are not recorded", order = 7)
    public void ignoredMaterials() {
        Actor finn = Actor.player("Finn");
        Block grass = block(1064, 0);
        Block fire = block(1064, 2);
        Block stone = block(1064, 4);
        long id = lastId() + 1;
        breakAs(finn, grass, Material.SHORT_GRASS);
        fire.setType(Material.AIR, false);
        placeAs(finn, fire, Material.FIRE);
        fire.setType(Material.AIR, false);
        breakAs(finn, stone, Material.STONE);
        lookup(grass);
        lookup(fire);
        lookup(stone, "#" + id + " Finn broke stone");
    }

    @GcbCase(value = "only the configured worlds are recorded", order = 8)
    public void worldFilter() {
        Actor gus = Actor.player("Gus");
        Block skipped = block(1080, 0);
        Block recorded = block(1080, 2);
        Block ignored = block(1080, 4);
        try {
            int count = changeLines().size();
            Kit.write("config.yml", DEFAULT_CONFIG.replace("worlds: []", "worlds:\n  - elsewhere"));
            expect("reload", "BlockTrail reloaded (changes: " + count + ").");
            breakAs(gus, skipped, Material.STONE);
            Kit.write("config.yml", """
                ignored-materials:
                  - cobblestone
                worlds:
                  - world
                page-size: 5
                max-radius: 32
                """);
            expect("reload", "BlockTrail reloaded (changes: " + count + ").");
            long id = lastId() + 1;
            breakAs(gus, recorded, Material.STONE);
            breakAs(gus, ignored, Material.COBBLESTONE);
            lookup(skipped);
            lookup(recorded, "#" + id + " Gus broke stone");
            lookup(ignored);
        } finally {
            restoreDefaultConfig();
        }
    }

    @GcbCase(value = "each exploded block is recorded", order = 9)
    public void explosionRecorded() {
        Block stone = block(1096, 0);
        Block dirt = block(1096, 1);
        Block air = block(1096, 2);
        Block grass = block(1096, 3);
        Block spared = block(1096, 4);
        stone.setType(Material.STONE, false);
        dirt.setType(Material.DIRT, false);
        air.setType(Material.AIR, false);
        grass.setType(Material.SHORT_GRASS, false);
        spared.setType(Material.COBBLESTONE, false);
        Creeper creeper = world().spawn(block(1096, 8).getLocation().add(0.5, 0, 0.5), Creeper.class);
        long id = lastId() + 1;
        canceller.spareFromExplosions(spared.getLocation());
        try {
            List<Block> blocks = new ArrayList<>(List.of(stone, dirt, air, grass, spared));
            EntityExplodeEvent event = new EntityExplodeEvent(creeper, creeper.getLocation(), blocks, 1.0f,
                ExplosionResult.DESTROY);
            Bukkit.getPluginManager().callEvent(event);
            GcbAssert.isFalse(event.isCancelled(), "BlockTrail does not cancel explosions");
            for (Block block : event.blockList()) {
                block.setType(Material.AIR, false);
            }
        } finally {
            canceller.clear();
            creeper.remove();
        }
        lookup(stone, "#" + id + " #creeper exploded stone");
        lookup(dirt, "#" + (id + 1) + " #creeper exploded dirt");
        lookup(air);
        lookup(grass);
        lookup(spared);
        GcbAssert.equals(Material.COBBLESTONE, spared.getType(), "the spared block is untouched");
    }

    @GcbCase(value = "changes.log uses the documented line format", order = 10)
    public void logFormat() {
        Actor hana = Actor.player("Hana");
        Block block = block(1112, 0);
        long id = lastId() + 1;
        long before = System.currentTimeMillis();
        breakAs(hana, block, Material.STONE);
        long after = System.currentTimeMillis();
        placeAs(hana, block, Material.OAK_PLANKS);
        List<String> lines = lastLines(2);
        String[] fields = lines.get(0).split(";", -1);
        GcbAssert.equals(12, fields.length, "twelve fields including block data: " + lines.get(0));
        long time = Long.parseLong(fields[1]);
        GcbAssert.isTrue(time >= before && time <= after, "the time is when the change was recorded: " + time);
        GcbAssert.equals(line(id, time, "Hana", "break", block, "stone", "air")
            + ";minecraft:stone;minecraft:air", lines.get(0), "break line");
        GcbAssert.equals("minecraft:stone", fields[10], "recorded broken block data");
        GcbAssert.equals("minecraft:air", fields[11], "recorded replacement block data");
        String[] placed = lines.get(1).split(";", -1);
        GcbAssert.equals(12, placed.length, "twelve fields: " + lines.get(1));
        GcbAssert.equals(line(id + 1, Long.parseLong(placed[1]), "Hana", "place", block, "air", "oak_planks")
                + ";minecraft:air;minecraft:oak_planks",
            lines.get(1), "place line");
    }

    @GcbCase(value = "player lists an actor's changes with paging", order = 11)
    public void playerPaging() {
        Actor ivan = Actor.player("Ivan");
        long id = lastId() + 1;
        List<Block> blocks = new ArrayList<>();
        for (int i = 0; i < 7; i++) {
            Block block = block(1128 + i, 0);
            blocks.add(block);
            breakAs(ivan, block, i % 2 == 0 ? Material.STONE : Material.DIRT);
        }
        List<String> described = new ArrayList<>();
        for (int i = 6; i >= 0; i--) {
            described.add("#" + (id + i) + " broke " + (i % 2 == 0 ? "stone" : "dirt") + " at " + at(blocks.get(i)));
        }
        List<String> first = new ArrayList<>(List.of("Changes by Ivan (page 1/2):"));
        first.addAll(described.subList(0, 5));
        GcbAssert.equals(first, trail("player Ivan"), "/trail player Ivan");
        List<String> second = new ArrayList<>(List.of("Changes by IVAN (page 2/2):"));
        second.addAll(described.subList(5, 7));
        GcbAssert.equals(second, trail("player IVAN 2"), "/trail player IVAN 2");
    }

    @GcbCase(value = "lookup and player validate their arguments", order = 12)
    public void lookupValidation() {
        expect("lookup nowhere 1 2 3", "Unknown world: nowhere");
        expect("lookup nowhere x 2 3", "Unknown world: nowhere");
        expect("lookup world 1 x 3", "Invalid coordinates.");
        expect("lookup world 1.5 2 3", "Invalid coordinates.");
        expect("lookup world 5000 -59 5000", "No changes at world 5000 -59 5000.");
        expect("player Nobody_12", "No changes by Nobody_12.");
        long id = lastId() + 1;
        Block block = block(1144, 0);
        breakAs(Actor.player("Jana"), block, Material.STONE);
        expect("player jana 2", "Page 2 does not exist; last page is 1.");
        expect("player jana 0", "Invalid page: 0");
        expect("player jana x", "Invalid page: x");
        expect("player jana 1", "Changes by jana (page 1/1):", "#" + id + " broke stone at " + at(block));
    }

    @GcbCase(value = "rollback restores broken and placed blocks", order = 13)
    public void rollbackRestores() {
        Actor kai = Actor.player("Kai");
        Block broken = block(1160, 0);
        Block placed = block(1161, 0);
        Block replaced = block(1162, 0);
        breakAs(kai, broken, Material.STONE);
        placed.setType(Material.AIR, false);
        placeAs(kai, placed, Material.GLASS);
        replaced.setType(Material.SHORT_GRASS, false);
        placeAs(kai, replaced, Material.DIRT);
        expect("rollback Kai " + at(broken) + " 3 60", "Rollback of Kai: 3 restored, 0 skipped.");
        GcbAssert.equals(Material.STONE, broken.getType(), "the broken block is back");
        GcbAssert.equals(Material.AIR, placed.getType(), "the placed block is gone");
        GcbAssert.equals(Material.SHORT_GRASS, replaced.getType(), "the replaced block is back");
    }

    @GcbCase(value = "rollback undoes changes newest first", order = 14)
    public void rollbackOrder() {
        Actor leo = Actor.player("Leo");
        Block block = block(1176, 0);
        breakAs(leo, block, Material.STONE);
        placeAs(leo, block, Material.DIRT);
        expect("rollback leo " + at(block) + " 0 60", "Rollback of leo: 2 restored, 0 skipped.");
        GcbAssert.equals(Material.STONE, block.getType(), "the block is back to its first state");
    }

    @GcbCase(value = "rollback only touches the actor's changes inside the radius", order = 15)
    public void rollbackArea() {
        Actor mia = Actor.player("Mia");
        Block centre = block(1192, 0);
        Block east = block(1195, 0);
        Block above = block(1192, Y + 2, 0);
        Block tooFar = block(1192, 4);
        Block other = block(1193, 0);
        for (Block block : List.of(centre, east, above, tooFar)) {
            breakAs(mia, block, Material.STONE);
        }
        breakAs(Actor.player("Nia"), other, Material.STONE);
        expect("rollback MIA " + at(centre) + " 3 60", "Rollback of MIA: 3 restored, 0 skipped.");
        GcbAssert.equals(Material.STONE, centre.getType(), "the centre is back");
        GcbAssert.equals(Material.STONE, east.getType(), "the block 3 east is back");
        GcbAssert.equals(Material.STONE, above.getType(), "the block 2 above is back");
        GcbAssert.equals(Material.AIR, tooFar.getType(), "the block 4 south is outside the radius");
        GcbAssert.equals(Material.AIR, other.getType(), "another actor's change stays");
    }

    @GcbCase(value = "rollback skips blocks that changed since", order = 16)
    public void rollbackSkips() {
        Actor omar = Actor.player("Omar");
        Block contested = block(1208, 0);
        Block free = block(1209, 0);
        long id = lastId() + 1;
        breakAs(omar, contested, Material.STONE);
        placeAs(Actor.player("Pia"), contested, Material.DIRT);
        breakAs(omar, free, Material.STONE);
        expect("rollback Omar " + at(contested) + " 2 60", "Rollback of Omar: 1 restored, 1 skipped.");
        GcbAssert.equals(Material.DIRT, contested.getType(), "the block changed since is left alone");
        GcbAssert.equals(Material.STONE, free.getType(), "the untouched block is restored");
        lookup(contested, "#" + (id + 1) + " Pia placed dirt over air", "#" + id + " Omar broke stone");
    }

    @GcbCase(value = "rolled back changes are marked and never rolled back twice", order = 17)
    public void rollbackMarks() {
        Actor quin = Actor.player("Quin");
        Block block = block(1224, 0);
        long id = lastId() + 1;
        breakAs(quin, block, Material.STONE);
        expect("rollback Quin " + at(block) + " 1 60", "Rollback of Quin: 1 restored, 0 skipped.");
        GcbAssert.equals(List.of("undo;" + id), lastLines(1), "the undo line is appended");
        lookup(block, "#" + id + " Quin broke stone (rolled back)");
        expect("player Quin", "Changes by Quin (page 1/1):", "#" + id + " broke stone at " + at(block) + " (rolled back)");
        block.setType(Material.AIR, false);
        expect("rollback Quin " + at(block) + " 1 60", "Nothing to roll back for Quin.");
        GcbAssert.equals(Material.AIR, block.getType(), "a rolled-back change is not applied again");
    }

    @GcbCase(value = "rollback validates radius and time", order = 18)
    public void rollbackValidation() {
        expect("rollback Rex world 0 -59 0 33 60", "Radius must be a whole number from 0 to 32.");
        expect("rollback Rex world 0 -59 0 -1 60", "Radius must be a whole number from 0 to 32.");
        expect("rollback Rex world 0 -59 0 x 60", "Radius must be a whole number from 0 to 32.");
        expect("rollback Rex world 0 -59 0 5 0", "Invalid time: 0");
        expect("rollback Rex world 0 -59 0 5 x", "Invalid time: x");
        expect("rollback Rex nowhere 0 -59 0 x x", "Unknown world: nowhere");
        expect("rollback Rex world 0 y 0 x x", "Invalid coordinates.");
        expect("rollback Nobody_18 world 0 -59 0 5 60", "Nothing to roll back for Nobody_18.");
        Block block = block(1240, 0);
        breakAs(Actor.player("Rex"), block, Material.STONE);
        expect("rollback Rex " + at(block) + " 0 60", "Rollback of Rex: 1 restored, 0 skipped.");
    }

    @GcbCase(value = "a real TNT explosion is recorded and rolled back", order = 19, ticks = 400)
    public void realTnt(GcbScript script) {
        World world = world();
        // Inside the world border (max-world-size 1024), where block ticking is not suspended.
        int cx = 600;
        int cz = 600;
        int reach = 7;
        List<Material> before = new ArrayList<>();
        for (int dx = -1; dx <= 1; dx++) {
            for (int dz = -1; dz <= 1; dz++) {
                world.getChunkAt((cx >> 4) + dx, (cz >> 4) + dz).setForceLoaded(true);
            }
        }
        script.step(() -> {
            for (int x = cx - reach; x <= cx + reach; x++) {
                for (int y = Y - reach; y <= Y + reach; y++) {
                    for (int z = cz - reach; z <= cz + reach; z++) {
                        before.add(world.getBlockAt(x, y, z).getType());
                    }
                }
            }
            TNTPrimed tnt = world.spawn(new Location(world, cx + 0.5, Y, cz + 0.5), TNTPrimed.class);
            tnt.setFuseTicks(10);
        });
        script.waitTicks(40);
        script.step(() -> {
            int changed = 0;
            int index = 0;
            for (int x = cx - reach; x <= cx + reach; x++) {
                for (int y = Y - reach; y <= Y + reach; y++) {
                    for (int z = cz - reach; z <= cz + reach; z++) {
                        if (world.getBlockAt(x, y, z).getType() != before.get(index++)) {
                            changed++;
                        }
                    }
                }
            }
            GcbAssert.isTrue(changed > 0, "the TNT exploded and destroyed blocks");
            List<String> history = trail("player #tnt");
            GcbAssert.isTrue(!history.isEmpty() && history.get(0).startsWith("Changes by #tnt (page 1/"),
                "the explosion is recorded: " + history);
            expect("rollback #TNT world " + cx + " " + Y + " " + cz + " 8 600",
                "Rollback of #TNT: " + changed + " restored, 0 skipped.");
            index = 0;
            for (int x = cx - reach; x <= cx + reach; x++) {
                for (int y = Y - reach; y <= Y + reach; y++) {
                    for (int z = cz - reach; z <= cz + reach; z++) {
                        Material expected = before.get(index++);
                        GcbAssert.equals(expected, world.getBlockAt(x, y, z).getType(),
                            "block " + x + " " + y + " " + z + " is restored");
                    }
                }
            }
        });
    }

    @GcbCase(value = "rollback honours the time window", order = 20)
    public void rollbackWindow() {
        long now = System.currentTimeMillis();
        Block old = block(1256, 0);
        Block recent = block(1257, 0);
        Block newest = block(1258, 0);
        for (Block block : List.of(old, recent, newest)) {
            block.setType(Material.AIR, false);
        }
        Kit.write("changes.log", String.join("\n",
            line(900, now - 7_200_000, "Sam", "break", old, "stone", "air"),
            line(901, now - 60_000, "Sam", "break", recent, "stone", "air"),
            line(902, now - 1_000, "Sam", "break", newest, "stone", "air")) + "\n");
        expect("reload", "BlockTrail reloaded (changes: 3).");
        expect("rollback Sam " + at(old) + " 5 3600", "Rollback of Sam: 2 restored, 0 skipped.");
        GcbAssert.equals(Material.AIR, old.getType(), "the change older than the window stays");
        GcbAssert.equals(Material.STONE, recent.getType(), "the change a minute ago is restored");
        GcbAssert.equals(Material.STONE, newest.getType(), "the newest change is restored");
        Block next = block(1260, 0);
        breakAs(Actor.player("Tara"), next, Material.STONE);
        lookup(next, "#903 Tara broke stone");
    }

    @GcbCase(value = "purge removes old changes and rewrites the log", order = 21)
    public void purge() {
        long now = System.currentTimeMillis();
        Block a = block(1272, 0);
        String l1 = line(1, now - 7_200_000, "Uma", "break", a, "stone", "air");
        String l2 = line(2, now - 7_100_000, "Uma", "break", block(1273, 0), "dirt", "air");
        String l3 = line(3, now - 1_000, "Uma", "place", block(1274, 0), "air", "glass");
        String l4 = line(4, now - 900, "Uma", "break", block(1275, 0), "stone", "air");
        String l5 = line(5, now - 800, "Vic", "break", block(1276, 0), "stone", "air");
        Kit.write("changes.log", String.join("\n", l1, l2, "undo;2", l3, l4, l5, "undo;4") + "\n");
        expect("reload", "BlockTrail reloaded (changes: 5).");
        expect("purge 3600", "Purge complete: 2 removed, 3 kept.");
        GcbAssert.equals(List.of(l3, l4, l5, "undo;4"), Kit.lines("changes.log"), "the rewritten changes.log");
        lookup(a);
        expect("player uma", "Changes by uma (page 1/1):",
            "#4 broke stone at world 1275 -59 0 (rolled back)", "#3 placed glass over air at world 1274 -59 0");
        Block next = block(1278, 0);
        breakAs(Actor.player("Uma"), next, Material.STONE);
        lookup(next, "#6 Uma broke stone");
        expect("purge x", "Invalid time: x");
    }

    @GcbCase(value = "reload reads changes and rollback marks from disk", order = 22)
    public void reloadFromDisk() {
        long now = System.currentTimeMillis();
        Block broken = block(1288, 0);
        Block placed = block(1289, 0);
        Block exploded = block(1290, 0);
        Kit.write("changes.log", String.join("\n",
            line(20, now - 5_000, "Vera", "break", broken, "stone", "air"),
            "",
            "undo;20",
            line(21, now - 4_000, "Vera", "place", placed, "air", "glass"),
            "this is not a change",
            "undo;99",
            line(25, now - 3_000, "#tnt", "explode", exploded, "dirt", "air")) + "\n");
        expect("reload", "BlockTrail reloaded (changes: 3).");
        lookup(broken, "#20 Vera broke stone (rolled back)");
        lookup(placed, "#21 Vera placed glass over air");
        lookup(exploded, "#25 #tnt exploded dirt");
        expect("player vera", "Changes by vera (page 1/1):",
            "#21 placed glass over air at " + at(placed),
            "#20 broke stone at " + at(broken) + " (rolled back)");
        Block next = block(1292, 0);
        breakAs(Actor.player("Wes"), next, Material.STONE);
        lookup(next, "#26 Wes broke stone");
    }

    @GcbCase(value = "permissions are enforced", order = 23)
    public void permissions() {
        Block block = block(1304, 0);
        breakAs(Actor.player("Xena"), block, Material.STONE);
        Actor nobody = Actor.limited("nobody_23");
        for (String line : List.of("lookup " + at(block), "player Xena", "rollback Xena " + at(block) + " 1 60",
                "purge 60", "reload")) {
            Kit.lines(nobody.run("trail " + line), "/trail " + line + " without permission", DENIED);
        }
        GcbAssert.equals(Material.AIR, block.getType(), "the denied rollback changed nothing");
        Actor looker = Actor.limited("looker_23", "blocktrail.lookup");
        List<String> seen = looker.run("trail lookup " + at(block));
        GcbAssert.isTrue(seen.size() == 2 && seen.get(1).endsWith(" Xena broke stone"), "lookup with blocktrail.lookup: " + seen);
        Kit.lines(looker.run("trail rollback Xena " + at(block) + " 1 60"), "rollback needs blocktrail.rollback", DENIED);
        Actor roller = Actor.limited("roller_23", "blocktrail.rollback");
        Kit.lines(roller.run("trail rollback Xena " + at(block) + " 1 60"), "rollback with blocktrail.rollback",
            "Rollback of Xena: 1 restored, 0 skipped.");
        Kit.lines(roller.run("trail purge 60"), "purge needs blocktrail.admin", DENIED);
        Actor admin = Actor.limited("admin_23", "blocktrail.admin");
        int count = changeLines().size();
        Kit.lines(admin.run("trail purge 999999"), "purge with blocktrail.admin",
            "Purge complete: 0 removed, " + count + " kept.");
    }

    @GcbCase(value = "rollback combines actor, radius and time filters", order = 24)
    public void rollbackCombinedFilters() {
        Kit.write("config.yml", DEFAULT_CONFIG);
        Block old = block(1240, 0);
        Block selected = block(1241, 0);
        Block otherActor = block(1242, 0);
        Block outside = block(1244, 0);
        for (Block changed : List.of(old, selected, otherActor, outside)) {
            changed.setType(Material.AIR, false);
        }
        long now = System.currentTimeMillis();
        Kit.write("changes.log", String.join("\n",
            line(1, now - 120_000, "Riley", "break", old, "stone", "air"),
            line(2, now - 1_000, "Riley", "break", selected, "stone", "air"),
            line(3, now - 1_000, "Sam", "break", otherActor, "stone", "air"),
            line(4, now - 1_000, "Riley", "break", outside, "stone", "air")) + "\n");
        expect("reload", "BlockTrail reloaded (changes: 4).");

        expect("rollback riley " + at(selected) + " 2 60", "Rollback of riley: 1 restored, 0 skipped.");

        GcbAssert.equals(Material.AIR, old.getType(), "an old Riley change is outside the time window");
        GcbAssert.equals(Material.STONE, selected.getType(), "the recent nearby Riley change is restored");
        GcbAssert.equals(Material.AIR, otherActor.getType(), "another actor's nearby change is untouched");
        GcbAssert.equals(Material.AIR, outside.getType(), "Riley's change outside the radius is untouched");
        GcbAssert.equals(List.of("undo;2"), Kit.lines("changes.log").stream()
            .filter(line -> line.startsWith("undo;")).toList(), "only the selected record is marked rolled back");
    }

    @GcbCase(value = "rollback restores directional block data and skips stale states", order = 26)
    public void rollbackRestoresBlockData() {
        Block stairs = block(1262, 0);
        stairs.setType(Material.OAK_STAIRS, false);
        stairs.setBlockData(Bukkit.createBlockData(
            "minecraft:oak_stairs[facing=east,half=top,shape=inner_left,waterlogged=true]"), false);
        String original = stairs.getBlockData().getAsString();
        Actor player = Actor.player("Wren");
        BlockBreakEvent event = new BlockBreakEvent(stairs, player.player());
        Bukkit.getPluginManager().callEvent(event);
        GcbAssert.isFalse(event.isCancelled(), "BlockTrail observes but does not cancel the break");
        stairs.setType(Material.AIR, false);
        String[] fields = changeLines().get(changeLines().size() - 1).split(";", -1);
        GcbAssert.equals(original, fields[10], "the log stores the complete original block state");
        GcbAssert.equals("minecraft:air", fields[11], "the log stores the complete post-break state");

        expect("rollback Wren " + at(stairs) + " 1 60", "Rollback of Wren: 1 restored, 0 skipped.");
        GcbAssert.equals(original, stairs.getBlockData().getAsString(), "rollback restores facing, half, shape and waterlogging");

        BlockBreakEvent second = new BlockBreakEvent(stairs, player.player());
        Bukkit.getPluginManager().callEvent(second);
        stairs.setType(Material.AIR, false);
        stairs.setBlockData(Bukkit.createBlockData(
            "minecraft:oak_stairs[facing=west,half=top,shape=inner_left,waterlogged=true]"), false);
        expect("rollback Wren " + at(stairs) + " 1 60", "Rollback of Wren: 0 restored, 1 skipped.");
        GcbAssert.equals("minecraft:oak_stairs[facing=west,half=top,shape=inner_left,waterlogged=true]",
            stairs.getBlockData().getAsString(), "rollback does not overwrite a later data-only change");
    }

    @GcbCase(value = "malformed commands show usage", order = 25)
    public void usage() {
        expect("", USAGE);
        expect("bogus", USAGE);
        expect("lookup world 1 2", "Usage: /trail lookup <world> <x> <y> <z>");
        expect("lookup world 1 2 3 4", "Usage: /trail lookup <world> <x> <y> <z>");
        expect("player", "Usage: /trail player <actor> [page]");
        expect("player a 1 2", "Usage: /trail player <actor> [page]");
        expect("rollback a world 1 2 3 4", "Usage: /trail rollback <actor> <world> <x> <y> <z> <radius> <seconds>");
        expect("purge", "Usage: /trail purge <seconds>");
        expect("reload now", "Usage: /trail reload");
        Kit.lines(Actor.limited("nobody_24").run("trail purge"), "usage comes before the permission check",
            "Usage: /trail purge <seconds>");
        List<String> reply = trail("LOOKUP world 5001 -59 5001");
        GcbAssert.equals(List.of("No changes at world 5001 -59 5001."), reply, "subcommands are case-insensitive");
    }
}
