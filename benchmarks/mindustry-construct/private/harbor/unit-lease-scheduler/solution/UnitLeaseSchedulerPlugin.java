
import arc.Core;
import arc.Events;
import mindustry.Vars;
import mindustry.ai.types.CargoAI;
import mindustry.ai.types.MinerAI;
import mindustry.ai.types.RepairAI;
import mindustry.content.UnitTypes;
import mindustry.game.EventType;
import mindustry.gen.Groups;
import mindustry.gen.Unit;
import mindustry.io.SaveFileReader;
import mindustry.io.SaveVersion;
import mindustry.mod.Plugin;
import mindustry.type.Item;

import java.io.*;
import java.util.*;

/** Server-side adapter for {@link LeaseScheduler}. */
public final class UnitLeaseSchedulerPlugin extends Plugin {
    private static final String CHUNK = "support-unit-leases-state";
    private static final LeaseScheduler.Policy DEFAULT_POLICY = new LeaseScheduler.Policy(300, 600, 100);
    private static volatile UnitLeaseSchedulerPlugin instance;

    private LeaseScheduler scheduler;
    private LeaseScheduler.PersistedState pendingState;
    private final Map<Integer, Long> revisions = new HashMap<>();
    private long logicalTick;

    public UnitLeaseSchedulerPlugin(){
        instance=this;
        scheduler=new LeaseScheduler(DEFAULT_POLICY);
        SaveVersion.addCustomChunk(CHUNK, new StateChunk());
        Events.on(EventType.UnitCreateEvent.class, e -> onApp(() -> reconcile(e.unit)));
        Events.on(EventType.UnitDestroyEvent.class, e -> onApp(() -> remove(e.unit)));
        Events.on(EventType.UnitChangeEvent.class, e -> onApp(() -> reconcile(e.unit)));
        Events.on(EventType.ResetEvent.class, e -> onApp(this::reset));
        Events.on(EventType.WorldLoadEvent.class, e -> onApp(this::worldLoaded));
        Events.run(EventType.Trigger.update, this::update);
    }

    public static UnitLeaseSchedulerPlugin instance(){ return instance; }
    public LeaseScheduler scheduler(){ return scheduler; }
    public LeaseScheduler.PersistedState exportState(){ return scheduler.save(); }
    public void importState(LeaseScheduler.PersistedState state){
        Objects.requireNonNull(state,"state");
        onApp(() -> { pendingState=state; recoverIfPossible(); });
    }

    private void onApp(Runnable action){
        if(Core.app == null || Core.app.isOnMainThread()) action.run();
        else Core.app.post(action);
    }

    private long now(){
        long game=Vars.state == null ? 0 : Math.max(0,(long)Vars.state.tick);
        logicalTick=Math.max(logicalTick,game);
        return logicalTick;
    }

    private void reset(){
        scheduler=new LeaseScheduler(DEFAULT_POLICY);
        pendingState=null; revisions.clear(); logicalTick=0;
    }

    private void worldLoaded(){
        revisions.clear();
        recoverIfPossible();
        reconcileAll();
    }

    private void recoverIfPossible(){
        if(pendingState==null || Groups.unit==null) return;
        LeaseScheduler.PersistedState saved=pendingState;
        // The core restores only units that really exist now; no saved phantom can retain a lease.
        ArrayList<LeaseScheduler.UnitRecord> actual=new ArrayList<>();
        for(Unit u:Groups.unit){
            LeaseScheduler.UnitKind k=kind(u);
            if(k!=null && validServerUnit(u)) actual.add(record(u, saved.lastTick()));
        }
        actual.sort(Comparator.comparingInt(LeaseScheduler.UnitRecord::unitId));
        LeaseScheduler.PersistedState filtered=new LeaseScheduler.PersistedState(
                saved.policy(),saved.lastTick(),saved.nextLeaseSequence(),saved.tasks(),
                saved.taskStatuses(),actual,saved.leases());
        scheduler=new LeaseScheduler(saved.policy(),filtered);
        logicalTick=Math.max(logicalTick,Math.max(0,saved.lastTick()));
        for(var u:actual) revisions.put(u.unitId(),u.revision());
        pendingState=null;
    }

    private void reconcileAll(){
        if(Groups.unit==null)return;
        HashSet<Integer> seen=new HashSet<>();
        for(Unit u:Groups.unit){ if(kind(u)!=null){seen.add(u.id());reconcile(u);} }
        for(LeaseScheduler.UnitRecord r:scheduler.snapshot(now()).units()) if(!seen.contains(r.unitId())) scheduler.removeUnit(r.unitId(),now());
    }

    private void reconcile(Unit unit){
        if(unit==null)return;
        LeaseScheduler.UnitKind kind=kind(unit);
        if(kind==null || !validServerUnit(unit)){ remove(unit); return; }
        long revision=revisions.merge(unit.id(),1L,Long::sum);
        scheduler.registerUnit(new LeaseScheduler.UnitRecord(unit.id(),kind,unit.team().id,true,revision));
    }

    private LeaseScheduler.UnitRecord record(Unit u,long base){
        long rev=Math.max(0,revisions.getOrDefault(u.id(),base < 0 ? 0 : base));
        return new LeaseScheduler.UnitRecord(u.id(),kind(u),u.team().id,true,rev);
    }

    private void remove(Unit unit){
        if(unit==null)return;
        revisions.merge(unit.id(),1L,Long::sum);
        scheduler.removeUnit(unit.id(),now());
    }

    private void update(){
        if(Vars.net != null && Vars.net.client()) return;
        logicalTick++;
        recoverIfPossible();
        reconcileLeases();
        LeaseScheduler.TickReport report=scheduler.tick(now());
        for(LeaseScheduler.Lease lease:report.assigned()) apply(lease);
    }

    private void reconcileLeases(){
        long tick=now();
        for(LeaseScheduler.Lease lease:scheduler.snapshot(tick).leases()){
            Unit u=resolve(lease.unitId());
            LeaseScheduler.Task task=findTask(lease.taskId());
            if(u==null || task==null || !LeaseScheduler.compatible(kind(u),task.kind())){
                scheduler.removeUnit(lease.unitId(),tick);
            }else{
                scheduler.heartbeat(lease.leaseId(),lease.unitId(),tick);
                if(!controllerMatches(u,task.kind())) apply(lease);
            }
        }
    }

    private LeaseScheduler.Task findTask(String id){
        for(LeaseScheduler.Task t:scheduler.snapshot(now()).tasks()) if(t.taskId().equals(id)) return t;
        return null;
    }

    private Unit resolve(int id){
        if(Groups.unit==null)return null;
        Unit u=Groups.unit.getByID(id);
        return validServerUnit(u) && kind(u)!=null ? u:null;
    }

    private boolean validServerUnit(Unit u){
        return u!=null && u.isAdded() && !u.dead() && u.health()>0f && u.team()!=null && u.type()!=null &&
                !u.isPlayer() && u.controller()!=null;
    }

    private LeaseScheduler.UnitKind kind(Unit u){
        if(u==null)return null;
        if(u.type()==UnitTypes.mono)return LeaseScheduler.UnitKind.MONO;
        if(u.type()==UnitTypes.poly)return LeaseScheduler.UnitKind.POLY;
        if(u.type()==UnitTypes.mega)return LeaseScheduler.UnitKind.MEGA;
        return null;
    }

    private boolean controllerMatches(Unit u,LeaseScheduler.TaskKind kind){
        return switch(kind){
            case MINE -> u.controller() instanceof MinerAI;
            case REPAIR -> u.controller() instanceof RepairAI;
            case TRANSPORT -> u.controller() instanceof CargoAI;
        };
    }

    private void apply(LeaseScheduler.Lease lease){
        Unit u=resolve(lease.unitId());
        LeaseScheduler.Task task=findTask(lease.taskId());
        if(u==null || task==null || u.team().id != scheduler.snapshot(now()).units().stream()
                .filter(x->x.unitId()==u.id()).mapToInt(LeaseScheduler.UnitRecord::teamId).findFirst().orElse(-1)) return;
        switch(task.kind()){
            case MINE -> {
                MinerAI ai=new MinerAI();
                Item item=Vars.content == null ? null : Vars.content.item(task.itemName());
                if(item==null)return;
                ai.targetItem=item; u.controller(ai);
            }
            case REPAIR -> u.controller(new RepairAI());
            case TRANSPORT -> u.controller(new CargoAI());
        }
    }

    private final class StateChunk implements SaveFileReader.CustomChunk {
        @Override public void write(DataOutput out) throws IOException { writeState(out,exportState()); }
        @Override public void read(DataInput in) throws IOException {
            LeaseScheduler.PersistedState state=readState(in);
            pendingState=state; // Save loading already occurs on the application thread.
        }
    }

    private static void writeState(DataOutput out,LeaseScheduler.PersistedState s)throws IOException{
        out.writeInt(1);
        out.writeLong(s.policy().leaseTicks());out.writeLong(s.policy().agingTicks());out.writeInt(s.policy().maximumPriority());
        out.writeLong(s.lastTick());out.writeLong(s.nextLeaseSequence());
        out.writeInt(s.tasks().size());
        for(LeaseScheduler.Task t:s.tasks()){
            out.writeUTF(t.taskId());out.writeByte(t.kind().ordinal());out.writeInt(t.priority());out.writeLong(t.createdTick());
            out.writeInt(t.targetPos());out.writeUTF(t.itemName());out.writeInt(t.amount());out.writeByte(s.taskStatuses().get(t.taskId()).ordinal());
        }
        out.writeInt(s.units().size());
        for(var u:s.units()){out.writeInt(u.unitId());out.writeByte(u.kind().ordinal());out.writeInt(u.teamId());out.writeBoolean(u.alive());out.writeLong(u.revision());}
        out.writeInt(s.leases().size());
        for(var l:s.leases()){out.writeUTF(l.leaseId());out.writeUTF(l.taskId());out.writeInt(l.unitId());out.writeLong(l.grantedTick());out.writeLong(l.heartbeatTick());out.writeLong(l.expiresTick());}
    }

    private static LeaseScheduler.PersistedState readState(DataInput in)throws IOException{
        if(in.readInt()!=1)throw new IOException("unsupported lease state version");
        var p=new LeaseScheduler.Policy(in.readLong(),in.readLong(),in.readInt());
        long last=in.readLong(),seq=in.readLong(); int n=bounded(in.readInt());
        ArrayList<LeaseScheduler.Task> ts=new ArrayList<>();LinkedHashMap<String,LeaseScheduler.TaskStatus> ss=new LinkedHashMap<>();
        for(int i=0;i<n;i++){String id=in.readUTF();var k=LeaseScheduler.TaskKind.values()[in.readUnsignedByte()];var t=new LeaseScheduler.Task(id,k,in.readInt(),in.readLong(),in.readInt(),in.readUTF(),in.readInt());ts.add(t);ss.put(id,LeaseScheduler.TaskStatus.values()[in.readUnsignedByte()]);}
        n=bounded(in.readInt());ArrayList<LeaseScheduler.UnitRecord> us=new ArrayList<>();
        for(int i=0;i<n;i++)us.add(new LeaseScheduler.UnitRecord(in.readInt(),LeaseScheduler.UnitKind.values()[in.readUnsignedByte()],in.readInt(),in.readBoolean(),in.readLong()));
        n=bounded(in.readInt());ArrayList<LeaseScheduler.Lease> ls=new ArrayList<>();
        for(int i=0;i<n;i++)ls.add(new LeaseScheduler.Lease(in.readUTF(),in.readUTF(),in.readInt(),in.readLong(),in.readLong(),in.readLong()));
        return new LeaseScheduler.PersistedState(p,last,seq,ts,ss,us,ls);
    }
    private static int bounded(int n)throws IOException{if(n<0||n>1_000_000)throw new IOException("invalid collection size");return n;}
}
