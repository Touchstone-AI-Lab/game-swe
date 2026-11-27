import io.gamecodebench.harness.GcbAssert;
import io.gamecodebench.harness.GcbCase;
import io.gamecodebench.harness.GcbSuite;
import java.io.File;
import java.util.List;
import java.util.function.Supplier;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.WorldType;
import org.bukkit.configuration.file.YamlConfiguration;
import org.mvplugins.multiverse.core.MultiverseCoreApi;
import org.mvplugins.multiverse.core.world.LoadedMultiverseWorld;
import org.mvplugins.multiverse.core.world.MultiverseWorld;
import org.mvplugins.multiverse.core.world.WorldManager;
import org.mvplugins.multiverse.core.world.options.CreateWorldOptions;
import org.mvplugins.multiverse.core.world.options.DeleteWorldOptions;
import org.mvplugins.multiverse.core.world.options.LoadWorldOptions;
import org.mvplugins.multiverse.core.world.options.RegenWorldOptions;
import org.mvplugins.multiverse.core.world.options.RemoveWorldOptions;
import org.mvplugins.multiverse.core.world.options.UnloadWorldOptions;

/**
 * Live-server grader for the world-name casing repair in Multiverse-Core.
 *
 * <p>Every case goes through the public {@code WorldManager} API with flat worlds and no
 * player. Each case uses its own world name so that the outcome of one case cannot leak
 * into another; a call that throws is reported as the failure of the step that made it.
 */
public final class WorldNameCaseSuite implements GcbSuite {

    private static final long SEED = 4242L;

    private static WorldManager worldManager() {
        GcbAssert.isTrue(MultiverseCoreApi.isLoaded(), "Multiverse-Core API must be loaded");
        return MultiverseCoreApi.get().getWorldManager();
    }

    private static <T> T call(String step, Supplier<T> body) {
        try {
            return body.get();
        } catch (RuntimeException | Error thrown) {
            GcbAssert.fail(step + " threw " + thrown.getClass().getSimpleName() + ": " + thrown.getMessage());
            return null;
        }
    }

    private static void succeeded(String step, org.mvplugins.multiverse.core.utils.result.Attempt<?, ?> attempt) {
        GcbAssert.notNull(attempt, step + " returned no result");
        GcbAssert.isTrue(attempt.isSuccess(), step + " must succeed"
                + (attempt.isFailure() ? ": " + attempt.getFailureReason() : ""));
    }

    private static LoadedMultiverseWorld create(WorldManager manager, String name) {
        var attempt = call("creating " + name, () -> manager.createWorld(
                CreateWorldOptions.worldName(name)
                        .worldType(WorldType.FLAT)
                        .generateStructures(false)
                        .seed(SEED)
                        .useSpawnAdjust(false)));
        succeeded("creating " + name, attempt);
        return attempt.get();
    }

    private static List<String> casings(String name) {
        return List.of(name, name.toLowerCase(java.util.Locale.ROOT), name.toUpperCase(java.util.Locale.ROOT));
    }

    private static long registered(WorldManager manager, String name) {
        return manager.getWorlds().stream().filter(world -> world.getName().equalsIgnoreCase(name)).count();
    }

    private static boolean inWorldsConfig(String name) {
        File file = new File(Bukkit.getPluginManager().getPlugin("Multiverse-Core").getDataFolder(), "worlds.yml");
        if (!file.isFile()) {
            return false;
        }
        YamlConfiguration yaml = YamlConfiguration.loadConfiguration(file);
        return yaml.getKeys(false).stream().anyMatch(key -> key.equalsIgnoreCase(name));
    }

    private static File folder(String name) {
        return new File(Bukkit.getWorldContainer(), name);
    }

    private static boolean bukkitLoaded(String name) {
        return Bukkit.getWorlds().stream().anyMatch(world -> world.getName().equalsIgnoreCase(name));
    }

    private static void assertForgotten(WorldManager manager, String name) {
        for (String casing : casings(name)) {
            GcbAssert.isFalse(manager.isWorld(casing), name + " must be forgotten, but isWorld(\"" + casing + "\") is true");
            GcbAssert.isFalse(manager.getWorld(casing).isDefined(), "getWorld(\"" + casing + "\") must be empty after " + name + " is gone");
            GcbAssert.isFalse(manager.getLoadedWorld(casing).isDefined(), "getLoadedWorld(\"" + casing + "\") must be empty");
            GcbAssert.isFalse(manager.getUnloadedWorld(casing).isDefined(), "getUnloadedWorld(\"" + casing + "\") must be empty");
        }
        GcbAssert.equals(0L, registered(manager, name), "getWorlds() must no longer list " + name);
        GcbAssert.isFalse(manager.getUnloadedWorlds().stream().anyMatch(w -> w.getName().equalsIgnoreCase(name)),
                "getUnloadedWorlds() must no longer list " + name);
        GcbAssert.isFalse(inWorldsConfig(name), "worlds.yml must no longer hold an entry for " + name);
    }

    private static void assertUnloaded(WorldManager manager, String name) {
        for (String casing : casings(name)) {
            GcbAssert.isFalse(manager.isLoadedWorld(casing), name + " must no longer be loaded (isLoadedWorld(\"" + casing + "\"))");
            GcbAssert.isFalse(manager.getLoadedWorld(casing).isDefined(), name + " must no longer be loaded (getLoadedWorld(\"" + casing + "\"))");
        }
        var unloaded = manager.getUnloadedWorld(name);
        GcbAssert.isTrue(unloaded.isDefined(), name + " must be tracked as an unloaded world (getUnloadedWorld)");
        GcbAssert.equals(name, unloaded.get().getName(), "the unloaded world keeps its original name");
        GcbAssert.isTrue(manager.isWorld(name), name + " must still be a known world (isWorld)");
        GcbAssert.equals(1L, registered(manager, name), "getWorlds() must list " + name + " exactly once");
        GcbAssert.isFalse(bukkitLoaded(name), "the Bukkit world " + name + " must be unloaded");
    }

    @GcbCase(value = "plugin is enabled", order = 0)
    public void pluginIsEnabled() {
        GcbAssert.isTrue(Bukkit.getPluginManager().isPluginEnabled("Multiverse-Core"),
                "Multiverse-Core must be enabled");
        GcbAssert.notNull(worldManager(), "the WorldManager service must be available");
    }

    @GcbCase(value = "world lookups ignore case", order = 1)
    public void lookupsIgnoreCase() {
        WorldManager manager = worldManager();
        create(manager, "GcbLookup");
        for (String casing : List.of("GcbLookup", "gcblookup", "GCBLOOKUP", "gCbLoOkUp")) {
            GcbAssert.isTrue(manager.isWorld(casing), "isWorld(\"" + casing + "\") must find GcbLookup");
            GcbAssert.isTrue(manager.isLoadedWorld(casing), "isLoadedWorld(\"" + casing + "\") must find GcbLookup");
            GcbAssert.isTrue(manager.getWorld(casing).isDefined(), "getWorld(\"" + casing + "\") must find GcbLookup");
            GcbAssert.isTrue(manager.getLoadedWorld(casing).isDefined(), "getLoadedWorld(\"" + casing + "\") must find GcbLookup");
        }
        GcbAssert.isFalse(manager.getWorld("gcblookupx").isDefined(), "an unknown name must not resolve");
        GcbAssert.equals(1L, registered(manager, "GcbLookup"), "getWorlds() must list GcbLookup exactly once");
    }

    @GcbCase(value = "worlds keep the name they were created with", order = 2)
    public void namesKeepTheirCasing() {
        WorldManager manager = worldManager();
        LoadedMultiverseWorld world = create(manager, "GcbKeepName");
        GcbAssert.equals("GcbKeepName", world.getName(), "the created world keeps its name");
        GcbAssert.equals("GcbKeepName", manager.getWorld("gcbkeepname").get().getName(),
                "a lookup by another casing returns the world under its original name");
        World bukkit = world.getBukkitWorld().getOrNull();
        GcbAssert.notNull(bukkit, "the created world must be loaded in Bukkit");
        GcbAssert.equals("GcbKeepName", bukkit.getName(), "the Bukkit world keeps the original name");
        GcbAssert.isTrue(folder("GcbKeepName").isDirectory(), "the world folder is named GcbKeepName");
        GcbAssert.isTrue(inWorldsConfig("GcbKeepName"), "worlds.yml holds an entry for GcbKeepName");
    }

    @GcbCase(value = "lower-case world goes through its whole lifecycle", order = 3)
    public void lowerCaseLifecycle() {
        WorldManager manager = worldManager();
        LoadedMultiverseWorld world = create(manager, "gcb_lower");
        succeeded("unloading gcb_lower", call("unloading gcb_lower",
                () -> manager.unloadWorld(UnloadWorldOptions.world(world))));
        assertUnloaded(manager, "gcb_lower");
        MultiverseWorld unloaded = manager.getUnloadedWorld("gcb_lower").get();
        succeeded("loading gcb_lower", call("loading gcb_lower",
                () -> manager.loadWorld(LoadWorldOptions.world(unloaded))));
        GcbAssert.isTrue(manager.isLoadedWorld("gcb_lower"), "gcb_lower must be loaded again");
        GcbAssert.isTrue(bukkitLoaded("gcb_lower"), "the Bukkit world gcb_lower must be loaded again");
        succeeded("removing gcb_lower", call("removing gcb_lower",
                () -> manager.removeWorld(RemoveWorldOptions.world(manager.getWorld("gcb_lower").get()))));
        assertForgotten(manager, "gcb_lower");
        GcbAssert.isTrue(folder("gcb_lower").isDirectory(), "removing keeps the world folder");

        LoadedMultiverseWorld doomed = create(manager, "gcb_lower_gone");
        succeeded("deleting gcb_lower_gone", call("deleting gcb_lower_gone",
                () -> manager.deleteWorld(DeleteWorldOptions.world(doomed))));
        assertForgotten(manager, "gcb_lower_gone");
        GcbAssert.isFalse(folder("gcb_lower_gone").exists(), "deleting removes the world folder");
    }

    @GcbCase(value = "mixed-case world can be unloaded", order = 4)
    public void mixedCaseUnload() {
        WorldManager manager = worldManager();
        LoadedMultiverseWorld world = create(manager, "GcbUnload");
        succeeded("unloading GcbUnload", call("unloading GcbUnload",
                () -> manager.unloadWorld(UnloadWorldOptions.world(world))));
        assertUnloaded(manager, "GcbUnload");
    }

    @GcbCase(value = "mixed-case world can be loaded again", order = 5)
    public void mixedCaseReload() {
        WorldManager manager = worldManager();
        LoadedMultiverseWorld world = create(manager, "GcbReload");
        succeeded("unloading GcbReload", call("unloading GcbReload",
                () -> manager.unloadWorld(UnloadWorldOptions.world(world))));
        var unloaded = manager.getUnloadedWorld("GcbReload");
        GcbAssert.isTrue(unloaded.isDefined(), "GcbReload must be tracked as unloaded");
        succeeded("loading GcbReload", call("loading GcbReload",
                () -> manager.loadWorld(LoadWorldOptions.world(unloaded.get()))));
        GcbAssert.isTrue(manager.isLoadedWorld("GcbReload"), "GcbReload must be loaded after loading it");
        for (String casing : casings("GcbReload")) {
            GcbAssert.isFalse(manager.getUnloadedWorld(casing).isDefined(), "getUnloadedWorld(\"" + casing + "\") must be empty after loading");
        }
        GcbAssert.equals("GcbReload", manager.getLoadedWorld("GcbReload").get().getName(),
                "the loaded world keeps its original name");
        GcbAssert.isTrue(bukkitLoaded("GcbReload"), "the Bukkit world GcbReload must be loaded");
        GcbAssert.equals(1L, registered(manager, "GcbReload"), "getWorlds() must list GcbReload exactly once");
    }

    @GcbCase(value = "loaded mixed-case world can be removed", order = 6)
    public void mixedCaseRemoveLoaded() {
        WorldManager manager = worldManager();
        LoadedMultiverseWorld world = create(manager, "GcbRemove");
        succeeded("removing GcbRemove", call("removing GcbRemove",
                () -> manager.removeWorld(RemoveWorldOptions.world(world))));
        assertForgotten(manager, "GcbRemove");
        GcbAssert.isFalse(bukkitLoaded("GcbRemove"), "removing a loaded world unloads its Bukkit world");
        GcbAssert.isTrue(folder("GcbRemove").isDirectory(), "removing keeps the world folder");
    }

    @GcbCase(value = "unloaded mixed-case world can be removed", order = 7)
    public void mixedCaseRemoveUnloaded() {
        WorldManager manager = worldManager();
        LoadedMultiverseWorld world = create(manager, "GcbRemoveIdle");
        succeeded("unloading GcbRemoveIdle", call("unloading GcbRemoveIdle",
                () -> manager.unloadWorld(UnloadWorldOptions.world(world))));
        var unloaded = manager.getUnloadedWorld("GcbRemoveIdle");
        GcbAssert.isTrue(unloaded.isDefined(), "GcbRemoveIdle must be tracked as unloaded");
        succeeded("removing GcbRemoveIdle", call("removing GcbRemoveIdle",
                () -> manager.removeWorld(RemoveWorldOptions.world(unloaded.get()))));
        assertForgotten(manager, "GcbRemoveIdle");
        GcbAssert.isTrue(folder("GcbRemoveIdle").isDirectory(), "removing keeps the world folder");
    }

    @GcbCase(value = "mixed-case world can be deleted", order = 8)
    public void mixedCaseDelete() {
        WorldManager manager = worldManager();
        LoadedMultiverseWorld world = create(manager, "GcbDelete");
        succeeded("deleting GcbDelete", call("deleting GcbDelete",
                () -> manager.deleteWorld(DeleteWorldOptions.world(world))));
        assertForgotten(manager, "GcbDelete");
        GcbAssert.isFalse(bukkitLoaded("GcbDelete"), "the Bukkit world GcbDelete must be unloaded");
        GcbAssert.isFalse(folder("GcbDelete").exists(), "deleting removes the world folder");
    }

    @GcbCase(value = "mixed-case world can be regenerated", order = 9)
    public void mixedCaseRegen() {
        WorldManager manager = worldManager();
        LoadedMultiverseWorld world = create(manager, "GcbRegen");
        var attempt = call("regenerating GcbRegen", () -> manager.regenWorld(
                RegenWorldOptions.world(world).seed(SEED + 1)));
        succeeded("regenerating GcbRegen", attempt);
        GcbAssert.equals(1L, registered(manager, "GcbRegen"), "getWorlds() must list GcbRegen exactly once");
        var loaded = manager.getLoadedWorld("GcbRegen");
        GcbAssert.isTrue(loaded.isDefined(), "the regenerated GcbRegen must be loaded");
        GcbAssert.equals("GcbRegen", loaded.get().getName(), "the regenerated world keeps its original name");
        GcbAssert.equals(SEED + 1, loaded.get().getSeed(), "the regenerated world uses the new seed");
        GcbAssert.isTrue(bukkitLoaded("GcbRegen"), "the Bukkit world GcbRegen must be loaded");
        GcbAssert.isTrue(inWorldsConfig("GcbRegen"), "worlds.yml holds an entry for the regenerated GcbRegen");
    }
}
