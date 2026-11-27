package io.gamecodebench.harness;

import java.util.Objects;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.entity.Entity;

/** Entity helpers. */
public final class GcbEntities {

    private GcbEntities() {
    }

    public static <T extends Entity> T spawn(Location at, Class<T> type) {
        Objects.requireNonNull(at, "at");
        World world = Objects.requireNonNull(at.getWorld(), "location has no world");
        // Without players no chunk is entity-ticking, and an entity added to such a
        // chunk never becomes valid; keep the target chunk force-loaded instead.
        at.getChunk().setForceLoaded(true);
        return world.spawn(at, Objects.requireNonNull(type, "type"));
    }

    public static void remove(Entity entity) {
        Objects.requireNonNull(entity, "entity").remove();
    }
}
