

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class TransferEngineCoreTests {
    private TransferEngineCoreTests() {}

    public static List<Outcome> runAll() {
        List<Outcome> outcomes = new ArrayList<>();
        run(outcomes, "checkpoint precedes mutation", TransferEngineCoreTests::checkpointPrecedesMutation);
        run(outcomes, "add failure compensates destination first", TransferEngineCoreTests::addFailureCompensates);
        run(outcomes, "compensation failure remains recoverable", TransferEngineCoreTests::compensationFailureRecovers);
        run(outcomes, "duplicate request performs no operations", TransferEngineCoreTests::duplicateIsOperationFree);
        run(outcomes, "source-removed state recovers once", TransferEngineCoreTests::sourceRemovedRecovers);
        run(outcomes, "malformed request does not mutate", TransferEngineCoreTests::malformedDoesNotMutate);
        return List.copyOf(outcomes);
    }

    private static void checkpointPrecedesMutation() {
        FakeAdapter adapter = standardAdapter();
        TransferEngine engine = new TransferEngine(adapter);
        TransferEngine.TransferResult result = engine.transfer(request("ordered"));
        require(result.successful(), "transfer did not commit");

        int prepared = adapter.calls.indexOf("checkpoint:PREPARED");
        int remove = adapter.calls.indexOf("remove:1");
        int removed = adapter.calls.indexOf("checkpoint:SOURCE_REMOVED");
        int add = adapter.calls.indexOf("add:2");
        require(prepared >= 0 && prepared < remove, "prepare was not durable before remove");
        require(removed >= 0 && removed < add, "removed state was not durable before add");
    }

    private static void addFailureCompensates() {
        FakeAdapter adapter = standardAdapter();
        adapter.failAdd = true;
        TransferEngine engine = new TransferEngine(adapter);
        TransferEngine.TransferResult result = engine.transfer(request("compensate"));
        require(result.phase() == TransferEngine.Phase.ROLLED_BACK, "transfer was not rolled back");

        int destination = adapter.calls.indexOf("restore:2");
        int source = adapter.calls.indexOf("restore:1");
        require(destination >= 0 && destination < source, "compensation order is incorrect");
        require(adapter.amount(1, "copper") == 100, "source was not restored");
        require(adapter.amount(2, "copper") == 0, "destination was not restored");
    }

    private static void duplicateIsOperationFree() {
        FakeAdapter adapter = standardAdapter();
        TransferEngine engine = new TransferEngine(adapter);
        TransferEngine.TransferResult first = engine.transfer(request("duplicate"));
        int callCount = adapter.calls.size();
        TransferEngine.TransferResult retry = engine.transfer(new TransferEngine.TransferRequest(
            "duplicate", 1, 2, "copper", 70
        ));
        require(first.equals(retry), "retry result changed");
        require(adapter.calls.size() == callCount, "retry invoked adapter operations");
    }

    private static void compensationFailureRecovers() {
        FakeAdapter adapter = standardAdapter();
        adapter.failAdd = true;
        adapter.failRestore = true;
        TransferEngine engine = new TransferEngine(adapter);
        TransferEngine.TransferResult result = engine.transfer(request("recoverable-failure"));
        require(
            result.phase() == TransferEngine.Phase.RECOVERY_REQUIRED,
            "compensation failure was not retained"
        );
        require(adapter.calls.contains("restore:2"), "destination restore was not attempted");
        require(adapter.calls.contains("restore:1"), "source restore was not attempted");
    }

    private static void sourceRemovedRecovers() {
        FakeAdapter adapter = standardAdapter();
        adapter.stores.get(1).put("copper", 60);
        TransferEngine.TransferRequest request = request("recover");
        TransferEngine.StorageSnapshot source = new TransferEngine.StorageSnapshot(
            1, Map.of("copper", 100)
        );
        TransferEngine.StorageSnapshot destination = new TransferEngine.StorageSnapshot(2, Map.of());
        TransferEngine.RemovedItems removed = new TransferEngine.RemovedItems(List.of(
            new TransferEngine.ItemPortion("copper", 40)
        ));
        TransferEngine.PersistedTransfer transfer = new TransferEngine.PersistedTransfer(
            request,
            TransferEngine.Phase.SOURCE_REMOVED,
            source,
            destination,
            removed,
            "source-removed"
        );
        TransferEngine engine = new TransferEngine(
            adapter,
            new TransferEngine.PersistedState(Map.of("recover", transfer))
        );
        TransferEngine.RecoveryReport first = engine.recover();
        int calls = adapter.calls.size();
        TransferEngine.RecoveryReport second = engine.recover();
        require(first.committed() == 1, "recovery did not commit");
        require(second.committed() == 0, "second recovery repeated commit");
        require(adapter.calls.size() == calls, "second recovery mutated adapter");
        require(adapter.amount(2, "copper") == 40, "recovered destination amount is incorrect");
    }

    private static void malformedDoesNotMutate() {
        FakeAdapter adapter = standardAdapter();
        TransferEngine engine = new TransferEngine(adapter);
        TransferEngine.TransferResult result = engine.transfer(new TransferEngine.TransferRequest(
            "malformed", 1, 1, "Copper", -1
        ));
        require(!result.successful(), "malformed request succeeded");
        require(adapter.calls.stream().noneMatch(call -> call.startsWith("remove:") || call.startsWith("add:")),
            "malformed request mutated storage");
    }

    private static TransferEngine.TransferRequest request(String requestId) {
        return new TransferEngine.TransferRequest(requestId, 1, 2, "copper", 40);
    }

    private static FakeAdapter standardAdapter() {
        FakeAdapter adapter = new FakeAdapter();
        adapter.stores.put(1, new LinkedHashMap<>(Map.of("copper", 100)));
        adapter.stores.put(2, new LinkedHashMap<>());
        adapter.capacities.put(2, 100);
        return adapter;
    }

    private static void run(List<Outcome> outcomes, String name, CheckedRunnable test) {
        try {
            test.run();
            outcomes.add(new Outcome(name, true, "ok"));
        } catch (Throwable error) {
            outcomes.add(new Outcome(name, false, error.toString()));
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) {
            throw new AssertionError(message);
        }
    }

    private interface CheckedRunnable {
        void run() throws Exception;
    }

    public record Outcome(String name, boolean passed, String message) {}

    private static final class FakeAdapter implements TransferEngine.Adapter {
        private final Map<Integer, Map<String, Integer>> stores = new HashMap<>();
        private final Map<Integer, Integer> capacities = new HashMap<>();
        private final List<String> calls = new ArrayList<>();
        private boolean failAdd;
        private boolean failRestore;

        @Override
        public TransferEngine.StorageSnapshot snapshot(int buildingPos) {
            calls.add("snapshot:" + buildingPos);
            return new TransferEngine.StorageSnapshot(
                buildingPos,
                new LinkedHashMap<>(stores.getOrDefault(buildingPos, Map.of()))
            );
        }

        @Override
        public int capacity(int buildingPos, String itemName) {
            calls.add("capacity:" + buildingPos);
            return capacities.getOrDefault(buildingPos, 0) - amount(buildingPos, itemName);
        }

        @Override
        public TransferEngine.RemovedItems remove(int buildingPos, String itemName, int amount) {
            calls.add("remove:" + buildingPos);
            stores.get(buildingPos).put(itemName, amount(buildingPos, itemName) - amount);
            return new TransferEngine.RemovedItems(List.of(
                new TransferEngine.ItemPortion(itemName, amount)
            ));
        }

        @Override
        public void add(int buildingPos, TransferEngine.RemovedItems items) {
            calls.add("add:" + buildingPos);
            if (failAdd) {
                throw new IllegalStateException("injected-add-failure");
            }
            for (TransferEngine.ItemPortion portion : items.portions()) {
                stores.computeIfAbsent(buildingPos, ignored -> new LinkedHashMap<>()).merge(
                    portion.itemName(), portion.amount(), Integer::sum
                );
            }
        }

        @Override
        public void restore(int buildingPos, TransferEngine.StorageSnapshot snapshot) {
            calls.add("restore:" + buildingPos);
            if (failRestore) {
                throw new IllegalStateException("injected-restore-failure");
            }
            stores.put(buildingPos, new LinkedHashMap<>(snapshot.items()));
        }

        @Override
        public void checkpoint(TransferEngine.PersistedState state) {
            TransferEngine.Phase phase = state.transfers().isEmpty()
                ? TransferEngine.Phase.REJECTED
                : state.transfers().values().iterator().next().phase();
            calls.add("checkpoint:" + phase);
        }

        private int amount(int buildingPos, String itemName) {
            return stores.getOrDefault(buildingPos, Map.of()).getOrDefault(itemName, 0);
        }
    }
}
