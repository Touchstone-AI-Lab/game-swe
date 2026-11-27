
import java.util.*;

/** Deterministic, server-agnostic wave work scheduler. All methods are synchronized. */
public final class ThreatArbiter {
    public enum EventKind { DEFEND, REPAIR }
    public enum EventStatus { OPEN, ASSIGNED, RESOLVED, EXPIRED }
    public enum ResponderKind { COMBAT, REPAIR }

    public record Policy(long leaseTicks, long agingTicks, int persistentRepairWaves) {
        public Policy { if (leaseTicks <= 0 || agingTicks <= 0 || persistentRepairWaves < 0) throw new IllegalArgumentException("invalid policy"); }
    }
    public record Threat(String eventId, int wave, int enemyId, String enemyType, int tilePos, int severity, long tick) {}
    public record Damage(String eventId, int wave, int buildingPos, String blockName, int damage, int strategicValue, long tick) {}
    public record Responder(int unitId, ResponderKind kind, int teamId, int tilePos, boolean alive, long revision) {}
    public record Event(String eventId, EventKind kind, int wave, int sourceId, String sourceType,
                        int tilePos, int priority, long createdTick, long updatedTick, EventStatus status) {}
    public record Assignment(String assignmentId, String eventId, int unitId, long assignedTick,
                             long heartbeatTick, long leaseUntilTick) {}
    public record Result(boolean changed, String reason, Event event, Assignment assignment) {
        public boolean accepted(){ return !"rejected".equals(reason); }
    }
    public record WaveReport(int wave, long tick, int resolved, int expired, int retained,
                             int released, List<Event> events) {
        public WaveReport { events = List.copyOf(events); }
    }
    public record TickReport(long tick, int expiredAssignments, int assignmentsCreated,
                             List<Assignment> assignments) {
        public TickReport { assignments = List.copyOf(assignments); }
    }
    public record Snapshot(long tick, List<Event> events, List<Responder> responders,
                           List<Assignment> assignments) {
        public Snapshot { events=List.copyOf(events); responders=List.copyOf(responders); assignments=List.copyOf(assignments); }
    }
    public record PersistedState(List<Event> events, List<Responder> responders,
                                 List<Assignment> assignments, long nextAssignmentId,
                                 Set<String> sourceKeys, Set<Integer> endedWaves) {
        public PersistedState {
            events=List.copyOf(events); responders=List.copyOf(responders); assignments=List.copyOf(assignments);
            sourceKeys=Set.copyOf(sourceKeys); endedWaves=Set.copyOf(endedWaves);
        }
        public PersistedState(List<Event> events,List<Responder> responders,List<Assignment> assignments,long nextAssignmentId){
            this(events,responders,assignments,nextAssignmentId,Set.of(),Set.of());
        }
    }

    private final Policy policy;
    private final Map<String,Event> events = new HashMap<>();
    private final Map<Integer,Responder> responders = new HashMap<>();
    private final Map<String,Assignment> assignments = new HashMap<>();
    private final Map<String,String> byEvent = new HashMap<>();
    private final Map<Integer,String> byUnit = new HashMap<>();
    private final Set<String> sourceKeys = new HashSet<>();
    private final Set<Integer> endedWaves = new HashSet<>();
    private final Map<String, Result> observationResults = new HashMap<>();
    private final Map<Integer, WaveReport> waveReports = new HashMap<>();
    private long nextAssignmentId = 1;

    public ThreatArbiter(Policy policy){ this(policy, null); }
    public ThreatArbiter(Policy policy, PersistedState state){
        this.policy=Objects.requireNonNull(policy,"policy");
        if(state!=null){
            nextAssignmentId=Math.max(1,state.nextAssignmentId()); sourceKeys.addAll(state.sourceKeys()); endedWaves.addAll(state.endedWaves());
            for(Event e:state.events()){ validateEvent(e); if(events.putIfAbsent(e.eventId(),e)!=null) throw new IllegalArgumentException("duplicate event"); sourceKeys.add(sourceKey(e)); }
            for(Responder r:state.responders()){ validateResponder(r); responders.put(r.unitId(),r); }
            for(Assignment a:state.assignments()){
                validateAssignment(a); Event e=events.get(a.eventId()); Responder r=responders.get(a.unitId());
                if(e!=null && e.status()==EventStatus.ASSIGNED && r!=null && r.alive() && !byEvent.containsKey(a.eventId()) && !byUnit.containsKey(a.unitId())){
                    assignments.put(a.assignmentId(),a); byEvent.put(a.eventId(),a.assignmentId()); byUnit.put(a.unitId(),a.assignmentId());
                }
            }
        }
    }

    public synchronized Result observeThreat(Threat t){
        Objects.requireNonNull(t,"threat"); validId(t.eventId()); validWaveTick(t.wave(),t.tick()); positive(t.enemyId(),"enemyId"); text(t.enemyType()); pos(t.tilePos()); positive(t.severity(),"severity");
        return observe(new Event(t.eventId(),EventKind.DEFEND,t.wave(),t.enemyId(),t.enemyType(),t.tilePos(),t.severity(),t.tick(),t.tick(),EventStatus.OPEN),"T:"+t.wave()+":"+t.enemyId(),t.tick());
    }
    public synchronized Result observeDamage(Damage d){
        Objects.requireNonNull(d,"damage"); validId(d.eventId()); validWaveTick(d.wave(),d.tick()); pos(d.buildingPos()); text(d.blockName()); positive(d.damage(),"damage"); positive(d.strategicValue(),"strategicValue");
        long sum=(long)d.damage()+d.strategicValue(); int priority=(int)Math.min(Integer.MAX_VALUE,sum);
        return observe(new Event(d.eventId(),EventKind.REPAIR,d.wave(),d.buildingPos(),d.blockName(),d.buildingPos(),priority,d.tick(),d.tick(),EventStatus.OPEN),"D:"+d.wave()+":"+d.buildingPos()+":"+d.damage()+":"+d.strategicValue()+":"+d.tick(),d.tick());
    }
    private Result observe(Event n,String key,long tick){
        Event old=events.get(n.eventId());
        if(old!=null){
            Result previous=observationResults.get(n.eventId());
            if(false) return previous;
            return equivalent(old,n)?new Result(false,"duplicate",old,assignmentFor(old.eventId())):new Result(false,"rejected",old,assignmentFor(old.eventId()));
        }
        if(sourceKeys.contains(key)) return new Result(false,"duplicate",null,null);
        events.put(n.eventId(),n); sourceKeys.add(key); assign(tick);
        Event now=events.get(n.eventId());
        Result result=new Result(true,"observed",now,assignmentFor(n.eventId()));
        observationResults.put(n.eventId(),result);
        return result;
    }
    public synchronized Result registerResponder(Responder r){
        validateResponder(r); Responder old=responders.get(r.unitId());
        if(old!=null && r.revision()<old.revision()) return new Result(false,"stale",null,assignmentForUnit(r.unitId()));
        if(old!=null && r.revision()==old.revision() && old.equals(r)) return new Result(false,"duplicate",null,assignmentForUnit(r.unitId()));
        responders.put(r.unitId(),r);
        if(!r.alive()) releaseUnit(r.unitId(),r.revision());
        assign(Math.max(0,r.revision()));
        Assignment a=assignmentForUnit(r.unitId()); return new Result(true,"registered",a==null?null:events.get(a.eventId()),a);
    }
    public synchronized Result heartbeat(String assignmentId,int unitId,long tick){
        validId(assignmentId); positive(unitId,"unitId"); nonnegative(tick,"tick"); Assignment a=assignments.get(assignmentId);
        if(a==null || a.unitId()!=unitId || !assignmentId.equals(byUnit.get(unitId))) return new Result(false,"rejected",null,null);
        Responder r=responders.get(unitId); Event e=events.get(a.eventId());
        if(r==null||!r.alive()||e==null||e.status()!=EventStatus.ASSIGNED||tick<a.heartbeatTick()) return new Result(false,"rejected",e,a);
        Assignment na=new Assignment(a.assignmentId(),a.eventId(),a.unitId(),a.assignedTick(),tick,safeAdd(tick,policy.leaseTicks())); assignments.put(assignmentId,na);
        return new Result(true,"renewed",e,na);
    }
    public synchronized Result resolve(String eventId,long tick){
        validId(eventId); nonnegative(tick,"tick"); Event e=events.get(eventId); if(e==null) return new Result(false,"missing",null,null);
        if(e.status()==EventStatus.RESOLVED||e.status()==EventStatus.EXPIRED) return new Result(false,"duplicate",e,null);
        Assignment a=releaseEvent(eventId); Event ne=with(e,EventStatus.RESOLVED,tick,e.wave()); events.put(eventId,ne); assign(tick);
        return new Result(true,"resolved",ne,a);
    }
    public synchronized Result removeResponder(int unitId,long tick){
        positive(unitId,"unitId"); nonnegative(tick,"tick"); Responder r=responders.remove(unitId); if(r==null)return new Result(false,"missing",null,null);
        Assignment a=releaseUnit(unitId,tick); assign(tick); return new Result(true,"removed",a==null?null:events.get(a.eventId()),a);
    }
    public synchronized WaveReport endWave(int wave,long tick){
        validWaveTick(wave,tick);
        WaveReport previous=waveReports.get(wave);
        if(previous!=null) return previous;
        if(endedWaves.contains(wave)) return new WaveReport(wave,tick,0,0,0,0,List.of());
        int resolved=0,expired=0,retained=0,released=0; List<Event> changed=new ArrayList<>();
        for(Event e:sortedEvents(tick)) if(e.wave()==wave && (e.status()==EventStatus.OPEN||e.status()==EventStatus.ASSIGNED)){
            if(releaseEvent(e.eventId())!=null) released++;
            Event ne;
            if(e.kind()==EventKind.REPAIR && wave-originalWave(e)<policy.persistentRepairWaves()){ ne=with(e,EventStatus.OPEN,tick,wave+1); retained++; }
            else if(e.status()==EventStatus.ASSIGNED){ ne=with(e,EventStatus.RESOLVED,tick,wave); resolved++; }
            else { ne=with(e,EventStatus.EXPIRED,tick,wave); expired++; }
            events.put(e.eventId(),ne); changed.add(ne);
        }
        endedWaves.add(wave); assign(tick);
        WaveReport report=new WaveReport(wave,tick,resolved,expired,retained,released,changed);
        waveReports.put(wave,report);
        return report;
    }
    public synchronized TickReport tick(long tick){
        nonnegative(tick,"tick"); int expired=0;
        for(Assignment a:new ArrayList<>(assignments.values())) if(tick>a.leaseUntilTick()) { releaseAssignment(a); expired++; }
        int before=assignments.size(); assign(tick); return new TickReport(tick,expired,assignments.size()-before,sortedAssignments());
    }
    public synchronized Snapshot snapshot(long tick){ nonnegative(tick,"tick"); return new Snapshot(tick,sortedEvents(tick),sortedResponders(),sortedAssignments()); }
    public synchronized PersistedState save(){ return new PersistedState(sortedEvents(0),sortedResponders(),sortedAssignments(),nextAssignmentId,new TreeSet<>(sourceKeys),new TreeSet<>(endedWaves)); }

    private void assign(long tick){
        List<Event> open=new ArrayList<>(); for(Event e:events.values())if(e.status()==EventStatus.OPEN)open.add(e);
        open.sort(eventComparator(tick));
        for(Event e:open){
            Responder best=null; long bestDist=Long.MAX_VALUE;
            for(Responder r:responders.values()) if(r.alive()&&!byUnit.containsKey(r.unitId())&&compatible(e,r)){
                long d=distance(e.tilePos(),r.tilePos()); if(best==null||d<bestDist||(d==bestDist&&(r.teamId()<best.teamId()||(r.teamId()==best.teamId()&&r.unitId()<best.unitId())))){best=r;bestDist=d;}
            }
            if(best!=null){ String id="assignment-"+(nextAssignmentId++); Assignment a=new Assignment(id,e.eventId(),best.unitId(),tick,tick,safeAdd(tick,policy.leaseTicks())); assignments.put(id,a);byEvent.put(e.eventId(),id);byUnit.put(best.unitId(),id);events.put(e.eventId(),with(e,EventStatus.ASSIGNED,tick,e.wave())); }
        }
    }
    private boolean compatible(Event e,Responder r){ return (e.kind()==EventKind.DEFEND&&r.kind()==ResponderKind.COMBAT)||(e.kind()==EventKind.REPAIR&&r.kind()==ResponderKind.REPAIR); }
    private static long distance(int a,int b){ int ax=(short)(a>>>16), ay=(short)a, bx=(short)(b>>>16), by=(short)b; return Math.abs((long)ax-bx)+Math.abs((long)ay-by); }
    private Comparator<Event> eventComparator(long tick){ return Comparator.<Event>comparingLong(e->effective(e,tick)).reversed().thenComparingLong(Event::createdTick).thenComparing(Event::eventId); }
    private long effective(Event e,long tick){return (long)e.priority()+Math.max(0,tick-e.createdTick())/policy.agingTicks();}
    private List<Event> sortedEvents(long tick){List<Event> x=new ArrayList<>(events.values());x.sort(Comparator.comparing(Event::eventId));return List.copyOf(x);}
    private List<Responder> sortedResponders(){List<Responder>x=new ArrayList<>(responders.values());x.sort(Comparator.comparingInt(Responder::unitId));return List.copyOf(x);}
    private List<Assignment> sortedAssignments(){List<Assignment>x=new ArrayList<>(assignments.values());x.sort(Comparator.comparing(Assignment::assignmentId));return List.copyOf(x);}
    private Assignment assignmentFor(String event){String id=byEvent.get(event);return id==null?null:assignments.get(id);} private Assignment assignmentForUnit(int unit){String id=byUnit.get(unit);return id==null?null:assignments.get(id);}
    private Assignment releaseEvent(String event){Assignment a=assignmentFor(event);if(a!=null)releaseAssignment(a);return a;}
    private Assignment releaseUnit(int unit,long tick){Assignment a=assignmentForUnit(unit);if(a!=null)releaseAssignment(a);return a;}
    private void releaseAssignment(Assignment a){assignments.remove(a.assignmentId());byEvent.remove(a.eventId());byUnit.remove(a.unitId());Event e=events.get(a.eventId());if(e!=null&&e.status()==EventStatus.ASSIGNED)events.put(e.eventId(),with(e,EventStatus.OPEN,Math.max(e.updatedTick(),a.heartbeatTick()),e.wave()));}
    private static Event with(Event e,EventStatus s,long tick,int wave){return new Event(e.eventId(),e.kind(),wave,e.sourceId(),e.sourceType(),e.tilePos(),e.priority(),e.createdTick(),tick,s);}
    private static boolean equivalent(Event a,Event b){return a.kind()==b.kind()&&a.wave()==b.wave()&&a.sourceId()==b.sourceId()&&a.sourceType().equals(b.sourceType())&&a.tilePos()==b.tilePos()&&a.priority()==b.priority()&&a.createdTick()==b.createdTick();}
    private static String sourceKey(Event e){return (e.kind()==EventKind.DEFEND?"T:":"D:")+e.wave()+":"+e.sourceId();}
    private int originalWave(Event e){
        if(e.kind()!=EventKind.REPAIR)return e.wave();
        String suffix=":"+e.sourceId()+":";
        int best=e.wave();
        for(String k:sourceKeys) if(k.startsWith("D:")&&k.contains(suffix)) try{best=Math.min(best,Integer.parseInt(k.substring(2,k.indexOf(':',2))));}catch(RuntimeException ignored){}
        return best;
    }
    private static long safeAdd(long a,long b){return a>Long.MAX_VALUE-b?Long.MAX_VALUE:a+b;}
    private static void validateEvent(Event e){Objects.requireNonNull(e);validId(e.eventId());Objects.requireNonNull(e.kind());Objects.requireNonNull(e.status());validWaveTick(e.wave(),e.createdTick());nonnegative(e.updatedTick(),"updatedTick");text(e.sourceType());pos(e.tilePos());positive(e.priority(),"priority");}
    private static void validateResponder(Responder r){Objects.requireNonNull(r,"responder");positive(r.unitId(),"unitId");Objects.requireNonNull(r.kind(),"kind");if(r.teamId()<0)throw new IllegalArgumentException("teamId");pos(r.tilePos());nonnegative(r.revision(),"revision");}
    private static void validateAssignment(Assignment a){Objects.requireNonNull(a);validId(a.assignmentId());validId(a.eventId());positive(a.unitId(),"unitId");nonnegative(a.assignedTick(),"assignedTick");nonnegative(a.heartbeatTick(),"heartbeatTick");nonnegative(a.leaseUntilTick(),"leaseUntilTick");}
    private static void validId(String s){text(s);} private static void text(String s){if(s==null||s.isBlank())throw new IllegalArgumentException("blank text");} private static void validWaveTick(int w,long t){positive(w,"wave");nonnegative(t,"tick");} private static void positive(int n,String s){if(n<=0)throw new IllegalArgumentException(s);} private static void nonnegative(long n,String s){if(n<0)throw new IllegalArgumentException(s);} private static void pos(int p){if(p<0)throw new IllegalArgumentException("position");}
}
