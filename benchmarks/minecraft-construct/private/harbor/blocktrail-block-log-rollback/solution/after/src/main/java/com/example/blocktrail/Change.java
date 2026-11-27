package com.example.blocktrail;

import org.bukkit.Material;

/** One recorded block change; the rolled-back mark is the only mutable part. */
public final class Change {

    private final long id;
    private final long time;
    private final String actor;
    private final Action action;
    private final String world;
    private final int x;
    private final int y;
    private final int z;
    private final Material from;
    private final Material to;
    private final String fromData;
    private final String toData;
    private boolean rolledBack;

    public Change(long id, long time, String actor, Action action, String world, int x, int y, int z,
                  Material from, Material to, String fromData, String toData) {
        this.id = id;
        this.time = time;
        this.actor = actor;
        this.action = action;
        this.world = world;
        this.x = x;
        this.y = y;
        this.z = z;
        this.from = from;
        this.to = to;
        this.fromData = fromData;
        this.toData = toData;
    }

    public long id() {
        return id;
    }

    public long time() {
        return time;
    }

    public String actor() {
        return actor;
    }

    public String world() {
        return world;
    }

    public int x() {
        return x;
    }

    public int y() {
        return y;
    }

    public int z() {
        return z;
    }

    public Material from() {
        return from;
    }

    public Material to() {
        return to;
    }

    public String fromData() {
        return fromData;
    }

    public String toData() {
        return toData;
    }

    public boolean rolledBack() {
        return rolledBack;
    }

    public void rolledBack(boolean rolledBack) {
        this.rolledBack = rolledBack;
    }

    public boolean at(String worldName, int bx, int by, int bz) {
        return world.equals(worldName) && x == bx && y == by && z == bz;
    }

    public static String key(Material material) {
        return material.getKey().getKey();
    }

    public String toLine() {
        String line = id + ";" + time + ";" + actor + ";" + action.key() + ";" + world + ";" + x + ";" + y + ";" + z + ";"
            + key(from) + ";" + key(to);
        return fromData == null || toData == null ? line : line + ";" + fromData + ";" + toData;
    }

    /** Parses a change line, or returns null for anything else. */
    public static Change parse(String line) {
        String[] f = line.split(";", -1);
        if (f.length != 10 && f.length != 12) {
            return null;
        }
        try {
            Action action = Action.fromKey(f[3]);
            Material from = Material.matchMaterial(f[8]);
            Material to = Material.matchMaterial(f[9]);
            if (action == null || from == null || to == null) {
                return null;
            }
            return new Change(Long.parseLong(f[0]), Long.parseLong(f[1]), f[2], action, f[4],
                Integer.parseInt(f[5]), Integer.parseInt(f[6]), Integer.parseInt(f[7]), from, to,
                f.length == 12 ? f[10] : null, f.length == 12 ? f[11] : null);
        } catch (NumberFormatException invalid) {
            return null;
        }
    }

    /** {@code #id actor broke stone}, without the location. */
    private String body(boolean withActor) {
        String who = withActor ? actor + " " : "";
        return switch (action) {
            case BREAK -> "#" + id + " " + who + "broke " + key(from);
            case PLACE -> "#" + id + " " + who + "placed " + key(to) + " over " + key(from);
            case EXPLODE -> "#" + id + " " + who + "exploded " + key(from);
        };
    }

    private String suffix() {
        return rolledBack ? " (rolled back)" : "";
    }

    public String describeAtBlock() {
        return body(true) + suffix();
    }

    public String describeForActor() {
        return body(false) + " at " + world + " " + x + " " + y + " " + z + suffix();
    }
}
