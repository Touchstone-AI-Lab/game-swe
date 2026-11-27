package com.example.wardstone;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.logging.Logger;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;

/** Reads and writes {@code regions.yml}. */
final class RegionStorage {
    private final Path file;
    private final Logger logger;

    RegionStorage(Path file, Logger logger) {
        this.file = file;
        this.logger = logger;
    }

    /**
     * Reads every region from the file. A missing file means no regions; entries
     * that are not well-formed regions are skipped with a warning.
     */
    List<Region> load() {
        if (!Files.isRegularFile(file)) {
            return List.of();
        }
        YamlConfiguration yaml = new YamlConfiguration();
        try {
            yaml.load(file.toFile());
        } catch (IOException | InvalidConfigurationException e) {
            logger.warning("Could not read " + file.getFileName() + ": " + e.getMessage());
            return List.of();
        }
        ConfigurationSection root = yaml.getConfigurationSection("regions");
        if (root == null) {
            return List.of();
        }
        List<Region> loaded = new ArrayList<>();
        for (String key : root.getKeys(false)) {
            Region region = readRegion(key, root.getConfigurationSection(key));
            if (region == null) {
                logger.warning("Skipping malformed region '" + key + "' in " + file.getFileName());
            } else {
                loaded.add(region);
            }
        }
        return loaded;
    }

    /** Writes every region, replacing the file only once the new content is complete. */
    void save(Collection<Region> regions) throws IOException {
        Files.createDirectories(file.getParent());
        Path temporary = file.resolveSibling(file.getFileName() + ".tmp");
        Files.writeString(temporary, RegionYaml.render(regions), StandardCharsets.UTF_8);
        try {
            Files.move(temporary, file, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        } catch (AtomicMoveNotSupportedException e) {
            Files.move(temporary, file, StandardCopyOption.REPLACE_EXISTING);
        }
    }

    private static Region readRegion(String key, ConfigurationSection section) {
        String name = Names.region(key);
        if (name == null || section == null) {
            return null;
        }
        String world = section.getString("world");
        int[] min = corner(section.getConfigurationSection("min"));
        int[] max = corner(section.getConfigurationSection("max"));
        if (world == null || world.isEmpty() || min == null || max == null) {
            return null;
        }
        Region region = new Region(name, world, min[0], min[1], min[2], max[0], max[1], max[2]);
        region.setPriority(section.getInt("priority", 0));
        readPlayers(section.getStringList("owners"), region, Role.OWNER);
        readPlayers(section.getStringList("members"), region, Role.MEMBER);
        ConfigurationSection flags = section.getConfigurationSection("flags");
        if (flags != null) {
            for (String flagKey : flags.getKeys(false)) {
                Flag flag = Flag.fromId(flagKey);
                String text = flags.getString(flagKey);
                FlagValue value = text == null ? null : FlagValue.fromId(text);
                if (flag != null && value != null) {
                    region.setFlag(flag, value);
                }
            }
        }
        return region;
    }

    private static int[] corner(ConfigurationSection section) {
        if (section == null) {
            return null;
        }
        int[] point = new int[3];
        String[] axes = {"x", "y", "z"};
        for (int i = 0; i < axes.length; i++) {
            if (!(section.get(axes[i]) instanceof Number number)) {
                return null;
            }
            point[i] = number.intValue();
        }
        return point;
    }

    private static void readPlayers(List<String> names, Region region, Role role) {
        for (String raw : names) {
            String player = Names.player(raw);
            if (player != null) {
                region.addPlayer(role, player);
            }
        }
    }
}
