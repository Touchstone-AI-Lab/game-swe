package com.example.wardstone;

import java.util.List;
import org.bukkit.block.Block;
import org.bukkit.entity.Player;
import org.bukkit.event.Cancellable;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockBurnEvent;
import org.bukkit.event.block.BlockFromToEvent;
import org.bukkit.event.block.BlockExplodeEvent;
import org.bukkit.event.block.BlockIgniteEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.entity.EntityExplodeEvent;

/** Applies the region flags to block events. */
public final class ProtectionListener implements Listener {

    private final WardstonePlugin plugin;

    public ProtectionListener(WardstonePlugin plugin) {
        this.plugin = plugin;
    }

    private void build(Player player, Block block, Flag flag, Cancellable event, String verb) {
        RegionStore.Decision decision = plugin.regions().decide(block, flag);
        if (!decision.denied() || player.hasPermission("wardstone.bypass")
            || decision.deciding().trusts(player.getName())) {
            return;
        }
        event.setCancelled(true);
        player.sendMessage("You cannot " + verb + " blocks in " + decision.deciding().name() + ".");
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onBreak(BlockBreakEvent event) {
        build(event.getPlayer(), event.getBlock(), Flag.BLOCK_BREAK, event, "break");
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onPlace(BlockPlaceEvent event) {
        build(event.getPlayer(), event.getBlockPlaced(), Flag.BLOCK_PLACE, event, "place");
    }

    private void filter(List<Block> blocks) {
        blocks.removeIf(block -> plugin.regions().decide(block, Flag.EXPLOSION).denied());
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onEntityExplode(EntityExplodeEvent event) {
        filter(event.blockList());
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onBlockExplode(BlockExplodeEvent event) {
        filter(event.blockList());
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onBurn(BlockBurnEvent event) {
        if (plugin.regions().decide(event.getBlock(), Flag.FIRE).denied()) {
            event.setCancelled(true);
        }
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onIgnite(BlockIgniteEvent event) {
        BlockIgniteEvent.IgniteCause cause = event.getCause();
        boolean natural = cause == BlockIgniteEvent.IgniteCause.SPREAD || cause == BlockIgniteEvent.IgniteCause.LAVA
            || cause == BlockIgniteEvent.IgniteCause.LIGHTNING;
        if (natural && plugin.regions().decide(event.getBlock(), Flag.FIRE).denied()) {
            event.setCancelled(true);
        }
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onFlow(BlockFromToEvent event) {
        if (plugin.regions().decide(event.getToBlock(), Flag.BLOCK_PLACE).denied()) {
            event.setCancelled(true);
        }
    }
}
