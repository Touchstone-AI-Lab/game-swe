package com.example.wardstone;

import java.util.Collection;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Renders the {@code regions.yml} document in its documented layout: corners as
 * flow mappings, owners and members as sorted flow sequences and flags as a block
 * mapping (or {@code {}} when a region sets none).
 */
final class RegionYaml {
    /** Scalars that YAML 1.1 always reads as plain strings when left unquoted. */
    private static final Pattern PLAIN_SAFE = Pattern.compile("[A-Za-z_][A-Za-z0-9_-]*");
    /** Plain words that YAML 1.1 would read as a boolean or null instead of a string. */
    private static final Set<String> RESERVED_WORDS =
            Set.of("y", "n", "yes", "no", "true", "false", "on", "off", "null");

    private RegionYaml() {
    }

    static String render(Collection<Region> regions) {
        if (regions.isEmpty()) {
            return "regions: {}\n";
        }
        StringBuilder out = new StringBuilder("regions:\n");
        for (Region region : regions) {
            out.append("  ").append(scalar(region.name())).append(":\n");
            out.append("    world: ").append(scalar(region.world())).append('\n');
            out.append("    min: ").append(point(region.minX(), region.minY(), region.minZ())).append('\n');
            out.append("    max: ").append(point(region.maxX(), region.maxY(), region.maxZ())).append('\n');
            out.append("    priority: ").append(region.priority()).append('\n');
            out.append("    owners: ").append(sequence(region.players(Role.OWNER))).append('\n');
            out.append("    members: ").append(sequence(region.players(Role.MEMBER))).append('\n');
            Map<Flag, FlagValue> flags = region.flags();
            if (flags.isEmpty()) {
                out.append("    flags: {}\n");
            } else {
                out.append("    flags:\n");
                for (Map.Entry<Flag, FlagValue> flag : flags.entrySet()) {
                    out.append("      ").append(flag.getKey().id()).append(": ")
                            .append(flag.getValue().id()).append('\n');
                }
            }
        }
        return out.toString();
    }

    private static String point(int x, int y, int z) {
        return "{x: " + x + ", y: " + y + ", z: " + z + "}";
    }

    private static String sequence(Collection<String> values) {
        StringBuilder out = new StringBuilder("[");
        for (String value : values) {
            if (out.length() > 1) {
                out.append(", ");
            }
            out.append(scalar(value));
        }
        return out.append(']').toString();
    }

    /**
     * Leaves a scalar plain when YAML reads it back as the same string, and
     * single-quotes it otherwise (numbers, booleans, null or special characters).
     */
    static String scalar(String value) {
        if (PLAIN_SAFE.matcher(value).matches()
                && !RESERVED_WORDS.contains(value.toLowerCase(Locale.ROOT))) {
            return value;
        }
        return "'" + value.replace("'", "''") + "'";
    }
}
