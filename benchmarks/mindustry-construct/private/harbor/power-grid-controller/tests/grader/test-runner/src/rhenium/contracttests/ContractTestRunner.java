
import arc.Core;
import arc.Events;
import arc.util.Log;
import arc.util.Time;
import mindustry.Vars;
import mindustry.content.Blocks;
import mindustry.game.EventType.WorldLoadEvent;
import mindustry.game.Team;
import mindustry.gen.Building;
import mindustry.world.Tile;
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
        check(cases, "shortage sheds deterministically", this::shed);
        check(cases, "hysteresis prevents oscillation", this::hysteresis);
        check(cases, "minimum off time boundary", this::minimumTime);
        check(cases, "split merge preserves locks", this::topology);
        check(cases, "invalid and stale samples are inert", this::invalid);
        check(cases, "save reload next action", this::reload);
        check(cases, "real consumer enabled state", this::realConsumer);
        check(cases, "active plugin and headless world", this::integration);
        finish(cases);
    }

    private GridController controller() { return new GridController(new GridController.Policy(0.8, 0.95, 10, 5)); }
    private GridController.GridSample sample(long grid, long revision, long tick, double production, List<GridController.Load> loads) {
        return new GridController.GridSample(grid, revision, tick, production, 0, 100, loads);
    }
    private List<GridController.Load> loads() {
        return List.of(new GridController.Load(20, 1, 60, true), new GridController.Load(10, 10, 60, true));
    }
    private void shed() {
        GridController c = controller();
        Object decision = c.observe(sample(1, 1, 0, 70, loads()));
        require(decision.toString().contains("20"), "lowest-priority load was not selected");
        require(c.snapshot().equals(c.snapshot()), "snapshot is unstable");
    }
    private void hysteresis() {
        GridController c = controller();
        c.observe(sample(1, 1, 0, 70, loads()));
        Object middle = c.observe(sample(1, 2, 5, 100, loads()));
        Object retry = c.observe(sample(1, 2, 5, 100, loads()));
        require(middle.equals(retry), "identical sample changed decision");
    }
    private void minimumTime() {
        GridController c = controller();
        c.observe(sample(1, 1, 0, 20, loads()));
        Object early = c.observe(sample(1, 2, 9, 500, loads()));
        Object boundary = c.observe(sample(1, 3, 10, 500, loads()));
        require(early != null && boundary != null, "minimum-time transition failed");
        require(c.snapshot().toString().contains("1"), "grid state disappeared");
    }
    private void topology() {
        GridController c = controller();
        c.observe(sample(1, 1, 0, 20, loads()));
        c.split(1, List.of(sample(2, 1, 1, 20, List.of(loads().get(0))),
            sample(3, 1, 1, 20, List.of(loads().get(1)))), 1);
        c.merge(List.of(2L, 3L), sample(4, 1, 2, 20, loads()), 2);
        require(c.snapshot().toString().contains("4"), "merged grid missing");
        require(!c.snapshot().toString().contains("gridId=1"), "parent grid survived split");
    }
    private void invalid() {
        GridController c = controller();
        c.observe(sample(1, 2, 5, 50, loads()));
        Object before = c.snapshot();
        try { c.observe(sample(1, 1, 4, 500, loads())); } catch (RuntimeException ignored) {}
        require(before.equals(c.snapshot()), "stale sample mutated state");
        try { c.observe(sample(1, 3, 6, Double.NaN, loads())); } catch (RuntimeException ignored) {}
        require(before.equals(c.snapshot()), "invalid sample mutated state");
    }
    private void reload() {
        GridController c = controller();
        c.observe(sample(1, 1, 0, 20, loads()));
        GridController loaded = new GridController(new GridController.Policy(0.8, 0.95, 10, 5), c.save());
        Object a = c.observe(sample(1, 2, 10, 500, loads()));
        Object b = loaded.observe(sample(1, 2, 10, 500, loads()));
        require(a.equals(b), "reload changed next decision");
    }
    private void realConsumer() {
        Tile tile = emptyTile();
        tile.setBlock(Blocks.arc, Team.sharded);
        Building building = tile.build;
        require(building != null, "real consumer was not created");
        GridController c = controller();
        var decision = c.observe(sample(
            99, 1, 0, 0, List.of(new GridController.Load(building.pos(), 1, 1, building.enabled))
        ));
        for (var action : decision.actions()) {
            if (action.buildingPos() == building.pos() && action.action() == GridController.Action.SHED) {
                building.enabled = false;
            }
        }
        require(!building.enabled, "real consumer was not disabled");
    }
    private static Tile emptyTile() {
        for (Tile tile : Vars.world.tiles) {
            if (tile.block() == Blocks.air && !tile.floor().isLiquid) return tile;
        }
        throw new IllegalStateException("no empty tile");
    }
    private void integration() throws Exception {
        Class<?> type = Class.forName("PowerGridControllerPlugin");
        Object plugin = type.getMethod("instance").invoke(null);
        require(plugin != null, "instance is null");
        require(type.getMethod("controller").invoke(plugin) != null, "controller is null");
        require(Vars.world != null && Vars.state.isGame(), "headless world is inactive");
    }
    private static void check(List<Case> cases, String name, Checked body) { try { body.run(); cases.add(new Case(name,true,"ok")); } catch(Throwable e){ cases.add(new Case(name,false,e.toString())); } }
    private static void finish(List<Case> cases) { boolean passed=cases.stream().allMatch(Case::passed); StringBuilder out=new StringBuilder("{\"passed\":").append(passed).append(",\"cases\":["); for(int i=0;i<cases.size();i++){if(i>0)out.append(',');Case c=cases.get(i);out.append("{\"name\":\"").append(esc(c.name())).append("\",\"passed\":").append(c.passed()).append(",\"message\":\"").append(esc(c.message())).append("\"}");} Log.info("MINDUSTRY_RESULT @",out.append("]}").toString());Core.app.exit(); }
    private static String esc(String s){return s.replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n");}
    private static void require(boolean v,String m){if(!v)throw new AssertionError(m);}
    private interface Checked{void run()throws Exception;}
    private record Case(String name,boolean passed,String message){}
}
