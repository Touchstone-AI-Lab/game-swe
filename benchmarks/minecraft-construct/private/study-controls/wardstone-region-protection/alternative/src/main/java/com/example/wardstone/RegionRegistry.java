package com.example.wardstone;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.NavigableMap;
import java.util.TreeMap;

/** The in-memory set of regions, keyed and iterated by name, with flag resolution. */
final class RegionRegistry {
    /** Highest priority first, then by name. */
    private static final Comparator<Region> BY_PRIORITY_THEN_NAME =
            Comparator.comparingInt((Region region) -> region.priority())
                    .reversed()
                    .thenComparing(Region::name);

    private final NavigableMap<String, Region> regions = new TreeMap<>();

    Region get(String name) {
        return regions.get(name);
    }

    void put(Region region) {
        regions.put(region.name(), region);
    }

    void remove(String name) {
        regions.remove(name);
    }

    int size() {
        return regions.size();
    }

    /** Every region, sorted by name. */
    Collection<Region> all() {
        return Collections.unmodifiableCollection(regions.values());
    }

    /** Replaces every region with the given ones. */
    void replaceAll(Collection<Region> replacement) {
        regions.clear();
        for (Region region : replacement) {
            put(region);
        }
    }

    /** The regions containing the block, highest priority first, then by name. */
    List<Region> regionsAt(String world, int x, int y, int z) {
        List<Region> found = new ArrayList<>();
        for (Region region : regions.values()) {
            if (region.contains(world, x, y, z)) {
                found.add(region);
            }
        }
        found.sort(BY_PRIORITY_THEN_NAME);
        return found;
    }

    /**
     * Resolves a flag at a block. Only the regions that contain the block and set
     * the flag take part, and only those at the highest priority among them count.
     *
     * @return the deciding region (the alphabetically first denying region at that
     *     priority) when the flag is denied, or {@code null} when it is allowed
     */
    Region denyingRegion(String world, int x, int y, int z, Flag flag) {
        boolean anySet = false;
        int topPriority = 0;
        Region decider = null;
        // Regions are visited in name order, so the first denial kept at the top
        // priority is the alphabetically first one.
        for (Region region : regions.values()) {
            FlagValue value = region.flag(flag);
            if (value == null || !region.contains(world, x, y, z)) {
                continue;
            }
            if (!anySet || region.priority() > topPriority) {
                anySet = true;
                topPriority = region.priority();
                decider = value == FlagValue.DENY ? region : null;
            } else if (region.priority() == topPriority && value == FlagValue.DENY && decider == null) {
                decider = region;
            }
        }
        return decider;
    }
}
