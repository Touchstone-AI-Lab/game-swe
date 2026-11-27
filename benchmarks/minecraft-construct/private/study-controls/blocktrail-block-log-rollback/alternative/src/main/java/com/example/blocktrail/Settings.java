package com.example.blocktrail;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import org.bukkit.Material;
import org.bukkit.configuration.file.FileConfiguration;

/** The values read from {@code config.yml}. */
record Settings(Set<String> ignoredMaterials, List<String> worlds, int pageSize, int maxRadius) {

    static final int DEFAULT_PAGE_SIZE = 5;
    static final int DEFAULT_MAX_RADIUS = 32;

    static Settings from(FileConfiguration config) {
        Set<String> ignored = new HashSet<>();
        for (String name : config.getStringList("ignored-materials")) {
            ignored.add(name.trim().toUpperCase(Locale.ROOT));
        }
        List<String> worlds = new ArrayList<>();
        for (String name : config.getStringList("worlds")) {
            worlds.add(name.trim());
        }
        int pageSize = config.getInt("page-size", DEFAULT_PAGE_SIZE);
        if (pageSize < 1) {
            pageSize = DEFAULT_PAGE_SIZE;
        }
        int maxRadius = config.getInt("max-radius", DEFAULT_MAX_RADIUS);
        if (maxRadius < 0) {
            maxRadius = DEFAULT_MAX_RADIUS;
        }
        return new Settings(Set.copyOf(ignored), List.copyOf(worlds), pageSize, maxRadius);
    }

    /** Whether a change of {@code material} in {@code world} passes both filters. */
    boolean records(Material material, String world) {
        if (ignoredMaterials.contains(material.name())) {
            return false;
        }
        if (worlds.isEmpty()) {
            return true;
        }
        for (String listed : worlds) {
            if (listed.equalsIgnoreCase(world)) {
                return true;
            }
        }
        return false;
    }
}
