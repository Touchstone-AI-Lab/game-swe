package phasetransitionprobe;
import basemod.BaseMod;
import basemod.interfaces.*;
import basemod.abstracts.events.PhasedEvent;
import basemod.abstracts.events.phases.*;
import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.backends.lwjgl.LwjglApplicationConfiguration;
import com.evacipated.cardcrawl.modthespire.lib.SpireInitializer;
import com.megacrit.cardcrawl.actions.GameActionManager;
import com.megacrit.cardcrawl.characters.AbstractPlayer;
import com.megacrit.cardcrawl.core.*;
import com.megacrit.cardcrawl.dungeons.*;
import com.megacrit.cardcrawl.events.GenericEventDialog;
import com.megacrit.cardcrawl.helpers.MonsterHelper;
import com.megacrit.cardcrawl.map.MapRoomNode;
import com.megacrit.cardcrawl.rooms.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
@SpireInitializer
public class Probe implements PostInitializeSubscriber,PostUpdateSubscriber {
 boolean ready,ran;
 public static void initialize(){LwjglApplicationConfiguration.disableAudio=true;BaseMod.subscribe(new Probe());}
 public void receivePostInitialize(){ready=true;}
 static class Event extends PhasedEvent {
  int maps;
  Event(){super("phase:probe","Phases",null);}
  public void openMap(){maps++;super.openMap();}
 }
 static class Phase extends TextPhase {
  final String id; int hidden,entered,resets;
  Runnable hiding,resetting,entering; boolean hideOnce,resetOnce,enterOnce;
  Phase(String id){super(id);this.id=id;addOption(id,i->{});}
  public void hide(PhasedEvent e){hidden++;if(hiding!=null&&!hideOnce){hideOnce=true;hiding.run();}super.hide(e);}
  public void reset(){resets++;if(resetting!=null&&!resetOnce){resetOnce=true;resetting.run();}super.reset();}
  public void transition(PhasedEvent e){entered++;if(entering!=null&&!enterOnce){enterOnce=true;entering.run();}super.transition(e);}
 }
 interface Scene {String run() throws Exception;}
 void record(String s)throws Exception{Files.write(Paths.get("/logs/probe.txt"),(System.getProperty("sts.verify.nonce")+"|"+s+"\n").getBytes(StandardCharsets.UTF_8),StandardOpenOption.CREATE,StandardOpenOption.APPEND);}
 void fresh(){
  if(AbstractDungeon.isScreenUp)AbstractDungeon.closeCurrentScreen();
  AbstractDungeon.player=CardCrawlGame.characterManager.recreateCharacter(AbstractPlayer.PlayerClass.IRONCLAD);
  AbstractDungeon.actionManager=new GameActionManager();
  MapRoomNode n=new MapRoomNode(0,0);n.room=new EventRoom();AbstractDungeon.setCurrMapNode(n);
 }
 Event start(Phase phase){Event e=new Event();AbstractDungeon.getCurrRoom().event=e;e.transitionPhase(phase);e.waitTimer=0;e.update();return e;}
 String current(Event e){return e.currentPhase instanceof Phase?((Phase)e.currentPhase).id:e.currentPhase==null?"null":"other";}
 String view(Event e){return e.imageEventText.optionList.isEmpty()?"empty":e.imageEventText.optionList.get(0).msg;}
 String state(Event e,Phase a,Phase b,Phase c){return "current="+current(e)+",oldHidden="+a.hidden+",middleEntered="+b.entered+",winnerEntered="+c.entered+",middleReset="+b.resets+",winnerReset="+c.resets+",maps="+e.maps+",view="+view(e);}
 void sample(String id,Scene s)throws Exception{String value="",error="none";try{fresh();value=s.run();}catch(Throwable t){error=t.getClass().getName();t.printStackTrace();}record("case,id="+id+",error="+error+","+value);}
 String redirect(String at,String mode){
  Phase a=new Phase("old"),b=new Phase("middle"),c=new Phase("winner");Event e=start(a);e.registerPhase("winner",c);
  Runnable redirect=()->{if(mode.equals("key"))e.transitionKey("winner");else e.transitionPhase(c);};
  if(at.equals("hide"))a.hiding=redirect;
  if(at.equals("reset"))b.resetting=redirect;
  if(at.equals("enter"))b.entering=redirect;
  e.transitionPhase(b);return state(e,a,b,c);
 }
 String sequential(boolean reuse){
  Phase a=new Phase("old"),b=new Phase("middle"),c=new Phase("winner");Event e=start(a);
  e.transitionPhase(b);e.transitionPhase(c);if(reuse){e.transitionPhase(b);e.transitionPhase(c);}return state(e,a,b,c);
 }
 String multi(){
  Phase a=new Phase("old"),b=new Phase("middle"),c=new Phase("winner"),d=new Phase("discarded");Event e=start(a);
  a.hiding=()->{e.transitionPhase(d);e.transitionPhase(c);};e.transitionPhase(b);
  return state(e,a,b,c)+",discardedEntered="+d.entered;
 }
 String chain(){
  Phase a=new Phase("old"),b=new Phase("middle"),c=new Phase("winner"),d=new Phase("hop");Event e=start(a);
  a.hiding=()->e.transitionPhase(d);d.entering=()->e.transitionPhase(c);e.transitionPhase(b);
  return state(e,a,b,c)+",hopEntered="+d.entered+",hopHidden="+d.hidden;
 }
 String failure(String at,boolean nested){
  Phase a=new Phase("old"),b=new Phase("middle"),c=new Phase("winner");Event e=start(a);
  RuntimeException sentinel=new RuntimeException("observer callback");
  Runnable action=()->{if(nested)e.transitionPhase(c);throw sentinel;};
  if(at.equals("hide"))a.hiding=action;if(at.equals("reset"))b.resetting=action;if(at.equals("enter"))b.entering=action;
  Throwable caught=null;try{e.transitionPhase(b);}catch(Throwable t){caught=t;}
  String before=current(e);int visited=c.entered;e.transitionPhase(c);
  return state(e,a,b,c)+",sameThrowable="+(caught==sentinel)+",before="+before+",winnerBefore="+visited;
 }
 String cross(){
  Phase a=new Phase("old"),b=new Phase("middle"),c=new Phase("winner");Event e=start(a);
  Phase otherStart=new Phase("otherStart"),otherEnd=new Phase("otherEnd");Event other=start(otherStart);
  a.hiding=()->other.transitionPhase(otherEnd);e.transitionPhase(b);
  return state(e,a,b,c)+",otherCurrent="+current(other)+",otherEntered="+otherEnd.entered;
 }
 String reopen(boolean redirect,boolean handled){
  Phase winner=new Phase("winner");Phase original=new Phase("old"){
   public boolean reopen(PhasedEvent e){if(redirect)e.transitionPhase(winner);return handled;}
  };Event e=start(original);e.reopen();return "current="+current(e)+",maps="+e.maps+",winnerEntered="+winner.entered;
 }
 String reopenCycle(){
  Phase winner=new Phase("winner");Phase original=new Phase("old"){
   public boolean reopen(PhasedEvent e){e.transitionPhase(winner);e.transitionPhase(this);return false;}
  };Event e=start(original);e.reopen();return "current="+current(e)+",maps="+e.maps+",winnerEntered="+winner.entered+",view="+view(e);
 }
 String invalid(boolean keyed){
  Phase a=new Phase("old");Event e=start(a);boolean rejected=false;
  try{if(keyed)e.transitionKey("missing");else e.transitionPhase(null);}catch(RuntimeException expected){rejected=true;}
  return "current="+current(e)+",oldHidden="+a.hidden+",rejected="+rejected+",view="+view(e);
 }
 String followup(String mode){
  Phase next=new Phase("winner");CombatPhase combat=new CombatPhase(MonsterHelper.CULTIST_ENC);
  if(mode.equals("phase"))combat.setNextPhase(next);
  if(mode.equals("key"))combat.setNextKey("next");
  if(mode.equals("phase-clear"))combat.setNextPhase(next).setNextPhase(null);
  if(mode.equals("key-clear"))combat.setNextKey("next").setNextKey(null);
  if(mode.equals("phase-key-clear"))combat.setNextPhase(next).setNextKey(null);
  if(mode.equals("key-phase-clear"))combat.setNextKey("next").setNextPhase(null);
  Event e=start(new Phase("old"));e.registerPhase("next",next);boolean before=combat.hasFollowup();
  String error="none";try{combat.postCombatTransition(e);}catch(Throwable t){error=t.getClass().getName();}
  String destination=current(e),combatError="none";boolean blocked=false;
  try{combat.transition(e);blocked=basemod.patches.com.megacrit.cardcrawl.rooms.AbstractRoom.EventCombatSave.noSave(AbstractDungeon.getCurrRoom());e.finishCombat();}
  catch(Throwable t){combatError=t.getClass().getName();t.printStackTrace();}
  return "hasFollowup="+before+",current="+destination+",transitionError="+error+",saveBlocked="+blocked+",combatError="+combatError;
 }
 public void receivePostUpdate(){if(!ready||ran||Gdx.graphics.getDeltaTime()<=0)return;ran=true;try{
  CardCrawlGame.mode=CardCrawlGame.GameMode.GAMEPLAY;
  AbstractDungeon.player=CardCrawlGame.characterManager.recreateCharacter(AbstractPlayer.PlayerClass.IRONCLAD);
  Settings.seed=12345L;AbstractDungeon.generateSeeds();CardCrawlGame.dungeon=new Exordium(AbstractDungeon.player,new ArrayList<String>());
  record("engine,gl="+(Gdx.gl!=null));
  for(String at:new String[]{"hide","reset","enter"})for(String mode:new String[]{"direct","key"})sample(at+"-"+mode,()->redirect(at,mode));
  sample("sequential",()->sequential(false));sample("reuse",()->sequential(true));sample("latest-request",()->multi());sample("chain",()->chain());sample("cross-event",()->cross());
  for(String at:new String[]{"hide","reset","enter"})for(boolean nested:new boolean[]{false,true})sample(at+"-throw-"+nested,()->failure(at,nested));
  for(boolean redirect:new boolean[]{false,true})for(boolean handled:new boolean[]{false,true})sample("reopen-"+redirect+"-"+handled,()->reopen(redirect,handled));
  for(String mode:new String[]{"none","phase","key","phase-clear","key-clear","phase-key-clear","key-phase-clear"})sample("followup-"+mode,()->followup(mode));
  sample("reopen-cycle",()->reopenCycle());sample("invalid-direct",()->invalid(false));sample("invalid-key",()->invalid(true));
  record("completed=true");System.exit(0);
 }catch(Throwable t){t.printStackTrace();System.exit(2);}}
}
