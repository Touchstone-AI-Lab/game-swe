
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.TreeMap;
import java.util.regex.Pattern;

public final class TransferEngine {
    private static final Pattern ITEM_NAME = Pattern.compile("[a-z0-9][a-z0-9-]*");

    private final Adapter adapter;
    private final TreeMap<String, PersistedTransfer> transfers = new TreeMap<>();

    public TransferEngine(Adapter adapter) {
        this(adapter, new PersistedState(Map.of()));
    }

    public TransferEngine(Adapter adapter, PersistedState persisted) {
        this.adapter = Objects.requireNonNull(adapter, "adapter");
        Objects.requireNonNull(persisted, "persisted");
        Objects.requireNonNull(persisted.transfers(), "persisted.transfers");

        for (Map.Entry<String, PersistedTransfer> entry : persisted.transfers().entrySet()) {
            String requestId = requireIdentifier(entry.getKey(), "persisted request ID");
            PersistedTransfer transfer = copyTransfer(entry.getValue());
            if (!requestId.equals(transfer.request().requestId())) {
                throw new IllegalArgumentException("Persisted request ID does not match its key");
            }
            if (transfers.put(requestId, transfer) != null) {
                throw new IllegalArgumentException("Duplicate persisted request ID");
            }
        }
    }

    public TransferResult transfer(TransferRequest request) {
        String validation = validateRequest(request);
        String requestId = request == null ? "" : normalize(request.requestId());

        if (!requestId.isEmpty()) {
            PersistedTransfer existing = transfers.get(requestId);
            if (existing != null) {
                return resultOf(existing);
            }
        }

        if (validation != null) {
            if (!requestId.isEmpty()) {
                PersistedTransfer rejected = new PersistedTransfer(
                    copyRequest(request),
                    Phase.REJECTED,
                    null,
                    null,
                    null,
                    validation
                );
                transfers.put(requestId, rejected);
                checkpointBestEffort();
                return resultOf(rejected);
            }
            return new TransferResult(requestId, Phase.REJECTED, false, validation);
        }

        StorageSnapshot sourceBefore;
        StorageSnapshot destinationBefore;
        int destinationCapacity;

        try {
            sourceBefore = validateSnapshot(adapter.snapshot(request.sourcePos()), request.sourcePos());
            destinationBefore = validateSnapshot(
                adapter.snapshot(request.destinationPos()),
                request.destinationPos()
            );
            destinationCapacity = adapter.capacity(request.destinationPos(), request.itemName());
            if (destinationCapacity < 0) {
                throw new IllegalStateException("Adapter returned negative capacity");
            }
        } catch (RuntimeException error) {
            return reject(request, "preflight-error:" + error.getClass().getSimpleName());
        }

        int available = sourceBefore.items().getOrDefault(request.itemName(), 0);
        if (available < request.amount()) {
            return reject(request, "insufficient-source-items");
        }
        if (destinationCapacity < request.amount()) {
            return reject(request, "insufficient-destination-capacity");
        }

        PersistedTransfer prepared = new PersistedTransfer(
            copyRequest(request),
            Phase.PREPARED,
            sourceBefore,
            destinationBefore,
            null,
            "prepared"
        );
        transfers.put(request.requestId(), prepared);
        try {
            checkpoint();
        } catch (RuntimeException error) {
            return resultOf(replace(prepared, Phase.PREPARED, null, "checkpoint-failed"));
        }

        RemovedItems removed;
        try {
            removed = validateRemoved(
                adapter.remove(request.sourcePos(), request.itemName(), request.amount()),
                request.itemName(),
                request.amount()
            );
        } catch (RuntimeException error) {
            return compensateAfterRemoveFailure(prepared, error);
        }

        PersistedTransfer sourceRemoved = replace(
            prepared,
            Phase.SOURCE_REMOVED,
            removed,
            "source-removed"
        );
        try {
            checkpoint();
        } catch (RuntimeException error) {
            return resultOf(replace(
                sourceRemoved,
                Phase.RECOVERY_REQUIRED,
                removed,
                "checkpoint-failed-after-remove"
            ));
        }

        try {
            adapter.add(request.destinationPos(), copyRemoved(removed));
        } catch (RuntimeException error) {
            return compensateAfterAddFailure(sourceRemoved, error);
        }

        PersistedTransfer committed = replace(
            sourceRemoved,
            Phase.COMMITTED,
            removed,
            "committed"
        );
        try {
            checkpoint();
        } catch (RuntimeException error) {
            return resultOf(replace(
                committed,
                Phase.RECOVERY_REQUIRED,
                removed,
                "checkpoint-failed-after-add"
            ));
        }
        return resultOf(committed);
    }

    public RecoveryReport recover() {
        int committed = 0;
        int rolledBack = 0;
        int stillRecoverable = 0;

        for (String requestId : new ArrayList<>(transfers.keySet())) {
            PersistedTransfer transfer = transfers.get(requestId);
            if (transfer == null) {
                continue;
            }

            switch (transfer.phase()) {
                case PREPARED -> {
                    if (restoreBoth(transfer)) {
                        replace(transfer, Phase.ROLLED_BACK, transfer.removed(), "recovered-prepared");
                        checkpointBestEffort();
                        rolledBack++;
                    } else {
                        replace(
                            transfer,
                            Phase.RECOVERY_REQUIRED,
                            transfer.removed(),
                            "restore-failed"
                        );
                        checkpointBestEffort();
                        stillRecoverable++;
                    }
                }
                case SOURCE_REMOVED -> {
                    try {
                        adapter.add(
                            transfer.request().destinationPos(),
                            copyRemoved(requireRemoved(transfer))
                        );
                        replace(transfer, Phase.COMMITTED, transfer.removed(), "recovered-commit");
                        checkpointBestEffort();
                        committed++;
                    } catch (RuntimeException error) {
                        if (restoreBoth(transfer)) {
                            replace(
                                transfer,
                                Phase.ROLLED_BACK,
                                transfer.removed(),
                                "recovered-rollback"
                            );
                            checkpointBestEffort();
                            rolledBack++;
                        } else {
                            replace(
                                transfer,
                                Phase.RECOVERY_REQUIRED,
                                transfer.removed(),
                                "recovery-compensation-failed"
                            );
                            checkpointBestEffort();
                            stillRecoverable++;
                        }
                    }
                }
                case RECOVERY_REQUIRED -> {
                    if (restoreBoth(transfer)) {
                        replace(
                            transfer,
                            Phase.ROLLED_BACK,
                            transfer.removed(),
                            "recovered-compensation"
                        );
                        checkpointBestEffort();
                        rolledBack++;
                    } else {
                        stillRecoverable++;
                    }
                }
                default -> {
                    // Final states require no recovery work.
                }
            }
        }

        return new RecoveryReport(committed, rolledBack, stillRecoverable);
    }

    public TransferResult status(String requestId) {
        String normalized = normalize(requestId);
        PersistedTransfer transfer = transfers.get(normalized);
        if (transfer == null) {
            return new TransferResult(normalized, Phase.REJECTED, false, "unknown-request");
        }
        return resultOf(transfer);
    }

    public PersistedState save() {
        Map<String, PersistedTransfer> copy = new LinkedHashMap<>();
        for (Map.Entry<String, PersistedTransfer> entry : transfers.entrySet()) {
            copy.put(entry.getKey(), copyTransfer(entry.getValue()));
        }
        return new PersistedState(Collections.unmodifiableMap(copy));
    }

    private TransferResult reject(TransferRequest request, String reason) {
        PersistedTransfer rejected = new PersistedTransfer(
            copyRequest(request),
            Phase.REJECTED,
            null,
            null,
            null,
            reason
        );
        transfers.put(request.requestId(), rejected);
        checkpointBestEffort();
        return resultOf(rejected);
    }

    private TransferResult compensateAfterRemoveFailure(
        PersistedTransfer prepared,
        RuntimeException error
    ) {
        boolean restored;
        try {
            adapter.restore(
                prepared.request().sourcePos(),
                copySnapshot(requireSnapshot(prepared.sourceBefore()))
            );
            restored = true;
        } catch (RuntimeException restoreError) {
            restored = false;
        }

        PersistedTransfer finalTransfer = replace(
            prepared,
            restored ? Phase.ROLLED_BACK : Phase.RECOVERY_REQUIRED,
            null,
            restored ? "remove-failed-rolled-back" : "remove-and-restore-failed"
        );
        checkpointBestEffort();
        return resultOf(finalTransfer);
    }

    private TransferResult compensateAfterAddFailure(
        PersistedTransfer sourceRemoved,
        RuntimeException error
    ) {
        boolean destinationRestored = restoreOne(
            sourceRemoved.request().destinationPos(),
            sourceRemoved.destinationBefore()
        );
        boolean sourceRestored = restoreOne(
            sourceRemoved.request().sourcePos(),
            sourceRemoved.sourceBefore()
        );
        boolean restored = destinationRestored && sourceRestored;

        PersistedTransfer finalTransfer = replace(
            sourceRemoved,
            restored ? Phase.ROLLED_BACK : Phase.RECOVERY_REQUIRED,
            sourceRemoved.removed(),
            restored ? "add-failed-rolled-back" : "add-and-compensation-failed"
        );
        checkpointBestEffort();
        return resultOf(finalTransfer);
    }

    private boolean restoreBoth(PersistedTransfer transfer) {
        boolean destination = restoreOne(
            transfer.request().destinationPos(),
            transfer.destinationBefore()
        );
        boolean source = restoreOne(transfer.request().sourcePos(), transfer.sourceBefore());
        return destination && source;
    }

    private boolean restoreOne(int buildingPos, StorageSnapshot snapshot) {
        if (snapshot == null) {
            return false;
        }
        try {
            adapter.restore(buildingPos, copySnapshot(snapshot));
            return true;
        } catch (RuntimeException error) {
            return false;
        }
    }

    private PersistedTransfer replace(
        PersistedTransfer original,
        Phase phase,
        RemovedItems removed,
        String reason
    ) {
        PersistedTransfer replacement = new PersistedTransfer(
            original.request(),
            phase,
            original.sourceBefore(),
            original.destinationBefore(),
            removed,
            reason
        );
        transfers.put(original.request().requestId(), copyTransfer(replacement));
        return transfers.get(original.request().requestId());
    }

    private void checkpoint() {
        adapter.checkpoint(save());
    }

    private void checkpointBestEffort() {
        try {
            checkpoint();
        } catch (RuntimeException ignored) {
            // The in-memory state remains authoritative until a later recovery attempt.
        }
    }

    private static TransferResult resultOf(PersistedTransfer transfer) {
        return new TransferResult(
            transfer.request().requestId(),
            transfer.phase(),
            transfer.phase() == Phase.COMMITTED,
            transfer.reason()
        );
    }

    private static String validateRequest(TransferRequest request) {
        if (request == null) {
            return "request-is-null";
        }
        if (normalize(request.requestId()).isEmpty()) {
            return "invalid-request-id";
        }
        if (!request.requestId().equals(request.requestId().trim())) {
            return "invalid-request-id";
        }
        if (request.sourcePos() < 0 || request.destinationPos() < 0) {
            return "invalid-building-position";
        }
        if (request.sourcePos() == request.destinationPos()) {
            return "identical-buildings";
        }
        if (request.itemName() == null || !ITEM_NAME.matcher(request.itemName()).matches()) {
            return "invalid-item-name";
        }
        if (request.amount() <= 0) {
            return "invalid-amount";
        }
        return null;
    }

    private static StorageSnapshot validateSnapshot(StorageSnapshot snapshot, int expectedPos) {
        StorageSnapshot copy = copySnapshot(requireSnapshot(snapshot));
        if (copy.buildingPos() != expectedPos) {
            throw new IllegalArgumentException("Snapshot building position mismatch");
        }
        return copy;
    }

    private static RemovedItems validateRemoved(
        RemovedItems removed,
        String expectedItem,
        int expectedAmount
    ) {
        RemovedItems copy = copyRemoved(Objects.requireNonNull(removed, "removed"));
        long total = 0;
        for (ItemPortion portion : copy.portions()) {
            if (!expectedItem.equals(portion.itemName())) {
                throw new IllegalArgumentException("Removed item name mismatch");
            }
            total += portion.amount();
        }
        if (total != expectedAmount) {
            throw new IllegalArgumentException("Removed item amount mismatch");
        }
        return copy;
    }

    private static PersistedTransfer copyTransfer(PersistedTransfer transfer) {
        Objects.requireNonNull(transfer, "transfer");
        TransferRequest request = copyRequest(transfer.request());
        Phase phase = Objects.requireNonNull(transfer.phase(), "phase");
        String reason = Objects.requireNonNullElse(transfer.reason(), "");
        StorageSnapshot source = transfer.sourceBefore() == null
            ? null
            : copySnapshot(transfer.sourceBefore());
        StorageSnapshot destination = transfer.destinationBefore() == null
            ? null
            : copySnapshot(transfer.destinationBefore());
        RemovedItems removed = transfer.removed() == null ? null : copyRemoved(transfer.removed());

        if ((phase == Phase.PREPARED || phase == Phase.SOURCE_REMOVED
            || phase == Phase.RECOVERY_REQUIRED)
            && (source == null || destination == null)) {
            throw new IllegalArgumentException("Recoverable transfer is missing snapshots");
        }
        if (phase == Phase.SOURCE_REMOVED && removed == null) {
            throw new IllegalArgumentException("Removed phase is missing removed items");
        }

        return new PersistedTransfer(request, phase, source, destination, removed, reason);
    }

    private static TransferRequest copyRequest(TransferRequest request) {
        Objects.requireNonNull(request, "request");
        return new TransferRequest(
            requireIdentifier(request.requestId(), "request ID"),
            request.sourcePos(),
            request.destinationPos(),
            Objects.requireNonNullElse(request.itemName(), ""),
            request.amount()
        );
    }

    private static StorageSnapshot copySnapshot(StorageSnapshot snapshot) {
        Objects.requireNonNull(snapshot, "snapshot");
        if (snapshot.buildingPos() < 0) {
            throw new IllegalArgumentException("Negative snapshot building position");
        }
        Objects.requireNonNull(snapshot.items(), "snapshot.items");
        Map<String, Integer> items = new TreeMap<>();
        for (Map.Entry<String, Integer> entry : snapshot.items().entrySet()) {
            String itemName = requireItemName(entry.getKey());
            Integer amount = Objects.requireNonNull(entry.getValue(), "snapshot amount");
            if (amount < 0) {
                throw new IllegalArgumentException("Negative snapshot item amount");
            }
            items.put(itemName, amount);
        }
        return new StorageSnapshot(snapshot.buildingPos(), Collections.unmodifiableMap(items));
    }

    private static RemovedItems copyRemoved(RemovedItems removed) {
        Objects.requireNonNull(removed, "removed");
        Objects.requireNonNull(removed.portions(), "removed.portions");
        List<ItemPortion> portions = new ArrayList<>();
        for (ItemPortion portion : removed.portions()) {
            Objects.requireNonNull(portion, "portion");
            String itemName = requireItemName(portion.itemName());
            if (portion.amount() <= 0) {
                throw new IllegalArgumentException("Invalid removed item amount");
            }
            portions.add(new ItemPortion(itemName, portion.amount()));
        }
        if (portions.isEmpty()) {
            throw new IllegalArgumentException("Removed items must not be empty");
        }
        return new RemovedItems(List.copyOf(portions));
    }

    private static RemovedItems requireRemoved(PersistedTransfer transfer) {
        return Objects.requireNonNull(transfer.removed(), "transfer.removed");
    }

    private static StorageSnapshot requireSnapshot(StorageSnapshot snapshot) {
        return Objects.requireNonNull(snapshot, "snapshot");
    }

    private static String requireIdentifier(String value, String label) {
        String normalized = normalize(value);
        if (normalized.isEmpty() || !normalized.equals(value)) {
            throw new IllegalArgumentException("Invalid " + label);
        }
        return normalized;
    }

    private static String requireItemName(String value) {
        if (value == null || !ITEM_NAME.matcher(value).matches()) {
            throw new IllegalArgumentException("Invalid item name");
        }
        return value;
    }

    private static String normalize(String value) {
        return value == null ? "" : value.trim();
    }

    public interface Adapter {
        StorageSnapshot snapshot(int buildingPos);

        int capacity(int buildingPos, String itemName);

        RemovedItems remove(int buildingPos, String itemName, int amount);

        void add(int buildingPos, RemovedItems items);

        void restore(int buildingPos, StorageSnapshot snapshot);

        void checkpoint(PersistedState state);
    }

    public record TransferRequest(
        String requestId,
        int sourcePos,
        int destinationPos,
        String itemName,
        int amount
    ) {}

    public enum Phase {
        REJECTED,
        PREPARED,
        SOURCE_REMOVED,
        COMMITTED,
        ROLLED_BACK,
        RECOVERY_REQUIRED
    }

    public record TransferResult(
        String requestId,
        Phase phase,
        boolean successful,
        String reason
    ) {}

    public record ItemPortion(String itemName, int amount) {}

    public record RemovedItems(List<ItemPortion> portions) {}

    public record StorageSnapshot(int buildingPos, Map<String, Integer> items) {}

    public record PersistedTransfer(
        TransferRequest request,
        Phase phase,
        StorageSnapshot sourceBefore,
        StorageSnapshot destinationBefore,
        RemovedItems removed,
        String reason
    ) {}

    public record PersistedState(Map<String, PersistedTransfer> transfers) {}

    public record RecoveryReport(int committed, int rolledBack, int stillRecoverable) {}
}
