
import java.util.*;

/** A deterministic, thread-safe, game-independent lease scheduler. */
public final class LeaseScheduler {
    public enum TaskKind { MINE, REPAIR, TRANSPORT }
    public enum TaskStatus { QUEUED, LEASED, COMPLETED, CANCELLED }
    public enum UnitKind { MONO, POLY, MEGA }

    public record Policy(long leaseTicks, long agingTicks, int maximumPriority) {
        public Policy {
            if (leaseTicks <= 0 || agingTicks <= 0 || maximumPriority < 0)
                throw new IllegalArgumentException("leaseTicks and agingTicks must be positive and maximumPriority non-negative");
        }
    }
    public record Task(String taskId, TaskKind kind, int priority, long createdTick,
                       int targetPos, String itemName, int amount) {}
    public record UnitRecord(int unitId, UnitKind kind, int teamId, boolean alive, long revision) {}
    public record Lease(String leaseId, String taskId, int unitId, long grantedTick,
                        long heartbeatTick, long expiresTick) {}
    public record Result(boolean success, boolean changed, String message, Lease lease) {
        public boolean accepted(){ return success; }
        public String code(){ return message; }
    }
    public record TickReport(long tick, List<Lease> assigned, List<Lease> released,
                             Snapshot snapshot) {
        public TickReport { assigned = List.copyOf(assigned); released = List.copyOf(released); }
        public List<Lease> assignments(){ return assigned; }
        public List<Lease> expirations(){ return released; }
    }
    public record Snapshot(long tick, List<Task> tasks, Map<String, TaskStatus> taskStatuses,
                           List<UnitRecord> units, List<Lease> leases) {
        public Snapshot {
            tasks = List.copyOf(tasks);
            taskStatuses = Collections.unmodifiableMap(new LinkedHashMap<>(taskStatuses));
            units = List.copyOf(units);
            leases = List.copyOf(leases);
        }
        public TaskStatus status(String taskId){ return taskStatuses.get(taskId); }
    }
    public record PersistedState(Policy policy, long lastTick, long nextLeaseSequence,
                                 List<Task> tasks, Map<String, TaskStatus> taskStatuses,
                                 List<UnitRecord> units, List<Lease> leases) {
        public PersistedState {
            tasks = tasks == null ? List.of() : List.copyOf(tasks);
            taskStatuses = taskStatuses == null ? Map.of() :
                    Collections.unmodifiableMap(new LinkedHashMap<>(taskStatuses));
            units = units == null ? List.of() : List.copyOf(units);
            leases = leases == null ? List.of() : List.copyOf(leases);
        }
    }

    private static final class TaskEntry {
        final Task task;
        TaskStatus status;
        TaskEntry(Task task, TaskStatus status){ this.task=task; this.status=status; }
    }

    private final Policy policy;
    private final TreeMap<String, TaskEntry> tasks = new TreeMap<>();
    private final TreeMap<Integer, UnitRecord> units = new TreeMap<>();
    private final TreeMap<String, Lease> leasesById = new TreeMap<>();
    private final HashMap<String, String> leaseByTask = new HashMap<>();
    private final HashMap<Integer, String> leaseByUnit = new HashMap<>();
    private long lastTick = -1;
    private long nextLeaseSequence = 1;
    private final HashMap<String, Integer> completedLeaseUnits = new HashMap<>();

    public LeaseScheduler(Policy policy){
        this.policy = Objects.requireNonNull(policy, "policy");
    }

    public LeaseScheduler(Policy policy, PersistedState state){
        this(policy);
        if(state == null) return;
        if(state.policy() != null && !state.policy().equals(policy))
            throw new IllegalArgumentException("persisted policy does not match");
        if(state.lastTick() < -1 || state.nextLeaseSequence() < 1)
            throw new IllegalArgumentException("invalid persisted sequencing");
        lastTick = state.lastTick();
        nextLeaseSequence = state.nextLeaseSequence();
        for(Task t : state.tasks()){
            if(!validTask(t)) throw new IllegalArgumentException("invalid persisted task");
            TaskStatus s = state.taskStatuses().getOrDefault(t.taskId(), TaskStatus.QUEUED);
            if(tasks.putIfAbsent(t.taskId(), new TaskEntry(t, s)) != null)
                throw new IllegalArgumentException("duplicate persisted task");
        }
        for(UnitRecord u : state.units()){
            if(!validUnit(u) || units.putIfAbsent(u.unitId(), u) != null)
                throw new IllegalArgumentException("invalid persisted unit");
        }
        // A lease is recovered only when both non-terminal task and matching live unit exist.
        ArrayList<Lease> sorted = new ArrayList<>(state.leases());
        sorted.sort(Comparator.comparing(Lease::leaseId));
        for(Lease l : sorted){
            TaskEntry e = l == null ? null : tasks.get(l.taskId());
            UnitRecord u = l == null ? null : units.get(l.unitId());
            if(!validLease(l) || e == null || e.status == TaskStatus.COMPLETED || e.status == TaskStatus.CANCELLED ||
               u == null || !u.alive() || !compatible(u.kind(), e.task.kind()) ||
               leaseByTask.containsKey(l.taskId()) || leaseByUnit.containsKey(l.unitId())){
                if(e != null && e.status == TaskStatus.LEASED) e.status = TaskStatus.QUEUED;
                continue;
            }
            if(lastTick >= l.expiresTick()) { e.status = TaskStatus.QUEUED; continue; }
            addLease(l); e.status = TaskStatus.LEASED;
        }
        for(TaskEntry e: tasks.values()) if(e.status == TaskStatus.LEASED && !leaseByTask.containsKey(e.task.taskId())) e.status=TaskStatus.QUEUED;
    }

    public synchronized Policy policy(){ return policy; }

    public synchronized Result upsertTask(Task task){
        if(!validTask(task)) return fail("invalid-task");
        TaskEntry old=tasks.get(task.taskId());
        if(old != null) return old.task.equals(task) ? ok(true,"queued",null) : fail("task-id-conflict");
        if(task.createdTick() < lastTick) return fail("stale-tick");
        tasks.put(task.taskId(),new TaskEntry(task,TaskStatus.QUEUED));
        return ok(true,"queued",null);
    }

    public synchronized Result registerUnit(UnitRecord unit){
        if(!validUnit(unit)) return fail("invalid-unit");
        UnitRecord old=units.get(unit.unitId());
        if(old != null){
            if(unit.revision() < old.revision()) return fail("stale-revision");
            if(unit.revision() == old.revision()) return old.equals(unit) ? ok(false,"duplicate",leaseForUnit(unit.unitId())) : fail("revision-conflict");
            boolean replaced = old.kind()!=unit.kind() || old.teamId()!=unit.teamId() || !unit.alive();
            if(replaced) releaseForUnit(unit.unitId());
        }
        units.put(unit.unitId(),unit);
        return ok(true, old == null ? "registered" : "updated", leaseForUnit(unit.unitId()));
    }

    public synchronized Result heartbeat(String leaseId,int unitId,long tick){
        if(!advance(tick) || !validId(leaseId) || unitId < 0) return fail("invalid-or-stale");
        expire(tick,null);
        Lease l=leasesById.get(leaseId);
        if(l==null || l.unitId()!=unitId) return fail("lease-mismatch");
        Lease n=new Lease(l.leaseId(),l.taskId(),l.unitId(),l.grantedTick(),tick,safeAdd(tick,policy.leaseTicks()));
        leasesById.put(leaseId,n);
        return ok(true,"heartbeat",n);
    }

    public synchronized Result complete(String leaseId,int unitId,long tick){
        if(!advance(tick) || !validId(leaseId) || unitId < 0) return fail("invalid-or-stale");
        expire(tick,null);
        Lease l=leasesById.get(leaseId);
        if(l==null || l.unitId()!=unitId) {
            Integer done=completedLeaseUnits.get(leaseId);
            return done != null && done == unitId ? ok(false,"completed",null) : fail("lease-mismatch");
        }
        removeLease(l);
        TaskEntry e=tasks.get(l.taskId());
        if(e!=null) e.status=TaskStatus.COMPLETED;
        completedLeaseUnits.put(leaseId,unitId);
        return ok(true,"completed",l);
    }

    public synchronized Result removeUnit(int unitId,long tick){
        if(!advance(tick) || unitId < 0) return fail("invalid-or-stale");
        UnitRecord old=units.remove(unitId);
        Lease l=releaseForUnit(unitId);
        if(old==null) return ok(false,"absent",l);
        return ok(true,"removed",l);
    }

    public synchronized Result cancelTask(String taskId,long tick){
        if(!advance(tick) || !validId(taskId)) return fail("invalid-or-stale");
        TaskEntry e=tasks.get(taskId);
        if(e==null) return fail("unknown-task");
        if(e.status==TaskStatus.CANCELLED) return ok(false,"cancelled",null);
        if(e.status==TaskStatus.COMPLETED) return ok(false,"completed",null);
        Lease l=leaseForTask(taskId);
        if(l!=null) removeLease(l);
        e.status=TaskStatus.CANCELLED;
        return ok(true,"cancelled",l);
    }

    public synchronized TickReport tick(long tick){
        if(!advance(tick)) return new TickReport(lastTick,List.of(),List.of(),snapshotInternal(lastTick));
        ArrayList<Lease> released=new ArrayList<>();
        expire(tick,released);
        // Invalid live assignments are also reconciled here.
        for(Lease l:new ArrayList<>(leasesById.values())){
            UnitRecord u=units.get(l.unitId()); TaskEntry e=tasks.get(l.taskId());
            if(u==null || !u.alive() || e==null || !compatible(u.kind(),e.task.kind())) { removeLease(l); released.add(l); }
        }
        ArrayList<TaskEntry> eligible=new ArrayList<>();
        for(TaskEntry e:tasks.values()) if(e.status==TaskStatus.QUEUED) eligible.add(e);
        eligible.sort((a,b)->{
            int c=Integer.compare(effective(b.task,tick),effective(a.task,tick));
            if(c==0)c=Long.compare(a.task.createdTick(),b.task.createdTick());
            if(c==0)c=a.task.taskId().compareTo(b.task.taskId());
            return c;
        });
        ArrayList<Lease> assigned=new ArrayList<>();
        for(TaskEntry e:eligible){
            UnitRecord chosen=null;
            for(UnitRecord u:availableUnits()) if(u.alive() && !leaseByUnit.containsKey(u.unitId()) && compatible(u.kind(),e.task.kind())) { chosen=u; break; }
            if(chosen==null) continue;
            String id="lease-"+(nextLeaseSequence++);
            Lease l=new Lease(id,e.task.taskId(),chosen.unitId(),tick,tick,safeAdd(tick,policy.leaseTicks()));
            addLease(l); e.status=TaskStatus.LEASED; assigned.add(l);
        }
        return new TickReport(tick,assigned,released,snapshotInternal(tick));
    }

    public synchronized Snapshot snapshot(long tick){
        if(tick < 0) throw new IllegalArgumentException("tick must be non-negative");
        return snapshotInternal(tick);
    }

    public synchronized PersistedState save(){
        Snapshot s=snapshotInternal(lastTick);
        return new PersistedState(policy,lastTick,nextLeaseSequence,s.tasks(),s.taskStatuses(),s.units(),s.leases());
    }

    private Snapshot snapshotInternal(long tick){
        ArrayList<Task> ts=new ArrayList<>(); LinkedHashMap<String,TaskStatus> ss=new LinkedHashMap<>();
        for(var x:tasks.entrySet()){ts.add(x.getValue().task);ss.put(x.getKey(),x.getValue().status);}
        ArrayList<UnitRecord> us=new ArrayList<>(units.values());
        ArrayList<Lease> ls=new ArrayList<>(leasesById.values());
        ls.sort(Comparator.comparing(Lease::leaseId));
        return new Snapshot(tick,ts,ss,us,ls);
    }
    private List<UnitRecord> availableUnits(){
        ArrayList<UnitRecord> out=new ArrayList<>(units.values());
        out.sort(Comparator.comparingInt((UnitRecord u)->u.kind().ordinal()).thenComparingInt(UnitRecord::unitId));
        return out;
    }
    private int effective(Task t,long tick){
        long age=Math.max(0,tick-t.createdTick())/policy.agingTicks();
        return (int)Math.min(policy.maximumPriority(),Math.min((long)Integer.MAX_VALUE,(long)t.priority()+age));
    }
    private void expire(long tick,List<Lease> out){
        for(Lease l:new ArrayList<>(leasesById.values())) if(tick>=l.expiresTick()){removeLease(l);if(out!=null)out.add(l);}
    }
    private Lease releaseForUnit(int id){Lease l=leaseForUnit(id);if(l!=null)removeLease(l);return l;}
    private void addLease(Lease l){leasesById.put(l.leaseId(),l);leaseByTask.put(l.taskId(),l.leaseId());leaseByUnit.put(l.unitId(),l.leaseId());}
    private void removeLease(Lease l){
        leasesById.remove(l.leaseId());leaseByTask.remove(l.taskId());leaseByUnit.remove(l.unitId());
        TaskEntry e=tasks.get(l.taskId());if(e!=null&&e.status==TaskStatus.LEASED)e.status=TaskStatus.QUEUED;
    }
    private Lease leaseForTask(String id){String x=leaseByTask.get(id);return x==null?null:leasesById.get(x);}
    private Lease leaseForUnit(int id){String x=leaseByUnit.get(id);return x==null?null:leasesById.get(x);}
    private boolean advance(long tick){if(tick<0||tick<lastTick)return false;lastTick=tick;return true;}
    private static long safeAdd(long a,long b){return a>Long.MAX_VALUE-b?Long.MAX_VALUE:a+b;}
    private static boolean validId(String s){return s!=null&&!s.isBlank()&&s.length()<=256;}
    private boolean validTask(Task t){
        return t!=null&&validId(t.taskId())&&t.kind()!=null&&t.priority()>=0&&t.priority()<=policy.maximumPriority()&&
               t.createdTick()>=0&&t.targetPos()>=0&&t.amount()>0&&t.itemName()!=null&&!t.itemName().isBlank();
    }
    private static boolean validUnit(UnitRecord u){return u!=null&&u.unitId()>=0&&u.kind()!=null&&u.teamId()>=0&&u.revision()>=0;}
    private static boolean validLease(Lease l){return l!=null&&validId(l.leaseId())&&validId(l.taskId())&&l.unitId()>=0&&l.grantedTick()>=0&&l.heartbeatTick()>=l.grantedTick()&&l.expiresTick()>l.heartbeatTick();}
    public static boolean compatible(UnitKind unit,TaskKind task){
        if(unit==null||task==null)return false;
        return switch(task){case MINE -> unit==UnitKind.MONO; case REPAIR -> unit==UnitKind.POLY||unit==UnitKind.MEGA; case TRANSPORT -> unit==UnitKind.MEGA;};
    }
    private static Result fail(String s){return new Result(false,false,s,null);}
    private static Result ok(boolean changed,String s,Lease l){return new Result(true,changed,s,l);}
}
