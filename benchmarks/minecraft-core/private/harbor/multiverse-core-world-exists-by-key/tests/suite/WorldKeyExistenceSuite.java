import io.gamecodebench.harness.GcbAssert;
import io.gamecodebench.harness.GcbCase;
import io.gamecodebench.harness.GcbSuite;
import java.io.File;
import org.bukkit.Bukkit;
import org.bukkit.NamespacedKey;
import org.bukkit.World;
import org.bukkit.WorldCreator;
import org.bukkit.WorldType;
import org.mvplugins.multiverse.core.MultiverseCoreApi;
import org.mvplugins.multiverse.core.world.LoadedMultiverseWorld;
import org.mvplugins.multiverse.core.world.MultiverseWorld;
import org.mvplugins.multiverse.core.world.WorldManager;
import org.mvplugins.multiverse.core.world.options.CloneWorldOptions;
import org.mvplugins.multiverse.core.world.options.CreateWorldOptions;
import org.mvplugins.multiverse.core.world.options.ImportWorldOptions;
import org.mvplugins.multiverse.core.world.options.UnloadWorldOptions;
import org.mvplugins.multiverse.core.world.reasons.CloneFailureReason;
import org.mvplugins.multiverse.core.world.reasons.CreateFailureReason;
import org.mvplugins.multiverse.core.world.reasons.ImportFailureReason;

/**
 * Live-server grader for the Multiverse-Core repair "world existence checks must consult
 * both the world name and the namespaced world key". Every case goes through the public
 * {@link WorldManager} API; no player is involved.
 */
public final class WorldKeyExistenceSuite implements GcbSuite {

    /** Bukkit name and namespaced key of the server's End dimension (level-name is "world"). */
    private static final String END_NAME = "world_the_end";
    private static final String END_KEY = "minecraft:the_end";

    /** A unit of work whose exception must be reported instead of aborting the case silently. */
    @FunctionalInterface
    private interface Action<T> {
        T run() throws Exception;
    }

    private static WorldManager worldManager() {
        GcbAssert.isTrue(MultiverseCoreApi.isLoaded(), "Multiverse-Core API must be loaded");
        return MultiverseCoreApi.get().getWorldManager();
    }

    private static CreateWorldOptions flat(CreateWorldOptions options) {
        return options.worldType(WorldType.FLAT).generateStructures(false).useSpawnAdjust(false);
    }

    private static LoadedMultiverseWorld createByName(WorldManager manager, String name) {
        var attempt = manager.createWorld(flat(CreateWorldOptions.worldName(name)));
        GcbAssert.isTrue(attempt.isSuccess(), "creating world " + name + " must succeed: " + attempt);
        return attempt.get();
    }

    private static LoadedMultiverseWorld createByKey(WorldManager manager, NamespacedKey key) {
        var attempt = manager.createWorld(flat(CreateWorldOptions.worldKey(key)));
        GcbAssert.isTrue(attempt.isSuccess(), "creating world " + key + " must succeed: " + attempt);
        return attempt.get();
    }

    private static <T> T call(Action<T> action, String what) {
        try {
            return action.run();
        } catch (Throwable thrown) {
            GcbAssert.fail(what + " threw " + thrown.getClass().getSimpleName() + ": " + thrown.getMessage());
            throw new IllegalStateException("unreachable");
        }
    }

    @GcbCase(value = "plugin is enabled", order = 0)
    public void pluginIsEnabled() {
        GcbAssert.isTrue(Bukkit.getPluginManager().isPluginEnabled("Multiverse-Core"),
                "Multiverse-Core must be enabled");
        GcbAssert.notNull(worldManager(), "the WorldManager service must be available");
    }

    @GcbCase(value = "worlds resolve by name and by key string", order = 1)
    public void lookupsByNameAndKeyString() {
        WorldManager manager = worldManager();
        LoadedMultiverseWorld created = createByName(manager, "gcb_lookup");
        GcbAssert.equals(NamespacedKey.minecraft("gcb_lookup"), created.getKey(),
                "a world created by name gets the minecraft key of its name");
        GcbAssert.isTrue(manager.getWorld("gcb_lookup").isDefined(), "gcb_lookup must resolve by name");
        GcbAssert.isTrue(manager.getWorld("minecraft:gcb_lookup").isDefined(),
                "gcb_lookup must resolve by its key string");
        GcbAssert.isTrue(manager.getLoadedWorld("minecraft:gcb_lookup").isDefined(),
                "gcb_lookup must resolve as a loaded world by its key string");
        GcbAssert.isTrue(manager.isWorld("minecraft:gcb_lookup") && manager.isLoadedWorld("minecraft:gcb_lookup"),
                "isWorld and isLoadedWorld must accept the key string");
        GcbAssert.equals("gcb_lookup", manager.getWorld("minecraft:gcb_lookup").get().getName(),
                "the key string lookup must return the same world");

        World end = Bukkit.getWorld(END_NAME);
        GcbAssert.notNull(end, "the server's End dimension must be loaded");
        GcbAssert.equals(NamespacedKey.minecraft("the_end"), end.getKey(), "the End carries the key minecraft:the_end");
        GcbAssert.isTrue(manager.getWorld(END_NAME).isDefined(), "the End must be known to Multiverse by name");
        GcbAssert.isTrue(manager.getWorld(END_KEY).isDefined(), "the End must be known to Multiverse by key string");
        GcbAssert.equals(END_NAME, manager.getWorld(END_KEY).get().getName(),
                "the End resolved by key string keeps its Bukkit name");
    }

    @GcbCase(value = "creating or cloning under an existing name is rejected", order = 2)
    public void existingNameIsRejected() {
        WorldManager manager = worldManager();
        LoadedMultiverseWorld plain = createByName(manager, "gcb_plain");
        NamespacedKey namedKey = new NamespacedKey("gcb", "named");
        LoadedMultiverseWorld named = createByKey(manager, namedKey);
        GcbAssert.equals("named", named.getName(), "a world created from the key gcb:named is named after the key path");
        GcbAssert.equals(namedKey, named.getKey(), "a world created from the key gcb:named keeps that key");

        var createPlain = call(() -> manager.createWorld(flat(CreateWorldOptions.worldName("gcb_plain"))),
                "createWorld(gcb_plain)");
        GcbAssert.isTrue(createPlain.isFailure()
                        && createPlain.getFailureReason() == CreateFailureReason.WORLD_EXIST_LOADED,
                "creating gcb_plain again must fail with WORLD_EXIST_LOADED, got " + createPlain);
        var createNamed = call(() -> manager.createWorld(flat(CreateWorldOptions.worldName("named"))),
                "createWorld(named)");
        GcbAssert.isTrue(createNamed.isFailure()
                        && createNamed.getFailureReason() == CreateFailureReason.WORLD_EXIST_LOADED,
                "creating a world under the existing name of gcb:named must fail with WORLD_EXIST_LOADED, got "
                        + createNamed);
        var cloneNamed = call(() -> manager.cloneWorld(CloneWorldOptions.fromTo((MultiverseWorld) plain, "named")),
                "cloneWorld(gcb_plain -> named)");
        GcbAssert.isTrue(cloneNamed.isFailure()
                        && cloneNamed.getFailureReason() == CloneFailureReason.WORLD_EXIST_LOADED,
                "cloning onto the existing name of gcb:named must fail with WORLD_EXIST_LOADED, got " + cloneNamed);

        GcbAssert.isTrue(manager.unloadWorld(UnloadWorldOptions.world(plain)).isSuccess(),
                "unloading gcb_plain must succeed");
        var createUnloaded = call(() -> manager.createWorld(flat(CreateWorldOptions.worldName("gcb_plain"))),
                "createWorld(gcb_plain) while unloaded");
        GcbAssert.isTrue(createUnloaded.isFailure()
                        && createUnloaded.getFailureReason() == CreateFailureReason.WORLD_EXIST_UNLOADED,
                "creating the unloaded gcb_plain again must fail with WORLD_EXIST_UNLOADED, got " + createUnloaded);
    }

    @GcbCase(value = "create is rejected when the name is an existing world key", order = 3)
    public void nameThatIsAnExistingKeyIsRejected() {
        WorldManager manager = worldManager();
        GcbAssert.notNull(Bukkit.getWorld(END_NAME), "the End dimension must be loaded");
        GcbAssert.isTrue(manager.isLoadedWorld(END_NAME), "the End must be a loaded Multiverse world");
        int before = manager.getWorlds().size();

        var attempt = call(() -> manager.createWorld(flat(CreateWorldOptions.worldName("the_end"))),
                "createWorld(the_end)");
        GcbAssert.isTrue(attempt.isFailure(),
                "createWorld(the_end) must fail: the name is the key of the loaded " + END_NAME);
        GcbAssert.equals(CreateFailureReason.WORLD_EXIST_LOADED, attempt.getFailureReason(),
                "createWorld(the_end) must be rejected as an existing loaded world, got " + attempt);
        GcbAssert.isNull(Bukkit.getWorld("the_end"), "no Bukkit world named the_end may be created");
        GcbAssert.equals(before, manager.getWorlds().size(), "the Multiverse world list must be unchanged");
        GcbAssert.isFalse(new File(Bukkit.getWorldContainer(), "the_end").exists(),
                "no the_end world folder may be created");
    }

    @GcbCase(value = "create is rejected when the key belongs to an existing world", order = 4)
    public void existingKeyIsRejectedOnCreate() {
        WorldManager manager = worldManager();
        NamespacedKey key = new NamespacedKey("gcb", "keyed");
        LoadedMultiverseWorld keyed = createByKey(manager, key);
        GcbAssert.isTrue(manager.getLoadedWorld("gcb:keyed").isDefined(), "gcb:keyed must be registered by key string");
        int before = manager.getWorlds().size();

        var loaded = call(() -> manager.createWorld(flat(CreateWorldOptions.worldKey(key))), "createWorld(gcb:keyed)");
        GcbAssert.isTrue(loaded.isFailure(), "creating gcb:keyed a second time must fail");
        GcbAssert.equals(CreateFailureReason.WORLD_EXIST_LOADED, loaded.getFailureReason(),
                "creating the loaded gcb:keyed again must be rejected as WORLD_EXIST_LOADED, got " + loaded);
        GcbAssert.equals(before, manager.getWorlds().size(), "the Multiverse world list must be unchanged");

        GcbAssert.isTrue(manager.unloadWorld(UnloadWorldOptions.world(keyed)).isSuccess(),
                "unloading gcb:keyed must succeed");
        GcbAssert.isTrue(manager.getUnloadedWorld("gcb:keyed").isDefined(), "gcb:keyed must be tracked as unloaded");
        var unloaded = call(() -> manager.createWorld(flat(CreateWorldOptions.worldKey(key))),
                "createWorld(gcb:keyed) while unloaded");
        GcbAssert.isTrue(unloaded.isFailure(), "creating the unloaded gcb:keyed again must fail");
        GcbAssert.equals(CreateFailureReason.WORLD_EXIST_UNLOADED, unloaded.getFailureReason(),
                "creating the unloaded gcb:keyed again must be rejected as WORLD_EXIST_UNLOADED, got " + unloaded);
        GcbAssert.isNull(Bukkit.getWorld("keyed"), "the rejected create must not load the world again");
    }

    @GcbCase(value = "clone is rejected when the target key belongs to an existing world", order = 5)
    public void existingKeyIsRejectedOnClone() {
        WorldManager manager = worldManager();
        LoadedMultiverseWorld source = createByName(manager, "gcb_clone_source");
        NamespacedKey targetKey = new NamespacedKey("gcb", "clone_target");
        createByKey(manager, targetKey);
        int before = manager.getWorlds().size();

        var attempt = call(() -> manager.cloneWorld(CloneWorldOptions.fromTo((MultiverseWorld) source, targetKey)),
                "cloneWorld(gcb_clone_source -> gcb:clone_target)");
        GcbAssert.isTrue(attempt.isFailure(), "cloning onto the existing key gcb:clone_target must fail");
        GcbAssert.equals(CloneFailureReason.WORLD_EXIST_LOADED, attempt.getFailureReason(),
                "cloning onto the loaded gcb:clone_target must be rejected as WORLD_EXIST_LOADED, got " + attempt);
        GcbAssert.equals(before, manager.getWorlds().size(), "the Multiverse world list must be unchanged");
        GcbAssert.isFalse(new File(Bukkit.getWorldContainer(), "gcb_clone_target").exists(),
                "a rejected clone must not copy the world folder");
    }

    @GcbCase(value = "import adopts a loaded Bukkit world addressed by key", order = 6)
    public void importLoadedBukkitWorldByKey() {
        WorldManager manager = worldManager();
        NamespacedKey key = new NamespacedKey("gcb", "direct");
        World bukkitWorld = WorldCreator.ofKey(key).type(WorldType.FLAT).generateStructures(false).createWorld();
        GcbAssert.notNull(bukkitWorld, "Paper must create the gcb:direct world");
        GcbAssert.equals("direct", bukkitWorld.getName(), "Paper names a keyed world after the key path");
        GcbAssert.isFalse(manager.isWorld("direct") || manager.isWorld("gcb:direct"),
                "the world must not be known to Multiverse before the import");

        var attempt = call(() -> manager.importWorld(ImportWorldOptions.worldKey(key)), "importWorld(gcb:direct)");
        GcbAssert.isTrue(attempt.isSuccess(), "importing the loaded world gcb:direct by key must succeed: " + attempt);
        LoadedMultiverseWorld imported = attempt.get();
        GcbAssert.equals(key, imported.getKey(), "the imported world keeps the Bukkit world's key");
        GcbAssert.equals("direct", imported.getName(), "the imported world keeps the Bukkit world's name");
        GcbAssert.isTrue(imported.getBukkitWorld().isDefined() && imported.getBukkitWorld().get() == bukkitWorld,
                "the import must adopt the running Bukkit world instead of creating another one");
        GcbAssert.isTrue(manager.isLoadedWorld("gcb:direct") && manager.isLoadedWorld("direct"),
                "the imported world must resolve by key string and by name");
    }

    @GcbCase(value = "import is rejected when the key belongs to an existing world", order = 7)
    public void existingKeyIsRejectedOnImport() {
        WorldManager manager = worldManager();
        NamespacedKey key = new NamespacedKey("gcb", "imported_twice");
        LoadedMultiverseWorld existing = createByKey(manager, key);
        int before = manager.getWorlds().size();

        var loaded = call(() -> manager.importWorld(ImportWorldOptions.worldKey(key)), "importWorld(gcb:imported_twice)");
        GcbAssert.isTrue(loaded.isFailure(), "importing the loaded gcb:imported_twice must fail");
        GcbAssert.equals(ImportFailureReason.WORLD_EXIST_LOADED, loaded.getFailureReason(),
                "importing the loaded gcb:imported_twice must be rejected as WORLD_EXIST_LOADED, got " + loaded);
        GcbAssert.equals(before, manager.getWorlds().size(), "the Multiverse world list must be unchanged");

        GcbAssert.isTrue(manager.unloadWorld(UnloadWorldOptions.world(existing)).isSuccess(),
                "unloading gcb:imported_twice must succeed");
        int beforeUnloadedImport = manager.getWorlds().size();
        var unloaded = call(() -> manager.importWorld(ImportWorldOptions.worldKey(key)),
                "importWorld(gcb:imported_twice) while unloaded");
        GcbAssert.isTrue(unloaded.isFailure(), "importing the unloaded gcb:imported_twice must fail");
        GcbAssert.equals(ImportFailureReason.WORLD_EXIST_UNLOADED, unloaded.getFailureReason(),
                "importing the unloaded gcb:imported_twice must be rejected as WORLD_EXIST_UNLOADED, got " + unloaded);
        GcbAssert.isNull(Bukkit.getWorld("imported_twice"), "the rejected import must not load the world again");
        GcbAssert.equals(beforeUnloadedImport, manager.getWorlds().size(),
                "the rejected import must leave the post-unload world list unchanged");
        GcbAssert.isTrue(manager.getUnloadedWorld(key.toString()).isDefined()
                        && manager.getUnloadedWorld("imported_twice").isDefined(),
                "the rejected import must retain the unloaded world under its key and name");
    }

    @GcbCase(value = "import is rejected when the name is an existing world key", order = 8)
    public void nameThatIsAnExistingKeyIsRejectedOnImport() {
        WorldManager manager = worldManager();
        GcbAssert.isTrue(manager.isLoadedWorld(END_NAME), "the End must be a loaded Multiverse world");
        int before = manager.getWorlds().size();
        var attempt = call(() -> manager.importWorld(ImportWorldOptions.worldName("the_end")), "importWorld(the_end)");
        GcbAssert.isTrue(attempt.isFailure(), "importWorld(the_end) must fail: the name is the key of the loaded " + END_NAME);
        GcbAssert.equals(ImportFailureReason.WORLD_EXIST_LOADED, attempt.getFailureReason(),
                "importWorld(the_end) must be rejected as an existing loaded world, got " + attempt);
        GcbAssert.isNull(Bukkit.getWorld("the_end"), "no Bukkit world named the_end may be created");
        GcbAssert.equals(before, manager.getWorlds().size(), "the Multiverse world list must be unchanged");
    }

    @GcbCase(value = "clone is rejected when the target name is an existing world key", order = 9)
    public void nameThatIsAnExistingKeyIsRejectedOnClone() {
        WorldManager manager = worldManager();
        LoadedMultiverseWorld source = createByName(manager, "gcb_clone_end");
        GcbAssert.isTrue(manager.isLoadedWorld(END_NAME), "the End must be a loaded Multiverse world");
        int before = manager.getWorlds().size();
        var attempt = call(() -> manager.cloneWorld(CloneWorldOptions.fromTo((MultiverseWorld) source, "the_end")),
                "cloneWorld(gcb_clone_end -> the_end)");
        GcbAssert.isTrue(attempt.isFailure(), "cloning onto the name the_end must fail: it is the key of the loaded " + END_NAME);
        GcbAssert.equals(CloneFailureReason.WORLD_EXIST_LOADED, attempt.getFailureReason(),
                "cloning onto the_end must be rejected as an existing loaded world, got " + attempt);
        GcbAssert.equals(before, manager.getWorlds().size(), "the Multiverse world list must be unchanged");
        GcbAssert.isFalse(new File(Bukkit.getWorldContainer(), "the_end").exists(),
                "a rejected clone must not copy the world folder");
        GcbAssert.isNull(Bukkit.getWorld("the_end"), "no Bukkit world named the_end may be created");
    }
}
