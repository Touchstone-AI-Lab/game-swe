package com.example.blocktrail;

import java.util.Locale;
import org.bukkit.Material;

/** Conversions between {@link Material} and the lower-case keys written to the log. */
final class Materials {

    private Materials() {
    }

    /** The material's lower-case key without namespace, e.g. {@code oak_planks}. */
    static String key(Material material) {
        return material.getKey().getKey();
    }

    /** Resolves a logged key such as {@code grass_block}, or returns {@code null}. */
    static Material fromKey(String key) {
        if (key.isEmpty()) {
            return null;
        }
        Material material = Material.getMaterial(key.toUpperCase(Locale.ROOT));
        if (material == null || material.isLegacy()) {
            return null;
        }
        return material;
    }
}
