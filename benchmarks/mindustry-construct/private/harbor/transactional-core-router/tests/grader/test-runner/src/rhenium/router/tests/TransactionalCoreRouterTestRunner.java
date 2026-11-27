
import arc.Core;
import arc.Events;
import arc.util.Log;
import arc.util.Time;
import mindustry.Vars;
import mindustry.content.Blocks;
import mindustry.content.Items;
import mindustry.game.EventType.WorldLoadEvent;
import mindustry.game.Team;
import mindustry.gen.Building;
import mindustry.mod.Plugin;
import mindustry.world.Tile;
import mindustry.io.SaveIO;

import java.util.ArrayList;
import java.util.List;

public final class TransactionalCoreRouterTestRunner extends Plugin {
    private final List<TestCase> cases = new ArrayList<>();
    private boolean reloadPending;
    private int reloadSourcePos;
    private int reloadDestinationPos;

    public TransactionalCoreRouterTestRunner() {
        Events.on(WorldLoadEvent.class, event -> Time.runTask(
            60f,
            reloadPending ? this::verifyReload : this::run
        ));
    }

    private void run() {
        for (TransferEngineCoreTests.Outcome outcome : TransferEngineCoreTests.runAll()) {
            cases.add(new TestCase(outcome.name(), outcome.passed(), outcome.message()));
        }
        check("real building transfer", this::realBuildingTransfer);
        check("duplicate request is idempotent", this::duplicateRequest);
        check("insufficient stock is rejected", this::insufficientStock);
        check("different teams are rejected", this::differentTeamsRejected);
        check("unknown item is rejected", this::unknownItemRejected);
        check("destroyed storage is rejected", this::destroyedStorageRejected);

        try {
            beginSaveReload();
        } catch (Throwable error) {
            cases.add(new TestCase("custom save chunk reload", false, error.toString()));
            emitAndExit();
        }
    }

    private void beginSaveReload() {
        Buildings buildings = createBuildings();
        buildings.source().items.add(Items.copper, 90);
        TransferEngine.TransferResult result = plugin().request(
            "persistent-transfer",
            buildings.source().pos(),
            buildings.destination().pos(),
            "copper",
            25
        );
        require(result.successful(), "persistent transfer did not commit");
        reloadSourcePos = buildings.source().pos();
        reloadDestinationPos = buildings.destination().pos();
        reloadPending = true;
        SaveIO.save(Vars.saveDirectory.child("mindustry-router-test.msav"));
        SaveIO.load(Vars.saveDirectory.child("mindustry-router-test.msav"));
    }

    private void verifyReload() {
        check("custom save chunk reload", () -> {
            Building source = Vars.world.build(reloadSourcePos);
            Building destination = Vars.world.build(reloadDestinationPos);
            require(source != null && destination != null, "saved buildings are missing");
            TransferEngine.TransferResult retry = plugin().request(
                "persistent-transfer",
                reloadSourcePos,
                reloadDestinationPos,
                "copper",
                60
            );
            require(retry.successful(), "committed request was not restored");
            require(source.items.get(Items.copper) == 65, "source changed after reload retry");
            require(destination.items.get(Items.copper) == 25, "destination changed after reload retry");
        });
        emitAndExit();
    }

    private void emitAndExit() {

        boolean passed = cases.stream().allMatch(TestCase::passed);
        StringBuilder json = new StringBuilder();
        json.append("{\"passed\":").append(passed).append(",\"cases\":[");
        for (int index = 0; index < cases.size(); index++) {
            if (index > 0) {
                json.append(',');
            }
            TestCase testCase = cases.get(index);
            json.append("{\"name\":\"")
                .append(escape(testCase.name()))
                .append("\",\"passed\":")
                .append(testCase.passed())
                .append(",\"message\":\"")
                .append(escape(testCase.message()))
                .append("\"}");
        }
        json.append("]}");
        Log.info("MINDUSTRY_RESULT @", json.toString());
        Core.app.exit();
    }

    private void differentTeamsRejected() {
        Buildings buildings = createBuildings();
        buildings.destination().tile.setBlock(Blocks.vault, Team.crux);
        boolean rejected = false;
        try {
            plugin().request(
                "team-transfer",
                buildings.source().pos(),
                buildings.destination().tile.build.pos(),
                "copper",
                1
            );
        } catch (IllegalArgumentException expected) {
            rejected = true;
        }
        require(rejected, "cross-team transfer was accepted");
    }

    private void unknownItemRejected() {
        Buildings buildings = createBuildings();
        boolean rejected = false;
        try {
            plugin().request(
                "unknown-item",
                buildings.source().pos(),
                buildings.destination().pos(),
                "not-a-base-item",
                1
            );
        } catch (IllegalArgumentException expected) {
            rejected = true;
        }
        require(rejected, "unknown item was accepted");
    }

    private void destroyedStorageRejected() {
        Buildings buildings = createBuildings();
        int sourcePos = buildings.source().pos();
        buildings.source().tile.setBlock(Blocks.air);
        boolean rejected = false;
        try {
            plugin().request(
                "destroyed-storage",
                sourcePos,
                buildings.destination().pos(),
                "copper",
                1
            );
        } catch (IllegalArgumentException expected) {
            rejected = true;
        }
        require(rejected, "destroyed source was accepted");
    }

    private void realBuildingTransfer() {
        Buildings buildings = createBuildings();
        buildings.source().items.add(Items.copper, 80);

        TransferEngine.TransferResult result = plugin().request(
            "real-transfer",
            buildings.source().pos(),
            buildings.destination().pos(),
            "copper",
            30
        );

        require(result.successful(), "Transfer did not commit");
        require(buildings.source().items.get(Items.copper) == 50, "Source amount is incorrect");
        require(
            buildings.destination().items.get(Items.copper) == 30,
            "Destination amount is incorrect"
        );
    }

    private void duplicateRequest() {
        Buildings buildings = createBuildings();
        buildings.source().items.add(Items.lead, 70);

        TransferEngine.TransferResult first = plugin().request(
            "duplicate-transfer",
            buildings.source().pos(),
            buildings.destination().pos(),
            "lead",
            20
        );
        TransferEngine.TransferResult retry = plugin().request(
            "duplicate-transfer",
            buildings.source().pos(),
            buildings.destination().pos(),
            "lead",
            60
        );

        require(first.equals(retry), "Retry did not return the original result");
        require(buildings.source().items.get(Items.lead) == 50, "Retry mutated source");
        require(buildings.destination().items.get(Items.lead) == 20, "Retry mutated destination");
    }

    private void insufficientStock() {
        Buildings buildings = createBuildings();
        buildings.source().items.add(Items.graphite, 5);

        TransferEngine.TransferResult result = plugin().request(
            "insufficient-transfer",
            buildings.source().pos(),
            buildings.destination().pos(),
            "graphite",
            10
        );

        require(!result.successful(), "Insufficient transfer unexpectedly succeeded");
        require(buildings.source().items.get(Items.graphite) == 5, "Source was mutated");
        require(buildings.destination().items.get(Items.graphite) == 0, "Destination was mutated");
    }

    private static TransactionalCoreRouterPlugin plugin() {
        return TransactionalCoreRouterPlugin.instance();
    }

    private static Buildings createBuildings() {
        Tile first = null;
        Tile second = null;
        for (Tile tile : Vars.world.tiles) {
            if (tile.block() == Blocks.air && !tile.floor().isLiquid) {
                if (first == null) {
                    first = tile;
                } else if (Math.abs(tile.x - first.x) > 3 || Math.abs(tile.y - first.y) > 3) {
                    second = tile;
                    break;
                }
            }
        }
        if (first == null || second == null) {
            throw new IllegalStateException("No suitable test tiles found");
        }
        first.setBlock(Blocks.vault, Team.sharded);
        second.setBlock(Blocks.vault, Team.sharded);
        return new Buildings(first.build, second.build);
    }

    private void check(String name, CheckedRunnable body) {
        try {
            body.run();
            cases.add(new TestCase(name, true, "ok"));
        } catch (Throwable error) {
            cases.add(new TestCase(name, false, error.toString()));
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) {
            throw new AssertionError(message);
        }
    }

    private static String escape(String value) {
        return value.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    private interface CheckedRunnable {
        void run() throws Exception;
    }

    private record Buildings(Building source, Building destination) {}

    private record TestCase(String name, boolean passed, String message) {}
}
