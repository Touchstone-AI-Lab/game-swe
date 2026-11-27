package gcbtest.recipesmith;

import io.gamecodebench.harness.GcbAssert;
import io.gamecodebench.harness.GcbCase;
import io.gamecodebench.harness.GcbScript;
import io.gamecodebench.harness.GcbSuite;
import io.gamecodebench.harness.GcbWorlds;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Set;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;
import org.bukkit.Bukkit;
import org.bukkit.Keyed;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.block.Furnace;
import org.bukkit.command.PluginCommand;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.inventory.BlastingRecipe;
import org.bukkit.inventory.CampfireRecipe;
import org.bukkit.inventory.CookingRecipe;
import org.bukkit.inventory.FurnaceInventory;
import org.bukkit.inventory.FurnaceRecipe;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.Recipe;
import org.bukkit.inventory.ShapedRecipe;
import org.bukkit.inventory.SmokingRecipe;
import org.bukkit.inventory.StonecuttingRecipe;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.permissions.Permission;
import org.bukkit.permissions.PermissionDefault;
import org.bukkit.plugin.java.JavaPlugin;

/** Hidden live-server cases for the Recipesmith construct task. */
public final class RecipesmithSuite implements GcbSuite {

    private static final String DENIED = "You do not have permission to do that.";
    private static final String USAGE = "Usage: /recipes <reload|list|disable|enable>";
    private static final Material X = null;

    @Override
    public void onEnable(JavaPlugin grader) {
    }

    // --- helpers -------------------------------------------------------------------------

    private static World world() {
        return GcbWorlds.main();
    }

    private static List<String> recipes(String arguments) {
        return Actor.console().run("recipes " + arguments);
    }

    private static void expect(String arguments, String... expected) {
        Kit.lines(recipes(arguments), "/recipes " + arguments, expected);
    }

    private static void seed(String yaml, String... reply) {
        Kit.write("recipes.yml", yaml);
        expect("reload", reply);
    }

    private static NamespacedKey key(String id) {
        return new NamespacedKey("recipesmith", id);
    }

    private static ItemStack[] grid(Material... slots) {
        GcbAssert.equals(9, slots.length, "a crafting grid has nine slots");
        ItemStack[] grid = new ItemStack[9];
        for (int i = 0; i < 9; i++) {
            grid[i] = slots[i] == null ? null : new ItemStack(slots[i]);
        }
        return grid;
    }

    private static ItemStack[] copy(ItemStack[] grid) {
        ItemStack[] copy = new ItemStack[grid.length];
        for (int i = 0; i < grid.length; i++) {
            copy[i] = grid[i] == null ? null : grid[i].clone();
        }
        return copy;
    }

    /** The key of the recipe the server matches for this grid, or null. */
    private static NamespacedKey matched(ItemStack[] grid) {
        Recipe recipe = Bukkit.getCraftingRecipe(copy(grid), world());
        return recipe instanceof Keyed keyed ? keyed.getKey() : null;
    }

    private static ItemStack crafted(ItemStack[] grid) {
        return Bukkit.craftItemResult(copy(grid), world()).getResult();
    }

    private static void crafts(ItemStack[] grid, NamespacedKey key, Material material, int amount, String what) {
        GcbAssert.equals(key, matched(grid), what + ": the matched recipe");
        ItemStack result = crafted(grid);
        GcbAssert.equals(material, result.getType(), what + ": the result");
        GcbAssert.equals(amount, result.getAmount(), what + ": the amount");
    }

    private static void noCraft(ItemStack[] grid, String what) {
        NamespacedKey key = matched(grid);
        GcbAssert.isNull(key, what + ": nothing is crafted");
    }

    private static String plain(Component component) {
        return component == null ? null : PlainTextComponentSerializer.plainText().serialize(component);
    }

    private static Set<String> ownKeys() {
        Set<String> keys = new HashSet<>();
        for (Iterator<Recipe> it = Bukkit.recipeIterator(); it.hasNext(); ) {
            if (it.next() instanceof Keyed keyed && keyed.getKey().getNamespace().equals("recipesmith")) {
                keys.add(keyed.getKey().getKey());
            }
        }
        return keys;
    }

    private static ItemStack[] torchGrid() {
        return grid(Material.COAL, X, X, Material.STICK, X, X, X, X, X);
    }

    private static ItemStack[] soulTorchGrid() {
        return grid(Material.COAL, X, X, Material.STICK, X, X, Material.SOUL_SAND, X, X);
    }

    private static ItemStack[] lanternGrid() {
        Material n = Material.IRON_NUGGET;
        return grid(n, n, n, n, Material.TORCH, n, n, n, n);
    }

    // --- cases ---------------------------------------------------------------------------

    @GcbCase(value = "Recipesmith is enabled", order = 0)
    public void sentinel() {
        GcbAssert.isTrue(Kit.plugin().isEnabled(), "Recipesmith is enabled");
        GcbAssert.equals("Recipesmith", Kit.plugin().getName(), "plugin name");
    }

    @GcbCase(value = "the default recipe file is written and loaded", order = 1)
    public void defaultFile() {
        YamlConfiguration yaml = Kit.yaml("recipes.yml");
        GcbAssert.equals("shaped", yaml.getString("recipes.compact_dirt.type"), "type");
        GcbAssert.equals(List.of("DD", "DD"), yaml.getStringList("recipes.compact_dirt.shape"), "shape");
        GcbAssert.equals("DIRT", yaml.getString("recipes.compact_dirt.ingredients.D"), "ingredient D");
        GcbAssert.equals("COARSE_DIRT", yaml.getString("recipes.compact_dirt.result.material"), "result material");
        GcbAssert.equals(4, yaml.getInt("recipes.compact_dirt.result.amount"), "result amount");
        GcbAssert.isTrue(yaml.isList("disabled-vanilla") && yaml.getList("disabled-vanilla").isEmpty(),
            "disabled-vanilla is an empty list");
        Recipe recipe = Bukkit.getRecipe(key("compact_dirt"));
        GcbAssert.isTrue(recipe instanceof ShapedRecipe, "recipesmith:compact_dirt is a shaped recipe: " + recipe);
        Material d = Material.DIRT;
        crafts(grid(d, d, X, d, d, X, X, X, X), key("compact_dirt"), Material.COARSE_DIRT, 4, "four dirt");
    }

    @GcbCase(value = "plugin.yml declares the recipes command and permission", order = 2)
    public void declarations() {
        PluginCommand command = Bukkit.getPluginCommand("recipes");
        GcbAssert.notNull(command, "/recipes is a plugin command");
        GcbAssert.equals("Recipesmith", command.getPlugin().getName(), "/recipes belongs to Recipesmith");
        GcbAssert.isNull(command.getPermission(), "/recipes has no permission key");
        Permission permission = Bukkit.getPluginManager().getPermission("recipesmith.admin");
        GcbAssert.notNull(permission, "recipesmith.admin is registered");
        GcbAssert.equals(PermissionDefault.OP, permission.getDefault(), "recipesmith.admin default");
    }

    @GcbCase(value = "shaped recipes craft their result anywhere in the grid", order = 3)
    public void shaped() {
        seed("""
            recipes:
              hardened_pick:
                type: shaped
                shape: ["DDD", " S ", " S "]
                ingredients: {D: DIAMOND_BLOCK, S: STICK}
                result:
                  material: DIAMOND_PICKAXE
                  name: "<aqua>Hardened Pick</aqua>"
                  lore: ["<gray>Forged by Recipesmith</gray>", "Second line"]
              emerald_bar:
                type: shaped
                shape: ["EE"]
                ingredients: {E: emerald}
                result: {material: experience_bottle, amount: 3}
            disabled-vanilla: []
            """, "Loaded 2 recipes, skipped 0, disabled 0 vanilla recipes.");
        Material b = Material.DIAMOND_BLOCK;
        Material s = Material.STICK;
        ItemStack[] pick = grid(b, b, b, X, s, X, X, s, X);
        crafts(pick, key("hardened_pick"), Material.DIAMOND_PICKAXE, 1, "the pick");
        ItemMeta meta = crafted(pick).getItemMeta();
        GcbAssert.equals("Hardened Pick", plain(meta.displayName()), "the display name");
        List<String> lore = new ArrayList<>();
        if (meta.lore() != null) {
            meta.lore().forEach(line -> lore.add(plain(line)));
        }
        GcbAssert.equals(List.of("Forged by Recipesmith", "Second line"), lore, "the lore");
        Material e = Material.EMERALD;
        crafts(grid(e, e, X, X, X, X, X, X, X), key("emerald_bar"), Material.EXPERIENCE_BOTTLE, 3, "top left");
        crafts(grid(X, X, X, X, X, X, X, e, e), key("emerald_bar"), Material.EXPERIENCE_BOTTLE, 3, "bottom right");
        noCraft(grid(X, X, X, X, e, X, X, X, X), "one emerald");
        noCraft(grid(e, X, X, e, X, X, X, X, X), "two emeralds in a column");
    }

    @GcbCase(value = "ingredient lists and tags accept any listed material", order = 4)
    public void choices() {
        seed("""
            recipes:
              spark:
                type: shaped
                shape: ["AB"]
                ingredients:
                  A: [COAL, CHARCOAL]
                  B: FLINT
                result: {material: FIRE_CHARGE, amount: 5}
              plank_mash:
                type: shapeless
                ingredients: ["#minecraft:planks", "#minecraft:planks", GRAVEL]
                result: {material: MUD, amount: 2}
            disabled-vanilla: []
            """, "Loaded 2 recipes, skipped 0, disabled 0 vanilla recipes.");
        Material f = Material.FLINT;
        crafts(grid(Material.COAL, f, X, X, X, X, X, X, X), key("spark"), Material.FIRE_CHARGE, 5, "coal and flint");
        crafts(grid(X, X, X, Material.CHARCOAL, f, X, X, X, X), key("spark"), Material.FIRE_CHARGE, 5,
            "charcoal and flint");
        noCraft(grid(Material.STICK, f, X, X, X, X, X, X, X), "a stick is not in the list");
        Material g = Material.GRAVEL;
        crafts(grid(Material.OAK_PLANKS, X, Material.BIRCH_PLANKS, X, g, X, X, X, X), key("plank_mash"), Material.MUD, 2,
            "oak and birch planks");
        crafts(grid(g, Material.SPRUCE_PLANKS, Material.SPRUCE_PLANKS, X, X, X, X, X, X), key("plank_mash"),
            Material.MUD, 2, "two spruce planks");
        noCraft(grid(Material.OAK_PLANKS, X, X, X, g, X, X, X, X), "one plank is not enough");
        noCraft(grid(Material.OAK_LOG, Material.OAK_PLANKS, g, X, X, X, X, X, X), "a log is not a plank");
    }

    @GcbCase(value = "shapeless recipes ignore positions but count items", order = 5)
    public void shapeless() {
        seed("""
            recipes:
              quick_bread:
                type: shapeless
                ingredients: [WHEAT, WHEAT, EGG]
                result: {material: BREAD, amount: 3}
            disabled-vanilla: []
            """, "Loaded 1 recipes, skipped 0, disabled 0 vanilla recipes.");
        Material w = Material.WHEAT;
        Material egg = Material.EGG;
        crafts(grid(w, X, X, X, egg, X, X, X, w), key("quick_bread"), Material.BREAD, 3, "corners and centre");
        crafts(grid(X, X, w, egg, X, X, w, X, X), key("quick_bread"), Material.BREAD, 3, "scattered");
        noCraft(grid(w, X, X, X, egg, X, X, X, X), "one wheat");
        noCraft(grid(w, w, X, egg, egg, X, X, X, X), "two eggs");
    }

    @GcbCase(value = "cooking and stonecutting recipes carry their settings", order = 6)
    public void cooking() {
        seed("""
            recipes:
              melt_gravel:
                type: smelting
                input: GRAVEL
                experience: 0.7
                cooking-time: 40
                group: gravel_work
                result: {material: FLINT, amount: 2}
              smoke_flesh:
                type: smoking
                input: ROTTEN_FLESH
                result: {material: LEATHER}
              blast_bars:
                type: blasting
                input: [IRON_BARS, IRON_TRAPDOOR]
                cooking-time: 50
                result: {material: IRON_NUGGET, amount: 3}
              roast_potato:
                type: campfire
                input: POISONOUS_POTATO
                experience: 1
                result: {material: BAKED_POTATO}
              cut_glass:
                type: stonecutting
                input: GLASS
                result: {material: GLASS_PANE, amount: 4}
            disabled-vanilla: []
            """, "Loaded 5 recipes, skipped 0, disabled 0 vanilla recipes.");
        Recipe melt = Bukkit.getRecipe(key("melt_gravel"));
        GcbAssert.isTrue(melt instanceof FurnaceRecipe, "melt_gravel is a FurnaceRecipe: " + melt);
        FurnaceRecipe furnace = (FurnaceRecipe) melt;
        GcbAssert.equals(40, furnace.getCookingTime(), "melt_gravel cooking time");
        GcbAssert.isTrue(Math.abs(furnace.getExperience() - 0.7f) < 1e-4, "melt_gravel experience " + furnace.getExperience());
        GcbAssert.equals("gravel_work", furnace.getGroup(), "melt_gravel group");
        GcbAssert.equals(Material.FLINT, furnace.getResult().getType(), "melt_gravel result");
        GcbAssert.equals(2, furnace.getResult().getAmount(), "melt_gravel amount");
        GcbAssert.isTrue(furnace.getInputChoice().test(new ItemStack(Material.GRAVEL)), "gravel is the input");
        GcbAssert.isFalse(furnace.getInputChoice().test(new ItemStack(Material.SAND)), "sand is not the input");
        checkCooking("smoke_flesh", SmokingRecipe.class, 100, 0f, Material.LEATHER, 1, Material.ROTTEN_FLESH);
        checkCooking("blast_bars", BlastingRecipe.class, 50, 0f, Material.IRON_NUGGET, 3, Material.IRON_BARS);
        GcbAssert.isTrue(((CookingRecipe<?>) Bukkit.getRecipe(key("blast_bars"))).getInputChoice()
            .test(new ItemStack(Material.IRON_TRAPDOOR)), "blast_bars also takes iron trapdoors");
        checkCooking("roast_potato", CampfireRecipe.class, 600, 1f, Material.BAKED_POTATO, 1, Material.POISONOUS_POTATO);
        Recipe cut = Bukkit.getRecipe(key("cut_glass"));
        GcbAssert.isTrue(cut instanceof StonecuttingRecipe, "cut_glass is a StonecuttingRecipe: " + cut);
        StonecuttingRecipe cutting = (StonecuttingRecipe) cut;
        GcbAssert.equals(Material.GLASS_PANE, cutting.getResult().getType(), "cut_glass result");
        GcbAssert.equals(4, cutting.getResult().getAmount(), "cut_glass amount");
        GcbAssert.isTrue(cutting.getInputChoice().test(new ItemStack(Material.GLASS)), "glass is the input");
    }

    private static void checkCooking(String id, Class<?> type, int time, float experience, Material result, int amount,
                                     Material input) {
        Recipe recipe = Bukkit.getRecipe(key(id));
        GcbAssert.isTrue(type.isInstance(recipe), id + " is a " + type.getSimpleName() + ": " + recipe);
        CookingRecipe<?> cooking = (CookingRecipe<?>) recipe;
        GcbAssert.equals(time, cooking.getCookingTime(), id + " cooking time");
        GcbAssert.isTrue(Math.abs(cooking.getExperience() - experience) < 1e-4, id + " experience " + cooking.getExperience());
        GcbAssert.equals(result, cooking.getResult().getType(), id + " result");
        GcbAssert.equals(amount, cooking.getResult().getAmount(), id + " amount");
        GcbAssert.isTrue(cooking.getInputChoice().test(new ItemStack(input)), id + " input");
    }

    @GcbCase(value = "a smelting recipe cooks in a real furnace", order = 7, ticks = 400)
    public void realFurnace(GcbScript script) {
        // Inside the world border (max-world-size 1024): block entities outside it do not tick.
        Block block = world().getBlockAt(300, -59, 300);
        block.getChunk().setForceLoaded(true);
        script.step(() -> {
            seed("""
                recipes:
                  melt_gravel:
                    type: smelting
                    input: GRAVEL
                    cooking-time: 40
                    result: {material: FLINT, amount: 2}
                disabled-vanilla: []
                """, "Loaded 1 recipes, skipped 0, disabled 0 vanilla recipes.");
            block.setType(Material.FURNACE);
            FurnaceInventory inventory = ((Furnace) block.getState()).getInventory();
            inventory.setSmelting(new ItemStack(Material.GRAVEL, 2));
            inventory.setFuel(new ItemStack(Material.COAL, 1));
        });
        script.waitTicks(130);
        script.step(() -> {
            Furnace furnace = (Furnace) block.getState();
            FurnaceInventory inventory = furnace.getInventory();
            ItemStack result = inventory.getResult();
            GcbAssert.notNull(result, "the furnace produced a result (input " + inventory.getSmelting() + ", fuel "
                + inventory.getFuel() + ", burn " + furnace.getBurnTime() + ", cook " + furnace.getCookTime() + "/"
                + furnace.getCookTimeTotal() + ", recipe " + Bukkit.getRecipe(key("melt_gravel")) + ")");
            GcbAssert.equals(Material.FLINT, result.getType(), "the furnace result");
            GcbAssert.equals(4, result.getAmount(), "two gravel smelt into four flint");
            GcbAssert.isTrue(inventory.getSmelting() == null || inventory.getSmelting().getType().isAir(),
                "the gravel is used up");
        });
    }

    @GcbCase(value = "recipes are registered under the plugin namespace", order = 8)
    public void namespace() {
        seed("""
            recipes:
              first_one:
                type: shapeless
                ingredients: [FLINT, FLINT, FLINT, FLINT]
                result: {material: GUNPOWDER}
              second_one:
                type: stonecutting
                input: GLASS
                result: {material: GLASS_PANE, amount: 2}
              third_one:
                type: smelting
                input: GRAVEL
                result: {material: FLINT}
            disabled-vanilla: []
            """, "Loaded 3 recipes, skipped 0, disabled 0 vanilla recipes.");
        GcbAssert.equals(Set.of("first_one", "second_one", "third_one"), ownKeys(), "the recipesmith keys");
    }

    @GcbCase(value = "invalid recipes are skipped with the first reason", order = 9)
    public void invalid() {
        seed("""
            recipes:
              good_one:
                type: shapeless
                ingredients: [FLINT, FLINT, FLINT]
                result: {material: GUNPOWDER}
              Bad-Id:
                type: shapeless
                ingredients: [FLINT]
                result: {material: STONE}
              no_type:
                ingredients: [FLINT]
                result: {material: STONE}
              odd_type:
                type: brewing
                result: {material: STONE}
              no_result:
                type: shapeless
                ingredients: [FLINT]
              bad_result:
                type: shapeless
                ingredients: [FLINT]
                result: {material: NOT_A_THING}
              block_result:
                type: shapeless
                ingredients: [FLINT]
                result: {material: WATER}
              big_amount:
                type: shapeless
                ingredients: [NOT_A_THING]
                result: {material: STONE, amount: 65}
              bad_shape:
                type: shaped
                shape: ["AAAA"]
                ingredients: {A: FLINT}
                result: {material: STONE}
              ragged_shape:
                type: shaped
                shape: ["AA", "A"]
                ingredients: {A: FLINT}
                result: {material: STONE}
              missing_key:
                type: shaped
                shape: ["AB"]
                ingredients: {A: NOT_A_THING}
                result: {material: STONE}
              unused_key:
                type: shaped
                shape: ["A"]
                ingredients: {A: FLINT, Z: STONE}
                result: {material: STONE}
              bad_ingredient:
                type: shapeless
                ingredients: [FLINT, NOT_A_THING, ALSO_NOT]
                result: {material: STONE}
              bad_tag:
                type: shapeless
                ingredients: ["#minecraft:not_a_tag"]
                result: {material: STONE}
              too_many:
                type: shapeless
                ingredients: [FLINT, FLINT, FLINT, FLINT, FLINT, FLINT, FLINT, FLINT, FLINT, NOT_A_THING]
                result: {material: STONE}
              bad_time:
                type: smelting
                input: FLINT
                cooking-time: 0
                result: {material: STONE}
              bad_xp:
                type: smelting
                input: FLINT
                experience: -1
                cooking-time: 0
                result: {material: STONE}
              bad_input:
                type: smoking
                input: NOT_A_THING
                experience: -1
                result: {material: STONE}
            disabled-vanilla: []
            """,
            "Loaded 1 recipes, skipped 17, disabled 0 vanilla recipes.",
            "Skipped Bad-Id: invalid id.",
            "Skipped no_type: unknown type none.",
            "Skipped odd_type: unknown type brewing.",
            "Skipped no_result: unknown result material none.",
            "Skipped bad_result: unknown result material NOT_A_THING.",
            "Skipped block_result: unknown result material WATER.",
            "Skipped big_amount: amount must be between 1 and 64.",
            "Skipped bad_shape: invalid shape.",
            "Skipped ragged_shape: invalid shape.",
            "Skipped missing_key: no ingredient for B.",
            "Skipped unused_key: unused ingredient Z.",
            "Skipped bad_ingredient: unknown material NOT_A_THING.",
            "Skipped bad_tag: unknown tag #minecraft:not_a_tag.",
            "Skipped too_many: shapeless recipes need 1 to 9 ingredients.",
            "Skipped bad_time: invalid cooking time.",
            "Skipped bad_xp: invalid experience.",
            "Skipped bad_input: unknown material NOT_A_THING.");
        GcbAssert.equals(Set.of("good_one"), ownKeys(), "only the valid recipe is registered");
        Material f = Material.FLINT;
        crafts(grid(f, f, f, X, X, X, X, X, X), key("good_one"), Material.GUNPOWDER, 1, "three flint");
    }

    @GcbCase(value = "reload removes recipes deleted from the file", order = 10)
    public void reloadRemoves() {
        String both = """
            recipes:
              keep_me:
                type: shapeless
                ingredients: [BONE, BONE, BONE, BONE]
                result: {material: BONE_BLOCK, amount: 2}
              drop_me:
                type: shapeless
                ingredients: [FLINT, GRAVEL]
                result: {material: SAND}
            disabled-vanilla: []
            """;
        seed(both, "Loaded 2 recipes, skipped 0, disabled 0 vanilla recipes.");
        ItemStack[] dropGrid = grid(Material.FLINT, Material.GRAVEL, X, X, X, X, X, X, X);
        crafts(dropGrid, key("drop_me"), Material.SAND, 1, "drop_me before");
        seed(both.replace("""
              drop_me:
                type: shapeless
                ingredients: [FLINT, GRAVEL]
                result: {material: SAND}
            """, ""), "Loaded 1 recipes, skipped 0, disabled 0 vanilla recipes.");
        GcbAssert.isNull(Bukkit.getRecipe(key("drop_me")), "drop_me is unregistered");
        noCraft(dropGrid, "drop_me after the reload");
        Material bone = Material.BONE;
        crafts(grid(bone, bone, X, bone, bone, X, X, X, X), key("keep_me"), Material.BONE_BLOCK, 2, "keep_me after");
        GcbAssert.equals(Set.of("keep_me"), ownKeys(), "the recipesmith keys");
    }

    @GcbCase(value = "disabled vanilla recipes cannot be crafted", order = 11)
    public void disabledVanilla() {
        crafts(torchGrid(), NamespacedKey.minecraft("torch"), Material.TORCH, 4, "torches before");
        seed("""
            recipes: {}
            disabled-vanilla:
              - minecraft:torch
              - soul_torch
              - minecraft:no_such_recipe
              - recipesmith:compact_dirt
            """,
            "Loaded 0 recipes, skipped 0, disabled 2 vanilla recipes.",
            "Unknown vanilla recipe: minecraft:no_such_recipe",
            "Unknown vanilla recipe: recipesmith:compact_dirt");
        GcbAssert.isNull(Bukkit.getRecipe(NamespacedKey.minecraft("torch")), "minecraft:torch is removed");
        noCraft(torchGrid(), "torch");
        noCraft(soulTorchGrid(), "soul torch");
    }

    @GcbCase(value = "reload restores vanilla recipes that are no longer disabled", order = 12)
    public void restoreVanilla() {
        seed("""
            recipes: {}
            disabled-vanilla: []
            """, "Loaded 0 recipes, skipped 0, disabled 0 vanilla recipes.");
        GcbAssert.notNull(Bukkit.getRecipe(NamespacedKey.minecraft("torch")), "minecraft:torch is back");
        crafts(torchGrid(), NamespacedKey.minecraft("torch"), Material.TORCH, 4, "torches");
        crafts(soulTorchGrid(), NamespacedKey.minecraft("soul_torch"), Material.SOUL_TORCH, 4, "soul torches");
    }

    @GcbCase(value = "disable and enable edit the file", order = 13)
    public void disableEnable() {
        seed("""
            recipes:
              r1:
                type: shapeless
                ingredients: [BONE, FLINT]
                result: {material: ARROW}
            disabled-vanilla: []
            """, "Loaded 1 recipes, skipped 0, disabled 0 vanilla recipes.");
        expect("disable minecraft:lantern", "Disabled minecraft:lantern.");
        YamlConfiguration yaml = Kit.yaml("recipes.yml");
        GcbAssert.equals(List.of("minecraft:lantern"), yaml.getStringList("disabled-vanilla"), "the saved list");
        GcbAssert.equals("shapeless", yaml.getString("recipes.r1.type"), "the recipes are kept");
        noCraft(lanternGrid(), "lantern while disabled");
        expect("disable lantern", "minecraft:lantern is already disabled.");
        expect("disable minecraft:nothing_here", "Unknown vanilla recipe: minecraft:nothing_here");
        expect("disable recipesmith:r1", "Unknown vanilla recipe: recipesmith:r1");
        expect("reload", "Loaded 1 recipes, skipped 0, disabled 1 vanilla recipes.");
        noCraft(lanternGrid(), "lantern after a reload");
        expect("enable minecraft:lantern", "Enabled minecraft:lantern.");
        GcbAssert.equals(List.of(), Kit.yaml("recipes.yml").getStringList("disabled-vanilla"), "the saved list");
        crafts(lanternGrid(), NamespacedKey.minecraft("lantern"), Material.LANTERN, 1, "lantern after enable");
        expect("enable minecraft:lantern", "minecraft:lantern is not disabled.");
        expect("enable torch", "minecraft:torch is not disabled.");
        crafts(grid(Material.BONE, Material.FLINT, X, X, X, X, X, X, X), key("r1"), Material.ARROW, 1, "r1 still works");
    }

    @GcbCase(value = "list shows the loaded recipes", order = 14)
    public void list() {
        seed("""
            recipes:
              zeta:
                type: shapeless
                ingredients: [WHITE_WOOL]
                result: {material: STRING, amount: 2}
              alpha:
                type: smelting
                input: GRAVEL
                result: {material: FLINT}
              mid:
                type: stonecutting
                input: GLASS
                result: {material: glass_pane, amount: 4}
              broken:
                type: shaped
                result: {material: STONE}
            disabled-vanilla: []
            """, "Loaded 3 recipes, skipped 1, disabled 0 vanilla recipes.", "Skipped broken: invalid shape.");
        expect("list", "Recipes (3):", "alpha: smelting -> 1 flint", "mid: stonecutting -> 4 glass_pane",
            "zeta: shapeless -> 2 string");
        seed("recipes: {}\ndisabled-vanilla: []\n", "Loaded 0 recipes, skipped 0, disabled 0 vanilla recipes.");
        expect("list", "No recipes.");
    }

    @GcbCase(value = "permissions are enforced", order = 15)
    public void permissions() {
        Actor nobody = Actor.limited("nobody_15");
        for (String line : List.of("reload", "list", "disable minecraft:torch", "enable minecraft:torch")) {
            Kit.lines(nobody.run("recipes " + line), "/recipes " + line + " without permission", DENIED);
        }
        crafts(torchGrid(), NamespacedKey.minecraft("torch"), Material.TORCH, 4, "a denied disable changes nothing");
        Actor admin = Actor.limited("admin_15", "recipesmith.admin");
        Kit.lines(admin.run("recipes list"), "recipesmith.admin lists", "No recipes.");
        Kit.lines(admin.run("recipes disable minecraft:torch"), "recipesmith.admin disables", "Disabled minecraft:torch.");
        Kit.lines(admin.run("recipes enable minecraft:torch"), "recipesmith.admin enables", "Enabled minecraft:torch.");
    }

    @GcbCase(value = "malformed commands show usage", order = 16)
    public void usage() {
        expect("", USAGE);
        expect("bogus", USAGE);
        expect("reload now", "Usage: /recipes reload");
        expect("list all", "Usage: /recipes list");
        expect("disable", "Usage: /recipes disable <key>");
        expect("disable a b", "Usage: /recipes disable <key>");
        expect("enable", "Usage: /recipes enable <key>");
        Kit.lines(Actor.limited("nobody_16").run("recipes disable"), "usage comes before the permission check",
            "Usage: /recipes disable <key>");
        expect("LIST", "No recipes.");
    }

    @GcbCase(value = "tagged ingredients craft a MiniMessage-named item with lore", order = 17)
    public void taggedRecipeMetadata() {
        seed("""
            recipes:
              trail_token:
                type: shapeless
                ingredients: ["#minecraft:planks", FLINT]
                group: tokens
                result:
                  material: FIREWORK_STAR
                  amount: 2
                  name: "<gold>Trail Token</gold>"
                  lore:
                    - "<gray>crafted from wood</gray>"
                    - "<yellow>and flint</yellow>"
            disabled-vanilla: []
            """, "Loaded 1 recipes, skipped 0, disabled 0 vanilla recipes.");

        ItemStack[] grid = grid(Material.BIRCH_PLANKS, Material.FLINT, X, X, X, X, X, X, X);
        crafts(grid, key("trail_token"), Material.FIREWORK_STAR, 2, "tagged trail token");
        ItemMeta meta = crafted(grid).getItemMeta();
        GcbAssert.equals("Trail Token", plain(meta.displayName()), "MiniMessage result name");
        GcbAssert.equals(List.of("crafted from wood", "and flint"),
            meta.lore().stream().map(RecipesmithSuite::plain).toList(), "MiniMessage result lore");
    }

}
