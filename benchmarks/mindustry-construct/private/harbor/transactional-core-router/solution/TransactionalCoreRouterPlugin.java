
import arc.Events;
import arc.util.CommandHandler;
import arc.util.Log;
import mindustry.Vars;
import mindustry.game.EventType.ResetEvent;
import mindustry.game.EventType.WorldLoadEvent;
import mindustry.game.Team;
import mindustry.gen.Building;
import mindustry.mod.Plugin;
import mindustry.type.Item;
import mindustry.io.SaveFileReader.CustomChunk;
import mindustry.io.SaveVersion;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class TransactionalCoreRouterPlugin extends Plugin {
    private static final String CHUNK_NAME = "mindustry-transactional-core-router";
    private static final int SAVE_VERSION = 1;
    private static boolean chunkRegistered;
    private static TransactionalCoreRouterPlugin current;

    private TransferEngine engine;
    private TransferEngine.PersistedState checkpoint =
        new TransferEngine.PersistedState(Map.of());

    public TransactionalCoreRouterPlugin() {
        current = this;
    }

    @Override
    public void init() {
        registerSaveChunk();
        engine = new TransferEngine(new BuildingAdapter(), checkpoint);
        Events.on(WorldLoadEvent.class, event -> engine.recover());
        Events.on(ResetEvent.class, event -> {
            checkpoint = new TransferEngine.PersistedState(Map.of());
            engine = new TransferEngine(new BuildingAdapter(), checkpoint);
        });
        Log.info("TRANSACTIONAL_CORE_ROUTER loaded");
    }

    @Override
    public void registerServerCommands(CommandHandler handler) {
        handler.register(
            "router-transfer",
            "<request-id> <source-pos> <destination-pos> <item> <amount>",
            "Transfer stock between two storage buildings.",
            args -> {
                try {
                    TransferEngine.TransferResult result = request(
                        args[0],
                        Integer.parseInt(args[1]),
                        Integer.parseInt(args[2]),
                        args[3],
                        Integer.parseInt(args[4])
                    );
                    Log.info(
                        "ROUTER_TRANSFER request=@ phase=@ successful=@ reason=@",
                        result.requestId(),
                        result.phase(),
                        result.successful(),
                        result.reason()
                    );
                } catch (RuntimeException error) {
                    Log.err("ROUTER_TRANSFER rejected: @", error.getClass().getSimpleName());
                }
            }
        );
    }

    public static TransactionalCoreRouterPlugin instance() {
        if (current == null) {
            throw new IllegalStateException("Plugin is not initialized");
        }
        return current;
    }

    public TransferEngine.TransferResult request(
        String requestId,
        int sourcePos,
        int destinationPos,
        String itemName,
        int amount
    ) {
        ensureEngine();
        if (requestId != null && engine.save().transfers().containsKey(requestId)) {
            return engine.transfer(new TransferEngine.TransferRequest(
                requestId, sourcePos, destinationPos, itemName, amount
            ));
        }
        requireSameTeam(storage(sourcePos), storage(destinationPos));
        baseItem(itemName);
        return engine.transfer(new TransferEngine.TransferRequest(
            requestId,
            sourcePos,
            destinationPos,
            itemName,
            amount
        ));
    }

    public TransferEngine.RecoveryReport recover() {
        ensureEngine();
        return engine.recover();
    }

    public TransferEngine.PersistedState exportState() {
        ensureEngine();
        return engine.save();
    }

    public void importState(TransferEngine.PersistedState state) {
        checkpoint = state;
        engine = new TransferEngine(new BuildingAdapter(), state);
    }

    private void ensureEngine() {
        if (engine == null) {
            engine = new TransferEngine(new BuildingAdapter(), checkpoint);
        }
    }

    private void registerSaveChunk() {
        if (chunkRegistered) {
            return;
        }
        chunkRegistered = true;
        SaveVersion.addCustomChunk(CHUNK_NAME, new CustomChunk() {
            @Override
            public void write(DataOutput output) throws IOException {
                writeState(output, exportState());
            }

            @Override
            public void read(DataInput input) throws IOException {
                try {
                    importState(readState(input));
                } catch (RuntimeException error) {
                    checkpoint = new TransferEngine.PersistedState(Map.of());
                    engine = new TransferEngine(new BuildingAdapter(), checkpoint);
                    Log.err("ROUTER_SAVE rejected corrupt state: @", error.getClass().getSimpleName());
                }
            }
        });
    }

    private static void writeState(
        DataOutput output,
        TransferEngine.PersistedState state
    ) throws IOException {
        output.writeInt(SAVE_VERSION);
        output.writeInt(state.transfers().size());
        for (Map.Entry<String, TransferEngine.PersistedTransfer> entry
            : state.transfers().entrySet()) {
            output.writeUTF(entry.getKey());
            TransferEngine.PersistedTransfer transfer = entry.getValue();
            writeRequest(output, transfer.request());
            output.writeUTF(transfer.phase().name());
            writeSnapshot(output, transfer.sourceBefore());
            writeSnapshot(output, transfer.destinationBefore());
            writeRemoved(output, transfer.removed());
            output.writeUTF(transfer.reason() == null ? "" : transfer.reason());
        }
    }

    private static TransferEngine.PersistedState readState(DataInput input) throws IOException {
        int version = input.readInt();
        if (version != SAVE_VERSION) {
            throw new IOException("Unsupported router save version");
        }
        int count = checkedCount(input.readInt(), 100_000, "transfer count");
        Map<String, TransferEngine.PersistedTransfer> transfers = new LinkedHashMap<>();
        for (int index = 0; index < count; index++) {
            String key = input.readUTF();
            TransferEngine.TransferRequest request = readRequest(input);
            TransferEngine.Phase phase = TransferEngine.Phase.valueOf(input.readUTF());
            TransferEngine.StorageSnapshot source = readSnapshot(input);
            TransferEngine.StorageSnapshot destination = readSnapshot(input);
            TransferEngine.RemovedItems removed = readRemoved(input);
            String reason = input.readUTF();
            if (transfers.put(key, new TransferEngine.PersistedTransfer(
                request, phase, source, destination, removed, reason
            )) != null) {
                throw new IOException("Duplicate transfer ID");
            }
        }
        return new TransferEngine.PersistedState(transfers);
    }

    private static void writeRequest(
        DataOutput output,
        TransferEngine.TransferRequest request
    ) throws IOException {
        output.writeUTF(request.requestId());
        output.writeInt(request.sourcePos());
        output.writeInt(request.destinationPos());
        output.writeUTF(request.itemName());
        output.writeInt(request.amount());
    }

    private static TransferEngine.TransferRequest readRequest(DataInput input) throws IOException {
        return new TransferEngine.TransferRequest(
            input.readUTF(),
            input.readInt(),
            input.readInt(),
            input.readUTF(),
            input.readInt()
        );
    }

    private static void writeSnapshot(
        DataOutput output,
        TransferEngine.StorageSnapshot snapshot
    ) throws IOException {
        output.writeBoolean(snapshot != null);
        if (snapshot == null) {
            return;
        }
        output.writeInt(snapshot.buildingPos());
        output.writeInt(snapshot.items().size());
        for (Map.Entry<String, Integer> entry : snapshot.items().entrySet()) {
            output.writeUTF(entry.getKey());
            output.writeInt(entry.getValue());
        }
    }

    private static TransferEngine.StorageSnapshot readSnapshot(DataInput input) throws IOException {
        if (!input.readBoolean()) {
            return null;
        }
        int buildingPos = input.readInt();
        int count = checkedCount(input.readInt(), 10_000, "snapshot item count");
        Map<String, Integer> items = new LinkedHashMap<>();
        for (int index = 0; index < count; index++) {
            if (items.put(input.readUTF(), input.readInt()) != null) {
                throw new IOException("Duplicate snapshot item");
            }
        }
        return new TransferEngine.StorageSnapshot(buildingPos, items);
    }

    private static void writeRemoved(
        DataOutput output,
        TransferEngine.RemovedItems removed
    ) throws IOException {
        output.writeBoolean(removed != null);
        if (removed == null) {
            return;
        }
        output.writeInt(removed.portions().size());
        for (TransferEngine.ItemPortion portion : removed.portions()) {
            output.writeUTF(portion.itemName());
            output.writeInt(portion.amount());
        }
    }

    private static TransferEngine.RemovedItems readRemoved(DataInput input) throws IOException {
        if (!input.readBoolean()) {
            return null;
        }
        int count = checkedCount(input.readInt(), 10_000, "removed item count");
        List<TransferEngine.ItemPortion> portions = new ArrayList<>();
        for (int index = 0; index < count; index++) {
            portions.add(new TransferEngine.ItemPortion(input.readUTF(), input.readInt()));
        }
        return new TransferEngine.RemovedItems(portions);
    }

    private static int checkedCount(int value, int maximum, String label) throws IOException {
        if (value < 0 || value > maximum) {
            throw new IOException("Invalid " + label);
        }
        return value;
    }

    private static Item baseItem(String name) {
        for (Item item : Vars.content.items()) {
            if (item.name.equals(name) && item.minfo.mod == null) {
                return item;
            }
        }
        throw new IllegalArgumentException("Unknown base-game item");
    }

    private static Building storage(int position) {
        Building building = Vars.world.build(position);
        if (building == null || building.items == null || !building.enabled) {
            throw new IllegalArgumentException("Storage building is unavailable");
        }
        if (building.team == Team.derelict) {
            throw new IllegalArgumentException("Derelict storage is not allowed");
        }
        return building;
    }

    private static void requireSameTeam(Building source, Building destination) {
        if (source.team != destination.team) {
            throw new IllegalArgumentException("Storage buildings must share a team");
        }
    }

    private final class BuildingAdapter implements TransferEngine.Adapter {
        @Override
        public TransferEngine.StorageSnapshot snapshot(int buildingPos) {
            Building building = storage(buildingPos);
            Map<String, Integer> items = new LinkedHashMap<>();
            for (Item item : Vars.content.items()) {
                if (item.minfo.mod == null) {
                    int amount = building.items.get(item);
                    if (amount > 0) {
                        items.put(item.name, amount);
                    }
                }
            }
            return new TransferEngine.StorageSnapshot(buildingPos, items);
        }

        @Override
        public int capacity(int buildingPos, String itemName) {
            Building destination = storage(buildingPos);
            Item item = baseItem(itemName);
            return Math.max(0, destination.block.itemCapacity - destination.items.get(item));
        }

        @Override
        public TransferEngine.RemovedItems remove(
            int buildingPos,
            String itemName,
            int amount
        ) {
            Building source = storage(buildingPos);
            Item item = baseItem(itemName);
            if (source.items.get(item) < amount) {
                throw new IllegalStateException("Source changed after preflight");
            }
            source.items.remove(item, amount);
            return new TransferEngine.RemovedItems(List.of(
                new TransferEngine.ItemPortion(itemName, amount)
            ));
        }

        @Override
        public void add(int buildingPos, TransferEngine.RemovedItems removed) {
            Building destination = storage(buildingPos);
            for (TransferEngine.ItemPortion portion : removed.portions()) {
                Item item = baseItem(portion.itemName());
                if (destination.items.get(item) + portion.amount()
                    > destination.block.itemCapacity) {
                    throw new IllegalStateException("Destination changed after preflight");
                }
            }
            for (TransferEngine.ItemPortion portion : removed.portions()) {
                destination.items.add(baseItem(portion.itemName()), portion.amount());
            }
        }

        @Override
        public void restore(int buildingPos, TransferEngine.StorageSnapshot snapshot) {
            Building building = storage(buildingPos);
            if (snapshot.buildingPos() != buildingPos) {
                throw new IllegalArgumentException("Snapshot position mismatch");
            }
            building.items.clear();
            for (Map.Entry<String, Integer> entry : snapshot.items().entrySet()) {
                building.items.add(baseItem(entry.getKey()), entry.getValue());
            }
        }

        @Override
        public void checkpoint(TransferEngine.PersistedState state) {
            checkpoint = state;
        }
    }
}
