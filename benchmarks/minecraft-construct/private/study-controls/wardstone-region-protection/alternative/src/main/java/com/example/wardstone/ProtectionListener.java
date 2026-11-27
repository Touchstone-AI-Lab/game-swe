package com.example.wardstone;

import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import org.bukkit.block.Block;
import org.bukkit.entity.Player;
import org.bukkit.event.Cancellable;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockBurnEvent;
import org.bukkit.event.block.BlockExplodeEvent;
import org.bukkit.event.block.BlockFromToEvent;
import org.bukkit.event.block.BlockIgniteEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.entity.EntityExplodeEvent;

/**
 * Applies region flags to building, explosions and fire. Players are only asked
 * for their name and permissions and sent plain messages.
 */
final class ProtectionListener implements Listener {
    static final String BYPASS_PERMISSION = "wardstone.bypass";

    private final RegionRegistry registry;

    ProtectionListener(RegionRegistry registry) {
        this.registry = registry;
    }

    @EventHandler(ignoreCancelled = true)
    public void onBlockBreak(BlockBreakEvent event) {
        guardBuilding(event, event.getPlayer(), event.getBlock(), Flag.BLOCK_BREAK, "break");
    }

    @EventHandler(ignoreCancelled = true)
    public void onBlockPlace(BlockPlaceEvent event) {
        guardBuilding(event, event.getPlayer(), event.getBlockPlaced(), Flag.BLOCK_PLACE, "place");
    }

    @EventHandler(ignoreCancelled = true)
    public void onBlockFromTo(BlockFromToEvent event) {
        if (denied(event.getToBlock(), Flag.BLOCK_PLACE) != null) {
            event.setCancelled(true);
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onEntityExplode(EntityExplodeEvent event) {
        removeProtected(event.blockList());
    }

    @EventHandler(ignoreCancelled = true)
    public void onBlockExplode(BlockExplodeEvent event) {
        removeProtected(event.blockList());
    }

    @EventHandler(ignoreCancelled = true)
    public void onBlockBurn(BlockBurnEvent event) {
        if (denied(event.getBlock(), Flag.FIRE) != null) {
            event.setCancelled(true);
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onBlockIgnite(BlockIgniteEvent event) {
        switch (event.getCause()) {
            case SPREAD, LAVA, LIGHTNING -> {
                if (denied(event.getBlock(), Flag.FIRE) != null) {
                    event.setCancelled(true);
                }
            }
            default -> {
                // Players and other ignition sources are not governed by the fire flag.
            }
        }
    }

    private void guardBuilding(Cancellable event, Player player, Block block, Flag flag, String verb) {
        Region decider = denied(block, flag);
        if (decider == null) {
            return;
        }
        if (player != null
                && (player.hasPermission(BYPASS_PERMISSION)
                        || decider.isOwnerOrMember(player.getName().toLowerCase(Locale.ROOT)))) {
            return;
        }
        event.setCancelled(true);
        if (player != null) {
            player.sendMessage("You cannot " + verb + " blocks in " + decider.name() + ".");
        }
    }

    /** Drops every block whose explosion flag is denied; the rest stay in order. */
    private void removeProtected(List<Block> blocks) {
        for (Iterator<Block> it = blocks.iterator(); it.hasNext(); ) {
            if (denied(it.next(), Flag.EXPLOSION) != null) {
                it.remove();
            }
        }
    }

    /** The deciding region when the flag is denied at the block, otherwise {@code null}. */
    private Region denied(Block block, Flag flag) {
        return registry.denyingRegion(block.getWorld().getName(), block.getX(), block.getY(), block.getZ(), flag);
    }
}
