package io.gamecodebench.harness;

import java.util.Objects;
import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.WorldCreator;
import org.bukkit.WorldType;

/** World helpers. */
public final class GcbWorlds {

    private GcbWorlds() {
    }

    /** The server's primary (overworld) world. */
    public static World main() {
        return Bukkit.getWorlds().get(0);
    }

    /** Loads or creates a structure-free flat world with the given name and seed. */
    public static World flat(String name, long seed) {
        Objects.requireNonNull(name, "name");
        World existing = Bukkit.getWorld(name);
        if (existing != null) {
            return existing;
        }
        World created = new WorldCreator(name).type(WorldType.FLAT).generateStructures(false).seed(seed).createWorld();
        if (created != null) {
            keepSpawnLoaded(created);
        }
        return created;
    }

    /** Unloads the named world without saving; false if it is not loaded or cannot be unloaded. */
    /**
     * Force-loads the 3x3 chunks around the world spawn so entities, block ticks and
     * scheduler-driven world state behave as on a populated server; a player-less
     * server otherwise keeps no chunk in the entity-ticking state.
     */
    public static void keepSpawnLoaded(World world) {
        Objects.requireNonNull(world, "world");
        org.bukkit.Chunk centre = world.getSpawnLocation().getChunk();
        for (int dx = -1; dx <= 1; dx++) {
            for (int dz = -1; dz <= 1; dz++) {
                world.getChunkAt(centre.getX() + dx, centre.getZ() + dz).setForceLoaded(true);
            }
        }
    }

    public static boolean unload(String name) {
        World world = Bukkit.getWorld(Objects.requireNonNull(name, "name"));
        return world != null && Bukkit.unloadWorld(world, false);
    }
}
