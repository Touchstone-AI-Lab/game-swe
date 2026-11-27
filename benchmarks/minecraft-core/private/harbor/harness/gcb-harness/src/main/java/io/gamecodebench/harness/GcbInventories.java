package io.gamecodebench.harness;

import java.util.Objects;
import net.kyori.adventure.text.Component;
import org.bukkit.Bukkit;
import org.bukkit.inventory.Inventory;

/** Inventory helpers. */
public final class GcbInventories {

    private GcbInventories() {
    }

    /** A holder-less chest-style inventory; size must be a multiple of 9 up to 54. */
    public static Inventory create(int size, String title) {
        return Bukkit.createInventory(null, size, Component.text(Objects.requireNonNull(title, "title")));
    }
}
