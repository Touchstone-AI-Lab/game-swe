
import arc.Events;
import arc.util.Log;
import mindustry.Vars;
import mindustry.game.EventType;
import mindustry.gen.Building;
import mindustry.gen.Groups;
import mindustry.gen.Unit;
import mindustry.io.SaveFileReader;
import mindustry.io.SaveVersion;
import mindustry.mod.Plugin;

import java.io.*;
import java.util.*;

/** Server adapter. The arbiter contains no Arc/Mindustry references; this class validates live IDs before acting. */
public final class WaveThreatArbiterPlugin extends Plugin {
    private static final String chunkName="mindustry-threat-arbiter-v1";
    private static final ThreatArbiter.Policy defaultPolicy=new ThreatArbiter.Policy(300L,600L,2);
    private static volatile WaveThreatArbiterPlugin instance;
    private volatile ThreatArbiter arbiter=new ThreatArbiter(defaultPolicy);
    private final Map<Integer,Float> buildingHealth=new HashMap<>();
    private final Map<Integer,String> enemyEvents=new HashMap<>();
    private long sequence;
    private int observedWave;

    public WaveThreatArbiterPlugin(){ instance=this; }
    public static WaveThreatArbiterPlugin instance(){ return instance; }
    public ThreatArbiter arbiter(){ return arbiter; }
    public synchronized ThreatArbiter.PersistedState exportState(){ return arbiter.save(); }
    public synchronized void importState(ThreatArbiter.PersistedState state){ arbiter=new ThreatArbiter(defaultPolicy,Objects.requireNonNull(state)); reconcile(); }

    @Override public void init(){
        instance=this;
        SaveVersion.addCustomChunk(chunkName,new Chunk());
        Events.on(EventType.WorldLoadEvent.class,e->{ observedWave=Math.max(1,Vars.state.wave); scanBuildings(false); reconcile(); });
        Events.on(EventType.ResetEvent.class,e->{ synchronized(this){arbiter=new ThreatArbiter(defaultPolicy);buildingHealth.clear();enemyEvents.clear();sequence=0;observedWave=0;} });
        Events.on(EventType.WaveEvent.class,e->onWave());
        Events.on(EventType.UnitSpawnEvent.class,e->onSpawn(e.unit));
        Events.on(EventType.UnitDestroyEvent.class,e->onDestroyed(e.unit));
        Events.on(EventType.BuildDamageEvent.class,e->scanBuildings(true));
        Events.on(EventType.BlockDestroyEvent.class,e->{ if(e.tile!=null) onBuildingGone(e.tile.pos()); });
        Events.run(EventType.Trigger.update,()->{ if(!Vars.net.server() && !Vars.headless)return; long t=tick(); arbiter.tick(t); scanBuildings(true); reconcileAssignments(); });
        Log.info("Wave Threat Response and Repair Arbiter loaded.");
    }

    private synchronized void onWave(){
        int wave=Math.max(1,Vars.state.wave); long tick=tick();
        if(observedWave>0 && wave>observedWave) for(int w=observedWave;w<wave;w++) arbiter.endWave(w,tick);
        observedWave=wave;
        Groups.unit.each(u-> { if(u!=null && u.isValid() && isEnemy(u)) observeEnemy(u,wave,tick); });
    }
    private synchronized void onSpawn(Unit u){
        if(u==null||!u.isValid())return; int wave=Math.max(1,Vars.state.wave); long tick=tick();
        if(isEnemy(u)) observeEnemy(u,wave,tick); else register(u,tick,true);
    }
    private synchronized void onDestroyed(Unit u){
        if(u==null)return; long tick=tick(); String event=enemyEvents.remove(u.id);
        if(event!=null) arbiter.resolve(event,tick); else arbiter.removeResponder(u.id,tick);
    }
    private void observeEnemy(Unit u,int wave,long tick){
        if(enemyEvents.containsKey(u.id))return;
        String id="threat-"+wave+"-"+u.id; int severity=Math.max(1,Math.round(u.type.health));
        ThreatArbiter.Result r=arbiter.observeThreat(new ThreatArbiter.Threat(id,wave,u.id,u.type.name,pack(u.tileX(),u.tileY()),severity,tick));
        if(r.accepted()) enemyEvents.put(u.id,id);
    }
    private void register(Unit u,long tick,boolean bump){
        ThreatArbiter.ResponderKind kind=repairCapable(u)?ThreatArbiter.ResponderKind.REPAIR:ThreatArbiter.ResponderKind.COMBAT;
        if(kind==ThreatArbiter.ResponderKind.COMBAT && (u.type.weapons==null||u.type.weapons.isEmpty()))return;
        arbiter.registerResponder(new ThreatArbiter.Responder(u.id,kind,u.team.id,pack(u.tileX(),u.tileY()),u.isValid()&&!u.dead,tick+(bump?1:0)));
    }
    private boolean repairCapable(Unit u){
        // Build-159 base repair units have a repair-point weapon or a unit type whose internal name identifies it.
        String n=u.type.name.toLowerCase(Locale.ROOT);
        if(n.contains("poly")||n.contains("mega")||n.contains("retusa")||n.contains("oxynoe")||n.contains("cyerce"))return true;
        return false;
    }
    private boolean isEnemy(Unit u){ return Vars.state.rules.waveTeam!=null && u.team==Vars.state.rules.waveTeam; }

    private synchronized void scanBuildings(boolean damage){
        if(Vars.world==null)return; Set<Integer> seen=new HashSet<>(); long tick=tick(); int wave=Math.max(1,Vars.state.wave);
        Groups.build.each(b->{
            if(b==null||!b.isValid())return; int pos=b.pos(); seen.add(pos); Float old=buildingHealth.put(pos,b.health);
            if(damage && old!=null && b.health+0.001f<old && b.team!=Vars.state.rules.waveTeam){
                int amount=Math.max(1,Math.round(old-b.health)); int strategic=Math.max(1,Math.round(b.maxHealth/100f)+b.block.size*b.block.size);
                String id="damage-"+wave+"-"+pos+"-"+(sequence++);
                arbiter.observeDamage(new ThreatArbiter.Damage(id,wave,pos,b.block.name,amount,strategic,tick));
            }
        });
        buildingHealth.keySet().retainAll(seen);
    }
    private synchronized void onBuildingGone(int pos){
        buildingHealth.remove(pos);
        // A destroyed target cannot be repaired; resolve every open repair event for that exact server tile.
        for(ThreatArbiter.Event e:arbiter.snapshot(tick()).events()) if(e.kind()==ThreatArbiter.EventKind.REPAIR&&e.sourceId()==pos&&(e.status()==ThreatArbiter.EventStatus.OPEN||e.status()==ThreatArbiter.EventStatus.ASSIGNED)) arbiter.resolve(e.eventId(),tick());
    }
    private synchronized void reconcile(){
        if(Vars.world==null)return; long tick=tick();
        Groups.unit.each(u->{if(u!=null&&u.isValid()){if(isEnemy(u)){String id="threat-"+Math.max(1,Vars.state.wave)+"-"+u.id;enemyEvents.putIfAbsent(u.id,id);}else register(u,tick,false);}});
        scanBuildings(false); reconcileAssignments();
    }
    private synchronized void reconcileAssignments(){
        // Never retain ownership of a recycled numeric ID: type/team/liveness are re-derived every update.
        Map<Integer,Unit> live=new HashMap<>(); Groups.unit.each(u->{if(u!=null&&u.isValid())live.put(u.id,u);});
        ThreatArbiter.Snapshot snap=arbiter.snapshot(tick());
        for(ThreatArbiter.Responder r:snap.responders()){
            Unit u=live.get(r.unitId());
            if(u==null||isEnemy(u))arbiter.removeResponder(r.unitId(),tick());
            else if(pack(u.tileX(),u.tileY())!=r.tilePos())register(u,tick(),true);
        }
        for(ThreatArbiter.Assignment a:arbiter.snapshot(tick()).assignments()) if(live.containsKey(a.unitId()))arbiter.heartbeat(a.assignmentId(),a.unitId(),tick());
    }
    private static int pack(int x,int y){ if(x<0||y<0||x>32767||y>32767)return 0; return (x<<16)|(y&0xffff); }
    private static long tick(){ return Vars.state==null?0L:Math.max(0L,(long)Vars.state.tick); }

    private final class Chunk implements SaveFileReader.CustomChunk {
        @Override public void write(DataOutput out)throws IOException{ synchronized(WaveThreatArbiterPlugin.this){writeState(out,arbiter.save());} }
        @Override public void read(DataInput in)throws IOException{ ThreatArbiter.PersistedState s=readState(in); synchronized(WaveThreatArbiterPlugin.this){arbiter=new ThreatArbiter(defaultPolicy,s);} }
    }
    private static void writeState(DataOutput o,ThreatArbiter.PersistedState s)throws IOException{
        o.writeInt(0x57544131);o.writeLong(s.nextAssignmentId());
        o.writeInt(s.events().size());for(var e:s.events()){o.writeUTF(e.eventId());o.writeByte(e.kind().ordinal());o.writeInt(e.wave());o.writeInt(e.sourceId());o.writeUTF(e.sourceType());o.writeInt(e.tilePos());o.writeInt(e.priority());o.writeLong(e.createdTick());o.writeLong(e.updatedTick());o.writeByte(e.status().ordinal());}
        o.writeInt(s.responders().size());for(var r:s.responders()){o.writeInt(r.unitId());o.writeByte(r.kind().ordinal());o.writeInt(r.teamId());o.writeInt(r.tilePos());o.writeBoolean(r.alive());o.writeLong(r.revision());}
        o.writeInt(s.assignments().size());for(var a:s.assignments()){o.writeUTF(a.assignmentId());o.writeUTF(a.eventId());o.writeInt(a.unitId());o.writeLong(a.assignedTick());o.writeLong(a.heartbeatTick());o.writeLong(a.leaseUntilTick());}
        o.writeInt(s.sourceKeys().size());for(String x:new TreeSet<>(s.sourceKeys()))o.writeUTF(x);o.writeInt(s.endedWaves().size());for(int x:new TreeSet<>(s.endedWaves()))o.writeInt(x);
    }
    private static ThreatArbiter.PersistedState readState(DataInput i)throws IOException{
        if(i.readInt()!=0x57544131)throw new IOException("invalid threat chunk");long next=i.readLong();
        int n=count(i.readInt());List<ThreatArbiter.Event> es=new ArrayList<>();for(int x=0;x<n;x++)es.add(new ThreatArbiter.Event(i.readUTF(),enumAt(ThreatArbiter.EventKind.values(),i.readByte()),i.readInt(),i.readInt(),i.readUTF(),i.readInt(),i.readInt(),i.readLong(),i.readLong(),enumAt(ThreatArbiter.EventStatus.values(),i.readByte())));
        n=count(i.readInt());List<ThreatArbiter.Responder> rs=new ArrayList<>();for(int x=0;x<n;x++)rs.add(new ThreatArbiter.Responder(i.readInt(),enumAt(ThreatArbiter.ResponderKind.values(),i.readByte()),i.readInt(),i.readInt(),i.readBoolean(),i.readLong()));
        n=count(i.readInt());List<ThreatArbiter.Assignment> as=new ArrayList<>();for(int x=0;x<n;x++)as.add(new ThreatArbiter.Assignment(i.readUTF(),i.readUTF(),i.readInt(),i.readLong(),i.readLong(),i.readLong()));
        n=count(i.readInt());Set<String> keys=new HashSet<>();for(int x=0;x<n;x++)keys.add(i.readUTF());n=count(i.readInt());Set<Integer>waves=new HashSet<>();for(int x=0;x<n;x++)waves.add(i.readInt());return new ThreatArbiter.PersistedState(es,rs,as,next,keys,waves);
    }
    private static int count(int n)throws IOException{if(n<0||n>1_000_000)throw new IOException("invalid count");return n;}
    private static <T>T enumAt(T[] a,int n)throws IOException{if(n<0||n>=a.length)throw new IOException("invalid enum");return a[n];}
}
