
import arc.Events;
import mindustry.Vars;
import mindustry.content.Blocks;
import mindustry.game.EventType.*;
import mindustry.game.Team;
import mindustry.game.EventType.Trigger;
import mindustry.gen.Groups;
import mindustry.gen.Player;
import mindustry.gen.Unit;
import mindustry.io.SaveFileReader.CustomChunk;
import mindustry.io.SaveVersion;
import mindustry.mod.Plugin;
import mindustry.world.Block;
import mindustry.world.Tile;
import mindustry.world.blocks.ConstructBlock.ConstructBuild;

import java.io.*;
import java.util.*;

/** Server-side adapter. All observations and world mutations originate in server game events. */
public final class BuildQuotaAuditorPlugin extends Plugin {
    private static final String CHUNK = "mindustry-build-quota-v1";
    private static volatile BuildQuotaAuditorPlugin instance;
    private volatile BuildQuotaEngine engine;
    private BuildQuotaEngine.PersistedState loaded;
    private long sequence;
    private final Map<Key,String> active = new HashMap<>();
    private final Map<Key,String> committed = new HashMap<>();
    private final Map<TileKey,PendingRemoval> removals = new HashMap<>();

    public BuildQuotaAuditorPlugin(){
        instance=this;
        engine=new BuildQuotaEngine(defaultPolicy());
    }
    public static BuildQuotaAuditorPlugin instance(){ return instance; }
    public BuildQuotaEngine engine(){ return engine; }
    public BuildQuotaEngine.PersistedState exportState(){ return engine.save(); }
    public void importState(BuildQuotaEngine.PersistedState state){ engine=new BuildQuotaEngine(engine.policy(),Objects.requireNonNull(state)); }

    @Override public void init(){
        SaveVersion.addCustomChunk(CHUNK,new Chunk());
        Events.on(BlockBuildBeginEvent.class,this::begin);
        Events.on(BlockBuildEndEvent.class,this::end);
        Events.on(PlayerLeave.class,e->{ if(e.player!=null) engine.playerOffline(e.player.uuid()); });
        Events.on(ResetEvent.class,e->reset());
        Events.on(WorldLoadEvent.class,e->worldLoaded());
        Events.run(Trigger.update,this::auditActive);
    }

    private static BuildQuotaEngine.Policy defaultPolicy(){
        // Operators/evaluators can replace this atomically through importState while policy defaults to unlimited.
        return new BuildQuotaEngine.Policy(60L*60L,Map.of(),Map.of());
    }
    private long tick(){
        long t=Vars.state==null?0L:(long)Math.floor(Vars.state.tick);
        long old=engine.save().lastTick(); return Math.max(old,Math.max(0,t));
    }
    private void begin(BlockBuildBeginEvent e){
        if(e==null||e.tile==null||e.team==null||e.team==Team.derelict) return;
        Player p=player(e.unit); if(p==null) return; // no guessed/client identity: only a server-owned unit/player link
        long now=tick(); int pos=e.tile.pos();
        if(e.breaking){
            Block b=deconstructedBlock(e.tile); if(b==null||b==Blocks.air)return;
            String id="remove:"+p.uuid()+":"+e.team.id+":"+pos+":"+(sequence++);
            removals.put(new TileKey(e.team.id,pos),new PendingRemoval(id,e.team.id,b.name,pos));
            return;
        }
        Block target=constructionTarget(e.tile);
        if(target==null||target==Blocks.air)return;
        String id="build:"+p.uuid()+":"+e.team.id+":"+pos+":"+(sequence++);
        Key key=new Key(e.team.id,pos,target.name);
        BuildQuotaEngine.Decision d=engine.begin(new BuildQuotaEngine.BuildIntent(id,p.uuid(),e.team.id,target.name,pos,now));
        if(d.accepted()) active.put(key,id); else rejectCorrelated(e.tile,e.unit,target,e.team);
    }
    private void end(BlockBuildEndEvent e){
        if(e==null||e.tile==null||e.team==null)return;
        if(e.breaking){
            PendingRemoval p=removals.remove(new TileKey(e.team.id,e.tile.pos()));
            if(p!=null){
                BuildQuotaEngine.Decision d=engine.remove(new BuildQuotaEngine.Removal(p.id(),p.team(),p.block(),p.tile(),tick()));
                if(d.accepted()) committed.remove(new Key(p.team(),p.tile(),p.block()));
            }
            return;
        }
        Block b=e.tile.block(); if(b==null)return;
        Key key=new Key(e.team.id,e.tile.pos(),b.name);
        String id=active.remove(key);
        if(id!=null){
            BuildQuotaEngine.Decision d=engine.finish(id);
            if(d.status()==BuildQuotaEngine.Status.COMMITTED) committed.put(key,id);
        }
    }

    private void auditActive(){
        if(active.isEmpty() || Vars.world==null)return;
        ArrayList<Map.Entry<Key,String>> copy=new ArrayList<>(active.entrySet());
        for(var entry:copy){
            Key k=entry.getKey(); Tile tile=Vars.world.tile(k.tile());
            if(tile!=null && tile.build instanceof ConstructBuild cb && cb.team.id==k.team() && cb.current!=null && cb.current.name.equals(k.block())) continue;
            if(!active.remove(k,entry.getValue()))continue;
            if(tile!=null && tile.block()!=null && tile.block().name.equals(k.block()) && tile.build!=null && tile.build.team.id==k.team()){
                BuildQuotaEngine.Decision d=engine.finish(entry.getValue());
                if(d.status()==BuildQuotaEngine.Status.COMMITTED)committed.put(k,entry.getValue());
            }else engine.cancel(entry.getValue());
        }
    }
    private void rejectCorrelated(Tile tile,Unit unit,Block target,Team team){
        // Never delete a completed/prior building. Only remove the exact team's placeholder for this target.
        if(tile.build instanceof ConstructBuild cb && cb.team==team && cb.current==target){ cb.remove(); tile.setNet(Blocks.air); }
        if(unit!=null && unit.plans()!=null){
            for(int j=unit.plans().size-1;j>=0;j--){ var p=unit.plans().get(j); if(!p.breaking&&p.x==tile.x&&p.y==tile.y&&p.block==target) unit.plans().removeIndex(j); }
        }
    }
    private static Block constructionTarget(Tile tile){ return tile.build instanceof ConstructBuild cb?cb.current:tile.block(); }
    private static Block deconstructedBlock(Tile tile){ return tile.build instanceof ConstructBuild cb?cb.previous:tile.block(); }
    private static Player player(Unit unit){
        if(unit==null)return null;
        return Groups.player.find(p->p!=null&&p.unit()==unit&&p.uuid()!=null&&!p.uuid().isBlank());
    }
    private void reset(){ active.clear(); committed.clear(); removals.clear(); loaded=null; engine=new BuildQuotaEngine(engine.policy()); }
    private void worldLoaded(){
        if(loaded!=null){ engine=new BuildQuotaEngine(engine.policy(),loaded); loaded=null; }
        // A save cannot preserve an in-progress event correlation. Release recovered holds, never commits.
        for(BuildQuotaEngine.Reservation r:engine.save().reservations()) engine.cancel(r.requestId());
        active.clear(); committed.clear(); removals.clear();
    }

    private record Key(int team,int tile,String block){}
    private record TileKey(int team,int tile){}
    private record PendingRemoval(String id,int team,String block,int tile){}
    private final class Chunk implements CustomChunk {
        @Override public void write(DataOutput out)throws IOException{ writeState(out,engine.save()); }
        @Override public void read(DataInput in)throws IOException{ loaded=readState(in); }
    }

    private static void writeState(DataOutput o,BuildQuotaEngine.PersistedState s)throws IOException{
        o.writeInt(1); o.writeLong(s.lastTick());
        o.writeInt(s.reservations().size()); for(var r:s.reservations()){str(o,r.requestId());str(o,r.playerId());o.writeInt(r.teamId());str(o,r.blockName());o.writeInt(r.tilePos());o.writeLong(r.tick());}
        o.writeInt(s.usage().size()); for(var u:s.usage()){str(o,u.requestId());str(o,u.playerId());o.writeInt(u.teamId());str(o,u.blockName());o.writeInt(u.tilePos());o.writeLong(u.tick());}
        o.writeInt(s.decisions().size()); for(var e:s.decisions().entrySet()){str(o,e.getKey());var d=e.getValue();o.writeInt(d.status().ordinal());o.writeBoolean(d.accepted());str(o,d.reason());}
    }
    private static BuildQuotaEngine.PersistedState readState(DataInput i)throws IOException{
        int version=i.readInt(); if(version!=1)throw new IOException("unsupported quota chunk version"); long tick=i.readLong();
        ArrayList<BuildQuotaEngine.Reservation> rs=new ArrayList<>(); int n=count(i); for(int x=0;x<n;x++)rs.add(new BuildQuotaEngine.Reservation(str(i),str(i),i.readInt(),str(i),i.readInt(),i.readLong()));
        ArrayList<BuildQuotaEngine.Usage> us=new ArrayList<>(); n=count(i); for(int x=0;x<n;x++)us.add(new BuildQuotaEngine.Usage(str(i),str(i),i.readInt(),str(i),i.readInt(),i.readLong()));
        TreeMap<String,BuildQuotaEngine.Decision> ds=new TreeMap<>(); n=count(i); for(int x=0;x<n;x++){String id=str(i);int ord=i.readInt();boolean ok=i.readBoolean();String why=str(i);BuildQuotaEngine.Status[] v=BuildQuotaEngine.Status.values();if(ord>=0&&ord<v.length)ds.put(id,new BuildQuotaEngine.Decision(id,v[ord],ok,why));}
        return new BuildQuotaEngine.PersistedState(tick,rs,us,ds);
    }
    private static int count(DataInput i)throws IOException{int n=i.readInt();if(n<0||n>1_000_000)throw new IOException("invalid quota collection size");return n;}
    private static void str(DataOutput o,String s)throws IOException{if(s==null){o.writeInt(-1);return;}byte[] b=s.getBytes(java.nio.charset.StandardCharsets.UTF_8);o.writeInt(b.length);o.write(b);}
    private static String str(DataInput i)throws IOException{int n=i.readInt();if(n<0)return null;if(n>1_048_576)throw new IOException("oversized quota string");byte[] b=new byte[n];i.readFully(b);return new String(b,java.nio.charset.StandardCharsets.UTF_8);}
}
