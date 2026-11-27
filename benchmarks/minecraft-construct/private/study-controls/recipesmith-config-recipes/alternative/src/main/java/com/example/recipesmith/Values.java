package com.example.recipesmith;

import java.math.BigInteger;
import java.util.Locale;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;

/** Small conversions shared by the parser, the registry and the command. */
final class Values {
    /** How a missing value is shown in a reason. */
    static final String MISSING = "none";

    private static final String MINECRAFT_PREFIX = NamespacedKey.MINECRAFT + ":";

    private Values() {
    }

    /** A configuration value as written in the file. */
    static String text(Object raw) {
        return String.valueOf(raw);
    }

    /** A configuration value as written in the file, or {@code none} when it is missing. */
    static String written(Object raw) {
        return raw == null ? MISSING : text(raw);
    }

    /**
     * Resolves a case-insensitive material name to a material that is an item, or {@code null}.
     * Air and legacy materials are not items that a recipe can use.
     */
    static Material itemMaterial(String name) {
        if (name == null || name.isEmpty()) {
            return null;
        }
        String bare = name.regionMatches(true, 0, MINECRAFT_PREFIX, 0, MINECRAFT_PREFIX.length())
                ? name.substring(MINECRAFT_PREFIX.length())
                : name;
        Material material = Material.getMaterial(bare.toUpperCase(Locale.ROOT));
        if (material == null || material.isLegacy() || material.isAir() || !material.isItem()) {
            return null;
        }
        return material;
    }

    /** The lower-case key of a material, such as {@code coarse_dirt}. */
    static String materialKey(Material material) {
        return material.name().toLowerCase(Locale.ROOT);
    }

    /**
     * A whole number from a YAML scalar (integers, or floating values without a fraction), or
     * {@code null} when the value is not a whole number.
     */
    static Long wholeNumber(Object raw) {
        if (raw instanceof Integer || raw instanceof Long || raw instanceof Short || raw instanceof Byte) {
            return ((Number) raw).longValue();
        }
        if (raw instanceof BigInteger big) {
            return big.bitLength() < Long.SIZE ? big.longValue() : null;
        }
        if (raw instanceof Double || raw instanceof Float) {
            double value = ((Number) raw).doubleValue();
            if (Double.isFinite(value) && value == Math.rint(value) && Math.abs(value) < 1.0e15) {
                return (long) value;
            }
        }
        return null;
    }

    /**
     * Parses a recipe key such as {@code minecraft:torch} or {@code torch} (the {@code minecraft}
     * namespace is assumed), or returns {@code null} when it is not a valid key.
     */
    static NamespacedKey parseKey(String raw) {
        if (raw == null || raw.isEmpty()) {
            return null;
        }
        try {
            return NamespacedKey.fromString(raw);
        } catch (IllegalArgumentException invalid) {
            return null;
        }
    }

    /** A key in {@code namespace:key} form, or the input as written when it is not a key. */
    static String displayKey(String raw) {
        NamespacedKey key = parseKey(raw);
        return key == null ? raw : key.toString();
    }
}
