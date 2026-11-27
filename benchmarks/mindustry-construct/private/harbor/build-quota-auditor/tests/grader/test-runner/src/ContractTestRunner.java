
import arc.Core;
import arc.Events;
import arc.util.Log;
import arc.util.Time;
import mindustry.Vars;
import mindustry.content.Blocks;
import mindustry.game.EventType.WorldLoadEvent;
import mindustry.game.Team;
import mindustry.world.Tile;
import mindustry.mod.Plugin;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

public final class ContractTestRunner extends Plugin {
    private final AtomicBoolean finished = new AtomicBoolean();

    public ContractTestRunner() {
        Events.on(WorldLoadEvent.class, event -> Time.runTask(30f, this::runChecks));
    }

    private void runChecks() {
        if (!finished.compareAndSet(false, true)) return;
        List<Case> cases = new ArrayList<>();
        check(cases, "reserve commit and quota", this::reserveCommitQuota);
        check(cases, "duplicate is idempotent", this::duplicate);
        check(cases, "cancel and offline release reservations", this::cancelOffline);
        check(cases, "single exact removal refund", this::removalRefund);
        check(cases, "rolling window boundary", this::windowBoundary);
        check(cases, "save reload preserves accounting", this::reload);
        check(cases, "real building identity and accounting", this::realBuilding);
        check(cases, "active plugin and headless world", this::integration);
        finish(cases);
    }

    private BuildQuotaEngine.Policy policy() {
        return new BuildQuotaEngine.Policy(100, Map.of("router", 1), Map.of("router", 2));
    }

    private BuildQuotaEngine.BuildIntent intent(String id, String player, int tile, long tick) {
        return new BuildQuotaEngine.BuildIntent(id, player, 1, "router", tile, tick);
    }

    private void reserveCommitQuota() {
        BuildQuotaEngine engine = new BuildQuotaEngine(policy());
        require(engine.begin(intent("a", "p1", 10, 0)).accepted(), "first begin rejected");
        require(engine.finish("a").accepted(), "finish rejected");
        require(!engine.begin(intent("b", "p1", 11, 1)).accepted(), "player quota bypassed");
        require(engine.begin(intent("c", "p2", 12, 1)).accepted(), "team capacity incorrectly rejected");
        require(!engine.begin(intent("d", "p3", 13, 1)).accepted(), "team quota bypassed");
    }

    private void duplicate() {
        BuildQuotaEngine engine = new BuildQuotaEngine(policy());
        var first = engine.begin(intent("same", "p1", 10, 0));
        var second = engine.begin(intent("same", "p2", 99, 50));
        require(first.equals(second), "duplicate result changed");
        require(engine.snapshot(50).equals(engine.snapshot(50)), "snapshot is unstable");
    }

    private void cancelOffline() {
        BuildQuotaEngine engine = new BuildQuotaEngine(policy());
        engine.begin(intent("cancel", "p1", 10, 0));
        require(engine.cancel("cancel").accepted(), "cancel failed");
        require(engine.begin(intent("replacement", "p1", 11, 1)).accepted(), "cancel did not release");
        engine.playerOffline("p1");
        require(engine.begin(intent("after-offline", "p1", 12, 2)).accepted(), "offline did not release");
    }

    private void removalRefund() {
        BuildQuotaEngine engine = new BuildQuotaEngine(policy());
        engine.begin(intent("built", "p1", 10, 0));
        engine.finish("built");
        var removal = new BuildQuotaEngine.Removal("remove-1", 1, "router", 10, 1);
        require(engine.remove(removal).accepted(), "valid removal rejected");
        require(engine.remove(removal).equals(engine.remove(removal)), "removal retry changed");
        require(engine.begin(intent("again", "p1", 11, 2)).accepted(), "refund did not restore quota");
    }

    private void windowBoundary() {
        BuildQuotaEngine engine = new BuildQuotaEngine(policy());
        engine.begin(intent("old", "p1", 10, 0));
        engine.finish("old");
        require(!engine.begin(intent("early", "p1", 11, 99)).accepted(), "usage expired early");
        require(engine.begin(intent("boundary", "p1", 12, 100)).accepted(), "usage did not expire at boundary");
    }

    private void reload() {
        BuildQuotaEngine engine = new BuildQuotaEngine(policy());
        engine.begin(intent("persisted", "p1", 10, 0));
        engine.finish("persisted");
        BuildQuotaEngine loaded = new BuildQuotaEngine(policy(), engine.save());
        require(!loaded.begin(intent("blocked", "p1", 11, 1)).accepted(), "reload granted capacity");
        require(loaded.save().equals(loaded.save()), "persisted state is unstable");
    }

    private void realBuilding() {
        Tile tile = emptyTile();
        tile.setBlock(Blocks.router, Team.sharded);
        require(tile.build != null, "real building was not created");
        BuildQuotaEngine engine = new BuildQuotaEngine(new BuildQuotaEngine.Policy(
            100, Map.of(tile.block().name, 1), Map.of(tile.block().name, 1)
        ));
        BuildQuotaEngine.BuildIntent intent = new BuildQuotaEngine.BuildIntent(
            "real-building", "server-player", tile.build.team.id, tile.block().name, tile.pos(), 0
        );
        require(engine.begin(intent).accepted(), "real building reservation failed");
        require(engine.finish(intent.requestId()).accepted(), "real building commit failed");
        require(engine.snapshot(0).toString().contains(tile.block().name), "real block accounting missing");
    }

    private static Tile emptyTile() {
        for (Tile tile : Vars.world.tiles) {
            if (tile.block() == Blocks.air && !tile.floor().isLiquid) return tile;
        }
        throw new IllegalStateException("no empty tile");
    }

    private void integration() throws Exception {
        Class<?> plugin = Class.forName("BuildQuotaAuditorPlugin");
        require(plugin.getMethod("instance").invoke(null) != null, "instance is null");
        require(plugin.getMethod("engine").invoke(plugin.getMethod("instance").invoke(null)) != null,
            "engine is null");
        require(Vars.world != null && Vars.state.isGame(), "headless world is inactive");
    }

    private static void check(List<Case> cases, String name, Checked body) {
        try { body.run(); cases.add(new Case(name, true, "ok")); }
        catch (Throwable error) { cases.add(new Case(name, false, error.toString())); }
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
        return value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n");
    }
    private static void require(boolean value, String message) { if (!value) throw new AssertionError(message); }
    private interface Checked { void run() throws Exception; }
    private record Case(String name, boolean passed, String message) {}
}
