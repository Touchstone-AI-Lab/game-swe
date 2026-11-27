package com.example.blocktrail;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.function.Supplier;
import org.bukkit.Material;
import org.bukkit.block.Block;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.entity.EntityExplodeEvent;

/** Records breaks, places and explosions that were not cancelled. */
final class ChangeListener implements Listener {

    private final ChangeStore store;
    private final Supplier<Settings> settings;

    ChangeListener(ChangeStore store, Supplier<Settings> settings) {
        this.store = store;
        this.settings = settings;
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onBreak(BlockBreakEvent event) {
        Block block = event.getBlock();
        Material from = block.getType();
        String world = block.getWorld().getName();
        if (!settings.get().records(from, world)) {
            return;
        }
        store.record(List.of(new ChangeStore.Draft(event.getPlayer().getName(), ChangeAction.BREAK,
                world, block.getX(), block.getY(), block.getZ(), from, Material.AIR,
                block.getBlockData().getAsString(), Material.AIR.createBlockData().getAsString())));
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onPlace(BlockPlaceEvent event) {
        Player player = event.getPlayer();
        if (player == null) {
            return;
        }
        Block placed = event.getBlockPlaced();
        Material from = event.getBlockReplacedState().getType();
        Material to = placed.getType();
        String world = placed.getWorld().getName();
        if (!settings.get().records(to, world)) {
            return;
        }
        store.record(List.of(new ChangeStore.Draft(player.getName(), ChangeAction.PLACE,
                world, placed.getX(), placed.getY(), placed.getZ(), from, to,
                event.getBlockReplacedState().getBlockData().getAsString(),
                placed.getBlockData().getAsString())));
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onExplode(EntityExplodeEvent event) {
        String actor = "#" + typeKey(event.getEntity());
        Settings current = settings.get();
        List<ChangeStore.Draft> drafts = new ArrayList<>();
        for (Block block : event.blockList()) {
            Material from = block.getType();
            String world = block.getWorld().getName();
            if (from.isAir() || !current.records(from, world)) {
                continue;
            }
            drafts.add(new ChangeStore.Draft(actor, ChangeAction.EXPLODE,
                    world, block.getX(), block.getY(), block.getZ(), from, Material.AIR,
                    block.getBlockData().getAsString(), Material.AIR.createBlockData().getAsString()));
        }
        store.record(drafts);
    }

    private static String typeKey(Entity entity) {
        EntityType type = entity.getType();
        try {
            return type.getKey().getKey();
        } catch (IllegalArgumentException e) {
            return type.name().toLowerCase(Locale.ROOT);
        }
    }
}
