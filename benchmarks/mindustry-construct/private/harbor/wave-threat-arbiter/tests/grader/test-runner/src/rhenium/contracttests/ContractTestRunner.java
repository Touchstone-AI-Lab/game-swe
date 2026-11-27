
import arc.Core;
import arc.Events;
import arc.util.Log;
import arc.util.Time;
import mindustry.Vars;
import mindustry.content.UnitTypes;
import mindustry.game.EventType.WorldLoadEvent;
import mindustry.game.Team;
import mindustry.gen.Groups;
import mindustry.gen.Unit;
import mindustry.mod.Plugin;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

public final class ContractTestRunner extends Plugin {
    private final AtomicBoolean finished = new AtomicBoolean();
    public ContractTestRunner(){Events.on(WorldLoadEvent.class,e->Time.runTask(30f,this::run));}
    private void run(){if(!finished.compareAndSet(false,true))return;List<Case> cases=new ArrayList<>();
        check(cases,"priority and capability assignment",this::assignment);
        check(cases,"event deduplication",this::duplicate);
        check(cases,"lease expiry and death requeue",this::requeue);
        check(cases,"wave cleanup isolation",this::waveCleanup);
        check(cases,"save reload determinism",this::reload);
        check(cases,"real enemy and responder assignment",this::realUnits);
        check(cases,"active plugin and headless world",this::integration);finish(cases);}
    private ThreatArbiter arbiter(){return new ThreatArbiter(new ThreatArbiter.Policy(10,5,2));}
    private void assignment(){ThreatArbiter a=arbiter();
        a.observeThreat(new ThreatArbiter.Threat("low",1,10,"dagger",10,1,0));
        a.observeThreat(new ThreatArbiter.Threat("high",1,11,"mace",20,10,0));
        a.observeDamage(new ThreatArbiter.Damage("repair",1,30,"router",20,5,0));
        a.registerResponder(new ThreatArbiter.Responder(2,ThreatArbiter.ResponderKind.COMBAT,1,0,true,1));
        a.registerResponder(new ThreatArbiter.Responder(1,ThreatArbiter.ResponderKind.REPAIR,1,0,true,1));
        Object report=a.tick(0);require(report!=null,"tick returned null");
        String snapshot=a.snapshot(0).toString();require(snapshot.contains("high")&&snapshot.contains("repair"),"events disappeared");}
    private void duplicate(){ThreatArbiter a=arbiter();ThreatArbiter.Threat t=new ThreatArbiter.Threat("same",1,1,"dagger",1,2,0);
        Object first=a.observeThreat(t);Object retry=a.observeThreat(t);require(first.equals(retry),"duplicate result changed");
        require(a.snapshot(0).equals(a.snapshot(0)),"snapshot is unstable");}
    private void requeue(){ThreatArbiter a=arbiter();a.observeThreat(new ThreatArbiter.Threat("work",1,1,"dagger",10,5,0));
        a.registerResponder(new ThreatArbiter.Responder(1,ThreatArbiter.ResponderKind.COMBAT,1,0,true,1));a.registerResponder(new ThreatArbiter.Responder(2,ThreatArbiter.ResponderKind.COMBAT,1,20,true,1));a.tick(0);
        a.removeResponder(1,1);a.tick(1);require(a.snapshot(1).toString().contains("work"),"death lost unresolved work");
        a.tick(11);require(a.snapshot(11).toString().contains("work"),"expiry lost unresolved work");}
    private void waveCleanup(){ThreatArbiter a=arbiter();a.observeThreat(new ThreatArbiter.Threat("wave1",1,1,"dagger",1,1,0));a.observeThreat(new ThreatArbiter.Threat("wave2",2,2,"dagger",2,1,0));
        Object first=a.endWave(1,1);Object retry=a.endWave(1,1);require(first.equals(retry),"wave cleanup is not idempotent");
        require(a.snapshot(1).toString().contains("wave2"),"cleanup affected another wave");}
    private void reload(){ThreatArbiter a=arbiter();a.observeDamage(new ThreatArbiter.Damage("saved",1,10,"router",10,10,0));a.registerResponder(new ThreatArbiter.Responder(1,ThreatArbiter.ResponderKind.REPAIR,1,0,true,1));a.tick(0);
        ThreatArbiter loaded=new ThreatArbiter(new ThreatArbiter.Policy(10,5,2),a.save());require(a.snapshot(1).equals(loaded.snapshot(1)),"reload changed state");
        require(loaded.save().equals(loaded.save()),"saved state is unstable");}
    private void realUnits(){Unit enemy=UnitTypes.dagger.create(Team.crux);Unit responder=UnitTypes.poly.create(Team.sharded);enemy.set(40f,40f);responder.set(24f,24f);enemy.add();responder.add();require(Groups.unit.getByID(enemy.id())==enemy&&Groups.unit.getByID(responder.id())==responder,"real units were not added");ThreatArbiter a=arbiter();a.observeThreat(new ThreatArbiter.Threat("real-enemy",1,enemy.id(),enemy.type.name,1,5,0));a.registerResponder(new ThreatArbiter.Responder(responder.id(),ThreatArbiter.ResponderKind.REPAIR,responder.team.id,0,true,1));a.observeDamage(new ThreatArbiter.Damage("real-repair",1,2,"router",10,5,0));a.tick(0);require(a.snapshot(0).assignments().stream().anyMatch(x->x.unitId()==responder.id()),"real responder was not assigned");enemy.remove();responder.remove();}
    private void integration()throws Exception{Class<?> type=Class.forName("WaveThreatArbiterPlugin");Object plugin=type.getMethod("instance").invoke(null);require(plugin!=null,"instance is null");require(type.getMethod("arbiter").invoke(plugin)!=null,"arbiter is null");require(Vars.world!=null&&Vars.state.isGame(),"headless world is inactive");}
    private static void check(List<Case> cases,String name,Checked body){try{body.run();cases.add(new Case(name,true,"ok"));}catch(Throwable e){cases.add(new Case(name,false,e.toString()));}}
    private static void finish(List<Case> cases){boolean passed=cases.stream().allMatch(Case::passed);StringBuilder out=new StringBuilder("{\"passed\":").append(passed).append(",\"cases\":[");for(int i=0;i<cases.size();i++){if(i>0)out.append(',');Case c=cases.get(i);out.append("{\"name\":\"").append(esc(c.name())).append("\",\"passed\":").append(c.passed()).append(",\"message\":\"").append(esc(c.message())).append("\"}");}Log.info("MINDUSTRY_RESULT @",out.append("]}").toString());Core.app.exit();}
    private static String esc(String s){return s.replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n");}
    private static void require(boolean v,String m){if(!v)throw new AssertionError(m);}
    private interface Checked{void run()throws Exception;}
    private record Case(String name,boolean passed,String message){}
}
