package com.example.wardstone;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;
import org.bukkit.block.Block;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

/** regions.yml and the regions it holds, plus flag resolution. */
public final class RegionStore {

    /** The result of resolving one flag at one block. */
    public record Decision(boolean denied, Region deciding) {
    }

    private final File file;
    private final Map<String, Region> regions = new TreeMap<>();

    public RegionStore(File dataFolder) {
        this.file = new File(dataFolder, "regions.yml");
    }

    public void load() {
        regions.clear();
        if (!file.isFile()) {
            return;
        }
        YamlConfiguration yaml = YamlConfiguration.loadConfiguration(file);
        ConfigurationSection section = yaml.getConfigurationSection("regions");
        if (section == null) {
            return;
        }
        for (String key : section.getKeys(false)) {
            ConfigurationSection entry = section.getConfigurationSection(key);
            if (entry == null) {
                continue;
            }
            String name = key.toLowerCase(Locale.ROOT);
            Region region = new Region(name, entry.getString("world", "world"),
                entry.getInt("min.x"), entry.getInt("min.y"), entry.getInt("min.z"),
                entry.getInt("max.x"), entry.getInt("max.y"), entry.getInt("max.z"));
            region.priority(entry.getInt("priority", 0));
            entry.getStringList("owners").forEach(owner -> region.owners().add(owner.toLowerCase(Locale.ROOT)));
            entry.getStringList("members").forEach(member -> region.members().add(member.toLowerCase(Locale.ROOT)));
            ConfigurationSection flags = entry.getConfigurationSection("flags");
            if (flags != null) {
                for (String flagKey : flags.getKeys(false)) {
                    Flag flag = Flag.fromKey(flagKey);
                    String value = String.valueOf(flags.get(flagKey)).toLowerCase(Locale.ROOT);
                    if (flag != null && (value.equals("allow") || value.equals("deny"))) {
                        region.flags().put(flag.key(), value.equals("allow"));
                    }
                }
            }
            regions.put(name, region);
        }
    }

    public void save() throws IOException {
        YamlConfiguration yaml = new YamlConfiguration();
        ConfigurationSection root = yaml.createSection("regions");
        for (Region region : regions.values()) {
            ConfigurationSection entry = root.createSection(region.name());
            entry.set("world", region.world());
            entry.set("min.x", region.minX());
            entry.set("min.y", region.minY());
            entry.set("min.z", region.minZ());
            entry.set("max.x", region.maxX());
            entry.set("max.y", region.maxY());
            entry.set("max.z", region.maxZ());
            entry.set("priority", region.priority());
            entry.set("owners", new ArrayList<>(region.owners()));
            entry.set("members", new ArrayList<>(region.members()));
            ConfigurationSection flags = entry.createSection("flags");
            region.flags().forEach((key, allow) -> flags.set(key, allow ? "allow" : "deny"));
        }
        file.getParentFile().mkdirs();
        yaml.save(file);
    }

    public Region get(String name) {
        return regions.get(name);
    }

    public void add(Region region) {
        regions.put(region.name(), region);
    }

    public void remove(String name) {
        regions.remove(name);
    }

    public Collection<Region> all() {
        return regions.values();
    }

    public List<Region> at(String world, int x, int y, int z) {
        List<Region> found = new ArrayList<>();
        for (Region region : regions.values()) {
            if (region.contains(world, x, y, z)) {
                found.add(region);
            }
        }
        return found;
    }

    /** Resolves a flag at a block: the highest priority setting wins, deny wins ties. */
    public Decision decide(Block block, Flag flag) {
        Integer top = null;
        Region deciding = null;
        boolean denied = false;
        for (Region region : at(block.getWorld().getName(), block.getX(), block.getY(), block.getZ())) {
            Boolean allow = region.flag(flag);
            if (allow == null) {
                continue;
            }
            if (top == null || region.priority() > top) {
                top = region.priority();
                denied = false;
                deciding = null;
            }
            if (region.priority() == top && !allow) {
                denied = true;
                if (deciding == null || region.name().compareTo(deciding.name()) < 0) {
                    deciding = region;
                }
            }
        }
        return new Decision(denied, deciding);
    }
}
