package com.example.wardstone;

import java.util.Map;
import java.util.SortedSet;
import java.util.TreeMap;
import java.util.TreeSet;

/** A named cuboid with inclusive bounds, a priority, owners, members and flags. */
public final class Region {

    private final String name;
    private final String world;
    private final int minX;
    private final int minY;
    private final int minZ;
    private final int maxX;
    private final int maxY;
    private final int maxZ;
    private int priority;
    private final SortedSet<String> owners = new TreeSet<>();
    private final SortedSet<String> members = new TreeSet<>();
    /** Flag key to allow (true) or deny (false), sorted by key. */
    private final Map<String, Boolean> flags = new TreeMap<>();

    public Region(String name, String world, int x1, int y1, int z1, int x2, int y2, int z2) {
        this.name = name;
        this.world = world;
        this.minX = Math.min(x1, x2);
        this.minY = Math.min(y1, y2);
        this.minZ = Math.min(z1, z2);
        this.maxX = Math.max(x1, x2);
        this.maxY = Math.max(y1, y2);
        this.maxZ = Math.max(z1, z2);
    }

    public String name() {
        return name;
    }

    public String world() {
        return world;
    }

    public int minX() {
        return minX;
    }

    public int minY() {
        return minY;
    }

    public int minZ() {
        return minZ;
    }

    public int maxX() {
        return maxX;
    }

    public int maxY() {
        return maxY;
    }

    public int maxZ() {
        return maxZ;
    }

    public long sizeX() {
        return (long) maxX - minX + 1;
    }

    public long sizeY() {
        return (long) maxY - minY + 1;
    }

    public long sizeZ() {
        return (long) maxZ - minZ + 1;
    }

    public long volume() {
        return sizeX() * sizeY() * sizeZ();
    }

    public int priority() {
        return priority;
    }

    public void priority(int priority) {
        this.priority = priority;
    }

    public SortedSet<String> owners() {
        return owners;
    }

    public SortedSet<String> members() {
        return members;
    }

    public Map<String, Boolean> flags() {
        return flags;
    }

    /** Whether the flag is set and to what: null when unset. */
    public Boolean flag(Flag flag) {
        return flags.get(flag.key());
    }

    public boolean contains(String worldName, int x, int y, int z) {
        return world.equals(worldName) && x >= minX && x <= maxX && y >= minY && y <= maxY && z >= minZ && z <= maxZ;
    }

    public boolean trusts(String player) {
        String lower = player.toLowerCase(java.util.Locale.ROOT);
        return owners.contains(lower) || members.contains(lower);
    }
}
