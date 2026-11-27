package com.example.blocktrail;

import org.bukkit.Material;
import org.bukkit.block.Block;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.entity.EntityExplodeEvent;

/** Records block changes once every other plugin has had its say. */
public final class TrailListener implements Listener {

    private final BlockTrailPlugin plugin;

    public TrailListener(BlockTrailPlugin plugin) {
        this.plugin = plugin;
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onBreak(BlockBreakEvent event) {
        Block block = event.getBlock();
        plugin.record(event.getPlayer().getName(), Action.BREAK, block, block.getType(), Material.AIR, block.getType(),
            block.getBlockData().getAsString(), "minecraft:air");
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onPlace(BlockPlaceEvent event) {
        Block block = event.getBlockPlaced();
        Material placed = block.getType();
        plugin.record(event.getPlayer().getName(), Action.PLACE, block, event.getBlockReplacedState().getType(),
            placed, placed, event.getBlockReplacedState().getBlockData().getAsString(), block.getBlockData().getAsString());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onExplode(EntityExplodeEvent event) {
        String actor = "#" + event.getEntityType().getKey().getKey();
        for (Block block : event.blockList()) {
            Material material = block.getType();
            if (!material.isAir()) {
                plugin.record(actor, Action.EXPLODE, block, material, Material.AIR, material,
                    block.getBlockData().getAsString(), "minecraft:air");
            }
        }
    }
}
