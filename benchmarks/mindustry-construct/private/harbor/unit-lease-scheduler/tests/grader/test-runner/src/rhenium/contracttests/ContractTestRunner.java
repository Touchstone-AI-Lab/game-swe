
import arc.Core;
import arc.Events;
import arc.util.Log;
import arc.util.Time;
import mindustry.Vars;
import mindustry.content.UnitTypes;
import mindustry.game.EventType.WorldLoadEvent;
import mindustry.game.Team;
import mindustry.gen.Groups;
import mindustry.gen.Unit;
import mindustry.mod.Plugin;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

public final class ContractTestRunner extends Plugin {
    private final AtomicBoolean finished = new AtomicBoolean();
    public ContractTestRunner() { Events.on(WorldLoadEvent.class, e -> Time.runTask(30f, this::run)); }

    private void run() {
        if (!finished.compareAndSet(false, true)) return;
        List<Case> cases = new ArrayList<>();
        check(cases, "deterministic assignment", this::assignment);
        check(cases, "duplicate and stale revision", this::deduplication);
        check(cases, "heartbeat timeout and reassignment", this::timeout);
        check(cases, "death and replacement", this::death);
        check(cases, "save reload determinism", this::reload);
        check(cases, "real mono lifecycle", this::realUnit);
        check(cases, "active plugin and real headless world", this::integration);
        finish(cases);
    }

    private LeaseScheduler scheduler() { return new LeaseScheduler(new LeaseScheduler.Policy(10, 5, 100)); }
    private LeaseScheduler.Task task(String id, LeaseScheduler.TaskKind kind, int priority, long tick) {
        return new LeaseScheduler.Task(id, kind, priority, tick, 10, "copper", 1);
    }

    private void assignment() {
        LeaseScheduler s = scheduler();
        s.upsertTask(task("low", LeaseScheduler.TaskKind.MINE, 1, 0));
        s.upsertTask(task("high", LeaseScheduler.TaskKind.MINE, 10, 0));
        s.registerUnit(new LeaseScheduler.UnitRecord(2, LeaseScheduler.UnitKind.MONO, 1, true, 1));
        Object report = s.tick(0);
        require(report != null, "tick returned null");
        require(s.snapshot(0).toString().contains("high"), "high-priority task disappeared");
        require(s.snapshot(0).equals(s.snapshot(0)), "snapshot is unstable");
    }

    private void deduplication() {
        LeaseScheduler s = scheduler();
        Object first = s.upsertTask(task("same", LeaseScheduler.TaskKind.REPAIR, 5, 0));
        Object retry = s.upsertTask(task("same", LeaseScheduler.TaskKind.REPAIR, 5, 0));
        require(first.equals(retry), "duplicate result changed");
        s.registerUnit(new LeaseScheduler.UnitRecord(3, LeaseScheduler.UnitKind.POLY, 1, true, 2));
        Object stale = s.registerUnit(new LeaseScheduler.UnitRecord(3, LeaseScheduler.UnitKind.POLY, 1, true, 1));
        require(stale != null, "stale revision returned null");
    }

    private void timeout() {
        LeaseScheduler s = scheduler();
        s.upsertTask(task("timeout", LeaseScheduler.TaskKind.MINE, 5, 0));
        s.registerUnit(new LeaseScheduler.UnitRecord(1, LeaseScheduler.UnitKind.MONO, 1, true, 1));
        s.tick(0);
        Object before = s.snapshot(0);
        s.tick(10);
        Object after = s.snapshot(10);
        require(before != null && after != null, "timeout corrupted snapshot");
        require(after.toString().contains("timeout"), "expired task was lost");
    }

    private void death() {
        LeaseScheduler s = scheduler();
        s.upsertTask(task("death", LeaseScheduler.TaskKind.REPAIR, 5, 0));
        s.registerUnit(new LeaseScheduler.UnitRecord(1, LeaseScheduler.UnitKind.POLY, 1, true, 1));
        s.registerUnit(new LeaseScheduler.UnitRecord(2, LeaseScheduler.UnitKind.POLY, 1, true, 1));
        s.tick(0);
        s.removeUnit(1, 1);
        s.tick(1);
        require(s.snapshot(1).toString().contains("death"), "unit death lost task");
        require(s.removeUnit(1, 2).equals(s.removeUnit(1, 2)), "death retry changed");
    }

    private void reload() {
        LeaseScheduler s = scheduler();
        s.upsertTask(task("saved", LeaseScheduler.TaskKind.TRANSPORT, 2, 0));
        s.registerUnit(new LeaseScheduler.UnitRecord(9, LeaseScheduler.UnitKind.MEGA, 1, true, 1));
        s.tick(0);
        LeaseScheduler loaded = new LeaseScheduler(new LeaseScheduler.Policy(10, 5, 100), s.save());
        require(s.snapshot(1).equals(loaded.snapshot(1)), "reload changed state");
        require(loaded.save().equals(loaded.save()), "saved state is unstable");
    }

    private void realUnit() {
        Unit unit = UnitTypes.mono.create(Team.sharded);
        unit.set(24f, 24f);
        unit.add();
        require(Groups.unit.getByID(unit.id()) == unit, "real mono was not added");
        LeaseScheduler s = scheduler();
        require(s.registerUnit(new LeaseScheduler.UnitRecord(unit.id(), LeaseScheduler.UnitKind.MONO, unit.team.id, true, 1)).accepted(),
            "real mono registration failed");
        s.upsertTask(task("real-mono-task", LeaseScheduler.TaskKind.MINE, 5, 0));
        s.tick(0);
        require(s.snapshot(0).leases().stream().anyMatch(x -> x.unitId() == unit.id()),
            "real mono was not assigned");
        unit.remove();
        s.removeUnit(unit.id(), 1);
        require(s.snapshot(1).units().stream().noneMatch(x -> x.unitId() == unit.id()),
            "removed mono remained registered");
    }

    private void integration() throws Exception {
        Class<?> type = Class.forName("UnitLeaseSchedulerPlugin");
        Object plugin = type.getMethod("instance").invoke(null);
        require(plugin != null, "instance is null");
        require(type.getMethod("scheduler").invoke(plugin) != null, "scheduler is null");
        require(Vars.world != null && Vars.state.isGame(), "headless world is inactive");
    }

    private static void check(List<Case> cases, String name, Checked body) {
        try { body.run(); cases.add(new Case(name, true, "ok")); }
        catch (Throwable e) { cases.add(new Case(name, false, e.toString())); }
    }
    private static void finish(List<Case> cases) {
        boolean passed = cases.stream().allMatch(Case::passed);
        StringBuilder out = new StringBuilder("{\"passed\":").append(passed).append(",\"cases\":[");
        for (int i = 0; i < cases.size(); i++) { if (i > 0) out.append(','); Case c = cases.get(i);
            out.append("{\"name\":\"").append(esc(c.name())).append("\",\"passed\":").append(c.passed())
                .append(",\"message\":\"").append(esc(c.message())).append("\"}"); }
        Log.info("MINDUSTRY_RESULT @", out.append("]}").toString()); Core.app.exit();
    }
    private static String esc(String s) { return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n"); }
    private static void require(boolean v, String m) { if (!v) throw new AssertionError(m); }
    private interface Checked { void run() throws Exception; }
    private record Case(String name, boolean passed, String message) {}
}
