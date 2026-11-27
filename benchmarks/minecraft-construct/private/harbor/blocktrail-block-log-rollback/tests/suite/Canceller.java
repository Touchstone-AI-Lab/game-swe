package gcbtest.blocktrail;

import java.util.HashSet;
import java.util.Set;
import org.bukkit.Location;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.entity.EntityExplodeEvent;

/** Another plugin's listener: cancels breaks and trims explosions at chosen blocks. */
public final class Canceller implements Listener {

    private final Set<Location> cancelBreaks = new HashSet<>();
    private final Set<Location> spareFromExplosions = new HashSet<>();

    public void cancelBreakAt(Location location) {
        cancelBreaks.add(location.toBlockLocation());
    }

    public void spareFromExplosions(Location location) {
        spareFromExplosions.add(location.toBlockLocation());
    }

    public void clear() {
        cancelBreaks.clear();
        spareFromExplosions.clear();
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onBreak(BlockBreakEvent event) {
        if (cancelBreaks.contains(event.getBlock().getLocation().toBlockLocation())) {
            event.setCancelled(true);
        }
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void onExplode(EntityExplodeEvent event) {
        event.blockList().removeIf(block -> spareFromExplosions.contains(block.getLocation().toBlockLocation()));
    }
}
