import arc.Core;
import arc.Events;
import arc.util.Log;
import arc.util.Time;
import mindustry.Vars;
import mindustry.content.Blocks;
import mindustry.game.EventType.WorldLoadEvent;
import mindustry.game.Team;
import mindustry.gen.Building;
import mindustry.mod.Plugin;
import mindustry.world.Tile;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

public final class ContractTestRunner extends Plugin {
    private static final int AREA = 8;
    private final AtomicBoolean finished = new AtomicBoolean();
    private int ax;
    private int ay;

    public ContractTestRunner() {
        Events.on(WorldLoadEvent.class, event -> Time.runTask(30f, this::runChecks));
    }

    private void runChecks() {
        if (!finished.compareAndSet(false, true)) return;
        List<Case> cases = new ArrayList<>();
        check(cases, "footprints and validation", this::footprintsAndValidation);
        check(cases, "matching rotation and untouched cells", this::matching);
        check(cases, "conflict removal and ordering", this::conflictsAndOrdering);
        check(cases, "budget refund and deferral", this::budget);
        check(cases, "applyTo replay and convergence", this::replay);
        check(cases, "checkpoint ordering", this::checkpoints);
        check(cases, "world observation of real buildings", this::observeWorld);
        check(cases, "reconcile a real world region", this::reconcileWorld);
        check(cases, "apply rejects unsafe operations", this::rejectUnsafe);
        finish(cases);
    }

    // ---- pure core -------------------------------------------------------------------------

    private static LayoutReconciler.Pricing pricing(int refund) {
        Map<String, Integer> cost = new HashMap<>();
        cost.put("conveyor", 1);
        cost.put("sorter", 2);
        cost.put("router", 3);
        cost.put("container", 10);
        cost.put("vault", 25);
        return new LayoutReconciler.Pricing(cost, refund);
    }

    private static LayoutReconciler core(int refund) {
        return new LayoutReconciler(20, 20, pricing(refund));
    }

    private static LayoutReconciler.Cell cell(int x, int y, String block, int size, int rotation) {
        return new LayoutReconciler.Cell(x, y, block, size, rotation);
    }

    private static LayoutReconciler.Op op(int seq, LayoutReconciler.Kind kind, int x, int y, String block,
                                          int size, int rotation) {
        return new LayoutReconciler.Op(seq, kind, x, y, block, size, rotation);
    }

    private void footprintsAndValidation() {
        int[][] lows = {{5, 1, 5}, {5, 2, 5}, {5, 3, 4}, {5, 4, 4}, {5, 5, 3}, {5, 6, 3}, {0, 8, -3}, {7, 7, 4}};
        for (int[] row : lows) {
            require(LayoutReconciler.low(row[0], row[1]) == row[2], "low(" + row[0] + "," + row[1] + ")");
        }

        illegal("zero width", () -> new LayoutReconciler(0, 5, pricing(0)));
        illegal("zero height", () -> new LayoutReconciler(5, 0, pricing(0)));
        illegal("null pricing", () -> new LayoutReconciler(5, 5, null));
        illegal("null cost map", () -> new LayoutReconciler(5, 5, new LayoutReconciler.Pricing(null, 0)));
        illegal("refund above 100", () -> new LayoutReconciler(5, 5, pricing(101)));
        illegal("negative refund", () -> new LayoutReconciler(5, 5, pricing(-1)));
        Map<String, Integer> blank = new HashMap<>();
        blank.put(" ", 1);
        illegal("blank cost key", () -> new LayoutReconciler(5, 5, new LayoutReconciler.Pricing(blank, 0)));
        Map<String, Integer> negative = new HashMap<>();
        negative.put("router", -1);
        illegal("negative cost", () -> new LayoutReconciler(5, 5, new LayoutReconciler.Pricing(negative, 0)));
        Map<String, Integer> missing = new HashMap<>();
        missing.put("router", null);
        illegal("null cost", () -> new LayoutReconciler(5, 5, new LayoutReconciler.Pricing(missing, 0)));
        new LayoutReconciler(1, 1, pricing(0));
        new LayoutReconciler(5, 5, pricing(100));

        Map<String, Integer> shared = new HashMap<>();
        shared.put("router", 3);
        LayoutReconciler copied = new LayoutReconciler(10, 10, new LayoutReconciler.Pricing(shared, 0));
        shared.clear();
        require(copied.plan(List.of(), List.of(cell(1, 1, "router", 1, 0)), 3).ops().size() == 1,
            "cost map was not copied");

        LayoutReconciler core = core(0);
        List<LayoutReconciler.Cell> none = List.of();
        illegal("null observed", () -> core.plan(null, none, 0));
        illegal("null desired", () -> core.plan(none, null, 0));
        illegal("null cell", () -> core.plan(Arrays.asList((LayoutReconciler.Cell) null), none, 0));
        illegal("null block", () -> core.plan(none, List.of(cell(1, 1, null, 1, 0)), 0));
        illegal("blank block", () -> core.plan(none, List.of(cell(1, 1, "  ", 1, 0)), 0));
        illegal("size zero", () -> core.plan(none, List.of(cell(1, 1, "router", 0, 0)), 0));
        illegal("size nine", () -> core.plan(none, List.of(cell(9, 9, "router", 9, 0)), 0));
        illegal("rotation four", () -> core.plan(none, List.of(cell(1, 1, "router", 1, 4)), 0));
        illegal("negative rotation", () -> core.plan(List.of(cell(1, 1, "router", 1, -1)), none, 0));
        illegal("size three at the left edge", () -> core.plan(none, List.of(cell(0, 5, "vault", 3, 0)), 0));
        illegal("size two at the right edge", () -> core.plan(none, List.of(cell(19, 5, "container", 2, 0)), 0));
        illegal("size two at the top edge", () -> core.plan(List.of(cell(5, 19, "container", 2, 0)), none, 0));
        illegal("size four at the bottom edge", () -> core.plan(none, List.of(cell(5, 0, "vault", 4, 0)), 0));
        illegal("x beyond width", () -> core.plan(none, List.of(cell(20, 0, "router", 1, 0)), 0));
        illegal("negative y", () -> core.plan(none, List.of(cell(0, -1, "router", 1, 0)), 0));
        illegal("overlapping desired", () -> core.plan(none,
            List.of(cell(2, 2, "container", 2, 0), cell(3, 3, "router", 1, 0)), 100));
        illegal("overlapping observed", () -> core.plan(
            List.of(cell(6, 6, "vault", 3, 0), cell(5, 7, "router", 1, 0)), none, 100));
        illegal("negative budget", () -> core.plan(none, none, -1));
        illegal("observed block without a cost", () -> core.plan(List.of(cell(1, 1, "duo", 1, 0)), none, 0));
        illegal("desired block without a cost", () -> core.plan(none, List.of(cell(1, 1, "duo", 1, 0)), 0));
        illegal("applyTo null cells", () -> core.applyTo(null, List.of()));
        illegal("applyTo overlapping cells", () -> core.applyTo(
            List.of(cell(2, 2, "container", 2, 0), cell(3, 2, "router", 1, 0)), List.of()));

        // Footprints that only just fit are valid.
        List<LayoutReconciler.Cell> edge = List.of(
            cell(18, 18, "container", 2, 0), cell(1, 1, "vault", 3, 3), cell(1, 17, "vault", 4, 0),
            cell(0, 5, "container", 2, 0), cell(19, 0, "router", 1, 0));
        require(core.plan(edge, edge, 0).kept() == 5, "edge footprints were rejected");
        // Touching footprints do not overlap.
        List<LayoutReconciler.Cell> touching = List.of(cell(2, 2, "container", 2, 0), cell(4, 2, "router", 1, 0),
            cell(6, 3, "vault", 3, 0));
        require(core.plan(touching, touching, 0).kept() == 3, "touching footprints were rejected");

        List<LayoutReconciler.Cell> observed = new ArrayList<>(List.of(cell(3, 3, "router", 1, 0)));
        List<LayoutReconciler.Cell> desired = new ArrayList<>(List.of(cell(3, 3, "conveyor", 1, 0)));
        core.plan(observed, desired, 10);
        require(observed.equals(List.of(cell(3, 3, "router", 1, 0)))
            && desired.equals(List.of(cell(3, 3, "conveyor", 1, 0))), "plan modified its arguments");
    }

    private void matching() {
        LayoutReconciler core = core(50);
        List<LayoutReconciler.Cell> observed = List.of(
            cell(1, 1, "conveyor", 1, 0), cell(2, 1, "conveyor", 1, 1), cell(10, 10, "router", 1, 0),
            cell(15, 15, "container", 2, 0), cell(7, 3, "conveyor", 1, 2));
        List<LayoutReconciler.Cell> desired = List.of(
            cell(7, 3, "conveyor", 1, 0), cell(1, 1, "conveyor", 1, 0), cell(2, 1, "conveyor", 1, 3));
        LayoutReconciler.Plan plan = core.plan(observed, desired, 0);
        require(plan.ops().equals(List.of(
            op(0, LayoutReconciler.Kind.ROTATE, 2, 1, "conveyor", 1, 3),
            op(1, LayoutReconciler.Kind.ROTATE, 7, 3, "conveyor", 1, 0))), "rotation plan: " + plan.ops());
        require(plan.kept() == 1 && plan.untouched() == 2, "kept/untouched: " + plan);
        require(plan.spent() == 0 && plan.refunded() == 0 && plan.deferred().isEmpty(), "rotations are free");
        unsupported("ops", () -> plan.ops().add(op(9, LayoutReconciler.Kind.PLACE, 0, 0, "router", 1, 0)));
        unsupported("deferred", () -> plan.deferred().add(cell(0, 0, "router", 1, 0)));

        List<LayoutReconciler.Cell> shuffledObserved = new ArrayList<>(observed);
        Collections.reverse(shuffledObserved);
        List<LayoutReconciler.Cell> shuffledDesired = new ArrayList<>(desired);
        Collections.reverse(shuffledDesired);
        require(core.plan(shuffledObserved, shuffledDesired, 0).equals(plan), "plan depends on input order");

        // Same origin and block but another size is not a match.
        LayoutReconciler.Plan resized = core.plan(
            List.of(cell(8, 8, "vault", 3, 0)), List.of(cell(8, 8, "vault", 4, 0)), 100);
        require(resized.ops().equals(List.of(
            op(0, LayoutReconciler.Kind.REMOVE, 8, 8, "vault", 3, 0),
            op(1, LayoutReconciler.Kind.PLACE, 8, 8, "vault", 4, 0))), "size mismatch: " + resized.ops());
        require(resized.kept() == 0 && resized.untouched() == 0, "size mismatch counters");

        LayoutReconciler.Plan empty = core.plan(List.of(), List.of(), 0);
        require(empty.ops().isEmpty() && empty.deferred().isEmpty() && empty.kept() == 0
            && empty.untouched() == 0, "empty plan");
    }

    private static List<LayoutReconciler.Cell> conflictObserved() {
        return List.of(
            cell(5, 5, "router", 1, 0), cell(6, 6, "conveyor", 1, 2), cell(9, 9, "conveyor", 1, 0),
            cell(12, 3, "container", 2, 3), cell(3, 12, "router", 1, 1), cell(0, 0, "conveyor", 1, 0),
            cell(15, 1, "conveyor", 1, 0), cell(14, 0, "conveyor", 1, 1), cell(8, 6, "router", 1, 0));
    }

    private static List<LayoutReconciler.Cell> conflictDesired() {
        return List.of(
            cell(3, 12, "conveyor", 1, 1), cell(13, 4, "router", 1, 2), cell(6, 6, "vault", 3, 0),
            cell(9, 9, "conveyor", 1, 0), cell(15, 1, "conveyor", 1, 2), cell(14, 0, "conveyor", 1, 0));
    }

    private static List<LayoutReconciler.Op> conflictOps() {
        return List.of(
            op(0, LayoutReconciler.Kind.REMOVE, 12, 3, "container", 2, 3),
            op(1, LayoutReconciler.Kind.REMOVE, 5, 5, "router", 1, 0),
            op(2, LayoutReconciler.Kind.REMOVE, 6, 6, "conveyor", 1, 2),
            op(3, LayoutReconciler.Kind.REMOVE, 3, 12, "router", 1, 1),
            op(4, LayoutReconciler.Kind.ROTATE, 14, 0, "conveyor", 1, 0),
            op(5, LayoutReconciler.Kind.ROTATE, 15, 1, "conveyor", 1, 2),
            op(6, LayoutReconciler.Kind.PLACE, 6, 6, "vault", 3, 0),
            op(7, LayoutReconciler.Kind.PLACE, 13, 4, "router", 1, 2),
            op(8, LayoutReconciler.Kind.PLACE, 3, 12, "conveyor", 1, 1));
    }

    private void conflictsAndOrdering() {
        LayoutReconciler.Plan plan = core(50).plan(conflictObserved(), conflictDesired(), 1000);
        require(plan.ops().equals(conflictOps()), "ordered operations: " + plan.ops());
        // (8,6) touches the vault footprint 5..7 but does not share a tile with it.
        require(plan.kept() == 1 && plan.untouched() == 2, "kept/untouched: " + plan);
        require(plan.refunded() == 7 && plan.spent() == 29 && plan.deferred().isEmpty(), "accounting: " + plan);

        // Larger footprints are placed first, then rows, then columns.
        LayoutReconciler.Plan order = core(0).plan(List.of(), List.of(
            cell(9, 2, "router", 1, 0), cell(2, 9, "container", 2, 0), cell(10, 10, "vault", 3, 0),
            cell(1, 2, "router", 1, 0), cell(15, 1, "container", 2, 0), cell(5, 1, "conveyor", 1, 0)), 1000);
        List<String> seen = new ArrayList<>();
        for (LayoutReconciler.Op value : order.ops()) seen.add(value.seq() + ":" + value.x() + "," + value.y());
        require(seen.equals(List.of("0:10,10", "1:15,1", "2:2,9", "3:5,1", "4:1,2", "5:9,2")),
            "placement order: " + seen);
    }

    private void budget() {
        List<LayoutReconciler.Cell> observed = List.of(cell(4, 4, "container", 2, 0));
        List<LayoutReconciler.Cell> desired = List.of(
            cell(1, 9, "conveyor", 1, 0), cell(4, 4, "vault", 3, 0), cell(11, 1, "router", 1, 0),
            cell(0, 9, "conveyor", 1, 0), cell(10, 1, "router", 1, 0));
        LayoutReconciler.Plan plan = core(50).plan(observed, desired, 2);
        require(plan.ops().equals(List.of(
            op(0, LayoutReconciler.Kind.REMOVE, 4, 4, "container", 2, 0),
            op(1, LayoutReconciler.Kind.PLACE, 10, 1, "router", 1, 0),
            op(2, LayoutReconciler.Kind.PLACE, 11, 1, "router", 1, 0),
            op(3, LayoutReconciler.Kind.PLACE, 0, 9, "conveyor", 1, 0))), "partial budget: " + plan.ops());
        require(plan.deferred().equals(List.of(cell(4, 4, "vault", 3, 0), cell(1, 9, "conveyor", 1, 0))),
            "deferred: " + plan.deferred());
        require(plan.refunded() == 5 && plan.spent() == 7, "partial accounting: " + plan);

        // The refund makes an exact fit; a free block is placed with no funds left.
        LayoutReconciler.Plan exact = core(50).plan(observed,
            List.of(cell(4, 4, "vault", 3, 0), cell(9, 9, "conveyor", 1, 0)), 20);
        require(exact.spent() == 25 && exact.deferred().equals(List.of(cell(9, 9, "conveyor", 1, 0))),
            "exact fit: " + exact);
        Map<String, Integer> free = new HashMap<>();
        free.put("sorter", 0);
        free.put("router", 3);
        LayoutReconciler.Plan zero = new LayoutReconciler(20, 20, new LayoutReconciler.Pricing(free, 0))
            .plan(List.of(), List.of(cell(1, 1, "router", 1, 0), cell(2, 2, "sorter", 1, 0)), 0);
        require(zero.ops().equals(List.of(op(0, LayoutReconciler.Kind.PLACE, 2, 2, "sorter", 1, 0)))
            && zero.deferred().equals(List.of(cell(1, 1, "router", 1, 0))), "free block: " + zero);

        // Refunds round down per removal, not on the sum.
        LayoutReconciler.Plan rounded = core(33).plan(
            List.of(cell(4, 4, "container", 2, 0), cell(8, 8, "router", 1, 0), cell(14, 14, "router", 1, 0)),
            List.of(cell(4, 4, "vault", 3, 0), cell(8, 8, "vault", 3, 0), cell(14, 14, "sorter", 1, 0)), 0);
        require(rounded.refunded() == 3 && rounded.spent() == 2, "refund rounding: " + rounded);
        require(rounded.deferred().equals(List.of(cell(4, 4, "vault", 3, 0), cell(8, 8, "vault", 3, 0))),
            "removals stand when the placement is deferred: " + rounded);
        require(rounded.ops().size() == 4 && rounded.ops().get(2).kind() == LayoutReconciler.Kind.REMOVE
            && rounded.ops().get(3).equals(op(3, LayoutReconciler.Kind.PLACE, 14, 14, "sorter", 1, 0)),
            "refund funds a later placement: " + rounded.ops());
        require(core(0).plan(List.of(cell(4, 4, "container", 2, 0)), List.of(cell(4, 4, "vault", 3, 0)), 24)
            .refunded() == 0, "refund percent zero");

        Map<String, Integer> huge = new HashMap<>();
        huge.put("vault", Integer.MAX_VALUE);
        huge.put("router", 1);
        LayoutReconciler.Plan wide = new LayoutReconciler(20, 20, new LayoutReconciler.Pricing(huge, 100)).plan(
            List.of(cell(2, 2, "vault", 3, 0), cell(8, 2, "vault", 3, 0)),
            List.of(cell(2, 2, "router", 1, 0), cell(8, 2, "router", 1, 0), cell(15, 15, "vault", 3, 0)),
            5L * Integer.MAX_VALUE);
        require(wide.refunded() == 2L * Integer.MAX_VALUE && wide.spent() == Integer.MAX_VALUE + 2L
            && wide.deferred().isEmpty(), "long accounting: " + wide);
    }

    private void replay() {
        LayoutReconciler core = core(50);
        List<LayoutReconciler.Cell> observed = new ArrayList<>(conflictObserved());
        LayoutReconciler.Plan plan = core.plan(observed, conflictDesired(), 1000);
        List<LayoutReconciler.Cell> result = core.applyTo(observed, plan.ops());
        require(observed.equals(conflictObserved()), "applyTo modified its argument");
        require(result.equals(List.of(
            cell(0, 0, "conveyor", 1, 0), cell(14, 0, "conveyor", 1, 0), cell(15, 1, "conveyor", 1, 2),
            cell(13, 4, "router", 1, 2), cell(6, 6, "vault", 3, 0), cell(8, 6, "router", 1, 0),
            cell(9, 9, "conveyor", 1, 0), cell(3, 12, "conveyor", 1, 1))), "replayed layout: " + result);
        unsupported("applyTo result", () -> result.add(cell(19, 19, "router", 1, 0)));
        LayoutReconciler.Plan again = core.plan(result, conflictDesired(), 0);
        require(again.ops().isEmpty() && again.kept() == 6 && again.untouched() == 2, "converged: " + again);

        // With deferred placements the replay still leaves nothing to remove or rotate.
        List<LayoutReconciler.Cell> small = List.of(cell(4, 4, "container", 2, 0), cell(1, 1, "conveyor", 1, 0));
        List<LayoutReconciler.Cell> wanted = List.of(cell(4, 4, "vault", 3, 0), cell(1, 1, "conveyor", 1, 2));
        LayoutReconciler.Plan partial = core.plan(small, wanted, 0);
        List<LayoutReconciler.Cell> after = core.applyTo(small, partial.ops());
        require(after.equals(List.of(cell(1, 1, "conveyor", 1, 2))), "partial replay: " + after);
        LayoutReconciler.Plan second = core.plan(after, wanted, 0);
        require(second.ops().isEmpty() && second.deferred().equals(List.of(cell(4, 4, "vault", 3, 0))),
            "partial convergence: " + second);

        illegal("null operations", () -> core.applyTo(small, null));
        illegal("null operation", () -> core.applyTo(small, Arrays.asList((LayoutReconciler.Op) null)));
        state("remove absent", () -> core.applyTo(small,
            List.of(op(0, LayoutReconciler.Kind.REMOVE, 9, 9, "router", 1, 0))));
        state("remove another block", () -> core.applyTo(small,
            List.of(op(0, LayoutReconciler.Kind.REMOVE, 1, 1, "router", 1, 0))));
        state("rotate absent", () -> core.applyTo(small,
            List.of(op(0, LayoutReconciler.Kind.ROTATE, 2, 1, "conveyor", 1, 1))));
        state("place on a footprint", () -> core.applyTo(small,
            List.of(op(0, LayoutReconciler.Kind.PLACE, 5, 5, "router", 1, 0))));
        state("place out of bounds", () -> core.applyTo(small,
            List.of(op(0, LayoutReconciler.Kind.PLACE, 19, 19, "container", 2, 0))));
        // Operations apply in order: the removal frees the footprint for the placement.
        require(core.applyTo(small, List.of(
            op(0, LayoutReconciler.Kind.REMOVE, 4, 4, "container", 2, 0),
            op(1, LayoutReconciler.Kind.PLACE, 5, 5, "router", 1, 3))).equals(
            List.of(cell(1, 1, "conveyor", 1, 0), cell(5, 5, "router", 1, 3))), "sequential replay");
    }

    private void checkpoints() {
        LayoutReconciler core = core(50);
        LayoutReconciler.Plan plan = core.plan(conflictObserved(), conflictDesired(), 1000);
        LayoutReconciler.Checkpoint start = core.begin(plan);
        require(start.ops().equals(plan.ops()) && start.next() == 0, "begin: " + start);
        illegal("begin null", () -> core.begin(null));
        LayoutReconciler.Checkpoint current = start;
        for (int i = 0; i < plan.ops().size(); i++) {
            LayoutReconciler.Op wrong = plan.ops().get((i + 1) % plan.ops().size());
            LayoutReconciler.Checkpoint at = current;
            state("out of order at " + i, () -> core.advance(at, wrong));
            state("null done at " + i, () -> core.advance(at, null));
            LayoutReconciler.Checkpoint next = core.advance(current, plan.ops().get(i));
            require(next.next() == i + 1 && next.ops().equals(plan.ops()), "advance " + i);
            require(current.next() == i, "advance changed its argument");
            current = next;
        }
        LayoutReconciler.Checkpoint done = current;
        state("advance past the end", () -> core.advance(done, plan.ops().get(0)));
        illegal("null checkpoint", () -> core.advance(null, plan.ops().get(0)));
        illegal("null operations", () -> core.advance(new LayoutReconciler.Checkpoint(null, 0), plan.ops().get(0)));
        illegal("negative next", () -> core.advance(
            new LayoutReconciler.Checkpoint(plan.ops(), -1), plan.ops().get(0)));
        illegal("next beyond the end", () -> core.advance(
            new LayoutReconciler.Checkpoint(plan.ops(), plan.ops().size() + 1), plan.ops().get(0)));
        List<LayoutReconciler.Op> gap = List.of(plan.ops().get(1), plan.ops().get(2));
        illegal("sequence does not start at zero", () -> core.advance(
            new LayoutReconciler.Checkpoint(gap, 0), gap.get(0)));
        List<LayoutReconciler.Op> swapped = List.of(plan.ops().get(0), plan.ops().get(2), plan.ops().get(1));
        illegal("sequence out of order", () -> core.advance(
            new LayoutReconciler.Checkpoint(swapped, 0), swapped.get(0)));
        // A complete but malformed checkpoint is malformed first.
        illegal("malformed complete checkpoint", () -> core.advance(
            new LayoutReconciler.Checkpoint(gap, 2), gap.get(0)));
        LayoutReconciler.Checkpoint empty = core.begin(core.plan(List.of(), List.of(), 0));
        state("empty plan is complete", () -> core.advance(empty, plan.ops().get(0)));
    }

    // ---- real world ------------------------------------------------------------------------

    private BlueprintReconcilerPlugin plugin() {
        BlueprintReconcilerPlugin plugin = BlueprintReconcilerPlugin.instance();
        require(plugin != null, "plugin instance is null");
        require(Vars.world != null && Vars.state.isGame(), "headless world is inactive");
        return plugin;
    }

    /** Finds once, then clears, an AREA x AREA square of plain air tiles. */
    private void area() {
        if (ax == 0 && ay == 0) {
            search:
            for (int y = 4; y + AREA + 4 < Vars.world.height(); y++) {
                for (int x = 4; x + AREA + 4 < Vars.world.width(); x++) {
                    if (free(x - 2, y - 2, AREA + 4)) {
                        ax = x;
                        ay = y;
                        break search;
                    }
                }
            }
            require(ax != 0, "the map has no free square for the world cases");
        }
        for (int dy = 0; dy < AREA; dy++) {
            for (int dx = 0; dx < AREA; dx++) {
                Tile tile = Vars.world.tile(ax + dx, ay + dy);
                if (tile.build != null) tile.build.tile.setAir();
            }
        }
        require(free(ax, ay, AREA), "the test square could not be cleared");
    }

    private static boolean free(int x, int y, int side) {
        for (int dy = 0; dy < side; dy++) {
            for (int dx = 0; dx < side; dx++) {
                Tile tile = Vars.world.tile(x + dx, y + dy);
                if (tile == null || tile.build != null || tile.block() != Blocks.air) return false;
            }
        }
        return true;
    }

    private static Building at(int x, int y) {
        return Vars.world.tile(x, y).build;
    }

    private void observeWorld() {
        BlueprintReconcilerPlugin plugin = plugin();
        area();
        require(Blocks.container.size == 2 && Blocks.vault.size == 3, "unexpected block sizes in this build");
        Vars.world.tile(ax, ay).setBlock(Blocks.conveyor, Team.sharded, 1);
        Vars.world.tile(ax + 3, ay + 3).setBlock(Blocks.container, Team.sharded, 0);
        Vars.world.tile(ax + 6, ay + 1).setBlock(Blocks.vault, Team.crux, 0);
        LayoutReconciler.Cell conveyor = cell(ax, ay, "conveyor", 1, 1);
        LayoutReconciler.Cell container = cell(ax + 3, ay + 3, "container", 2, 0);
        LayoutReconciler.Cell vault = cell(ax + 6, ay + 1, "vault", 3, 0);

        List<LayoutReconciler.Cell> all = plugin.observe(ax, ay, ax + AREA - 1, ay + AREA - 1);
        require(all.equals(List.of(conveyor, vault, container)), "observed region: " + all);
        unsupported("observe result", () -> all.add(conveyor));
        require(plugin.observe(ax + 4, ay + 4, ax + 4, ay + 4).equals(List.of(container)),
            "a building is observed through a tile that is not its origin");
        require(plugin.observe(ax + 5, ay, ax + 5, ay).equals(List.of(vault)),
            "a size-3 building is observed through its corner tile");
        require(plugin.observe(ax + 5, ay, ax + 7, ay + 2).equals(List.of(vault)),
            "a building that covers several tiles is observed once");
        require(plugin.observe(ax + 1, ay + 1, ax + 2, ay + 2).isEmpty(), "empty tiles produced cells");
        require(plugin.observe(ax + 4, ay, ax + 4, ay + 2).isEmpty(), "the column beside the vault is empty");
        require(plugin.observe(ax, ay, ax, ay).equals(List.of(conveyor)), "single tile rectangle");
        illegal("x0 > x1", () -> plugin.observe(ax + 1, ay, ax, ay));
        illegal("y0 > y1", () -> plugin.observe(ax, ay + 1, ax, ay));
        require(plugin.observe(-50, ay, ax, ay).contains(conveyor), "rectangle left of the world");
        List<LayoutReconciler.Cell> whole = plugin.observe(-1000, -1000, 100000, 100000);
        require(whole.containsAll(all), "rectangle larger than the world");
        for (int i = 1; i < whole.size(); i++) {
            LayoutReconciler.Cell a = whole.get(i - 1);
            LayoutReconciler.Cell b = whole.get(i);
            require(a.y() < b.y() || (a.y() == b.y() && a.x() < b.x()), "world cells are not ordered or repeat");
        }

        LayoutReconciler core = plugin.core(pricing(0));
        int w = Vars.world.width();
        int h = Vars.world.height();
        require(core.plan(List.of(), List.of(cell(w - 1, h - 1, "conveyor", 1, 0)), 5).ops().size() == 1,
            "core does not cover the whole world");
        illegal("core wider than the world", () -> core.plan(List.of(), List.of(cell(w, 0, "conveyor", 1, 0)), 5));
        illegal("core taller than the world", () -> core.plan(List.of(), List.of(cell(0, h, "conveyor", 1, 0)), 5));
    }

    @SuppressWarnings("unchecked")
    private static List<LayoutReconciler.Op> exported(BlueprintReconcilerPlugin plugin) {
        Object state = plugin.exportState();
        require(state instanceof List, "exportState is not a list");
        return (List<LayoutReconciler.Op>) state;
    }

    private void reconcileWorld() {
        BlueprintReconcilerPlugin plugin = plugin();
        area();
        Vars.world.tile(ax, ay).setBlock(Blocks.conveyor, Team.sharded, 0);
        Vars.world.tile(ax + 3, ay + 3).setBlock(Blocks.container, Team.sharded, 0);
        Vars.world.tile(ax + 7, ay + 7).setBlock(Blocks.router, Team.sharded, 0);
        List<LayoutReconciler.Cell> desired = List.of(
            cell(ax + 1, ay + 6, "sorter", 1, 0), cell(ax, ay, "conveyor", 1, 1),
            cell(ax + 6, ay, "router", 1, 0), cell(ax + 4, ay + 4, "vault", 3, 0));
        LayoutReconciler core = plugin.core(pricing(50));
        List<LayoutReconciler.Cell> observed = plugin.observe(ax, ay, ax + AREA - 1, ay + AREA - 1);
        LayoutReconciler.Plan plan = core.plan(observed, desired, 28);
        require(plan.ops().equals(List.of(
            op(0, LayoutReconciler.Kind.REMOVE, ax + 3, ay + 3, "container", 2, 0),
            op(1, LayoutReconciler.Kind.ROTATE, ax, ay, "conveyor", 1, 1),
            op(2, LayoutReconciler.Kind.PLACE, ax + 4, ay + 4, "vault", 3, 0),
            op(3, LayoutReconciler.Kind.PLACE, ax + 6, ay, "router", 1, 0),
            op(4, LayoutReconciler.Kind.PLACE, ax + 1, ay + 6, "sorter", 1, 0))), "world plan: " + plan.ops());
        require(plan.untouched() == 1 && plan.deferred().isEmpty(), "world plan counters: " + plan);

        int before = exported(plugin).size();
        require(plugin.apply(plan.ops().get(0), Team.sharded), "remove was rejected");
        require(free(ax + 3, ay + 3, 2), "the removed footprint still holds a building");
        require(plugin.apply(plan.ops().get(1), Team.sharded), "rotate was rejected");
        require(at(ax, ay) != null && at(ax, ay).block == Blocks.conveyor && at(ax, ay).rotation == 1,
            "the conveyor was not rotated");
        require(plugin.apply(plan.ops().get(2), Team.sharded), "vault placement was rejected");
        Building vault = at(ax + 4, ay + 4);
        require(vault != null && vault.block == Blocks.vault && vault.tile == Vars.world.tile(ax + 4, ay + 4)
            && vault.team == Team.sharded, "the vault does not stand at its origin");
        for (int dy = 0; dy < 3; dy++) {
            for (int dx = 0; dx < 3; dx++) require(at(ax + 3 + dx, ay + 3 + dy) == vault, "vault footprint");
        }
        require(plugin.apply(plan.ops().get(3), Team.crux), "router placement was rejected");
        require(at(ax + 6, ay) != null && at(ax + 6, ay).block == Blocks.router && at(ax + 6, ay).team == Team.crux,
            "the router was not placed for the requested team");
        require(plugin.apply(plan.ops().get(4), Team.sharded), "sorter placement was rejected");
        require(at(ax + 1, ay + 6) != null && at(ax + 1, ay + 6).block == Blocks.sorter, "the sorter is missing");
        require(at(ax + 7, ay + 7) != null && at(ax + 7, ay + 7).block == Blocks.router, "untouched router is gone");

        List<LayoutReconciler.Cell> result = plugin.observe(ax, ay, ax + AREA - 1, ay + AREA - 1);
        require(result.equals(core.applyTo(observed, plan.ops())), "world and replay disagree: " + result);
        require(core.plan(result, desired, 0).ops().isEmpty(), "the world did not converge");
        List<LayoutReconciler.Op> state = exported(plugin);
        require(state.size() == before + 5 && state.subList(before, state.size()).equals(plan.ops()),
            "exportState does not list the applied operations: " + state);
        unsupported("exportState", () -> state.add(plan.ops().get(0)));
    }

    private void rejectUnsafe() {
        BlueprintReconcilerPlugin plugin = plugin();
        area();
        Vars.world.tile(ax + 2, ay + 2).setBlock(Blocks.router, Team.sharded, 0);
        Vars.world.tile(ax + 5, ay + 5).setBlock(Blocks.container, Team.sharded, 0);
        Building router = at(ax + 2, ay + 2);
        Building container = at(ax + 5, ay + 5);
        int before = exported(plugin).size();
        LayoutReconciler.Kind place = LayoutReconciler.Kind.PLACE;
        LayoutReconciler.Kind remove = LayoutReconciler.Kind.REMOVE;
        LayoutReconciler.Kind rotate = LayoutReconciler.Kind.ROTATE;

        require(!plugin.apply(null, Team.sharded), "null operation accepted");
        require(!plugin.apply(op(0, place, ax, ay, "conveyor", 1, 0), null), "null team accepted");
        require(at(ax, ay) == null, "null team placed a building");
        require(!plugin.apply(op(0, place, ax + 2, ay + 2, "conveyor", 1, 0), Team.sharded), "placed on a building");
        require(at(ax + 2, ay + 2) == router, "the occupied tile was replaced");
        require(!plugin.apply(op(0, place, ax + 4, ay + 4, "vault", 3, 0), Team.sharded),
            "placed over part of another footprint");
        require(at(ax + 5, ay + 5) == container && at(ax + 6, ay + 6) == container && at(ax + 4, ay + 4) == null
            && at(ax + 3, ay + 3) == null, "a rejected placement changed the world");
        require(!plugin.apply(op(0, place, ax, ay, "no-such-block", 1, 0), Team.sharded), "unknown block accepted");
        require(!plugin.apply(op(0, place, ax, ay + 4, "container", 3, 0), Team.sharded), "wrong size accepted");
        require(!plugin.apply(op(0, place, ax, ay + 4, "vault", 1, 0), Team.sharded), "wrong size accepted");
        require(at(ax, ay + 4) == null && at(ax, ay) == null, "a rejected placement left a building");
        require(!plugin.apply(op(0, place, -1, ay, "router", 1, 0), Team.sharded), "placed outside the world");
        require(!plugin.apply(op(0, place, Vars.world.width(), ay, "router", 1, 0), Team.sharded),
            "placed outside the world");
        Tile wall = null;
        for (Tile tile : Vars.world.tiles) {
            if (tile.build == null && tile.block() != Blocks.air) {
                wall = tile;
                break;
            }
        }
        if (wall != null) {
            require(!plugin.apply(op(0, place, wall.x, wall.y, "router", 1, 0), Team.sharded),
                "placed on a tile that is not air");
            require(wall.build == null && wall.block() != Blocks.router, "a wall tile was replaced");
        }
        require(!plugin.apply(op(0, remove, ax + 2, ay + 2, "conveyor", 1, 0), Team.sharded),
            "removed a building of another block");
        require(!plugin.apply(op(0, remove, ax + 6, ay + 6, "container", 2, 0), Team.sharded),
            "removed through a tile that is not the origin");
        require(!plugin.apply(op(0, remove, ax, ay, "router", 1, 0), Team.sharded), "removed nothing");
        require(!plugin.apply(op(0, rotate, ax, ay, "router", 1, 1), Team.sharded), "rotated nothing");
        require(!plugin.apply(op(0, rotate, ax + 2, ay + 2, "sorter", 1, 1), Team.sharded),
            "rotated a building of another block");
        require(at(ax + 2, ay + 2) == router && at(ax + 5, ay + 5) == container && at(ax + 6, ay + 6) == container,
            "a rejected operation changed the world");
        require(exported(plugin).size() == before, "rejected operations were recorded");

        LayoutReconciler.Op valid = op(7, remove, ax + 2, ay + 2, "router", 1, 0);
        require(plugin.apply(valid, Team.sharded), "valid removal rejected");
        require(at(ax + 2, ay + 2) == null, "valid removal left the building");
        List<LayoutReconciler.Op> state = exported(plugin);
        require(state.size() == before + 1 && state.get(before).equals(valid), "valid operation was not recorded");
        area();
    }

    // ---- harness ---------------------------------------------------------------------------

    private static void illegal(String label, Checked body) {
        expect(label, body, IllegalArgumentException.class);
    }

    private static void state(String label, Checked body) {
        expect(label, body, IllegalStateException.class);
    }

    private static void unsupported(String label, Checked body) {
        expect(label + " is mutable", body, UnsupportedOperationException.class);
    }

    private static void expect(String label, Checked body, Class<? extends Throwable> type) {
        try {
            body.run();
        } catch (Throwable error) {
            if (type.isInstance(error)) return;
            throw new AssertionError(label + ": expected " + type.getSimpleName() + ", got " + error);
        }
        throw new AssertionError(label + ": expected " + type.getSimpleName());
    }

    private static void check(List<Case> cases, String name, Checked body) {
        try {
            body.run();
            cases.add(new Case(name, true, "ok"));
        } catch (Throwable error) {
            cases.add(new Case(name, false, error.toString()));
        }
    }

    private static void finish(List<Case> cases) {
        boolean passed = cases.stream().allMatch(Case::passed);
        StringBuilder out = new StringBuilder("{\"passed\":").append(passed).append(",\"cases\":[");
        for (int i = 0; i < cases.size(); i++) {
            if (i > 0) out.append(',');
            Case value = cases.get(i);
            out.append("{\"name\":\"").append(escape(value.name())).append("\",\"passed\":")
                .append(value.passed()).append(",\"message\":\"").append(escape(value.message())).append("\"}");
        }
        Log.info("MINDUSTRY_RESULT @", out.append("]}").toString());
        Core.app.exit();
    }

    private static String escape(String value) {
        StringBuilder out = new StringBuilder();
        for (char c : value.toCharArray()) {
            if (c == '\\' || c == '"') out.append('\\').append(c);
            else if (c < 0x20) out.append(' ');
            else out.append(c);
        }
        return out.toString();
    }

    private static void require(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }

    private interface Checked {
        void run() throws Exception;
    }

    private record Case(String name, boolean passed, String message) {}
}
