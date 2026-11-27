package com.example.blocktrail;

import java.util.EnumSet;
import java.util.HashSet;
import java.util.Set;
import org.bukkit.Material;
import org.bukkit.configuration.file.FileConfiguration;

/** The values read from config.yml. */
public record TrailSettings(Set<Material> ignored, Set<String> worlds, int pageSize, int maxRadius) {

    public static TrailSettings from(FileConfiguration config) {
        Set<Material> ignored = EnumSet.noneOf(Material.class);
        for (String name : config.getStringList("ignored-materials")) {
            Material material = Material.matchMaterial(name.trim());
            if (material != null) {
                ignored.add(material);
            }
        }
        Set<String> worlds = new HashSet<>(config.getStringList("worlds"));
        return new TrailSettings(ignored, worlds, Math.max(1, config.getInt("page-size", 5)),
            Math.max(0, config.getInt("max-radius", 32)));
    }

    public boolean records(String world, Material material) {
        return !ignored.contains(material) && (worlds.isEmpty() || worlds.contains(world));
    }
}
