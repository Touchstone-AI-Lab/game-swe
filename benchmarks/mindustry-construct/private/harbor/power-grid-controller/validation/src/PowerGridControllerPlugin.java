
import arc.Events;
import mindustry.Vars;
import mindustry.game.EventType;
import mindustry.gen.Building;
import mindustry.gen.Groups;
import mindustry.io.SaveFileReader;
import mindustry.io.SaveVersion;
import mindustry.mod.Plugin;

import java.io.*;
import java.lang.reflect.*;
import java.util.*;

/** Dedicated-server adapter. All world reads and mutations occur from Trigger.update. */
public final class PowerGridControllerPlugin extends Plugin {
    private static final String chunkName = "mindustry-power-grid-controller-v1";
    private static volatile PowerGridControllerPlugin instance;
    private volatile GridController controller;
    private GridController.PersistedState pendingState;
    private final Map<Long, Set<Integer>> previousMembership = new HashMap<>();
    private long revision;

    public PowerGridControllerPlugin() {
        instance = this;
        controller = new GridController(new GridController.Policy(0.20, 0.80, 60, 60));
    }

    public static PowerGridControllerPlugin instance() { return instance; }
    public GridController controller() { return controller; }
    public synchronized GridController.PersistedState exportState() { return controller.save(); }
    public synchronized void importState(GridController.PersistedState state) {
        controller = new GridController(controller.policy(), Objects.requireNonNull(state, "state"));
        previousMembership.clear();
    }

    @Override public void init() {
        instance = this;
        SaveVersion.addCustomChunk(chunkName, new SaveFileReader.CustomChunk() {
            @Override public void write(DataOutput output) throws IOException { writeState(output, exportState()); }
            @Override public void read(DataInput input) throws IOException { pendingState = readState(input); }
        });
        Events.on(EventType.ResetEvent.class, e -> clearWorld());
        Events.on(EventType.WorldLoadEvent.class, e -> {
            previousMembership.clear(); revision = 0;
            if (pendingState != null) { importState(pendingState); pendingState = null; }
        });
        Events.run(EventType.Trigger.update, this::update);
    }

    private void clearWorld() {
        controller = new GridController(controller.policy());
        pendingState = null; previousMembership.clear(); revision = 0;
    }

    private void update() {
        if (Vars.state == null || !Vars.state.isGame()) return;
        // Group by the actual PowerGraph object, never by client-provided data.
        IdentityHashMap<Object, ArrayList<Building>> grouped = new IdentityHashMap<>();
        Groups.build.each(b -> {
            Object graph = graphOf(b);
            if (graph != null) grouped.computeIfAbsent(graph, ignored -> new ArrayList<>()).add(b);
        });
        ArrayList<GraphReading> readings = new ArrayList<>();
        long tick = Math.max(0L, (long)Vars.state.tick);
        for (Map.Entry<Object, ArrayList<Building>> entry : grouped.entrySet()) {
            GraphReading reading = readGraph(entry.getKey(), entry.getValue(), tick);
            if (!reading.members.isEmpty()) readings.add(reading);
        }
        readings.sort(Comparator.comparingLong(r -> r.id));

        Map<Long, Set<Integer>> current = new HashMap<>();
        for (GraphReading r : readings) current.put(r.id, r.members);
        reconcileTopology(readings, current, tick);
        previousMembership.clear(); previousMembership.putAll(current);
    }

    private void reconcileTopology(List<GraphReading> readings, Map<Long, Set<Integer>> current, long tick) {
        Map<Long, GraphReading> byId = new HashMap<>();
        for (GraphReading r : readings) byId.put(r.id, r);
        Map<Long, Set<Long>> oldToNew = new HashMap<>();
        Map<Long, Set<Long>> newToOld = new HashMap<>();
        for (Map.Entry<Long, Set<Integer>> old : previousMembership.entrySet()) {
            for (GraphReading r : readings) {
                if (intersects(old.getValue(), r.members)) {
                    oldToNew.computeIfAbsent(old.getKey(), x -> new TreeSet<>()).add(r.id);
                    newToOld.computeIfAbsent(r.id, x -> new TreeSet<>()).add(old.getKey());
                }
            }
        }
        Set<Long> handledOld = new HashSet<>(), handledNew = new HashSet<>();

        // Handle unambiguous splits first. The core transfers each building's lock exactly once.
        for (Map.Entry<Long, Set<Long>> e : oldToNew.entrySet()) {
            if (e.getValue().size() <= 1) continue;
            boolean pure = true;
            for (long nid : e.getValue()) if (newToOld.getOrDefault(nid, Set.of()).size() != 1) pure = false;
            if (!pure) continue;
            ArrayList<GridController.GridSample> children = new ArrayList<>();
            for (long nid : e.getValue()) children.add(byId.get(nid).sample);
            try {
                apply(controller.split(e.getKey(), children, tick));
                handledOld.add(e.getKey()); handledNew.addAll(e.getValue());
            } catch (IllegalArgumentException ignored) { }
        }

        // Handle unambiguous merges, preserving the most restrictive per-building history.
        for (Map.Entry<Long, Set<Long>> e : newToOld.entrySet()) {
            if (handledNew.contains(e.getKey()) || e.getValue().size() <= 1) continue;
            boolean pure = true;
            for (long oid : e.getValue()) if (oldToNew.getOrDefault(oid, Set.of()).size() != 1 || handledOld.contains(oid)) pure = false;
            if (!pure) continue;
            try {
                apply(controller.merge(new ArrayList<>(e.getValue()), byId.get(e.getKey()).sample, tick));
                handledNew.add(e.getKey()); handledOld.addAll(e.getValue());
            } catch (IllegalArgumentException ignored) { }
        }

        // Unchanged graphs and newly created independent graphs.
        for (GraphReading r : readings) if (!handledNew.contains(r.id)) {
            Set<Long> origins = newToOld.getOrDefault(r.id, Set.of());
            if (origins.size() <= 1) {
                try { apply(controller.observe(r.sample)); handledNew.add(r.id); }
                catch (IllegalArgumentException ignored) { }
            }
        }
        for (Long old : previousMembership.keySet()) {
            if (!handledOld.contains(old) && !oldToNew.containsKey(old)) {
                try { controller.removeGrid(old, tick); } catch (IllegalArgumentException ignored) { }
            }
        }
    }

    private static boolean intersects(Set<Integer> a, Set<Integer> b) {
        Set<Integer> small = a.size() <= b.size() ? a : b, large = small == a ? b : a;
        for (int value : small) if (large.contains(value)) return true;
        return false;
    }

    private void apply(GridController.Decision decision) {
        for (GridController.LoadAction action : decision.actions()) {
            Building b = Vars.world.build(action.buildingPos());
            if (b == null || !isControllableConsumer(b)) continue;
            boolean enabled = action.action() == GridController.Action.RESTORE;
            if (b.enabled != enabled) b.enabled = enabled;
        }
    }

    private GraphReading readGraph(Object graph, List<Building> buildings, long tick) {
        buildings.sort(Comparator.comparingInt(Building::pos));
        TreeSet<Integer> members = new TreeSet<>();
        ArrayList<GridController.Load> loads = new ArrayList<>();
        for (Building b : buildings) {
            members.add(b.pos());
            if (isControllableConsumer(b)) {
                double demand = Math.max(0d, requestedPower(b));
                loads.add(new GridController.Load(b.pos(), priority(b), demand, b.enabled));
            }
        }
        long id = members.isEmpty() ? 0 : Integer.toUnsignedLong(members.first());
        double production = nonnegative(number(graph, "getLastPowerProduced", "getPowerProduced", "getProduction"));
        double stored = nonnegative(number(graph, "getBatteryStored"));
        double capacity = nonnegative(number(graph, "getBatteryCapacity"));
        if (stored > capacity) capacity = stored;
        GridController.GridSample sample = new GridController.GridSample(id, ++revision, tick,
                production, stored, capacity, loads);
        return new GraphReading(id, Set.copyOf(members), sample);
    }

    private static Object graphOf(Building b) {
        if (b == null || b.power == null) return null;
        try { return b.power.graph; } catch (Throwable ignored) { return null; }
    }

    private static boolean isControllableConsumer(Building b) {
        if (b == null || b.block == null || b.power == null) return false;
        String cn = b.block.getClass().getName();
        // Never touch infrastructure or power producers/storage.
        if (cn.contains("PowerGenerator") || cn.contains("Battery") || cn.contains("PowerNode") ||
            cn.contains("PowerSource") || cn.contains("CoreBlock") || cn.contains("NuclearReactor") ||
            cn.contains("ImpactReactor") || cn.contains("ConsumeGenerator")) return false;
        // Blocks supplied by mods have non-null mod metadata. Reflection keeps this compatible
        // with metadata layout changes while defaulting safely to "not controllable" on errors.
        try {
            Object minfo = field(b.block, "minfo");
            if (minfo != null && field(minfo, "mod") != null) return false;
        } catch (Throwable ignored) { return false; }
        return requestedPower(b) > 0d;
    }

    private static int priority(Building b) {
        // Stable server-derived priority. Bigger blocks are treated as more important; block ID
        // provides deterministic differentiation without accepting client configuration.
        int size = b.block.size;
        return size * 1_000_000 - b.block.id;
    }

    private static double requestedPower(Building b) {
        try {
            Object consumer = field(b.block, "consPower");
            if (consumer == null) return 0d;
            for (Method m : consumer.getClass().getMethods()) {
                if (m.getName().equals("requestedPower") && m.getParameterCount() == 1)
                    return ((Number)m.invoke(consumer, b)).doubleValue();
            }
            Object usage = field(consumer, "usage");
            return usage instanceof Number n ? n.doubleValue() : 0d;
        } catch (Throwable ignored) { return 0d; }
    }

    private record GraphReading(long id, Set<Integer> members, GridController.GridSample sample) {}

    private static Object field(Object target, String name) throws ReflectiveOperationException {
        Class<?> c = target.getClass();
        while (c != null) {
            try { Field f=c.getDeclaredField(name); f.setAccessible(true); return f.get(target); }
            catch (NoSuchFieldException e) { c=c.getSuperclass(); }
        }
        throw new NoSuchFieldException(name);
    }
    private static double number(Object target, String... methods) {
        for (String name : methods) try {
            Method m=target.getClass().getMethod(name); Object v=m.invoke(target);
            if(v instanceof Number n && Double.isFinite(n.doubleValue())) return n.doubleValue();
        } catch(Throwable ignored) { }
        return 0d;
    }
    private static double nonnegative(double value) { return Double.isFinite(value) && value > 0 ? value : 0d; }

    private static void writeState(DataOutput out, GridController.PersistedState state) throws IOException {
        out.writeInt(1); out.writeInt(state.grids().size());
        for (GridController.GridState g : state.grids()) {
            out.writeLong(g.gridId()); out.writeLong(g.revision()); out.writeLong(g.tick());
            out.writeDouble(g.production()); out.writeDouble(g.batteryStored()); out.writeDouble(g.batteryCapacity());
            out.writeInt(g.loads().size());
            for (GridController.LoadState ls : g.loads()) {
                GridController.Load l=ls.load(); out.writeInt(l.buildingPos()); out.writeInt(l.priority());
                out.writeDouble(l.demand()); out.writeBoolean(l.enabled()); out.writeLong(ls.changedTick());
            }
        }
        out.writeInt(state.removedGridIds().size()); for(long id:state.removedGridIds())out.writeLong(id);
    }

    private static GridController.PersistedState readState(DataInput in) throws IOException {
        try {
            if(in.readInt()!=1) throw new IOException("unsupported controller chunk");
            int count=bounded(in.readInt()); ArrayList<GridController.GridState> grids=new ArrayList<>(count);
            for(int i=0;i<count;i++){
                long id=in.readLong(), rev=in.readLong(), tick=in.readLong(); double p=in.readDouble(),s=in.readDouble(),c=in.readDouble();
                int n=bounded(in.readInt()); ArrayList<GridController.LoadState> loads=new ArrayList<>(n);
                for(int j=0;j<n;j++){GridController.Load l=new GridController.Load(in.readInt(),in.readInt(),in.readDouble(),in.readBoolean());loads.add(new GridController.LoadState(l,in.readLong()));}
                grids.add(new GridController.GridState(id,rev,tick,p,s,c,loads));
            }
            int n=bounded(in.readInt());ArrayList<Long> removed=new ArrayList<>(n);for(int i=0;i<n;i++)removed.add(in.readLong());
            return new GridController.PersistedState(grids,removed);
        } catch (IllegalArgumentException e) { throw new IOException("malformed controller state",e); }
    }
    private static int bounded(int n)throws IOException{if(n<0||n>1_000_000)throw new IOException("invalid count");return n;}
}
