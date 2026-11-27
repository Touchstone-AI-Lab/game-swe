package com.example.blocktrail;

import java.util.regex.Pattern;
import org.bukkit.Bukkit;

/** One recorded block change. Everything except the rolled-back mark is immutable. */
final class Change {

    private static final Pattern POSITIVE = Pattern.compile("[0-9]+");
    private static final Pattern WHOLE = Pattern.compile("-?[0-9]+");

    private final long id;
    private final long time;
    private final String actor;
    private final ChangeAction action;
    private final String world;
    private final int x;
    private final int y;
    private final int z;
    private final String from;
    private final String to;
    private final String fromData;
    private final String toData;
    private boolean rolledBack;

    Change(long id, long time, String actor, ChangeAction action, String world,
           int x, int y, int z, String from, String to, String fromData, String toData) {
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

    long id() {
        return id;
    }

    long time() {
        return time;
    }

    String actor() {
        return actor;
    }

    String world() {
        return world;
    }

    int x() {
        return x;
    }

    int y() {
        return y;
    }

    int z() {
        return z;
    }

    String from() {
        return from;
    }

    String to() {
        return to;
    }

    String fromData() {
        return fromData;
    }

    String toData() {
        return toData;
    }

    boolean rolledBack() {
        return rolledBack;
    }

    void markRolledBack() {
        rolledBack = true;
    }

    boolean isAt(String worldName, int bx, int by, int bz) {
        return world.equalsIgnoreCase(worldName) && x == bx && y == by && z == bz;
    }

    /** Twelve fields for full block states; legacy entries retain their ten-field format. */
    String toLogLine() {
        return id + ";" + time + ";" + actor + ";" + action.key() + ";" + world + ";"
                + x + ";" + y + ";" + z + ";" + from + ";" + to
                + (fromData == null ? "" : ";" + fromData + ";" + toData);
    }

    String toUndoLine() {
        return "undo;" + id;
    }

    /** For example {@code #7 Alice placed oak_planks over air (rolled back)}. */
    String describe() {
        return "#" + id + " " + actor + " " + what() + suffix();
    }

    /** For example {@code #12 broke stone at world 10 -59 4 (rolled back)}. */
    String describeWithoutActor() {
        return "#" + id + " " + what() + " at " + world + " " + x + " " + y + " " + z + suffix();
    }

    private String what() {
        if (action == ChangeAction.PLACE) {
            return action.verb() + " " + to + " over " + from;
        }
        return action.verb() + " " + from;
    }

    private String suffix() {
        return rolledBack ? " (rolled back)" : "";
    }

    /** Parses a change line of the log, or returns {@code null} when it is malformed. */
    static Change parse(String line) {
        String[] f = line.split(";", -1);
        if (f.length != 10 && f.length != 12) {
            return null;
        }
        try {
            if (!POSITIVE.matcher(f[0]).matches() || !WHOLE.matcher(f[1]).matches()) {
                return null;
            }
            long id = Long.parseLong(f[0]);
            long time = Long.parseLong(f[1]);
            String actor = f[2];
            ChangeAction action = ChangeAction.fromKey(f[3]);
            String world = f[4];
            if (id < 1 || actor.isEmpty() || action == null || world.isEmpty()) {
                return null;
            }
            if (!WHOLE.matcher(f[5]).matches() || !WHOLE.matcher(f[6]).matches()
                    || !WHOLE.matcher(f[7]).matches()) {
                return null;
            }
            int x = Integer.parseInt(f[5]);
            int y = Integer.parseInt(f[6]);
            int z = Integer.parseInt(f[7]);
            var from = Materials.fromKey(f[8]);
            var to = Materials.fromKey(f[9]);
            if (from == null || to == null) {
                return null;
            }
            String fromData = null;
            String toData = null;
            if (f.length == 12) {
                var before = Bukkit.createBlockData(f[10]);
                var after = Bukkit.createBlockData(f[11]);
                if (before.getMaterial() != from || after.getMaterial() != to) {
                    return null;
                }
                fromData = before.getAsString();
                toData = after.getAsString();
            }
            return new Change(id, time, actor, action, world, x, y, z,
                    Materials.key(from), Materials.key(to), fromData, toData);
        } catch (IllegalArgumentException e) {
            return null;
        }
    }

    /** Parses an {@code undo;<id>} line, or returns {@code null} when it is not one. */
    static Long parseUndoId(String line) {
        String[] f = line.split(";", -1);
        if (f.length != 2 || !f[0].equals("undo") || !POSITIVE.matcher(f[1]).matches()) {
            return null;
        }
        try {
            return Long.parseLong(f[1]);
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
