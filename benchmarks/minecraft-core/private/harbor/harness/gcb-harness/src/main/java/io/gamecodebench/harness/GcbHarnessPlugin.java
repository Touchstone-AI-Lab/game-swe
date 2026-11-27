package io.gamecodebench.harness;

import java.util.List;
import org.bukkit.Bukkit;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.server.ServerLoadEvent;
import org.bukkit.plugin.Plugin;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scheduler.BukkitTask;

/** Harness entry point: bootstraps the world or drives the registered suite and reports once. */
public final class GcbHarnessPlugin extends JavaPlugin implements Listener {

    private static volatile Plugin candidatePlugin;

    private final ResultWriter writer = new ResultWriter();
    private HarnessSettings settings;
    private BukkitTask ticker;
    private SuiteRunner runner;
    private int tick;

    /** The verified candidate plugin, or null before verification. */
    static Plugin candidatePlugin() {
        return candidatePlugin;
    }

    @Override
    public void onEnable() {
        settings = HarnessSettings.fromSystemProperties();
        getLogger().info("GCB harness " + ResultWriter.VERSION + " mode=" + settings.mode()
            + " candidate=" + settings.candidate() + " maxTicks=" + settings.maxTicks()
            + " settleTicks=" + settings.settleTicks());
        Bukkit.getPluginManager().registerEvents(this, this);
    }

    @Override
    public void onDisable() {
        if (ticker != null) {
            ticker.cancel();
        }
        // If the server goes down before the run completes, still leave one truthful envelope.
        if (!settings.bootstrap() && !writer.emitted()) {
            emit("harness disabled before the suite completed", partialResults());
        }
    }

    @EventHandler
    public void onServerLoad(ServerLoadEvent event) {
        if (event.getType() != ServerLoadEvent.LoadType.STARTUP) {
            return;
        }
        if (settings.bootstrap()) {
            getLogger().info("GCB bootstrap: world ready");
            Bukkit.shutdown();
            return;
        }
        if (!HarnessSettings.MODE_RUN_SUITE.equals(settings.mode())) {
            finish("unknown gcb.mode: " + settings.mode(), List.of());
            return;
        }
        for (org.bukkit.World world : Bukkit.getWorlds()) {
            GcbWorlds.keepSpawnLoaded(world);
        }
        ticker = Bukkit.getScheduler().runTaskTimer(this, this::onTick, 0L, 1L);
    }

    private void onTick() {
        if (writer.emitted()) {
            return;
        }
        tick++;
        if (tick <= settings.settleTicks()) {
            return;
        }
        if (runner == null) {
            String problem = prepare();
            if (problem != null) {
                finish(problem, List.of());
                return;
            }
        }
        if (tick - settings.settleTicks() > settings.maxTicks()) {
            finish("suite exceeded tick budget", runner.results());
            return;
        }
        runner.tick();
        if (runner.finished()) {
            finish(null, runner.results());
        }
    }

    /** Verifies the preconditions and creates the runner; returns a fatal message on failure. */
    private String prepare() {
        String name = settings.candidate();
        Plugin plugin = name.isEmpty() ? null : Bukkit.getPluginManager().getPlugin(name);
        if (plugin == null) {
            return "candidate plugin not found: " + name;
        }
        if (!plugin.isEnabled()) {
            return "candidate plugin not enabled: " + name;
        }
        candidatePlugin = plugin;
        String registration = CaseRegistry.fatalError();
        if (registration != null) {
            return registration;
        }
        List<GcbCaseRecord> cases = CaseRegistry.sortedCases();
        if (cases.isEmpty()) {
            return "no cases registered";
        }
        getLogger().info("GCB running " + cases.size() + " case(s) against " + name);
        runner = new SuiteRunner(cases);
        return null;
    }

    private void finish(String fatal, List<CaseResult> cases) {
        if (ticker != null) {
            ticker.cancel();
        }
        if (emit(fatal, cases)) {
            Bukkit.shutdown();
        }
    }

    private boolean emit(String fatal, List<CaseResult> cases) {
        if (fatal != null) {
            getLogger().severe("GCB fatal: " + fatal);
        }
        return writer.emit(settings.nonce(), settings.candidate(), fatal, cases);
    }

    private List<CaseResult> partialResults() {
        return runner == null ? List.of() : runner.results();
    }
}
