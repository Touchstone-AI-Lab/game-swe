package com.example.wardstone;

import java.math.BigInteger;
import java.util.Collections;
import java.util.EnumMap;
import java.util.Map;
import java.util.SortedSet;
import java.util.TreeSet;

/**
 * A named cuboid in one world. Its corners are normalised on construction and
 * every bound is inclusive. Names, owners and members are expected in lower case.
 */
final class Region {
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
    private final Map<Flag, FlagValue> flags = new EnumMap<>(Flag.class);

    Region(String name, String world, int x1, int y1, int z1, int x2, int y2, int z2) {
        this.name = name;
        this.world = world;
        this.minX = Math.min(x1, x2);
        this.minY = Math.min(y1, y2);
        this.minZ = Math.min(z1, z2);
        this.maxX = Math.max(x1, x2);
        this.maxY = Math.max(y1, y2);
        this.maxZ = Math.max(z1, z2);
    }

    String name() {
        return name;
    }

    String world() {
        return world;
    }

    int minX() {
        return minX;
    }

    int minY() {
        return minY;
    }

    int minZ() {
        return minZ;
    }

    int maxX() {
        return maxX;
    }

    int maxY() {
        return maxY;
    }

    int maxZ() {
        return maxZ;
    }

    /** Number of blocks along x, both corners included. */
    long sizeX() {
        return (long) maxX - minX + 1;
    }

    /** Number of blocks along y, both corners included. */
    long sizeY() {
        return (long) maxY - minY + 1;
    }

    /** Number of blocks along z, both corners included. */
    long sizeZ() {
        return (long) maxZ - minZ + 1;
    }

    /** Block count; exact even when it does not fit in a {@code long}. */
    BigInteger volume() {
        return BigInteger.valueOf(sizeX())
                .multiply(BigInteger.valueOf(sizeY()))
                .multiply(BigInteger.valueOf(sizeZ()));
    }

    /**
     * Whether the block at the given coordinates of the named world lies inside.
     * World names are compared case-insensitively, as Bukkit looks worlds up.
     */
    boolean contains(String worldName, int x, int y, int z) {
        return world.equalsIgnoreCase(worldName)
                && x >= minX && x <= maxX
                && y >= minY && y <= maxY
                && z >= minZ && z <= maxZ;
    }

    int priority() {
        return priority;
    }

    void setPriority(int priority) {
        this.priority = priority;
    }

    /** Sorted, read-only view of the players with the given role. */
    SortedSet<String> players(Role role) {
        return Collections.unmodifiableSortedSet(set(role));
    }

    /** Adds a lower-case player name; returns false when it was already listed. */
    boolean addPlayer(Role role, String player) {
        return set(role).add(player);
    }

    /** Removes a lower-case player name; returns false when it was not listed. */
    boolean removePlayer(Role role, String player) {
        return set(role).remove(player);
    }

    /** Whether the lower-case player name is an owner or a member. */
    boolean isOwnerOrMember(String player) {
        return owners.contains(player) || members.contains(player);
    }

    /** The value this region sets the flag to, or {@code null} when it does not set it. */
    FlagValue flag(Flag flag) {
        return flags.get(flag);
    }

    void setFlag(Flag flag, FlagValue value) {
        flags.put(flag, value);
    }

    void clearFlag(Flag flag) {
        flags.remove(flag);
    }

    /** The flags this region sets, iterated in flag-name order. */
    Map<Flag, FlagValue> flags() {
        return Collections.unmodifiableMap(flags);
    }

    private SortedSet<String> set(Role role) {
        return role == Role.OWNER ? owners : members;
    }
}
