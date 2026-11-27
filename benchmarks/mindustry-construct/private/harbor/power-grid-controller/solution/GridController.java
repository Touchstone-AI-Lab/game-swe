
import java.util.*;

/** A deterministic, thread-agnostic power-grid load shedding state machine. */
public final class GridController {
    public enum Action { SHED, RESTORE, HOLD }

    public record Policy(double shedRatio, double restoreRatio, long minimumOffTicks, long minimumOnTicks) {
        public Policy {
            finite(shedRatio, "shedRatio"); finite(restoreRatio, "restoreRatio");
            if (shedRatio < 0 || shedRatio > 1 || restoreRatio < 0 || restoreRatio > 1 || shedRatio >= restoreRatio)
                throw new IllegalArgumentException("ratios must satisfy 0 <= shedRatio < restoreRatio <= 1");
            if (minimumOffTicks < 0 || minimumOnTicks < 0) throw new IllegalArgumentException("negative minimum time");
        }
    }

    public record Load(int buildingPos, int priority, double demand, boolean enabled) {
        public Load { finite(demand, "demand"); if (demand < 0) throw new IllegalArgumentException("negative demand"); }
    }

    public record GridSample(long gridId, long revision, long tick, double production,
                             double batteryStored, double batteryCapacity, List<Load> loads) {
        public GridSample {
            if (revision < 0 || tick < 0) throw new IllegalArgumentException("negative revision/tick");
            finite(production, "production"); finite(batteryStored, "batteryStored"); finite(batteryCapacity, "batteryCapacity");
            if (production < 0 || batteryStored < 0 || batteryCapacity < 0 || batteryStored > batteryCapacity)
                throw new IllegalArgumentException("invalid energy");
            loads = immutableLoads(loads);
        }
    }

    public record LoadAction(int buildingPos, Action action) {
        public LoadAction { Objects.requireNonNull(action, "action"); if (action == Action.HOLD) throw new IllegalArgumentException("HOLD is not a load mutation"); }
    }

    public record Decision(long gridId, long revision, long tick, Action action, List<LoadAction> actions) {
        public Decision {
            Objects.requireNonNull(action, "action");
            actions = List.copyOf(Objects.requireNonNull(actions, "actions"));
            Action derived = aggregate(actions);
            if (action != derived) throw new IllegalArgumentException("action does not match actions");
        }
        public Decision(long gridId, long revision, long tick, List<LoadAction> actions) {
            this(gridId, revision, tick, aggregate(actions), actions);
        }
        public static Decision hold(long id, long revision, long tick) { return new Decision(id, revision, tick, Action.HOLD, List.of()); }
    }

    /** Persisted per-load switching history. */
    public record LoadState(Load load, long changedTick) {
        public LoadState { Objects.requireNonNull(load, "load"); if (changedTick < 0) throw new IllegalArgumentException("negative changedTick"); }
    }

    public record GridState(long gridId, long revision, long tick, double production,
                            double batteryStored, double batteryCapacity, List<LoadState> loads) {
        public GridState {
            if (revision < 0 || tick < 0) throw new IllegalArgumentException("negative revision/tick");
            finite(production, "production"); finite(batteryStored, "batteryStored"); finite(batteryCapacity, "batteryCapacity");
            if (production < 0 || batteryStored < 0 || batteryCapacity < 0 || batteryStored > batteryCapacity)
                throw new IllegalArgumentException("invalid energy");
            Objects.requireNonNull(loads, "loads");
            ArrayList<LoadState> copy = new ArrayList<>(loads);
            copy.sort(Comparator.comparingInt(x -> x.load().buildingPos()));
            int prior = 0; boolean first = true;
            for (LoadState state : copy) {
                Objects.requireNonNull(state, "load state");
                if (state.changedTick() > tick) throw new IllegalArgumentException("change is in the future");
                int p = state.load().buildingPos();
                if (!first && p == prior) throw new IllegalArgumentException("duplicate building");
                first = false; prior = p;
            }
            loads = List.copyOf(copy);
        }
        public GridState(long gridId, long revision, long tick, List<LoadState> loads) {
            this(gridId, revision, tick, 0, 0, 0, loads);
        }
    }

    public record Snapshot(List<GridState> grids) {
        public Snapshot { grids = sortedGrids(grids); }
    }

    public record PersistedState(List<GridState> grids, List<Long> removedGridIds) {
        public PersistedState {
            grids = sortedGrids(grids);
            Objects.requireNonNull(removedGridIds, "removedGridIds");
            TreeSet<Long> ids = new TreeSet<>();
            for (Long id : removedGridIds) if (id == null || !ids.add(id)) throw new IllegalArgumentException("invalid/duplicate removed grid");
            for (GridState grid : grids) if (ids.contains(grid.gridId())) throw new IllegalArgumentException("live grid is tombstoned");
            removedGridIds = List.copyOf(ids);
        }
        public PersistedState(List<GridState> grids) { this(grids, List.of()); }
    }

    private static final class MutableGrid {
        long id, revision, tick; double production, stored, capacity;
        final TreeMap<Integer, MutableLoad> loads = new TreeMap<>();
        GridSample lastInput; Decision lastDecision;
    }
    private static final class MutableLoad {
        int pos, priority; double demand; boolean enabled; long changed;
        MutableLoad(Load l, long changed) { pos=l.buildingPos(); priority=l.priority(); demand=l.demand(); enabled=l.enabled(); this.changed=changed; }
        Load load() { return new Load(pos, priority, demand, enabled); }
    }

    private final Policy policy;
    private final TreeMap<Long, MutableGrid> grids = new TreeMap<>();
    private final TreeSet<Long> removed = new TreeSet<>();

    public GridController(Policy policy) { this.policy = Objects.requireNonNull(policy, "policy"); }
    public GridController(Policy policy, PersistedState state) {
        this(policy); Objects.requireNonNull(state, "state");
        removed.addAll(state.removedGridIds());
        for (GridState gs : state.grids()) {
            if (grids.put(gs.gridId(), fromState(gs)) != null) throw new IllegalArgumentException("duplicate grid");
        }
    }
    public Policy policy() { return policy; }

    public synchronized Decision observe(GridSample sample) {
        validateSample(sample); Objects.requireNonNull(sample, "sample");
        if (removed.contains(sample.gridId())) throw new IllegalArgumentException("removed grid");
        MutableGrid old = grids.get(sample.gridId());
        if (old != null) {
            if (sample.tick() < old.tick || sample.revision() < old.revision) throw new IllegalArgumentException("stale sample");
            if (sample.tick() == old.tick && sample.revision() == old.revision) {
                if (sample.equals(old.lastInput) && old.lastDecision != null) return old.lastDecision;
                throw new IllegalArgumentException("conflicting duplicate sample");
            }
        }
        MutableGrid next = copy(old, sample.gridId());
        reconcile(next, sample);
        Decision decision = decide(next, sample, old == null);
        next.lastInput = sample; next.lastDecision = decision;
        grids.put(sample.gridId(), next);
        return decision;
    }

    public synchronized Decision split(long parentGridId, List<GridSample> children, long tick) {
        if (tick < 0) throw new IllegalArgumentException("negative tick");
        Objects.requireNonNull(children, "children");
        MutableGrid parent = grids.get(parentGridId);
        if (parent == null || removed.contains(parentGridId) || tick < parent.tick) throw new IllegalArgumentException("unknown/stale parent");
        HashSet<Long> childIds = new HashSet<>(); HashSet<Integer> buildings = new HashSet<>();
        for (GridSample child : children) {
            validateSample(child);
            if (child.tick() != tick || !childIds.add(child.gridId()) || (removed.contains(child.gridId()) && child.gridId() != parentGridId)) throw new IllegalArgumentException("invalid child");
            for (Load l : child.loads()) if (!buildings.add(l.buildingPos())) throw new IllegalArgumentException("building in multiple children");
        }
        ArrayList<Decision> decisions = new ArrayList<>();
        TreeMap<Long, MutableGrid> replacements = new TreeMap<>();
        for (GridSample child : children) {
            MutableGrid g = new MutableGrid(); g.id=child.gridId();
            for (Load l : child.loads()) {
                MutableLoad history = parent.loads.get(l.buildingPos());
                if (history != null) g.loads.put(l.buildingPos(), cloneLoad(history));
            }
            reconcile(g, child); Decision d=decide(g, child, false); g.lastInput=child; g.lastDecision=d;
            replacements.put(g.id,g); decisions.add(d);
        }
        grids.remove(parentGridId);
        if (replacements.containsKey(parentGridId)) removed.remove(parentGridId); else removed.add(parentGridId);
        grids.putAll(replacements);
        return combine(parentGridId, tick, decisions);
    }

    public synchronized Decision merge(List<Long> sourceGridIds, GridSample merged, long tick) {
        Objects.requireNonNull(sourceGridIds, "sourceGridIds"); validateSample(merged);
        if (tick < 0 || merged.tick() != tick || sourceGridIds.isEmpty()) throw new IllegalArgumentException("invalid merge");
        HashSet<Long> ids = new HashSet<>(); TreeMap<Integer, MutableLoad> histories = new TreeMap<>();
        for (Long id : sourceGridIds) {
            if (id == null || !ids.add(id)) throw new IllegalArgumentException("duplicate source");
            MutableGrid g=grids.get(id); if(g==null || removed.contains(id) || tick<g.tick) throw new IllegalArgumentException("unknown/stale source");
            for(MutableLoad l:g.loads.values()) {
                MutableLoad prior=histories.get(l.pos);
                if(prior==null || l.changed>prior.changed) histories.put(l.pos,cloneLoad(l));
            }
        }
        if (removed.contains(merged.gridId()) && !ids.contains(merged.gridId())) throw new IllegalArgumentException("removed destination");
        MutableGrid g=new MutableGrid(); g.id=merged.gridId(); g.loads.putAll(histories); reconcile(g,merged);
        Decision d=decide(g,merged,false); g.lastInput=merged; g.lastDecision=d;
        for(long id:ids){ grids.remove(id); if(id!=merged.gridId()) removed.add(id); }
        removed.remove(merged.gridId()); grids.put(merged.gridId(),g); return d;
    }

    public synchronized Decision removeGrid(long gridId, long tick) {
        if(tick<0) throw new IllegalArgumentException("negative tick"); MutableGrid g=grids.get(gridId);
        if(g!=null && tick<g.tick) throw new IllegalArgumentException("stale removal");
        grids.remove(gridId); removed.add(gridId); return Decision.hold(gridId, g==null?0:g.revision, tick);
    }

    public synchronized Snapshot snapshot() { return new Snapshot(states()); }
    public synchronized PersistedState save() { return new PersistedState(states(), new ArrayList<>(removed)); }

    private List<GridState> states(){ ArrayList<GridState> out=new ArrayList<>(); for(MutableGrid g:grids.values()) out.add(toState(g)); return List.copyOf(out); }

    private void reconcile(MutableGrid g, GridSample s) {
        TreeMap<Integer,MutableLoad> next=new TreeMap<>();
        for(Load l:s.loads()) {
            MutableLoad m=g.loads.get(l.buildingPos());
            if(m==null) m=new MutableLoad(l, Math.max(0L, s.tick() - (l.enabled() ? policy.minimumOnTicks() : policy.minimumOffTicks())));
            else {
                m=cloneLoad(m); m.priority=l.priority(); m.demand=l.demand();
                if(m.enabled!=l.enabled()){m.enabled=l.enabled();m.changed=s.tick();}
            }
            next.put(m.pos,m);
        }
        g.loads.clear();g.loads.putAll(next);g.id=s.gridId();g.revision=s.revision();g.tick=s.tick();g.production=s.production();g.stored=s.batteryStored();g.capacity=s.batteryCapacity();
    }

    private Decision decide(MutableGrid g, GridSample s, boolean firstObservation) {
        ArrayList<LoadAction> actions=new ArrayList<>();
        double enabledDemand=0; for(MutableLoad l:g.loads.values())if(l.enabled)enabledDemand+=l.demand;
        double ratio=s.batteryCapacity()==0 ? (s.production()+1e-12>=enabledDemand?1d:0d) : s.batteryStored()/s.batteryCapacity();
        if(ratio<=policy.shedRatio() && enabledDemand>s.production()+1e-9) {
            ArrayList<MutableLoad> candidates=new ArrayList<>();
            for(MutableLoad l:g.loads.values())if(l.enabled && (firstObservation || elapsed(s.tick(),l.changed)>=policy.minimumOnTicks()))candidates.add(l);
            candidates.sort(Comparator.comparingInt((MutableLoad l)->l.priority).thenComparingInt(l->l.pos));
            for(MutableLoad l:candidates){ if(enabledDemand<=s.production()+1e-9)break; l.enabled=false;l.changed=s.tick();enabledDemand-=l.demand;actions.add(new LoadAction(l.pos,Action.SHED)); }
        } else if(ratio>=policy.restoreRatio()) {
            ArrayList<MutableLoad> candidates=new ArrayList<>();
            for(MutableLoad l:g.loads.values())if(!l.enabled && (firstObservation || elapsed(s.tick(),l.changed)>=policy.minimumOffTicks()))candidates.add(l);
            candidates.sort(Comparator.comparingInt((MutableLoad l)->l.priority).reversed().thenComparingInt(l->l.pos));
            for(MutableLoad l:candidates){ if(enabledDemand+l.demand<=s.production()+1e-9){l.enabled=true;l.changed=s.tick();enabledDemand+=l.demand;actions.add(new LoadAction(l.pos,Action.RESTORE));} }
        }
        return new Decision(s.gridId(),s.revision(),s.tick(),actions);
    }

    private static long elapsed(long now,long then){return now>=then?now-then:0;}
    private static Decision combine(long id,long tick,List<Decision> ds){ArrayList<LoadAction>a=new ArrayList<>();long rev=0;for(Decision d:ds){a.addAll(d.actions());rev=Math.max(rev,d.revision());}a.sort(Comparator.comparingInt(LoadAction::buildingPos));return new Decision(id,rev,tick,a);}
    private static MutableGrid copy(MutableGrid old,long id){MutableGrid g=new MutableGrid();g.id=id;if(old!=null){g.revision=old.revision;g.tick=old.tick;g.production=old.production;g.stored=old.stored;g.capacity=old.capacity;for(MutableLoad l:old.loads.values())g.loads.put(l.pos,cloneLoad(l));g.lastInput=old.lastInput;g.lastDecision=old.lastDecision;}return g;}
    private static MutableLoad cloneLoad(MutableLoad l){MutableLoad n=new MutableLoad(l.load(),l.changed);return n;}
    private static MutableGrid fromState(GridState s){MutableGrid g=new MutableGrid();g.id=s.gridId();g.revision=s.revision();g.tick=s.tick();g.production=s.production();g.stored=s.batteryStored();g.capacity=s.batteryCapacity();for(LoadState ls:s.loads())g.loads.put(ls.load().buildingPos(),new MutableLoad(ls.load(),ls.changedTick()));return g;}
    private static GridState toState(MutableGrid g){ArrayList<LoadState> ls=new ArrayList<>();for(MutableLoad l:g.loads.values())ls.add(new LoadState(l.load(),l.changed));return new GridState(g.id,g.revision,g.tick,g.production,g.stored,g.capacity,ls);}
    private static void validateSample(GridSample s){Objects.requireNonNull(s,"sample");}
    private static List<Load> immutableLoads(List<Load> loads){Objects.requireNonNull(loads,"loads");ArrayList<Load> c=new ArrayList<>(loads);c.sort(Comparator.comparingInt(Load::buildingPos));Integer p=null;for(Load l:c){Objects.requireNonNull(l,"load");if(p!=null&&p==l.buildingPos())throw new IllegalArgumentException("duplicate building");p=l.buildingPos();}return List.copyOf(c);}
    private static List<GridState> sortedGrids(List<GridState> grids){Objects.requireNonNull(grids,"grids");ArrayList<GridState> c=new ArrayList<>(grids);c.sort(Comparator.comparingLong(GridState::gridId));Long p=null;for(GridState g:c){Objects.requireNonNull(g,"grid");if(p!=null&&p==g.gridId())throw new IllegalArgumentException("duplicate grid");p=g.gridId();}return List.copyOf(c);}
    private static Action aggregate(List<LoadAction> actions){Objects.requireNonNull(actions,"actions");if(actions.isEmpty())return Action.HOLD;Action a=Objects.requireNonNull(actions.get(0),"action").action();for(LoadAction x:actions)if(Objects.requireNonNull(x,"action").action()!=a)throw new IllegalArgumentException("mixed decision actions");return a;}
    private static void finite(double v,String n){if(!Double.isFinite(v))throw new IllegalArgumentException(n+" is not finite");}
}
