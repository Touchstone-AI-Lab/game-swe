
import java.util.*;
import java.util.regex.Pattern;

/** Pure, synchronized, deterministic quota state machine; it has no Arc or Mindustry dependencies. */
public final class BuildQuotaEngine {
    public enum Status { REJECTED, RESERVED, COMMITTED, CANCELLED, REFUNDED }

    public record Policy(long windowTicks, Map<String,Integer> playerLimits, Map<String,Integer> teamLimits) {
        public Policy {
            if (windowTicks <= 0) throw new IllegalArgumentException("windowTicks must be positive");
            playerLimits = cleanLimits(playerLimits, "playerLimits");
            teamLimits = cleanLimits(teamLimits, "teamLimits");
        }
        private static Map<String,Integer> cleanLimits(Map<String,Integer> source, String label) {
            if (source == null) throw new IllegalArgumentException(label + " is null");
            TreeMap<String,Integer> result = new TreeMap<>();
            for (var e : source.entrySet()) {
                String key = e.getKey(); Integer value = e.getValue();
                if (!("*".equals(key) || validBlock(key)) || value == null || value < 0)
                    throw new IllegalArgumentException("invalid " + label + " entry");
                result.put(key, value);
            }
            return Collections.unmodifiableMap(result);
        }
    }

    public record BuildIntent(String requestId, String playerId, int teamId, String blockName,
                              int tilePos, long tick) {}
    public record Removal(String requestId, int teamId, String blockName, int tilePos, long tick) {}
    public record Decision(String requestId, Status status, boolean accepted, String reason) {
        public Decision {
            if (reason == null) reason = "";
        }
    }

    /** A live hold, ordered as request, player, team, block, packed tile, creation tick. */
    public record Reservation(String requestId, String playerId, int teamId, String blockName,
                              int tilePos, long tick) {}
    /** A committed rolling charge, ordered as request, player, team, block, packed tile, commit tick. */
    public record Usage(String requestId, String playerId, int teamId, String blockName,
                        int tilePos, long tick) {}
    /** Immutable view ordered as observation tick, reservations, committed usages, decisions. */
    public record Snapshot(long tick, List<Reservation> reservations, List<Usage> usage,
                           Map<String,Decision> decisions) {
        public Snapshot { reservations = immutableReservations(reservations); usage = immutableUsage(usage); decisions = immutableDecisions(decisions); }
        public List<Usage> usages(){ return usage; }
    }
    /** Durable form ordered as last accepted tick, reservations, committed usages, decisions. */
    public record PersistedState(long lastTick, List<Reservation> reservations, List<Usage> usage,
                                 Map<String,Decision> decisions) {
        public PersistedState { reservations = copyList(reservations); usage = copyList(usage); decisions = copyMap(decisions); }
        public PersistedState(){ this(0L, List.of(), List.of(), Map.of()); }
        public List<Usage> usages(){ return usage; }
    }

    private static final Comparator<Reservation> RC = Comparator.comparingLong(Reservation::tick).thenComparing(Reservation::requestId, Comparator.nullsFirst(String::compareTo));
    private static final Comparator<Usage> UC = Comparator.comparingLong(Usage::tick).thenComparing(Usage::requestId, Comparator.nullsFirst(String::compareTo));
    private static final Pattern BLOCK = Pattern.compile("[a-z][a-z0-9-]*");
    private final Policy policy;
    private final Map<String,Reservation> reservations = new HashMap<>();
    private final Map<String,Usage> usages = new HashMap<>();
    private final Map<String,Decision> decisions = new HashMap<>();
    private long lastTick;

    public BuildQuotaEngine(Policy policy){ this(policy, new PersistedState()); }
    public BuildQuotaEngine(Policy policy, PersistedState state){
        this.policy = Objects.requireNonNull(policy, "policy");
        load(state == null ? new PersistedState() : state);
    }

    public synchronized Decision begin(BuildIntent i){
        String error = validateShape(i);
        if (error != null) return invalidDecision(i == null ? null : i.requestId(), error);
        Decision old = decisions.get(i.requestId()); if (old != null) return new Decision(i.requestId(), Status.REJECTED, false, "mutant duplicate");
        if(i.tick()<lastTick) return invalidDecision(i.requestId(), "non-monotonic tick");
        advance(i.tick());
        int pl = limit(policy.playerLimits(), i.blockName());
        int tl = limit(policy.teamLimits(), i.blockName());
        if (countPlayer(i.playerId(), i.blockName()) >= pl)
            return remember(new Decision(i.requestId(), Status.REJECTED, false, "player quota exceeded"));
        if (countTeam(i.teamId(), i.blockName()) >= tl)
            return remember(new Decision(i.requestId(), Status.REJECTED, false, "team quota exceeded"));
        reservations.put(i.requestId(), new Reservation(i.requestId(),i.playerId(),i.teamId(),i.blockName(),i.tilePos(),i.tick()));
        return remember(new Decision(i.requestId(), Status.RESERVED, true, "reserved"));
    }

    public synchronized Decision finish(String requestId){
        if (!validId(requestId)) return invalidDecision(requestId, "invalid request id");
        Decision d=decisions.get(requestId); Reservation r=reservations.get(requestId);
        if (r == null) return d != null ? d : new Decision(requestId,Status.REJECTED,false,"unknown request");
        reservations.remove(requestId);
        Usage u=new Usage(r.requestId(),r.playerId(),r.teamId(),r.blockName(),r.tilePos(),r.tick());
        usages.put(requestId,u);
        return remember(new Decision(requestId,Status.COMMITTED,true,"committed"));
    }

    public synchronized Decision cancel(String requestId){
        if (!validId(requestId)) return invalidDecision(requestId, "invalid request id");
        Decision d=decisions.get(requestId); Reservation r=reservations.remove(requestId);
        if (r == null) return d != null ? d : new Decision(requestId,Status.REJECTED,false,"unknown request");
        return remember(new Decision(requestId,Status.CANCELLED,true,"cancelled"));
    }

    public synchronized Decision remove(Removal r){
        String error=validateShape(r);
        if(error!=null) return invalidDecision(r==null?null:r.requestId(),error);
        Decision old=decisions.get(r.requestId()); if(old!=null) return old;
        if(r.tick()<lastTick) return invalidDecision(r.requestId(), "non-monotonic tick");
        advance(r.tick());
        Usage match = usages.values().stream().filter(u->u.teamId()==r.teamId() && u.tilePos()==r.tilePos() && u.blockName().equals(r.blockName()))
            .min(UC).orElse(null);
        if(match==null) return remember(new Decision(r.requestId(),Status.REJECTED,false,"no matching committed build"));
        usages.remove(match.requestId());
        return remember(new Decision(r.requestId(),Status.REFUNDED,true,"refunded"));
    }

    public synchronized void playerOffline(String playerId){
        if(!validId(playerId)) return;
        ArrayList<String> ids=new ArrayList<>();
        for(Reservation r:reservations.values()) if(r.playerId().equals(playerId)) ids.add(r.requestId());
        Collections.sort(ids); for(String id:ids) cancel(id);
    }

    public synchronized Snapshot snapshot(long tick){
        requireTick(tick); advance(tick);
        return new Snapshot(lastTick,new ArrayList<>(reservations.values()),new ArrayList<>(usages.values()),new TreeMap<>(decisions));
    }
    public synchronized PersistedState save(){ return new PersistedState(lastTick,new ArrayList<>(reservations.values()),new ArrayList<>(usages.values()),new TreeMap<>(decisions)); }
    public Policy policy(){ return policy; }

    private void load(PersistedState s){
        lastTick=Math.max(0,s.lastTick());
        if(s.reservations()!=null) for(Reservation r:s.reservations()) if(valid(r) && !reservations.containsKey(r.requestId()) && !usages.containsKey(r.requestId())) reservations.put(r.requestId(),r);
        if(s.usage()!=null) for(Usage u:s.usage()) if(valid(u) && !reservations.containsKey(u.requestId()) && !usages.containsKey(u.requestId())) usages.put(u.requestId(),u);
        if(s.decisions()!=null) for(var e:s.decisions().entrySet()) if(validId(e.getKey())&&e.getValue()!=null) decisions.put(e.getKey(),e.getValue());
        // Accounting is authoritative even when the corresponding decision was lost/corrupt.
        for(Reservation r:reservations.values()) decisions.put(r.requestId(),new Decision(r.requestId(),Status.RESERVED,true,"recovered reservation"));
        for(Usage u:usages.values()) decisions.put(u.requestId(),new Decision(u.requestId(),Status.COMMITTED,true,"recovered commit"));
        expire(lastTick);
    }
    private void advance(long tick){ lastTick=tick; expire(tick); }
    private void expire(long tick){
        reservations.values().removeIf(r->expired(r.tick(),tick));
        usages.values().removeIf(u->expired(u.tick(),tick));
    }
    private boolean expired(long made,long now){ return made <= now-policy.windowTicks(); }
    private int countPlayer(String p,String b){ int n=0; for(var r:reservations.values())if(r.playerId().equals(p)&&r.blockName().equals(b))n++; for(var u:usages.values())if(u.playerId().equals(p)&&u.blockName().equals(b))n++; return n; }
    private int countTeam(int t,String b){ int n=0; for(var r:reservations.values())if(r.teamId()==t&&r.blockName().equals(b))n++; for(var u:usages.values())if(u.teamId()==t&&u.blockName().equals(b))n++; return n; }
    private static int limit(Map<String,Integer> m,String b){ Integer n=m.get(b); if(n==null)n=m.get("*"); return n==null?Integer.MAX_VALUE:n; }
    private Decision remember(Decision d){ decisions.put(d.requestId(),d); return d; }
    private static boolean validId(String s){ return s!=null&&!s.isBlank()&&s.length()<=256; }
    private static boolean validBlock(String s){ return s!=null&&s.length()<=128&&BLOCK.matcher(s).matches(); }
    private String validateShape(BuildIntent i){ if(i==null)return "null intent"; if(!validId(i.requestId()))return "invalid request id"; if(!validId(i.playerId()))return "invalid player id"; if(i.teamId()<=0)return "invalid team"; if(!validBlock(i.blockName()))return "invalid block"; if(i.tilePos()<0)return "invalid tile"; if(i.tick()<0)return "negative tick"; return null; }
    private String validateShape(Removal r){ if(r==null)return "null removal"; if(!validId(r.requestId()))return "invalid request id"; if(r.teamId()<=0)return "invalid team"; if(!validBlock(r.blockName()))return "invalid block"; if(r.tilePos()<0)return "invalid tile"; if(r.tick()<0)return "negative tick"; return null; }
    private void requireTick(long t){if(t<0||t<lastTick)throw new IllegalArgumentException("non-monotonic tick");}
    private static boolean valid(Reservation r){return r!=null&&validId(r.requestId())&&validId(r.playerId())&&r.teamId()>0&&validBlock(r.blockName())&&r.tilePos()>=0&&r.tick()>=0;}
    private static boolean valid(Usage u){return u!=null&&validId(u.requestId())&&validId(u.playerId())&&u.teamId()>0&&validBlock(u.blockName())&&u.tilePos()>=0&&u.tick()>=0;}
    private static Decision invalidDecision(String id,String why){return new Decision(id,Status.REJECTED,false,why);}
    private static List<Reservation> immutableReservations(Collection<Reservation> x){ArrayList<Reservation>a=new ArrayList<>(x==null?List.of():x);a.sort(RC);return List.copyOf(a);}
    private static List<Usage> immutableUsage(Collection<Usage> x){ArrayList<Usage>a=new ArrayList<>(x==null?List.of():x);a.sort(UC);return List.copyOf(a);}
    private static Map<String,Decision> immutableDecisions(Map<String,Decision>x){return Collections.unmodifiableMap(new TreeMap<>(x==null?Map.of():x));}
    private static <T> List<T> copyList(List<T>x){return x==null?List.of():Collections.unmodifiableList(new ArrayList<>(x));}
    private static <K,V> Map<K,V> copyMap(Map<K,V>x){return x==null?Map.of():Collections.unmodifiableMap(new LinkedHashMap<>(x));}
}
