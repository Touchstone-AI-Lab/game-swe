import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Stateless planner that reconciles observed buildings with a desired layout. */
public final class LayoutReconciler {
    public enum Kind { REMOVE, ROTATE, PLACE }
    public record Cell(int x, int y, String block, int size, int rotation) {}
    public record Op(int seq, Kind kind, int x, int y, String block, int size, int rotation) {}
    public record Pricing(Map<String, Integer> cost, int refundPercent) {}
    public record Plan(List<Op> ops, List<Cell> deferred, int kept, int untouched, long spent, long refunded) {}
    public record Checkpoint(List<Op> ops, int next) {}

    private static final Comparator<Cell> ROW_ORDER =
        Comparator.comparingInt(Cell::y).thenComparingInt(Cell::x);
    private static final Comparator<Cell> PLACE_ORDER =
        Comparator.comparingInt((Cell cell) -> -cell.size()).thenComparing(ROW_ORDER);

    private final int width;
    private final int height;
    private final Map<String, Integer> cost;
    private final int refundPercent;

    public LayoutReconciler(int width, int height, Pricing pricing) {
        if (width < 1 || height < 1 || pricing == null || pricing.cost() == null
            || pricing.refundPercent() < 0 || pricing.refundPercent() > 100) {
            throw new IllegalArgumentException("invalid configuration");
        }
        Map<String, Integer> copy = new HashMap<>();
        for (Map.Entry<String, Integer> entry : pricing.cost().entrySet()) {
            if (blank(entry.getKey()) || entry.getValue() == null || entry.getValue() < 0) {
                throw new IllegalArgumentException("invalid cost");
            }
            copy.put(entry.getKey(), entry.getValue());
        }
        this.width = width;
        this.height = height;
        this.cost = copy;
        this.refundPercent = pricing.refundPercent();
    }

    public static int low(int origin, int size) {
        return origin - (size - 1) / 2;
    }

    public Plan plan(List<Cell> observed, List<Cell> desired, long budget) {
        validate(observed);
        validate(desired);
        if (budget < 0) throw new IllegalArgumentException("negative budget");
        for (Cell cell : observed) price(cell.block());
        for (Cell cell : desired) price(cell.block());

        Map<Long, Cell> byOrigin = new HashMap<>();
        for (Cell cell : observed) byOrigin.put(key(cell.x(), cell.y()), cell);

        List<Cell> rotations = new ArrayList<>();
        List<Cell> candidates = new ArrayList<>();
        List<Cell> matched = new ArrayList<>();
        int kept = 0;
        for (Cell wanted : desired) {
            Cell seen = byOrigin.get(key(wanted.x(), wanted.y()));
            if (seen != null && seen.block().equals(wanted.block()) && seen.size() == wanted.size()) {
                matched.add(seen);
                if (seen.rotation() == wanted.rotation()) kept++;
                else rotations.add(wanted);
            } else {
                candidates.add(wanted);
            }
        }

        List<Cell> removals = new ArrayList<>();
        int untouched = 0;
        for (Cell seen : observed) {
            if (matched.contains(seen)) continue;
            boolean conflict = false;
            for (Cell wanted : candidates) {
                if (overlaps(seen, wanted)) { conflict = true; break; }
            }
            if (conflict) removals.add(seen);
            else untouched++;
        }

        removals.sort(ROW_ORDER);
        rotations.sort(ROW_ORDER);
        candidates.sort(PLACE_ORDER);

        long refunded = 0;
        for (Cell cell : removals) refunded += (long) price(cell.block()) * refundPercent / 100;
        long funds = Math.addExact(budget, refunded);
        long spent = 0;

        List<Op> ops = new ArrayList<>();
        for (Cell cell : removals) ops.add(op(ops.size(), Kind.REMOVE, cell));
        for (Cell cell : rotations) ops.add(op(ops.size(), Kind.ROTATE, cell));
        List<Cell> deferred = new ArrayList<>();
        for (Cell cell : candidates) {
            long value = price(cell.block());
            if (value <= funds) {
                funds -= value;
                spent += value;
                ops.add(op(ops.size(), Kind.PLACE, cell));
            } else {
                deferred.add(cell);
            }
        }
        return new Plan(List.copyOf(ops), List.copyOf(deferred), kept, untouched, spent, refunded);
    }

    public List<Cell> applyTo(List<Cell> observed, List<Op> ops) {
        validate(observed);
        if (ops == null) throw new IllegalArgumentException("null operations");
        List<Cell> cells = new ArrayList<>(observed);
        for (Op op : ops) {
            if (op == null || op.kind() == null) throw new IllegalArgumentException("null operation");
            if (op.kind() == Kind.PLACE) {
                Cell cell = new Cell(op.x(), op.y(), op.block(), op.size(), op.rotation());
                if (!wellFormed(cell)) throw new IllegalStateException("placement out of bounds");
                for (Cell other : cells) {
                    if (overlaps(cell, other)) throw new IllegalStateException("placement is blocked");
                }
                cells.add(cell);
                continue;
            }
            int index = -1;
            for (int i = 0; i < cells.size(); i++) {
                Cell cell = cells.get(i);
                if (cell.x() == op.x() && cell.y() == op.y() && cell.size() == op.size()
                    && cell.block().equals(op.block())) {
                    index = i;
                    break;
                }
            }
            if (index < 0) throw new IllegalStateException("no such building");
            if (op.kind() == Kind.REMOVE) {
                cells.remove(index);
            } else {
                if (op.rotation() < 0 || op.rotation() > 3) throw new IllegalStateException("invalid rotation");
                cells.set(index, new Cell(op.x(), op.y(), op.block(), op.size(), op.rotation()));
            }
        }
        cells.sort(ROW_ORDER);
        return List.copyOf(cells);
    }

    public Checkpoint begin(Plan plan) {
        if (plan == null || plan.ops() == null) throw new IllegalArgumentException("null plan");
        return new Checkpoint(List.copyOf(plan.ops()), 0);
    }

    public Checkpoint advance(Checkpoint checkpoint, Op done) {
        if (checkpoint == null || checkpoint.ops() == null || checkpoint.next() < 0
            || checkpoint.next() > checkpoint.ops().size()) {
            throw new IllegalArgumentException("invalid checkpoint");
        }
        for (int i = 0; i < checkpoint.ops().size(); i++) {
            Op op = checkpoint.ops().get(i);
            if (op == null || op.seq() != i) throw new IllegalArgumentException("invalid checkpoint");
        }
        if (checkpoint.next() == checkpoint.ops().size()) throw new IllegalStateException("complete");
        if (!checkpoint.ops().get(checkpoint.next()).equals(done)) {
            throw new IllegalStateException("out of order");
        }
        return new Checkpoint(List.copyOf(checkpoint.ops()), checkpoint.next() + 1);
    }

    private void validate(List<Cell> cells) {
        if (cells == null) throw new IllegalArgumentException("null cells");
        for (Cell cell : cells) {
            if (cell == null || !wellFormed(cell)) throw new IllegalArgumentException("invalid cell");
        }
        for (int i = 0; i < cells.size(); i++) {
            for (int j = i + 1; j < cells.size(); j++) {
                if (overlaps(cells.get(i), cells.get(j))) throw new IllegalArgumentException("overlap");
            }
        }
    }

    private boolean wellFormed(Cell cell) {
        if (blank(cell.block()) || cell.size() < 1 || cell.size() > 8
            || cell.rotation() < 0 || cell.rotation() > 3) {
            return false;
        }
        long left = (long) cell.x() - (cell.size() - 1) / 2;
        long bottom = (long) cell.y() - (cell.size() - 1) / 2;
        return left >= 0 && bottom >= 0 && left + cell.size() <= width && bottom + cell.size() <= height;
    }

    private static boolean overlaps(Cell a, Cell b) {
        long al = (long) a.x() - (a.size() - 1) / 2;
        long ab = (long) a.y() - (a.size() - 1) / 2;
        long bl = (long) b.x() - (b.size() - 1) / 2;
        long bb = (long) b.y() - (b.size() - 1) / 2;
        return al < bl + b.size() && bl < al + a.size() && ab < bb + b.size() && bb < ab + a.size();
    }

    private int price(String block) {
        Integer value = cost.get(block);
        if (value == null) throw new IllegalArgumentException("no cost for " + block);
        return value;
    }

    private static Op op(int seq, Kind kind, Cell cell) {
        return new Op(seq, kind, cell.x(), cell.y(), cell.block(), cell.size(), cell.rotation());
    }

    private static long key(int x, int y) {
        return ((long) x << 32) ^ (y & 0xffffffffL);
    }

    private static boolean blank(String value) {
        return value == null || value.isBlank();
    }
}
