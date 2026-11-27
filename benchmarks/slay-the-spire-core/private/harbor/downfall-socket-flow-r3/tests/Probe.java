package socketflowprobe;
import basemod.BaseMod;
import basemod.interfaces.*;
import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.backends.lwjgl.LwjglApplicationConfiguration;
import com.evacipated.cardcrawl.modthespire.lib.*;
import javassist.*;
import javassist.expr.*;
import com.megacrit.cardcrawl.cards.*;
import com.megacrit.cardcrawl.core.*;
import com.megacrit.cardcrawl.dungeons.*;
import com.megacrit.cardcrawl.map.MapRoomNode;
import com.megacrit.cardcrawl.rooms.*;
import com.megacrit.cardcrawl.helpers.Hitbox;
import guardian.GuardianMod;
import guardian.cards.*;
import guardian.patches.GuardianEnum;
import guardian.vfx.SocketGemEffect;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
@SpireInitializer
public class Probe implements PostInitializeSubscriber,PostUpdateSubscriber {
 public static String nativeError="none";
 // The stock render guard drops the entire frame, including input and timers,
 // when software GL takes over 100 ms. Keep the real update/render path running;
 // only the guard's measurement is bounded, not the engine clock or game state.
 public static long slowFrames;
 @SpirePatch(clz=CardCrawlGame.class,method="render")
 public static class SoftwareFrameGuard {
  @SpireInstrumentPatch
  public static ExprEditor instrument(){return new ExprEditor(){
   public void edit(MethodCall call)throws CannotCompileException{
    if(call.getMethodName().equals("getRawDeltaTime"))
     call.replace("{ float measured = $proceed($$); if (measured > 0.1f) socketflowprobe.Probe.slowFrames++; $_ = Math.min(measured, 0.099f); }");
   }
  };}
 }

 @SpirePatch(clz=SocketGemEffect.class,method="update")
 public static class ContainObservedException {
  @SpireRawPatch
  public static void Raw(CtBehavior method)throws Exception {
   method.addCatch("{ socketflowprobe.Probe.nativeError = $e.getClass().getName(); this.isDone = true; return; }",method.getDeclaringClass().getClassPool().get("java.lang.Throwable"));
  }
 }
 boolean ready,ran;java.awt.Robot robot;int scene,phase,pressed;long start,pressedAt,phaseAt;
 String[] scenes={"complete","cancel-gem-mouse","cancel-gem-escape","cancel-socket-mouse","cancel-socket-escape","smith-control","smith-guardian-control","cancel-gem-smith-mouse","cancel-gem-smith-escape","cancel-gem-smith-guardian","back-reselect-mouse","back-reselect-escape"};
 AbstractGuardianCard gem,host,green;AbstractCard ordinary;SocketGemEffect effect;String last="";
 public static void initialize(){LwjglApplicationConfiguration.disableAudio=true;BaseMod.subscribe(new Probe());}
 public void receivePostInitialize(){ready=true;}
 void record(String value)throws Exception{if(!(value.startsWith("engine,")||value.startsWith("case,")||value.equals("completed=true")))return;Files.write(Paths.get("/logs/probe.txt"),(System.getProperty("sts.verify.nonce")+"|"+value+"\n").getBytes(StandardCharsets.UTF_8),StandardOpenOption.CREATE,StandardOpenOption.APPEND);}
 String members(List<AbstractCard> cards){List<String> ids=new ArrayList<>();for(AbstractCard c:cards)ids.add(c.cardID);return String.join(";",ids);}
 String state(){return "error="+nativeError+",hostUpgraded="+host.upgraded+",screen="+AbstractDungeon.screen+",up="+AbstractDungeon.isScreenUp+",gems="+GuardianMod.gridScreenForGems+",sockets="+GuardianMod.gridScreenForSockets+",target="+(AbstractDungeon.gridSelectScreen.targetGroup==null?"none":members(AbstractDungeon.gridSelectScreen.targetGroup.group))+",selected="+members(AbstractDungeon.gridSelectScreen.selectedCards)+",deck="+members(AbstractDungeon.player.masterDeck.group)+",hostGems="+host.sockets+",hidden="+CampfireUI.hidden+",done="+(effect!=null&&effect.isDone)+",gemSelect="+(effect!=null&&effect.gemSelect)+",socketSelect="+(effect!=null&&effect.socketSelect)+",chosen="+(effect==null||effect.gemChosen==null?"none":effect.gemChosen.cardID)+",ordinaryUpgraded="+ordinary.upgraded+",cancelHidden="+AbstractDungeon.overlayMenu.cancelButton.isHidden;}
 void fresh()throws Exception{
  if(AbstractDungeon.isScreenUp)AbstractDungeon.closeCurrentScreen();
  AbstractDungeon.effectList.clear();AbstractDungeon.effectsQueue.clear();
  AbstractDungeon.player=CardCrawlGame.characterManager.recreateCharacter(GuardianEnum.GUARDIAN);
  Settings.FAST_MODE=true;Settings.seed=12345L;AbstractDungeon.generateSeeds();CardCrawlGame.dungeon=new Exordium(AbstractDungeon.player,new ArrayList<String>());
  if(AbstractDungeon.isScreenUp)AbstractDungeon.closeCurrentScreen();
  gem=new Gem_Red();green=new Gem_Green();host=new PrismaticBeam();AbstractDungeon.player.masterDeck.clear();AbstractDungeon.player.masterDeck.addToTop(gem);AbstractDungeon.player.masterDeck.addToTop(green);AbstractDungeon.player.masterDeck.addToTop(host);ordinary=new com.megacrit.cardcrawl.cards.red.Strike_Red();AbstractDungeon.player.masterDeck.addToTop(ordinary);
  MapRoomNode node=new MapRoomNode(0,0);node.room=new RestRoom();AbstractDungeon.setCurrMapNode(node);node.room.onPlayerEntry();
  // Character construction queues a starting-deck animation. It belongs to
  // setup, before our explicit four-card deck, and must not block campfire input.
  AbstractDungeon.effectList.clear();AbstractDungeon.effectsQueue.clear();
  CardCrawlGame.fadeIn(0.0f);
  nativeError="none";phase=0;effect=null;last="";start=phaseAt=System.nanoTime();record("scene,id="+scenes[scene]+",start="+state());
 }
 double seconds(long since){return (System.nanoTime()-since)/1.0e9;}
 boolean click(Hitbox hb){
  if(pressed!=0||seconds(pressedAt)<.3)return false;
  robot.mouseMove(Math.round(hb.cX),Settings.HEIGHT-Math.round(hb.cY));
  if(!hb.hovered)return false;
  robot.mousePress(java.awt.event.InputEvent.BUTTON1_DOWN_MASK);pressed=1;pressedAt=System.nanoTime();return true;
 }
 boolean cancel(){if(scenes[scene].endsWith("escape")){if(pressed!=0||seconds(pressedAt)<.3)return false;robot.keyPress(java.awt.event.KeyEvent.VK_ESCAPE);pressed=2;pressedAt=System.nanoTime();return true;}return click(AbstractDungeon.overlayMenu.cancelButton.hb);}
 void step()throws Exception{
  if(pressed!=0&&seconds(pressedAt)>.15){if(pressed==1)robot.mouseRelease(java.awt.event.InputEvent.BUTTON1_DOWN_MASK);else robot.keyRelease(java.awt.event.KeyEvent.VK_ESCAPE);pressed=0;pressedAt=System.nanoTime();}
  String now=state();if(!now.equals(last)){record("event,id="+scenes[scene]+",time="+seconds(start)+",phase="+phase+","+now);last=now;}
  if(scenes[scene].startsWith("smith-")&&phase==0&&seconds(start)>.7){new com.megacrit.cardcrawl.ui.campfire.SmithOption(true).useOption();phase=6;phaseAt=System.nanoTime();}
  if((phase==0||(phase==1&&seconds(phaseAt)>1.5))&&seconds(start)>.7&&GuardianMod.socketBonfireOption!=null&&!AbstractDungeon.isScreenUp){if(click(GuardianMod.socketBonfireOption.hb)){phase=1;phaseAt=System.nanoTime();}}
  if(phase==1&&GuardianMod.currSocketGemEffect!=null&&AbstractDungeon.screen==AbstractDungeon.CurrentScreen.GRID&&AbstractDungeon.gridSelectScreen.targetGroup.contains(gem)&&AbstractDungeon.isScreenUp){effect=GuardianMod.currSocketGemEffect;phase=2;phaseAt=System.nanoTime();}
  if(phase==2&&seconds(phaseAt)>.6){
   if(scenes[scene].startsWith("cancel-gem")){if(cancel()){phase=5;phaseAt=System.nanoTime();}}
   else if(click(gem.hb)){phase=3;phaseAt=System.nanoTime();}
  }
  if(phase==3&&AbstractDungeon.screen==AbstractDungeon.CurrentScreen.GRID&&AbstractDungeon.gridSelectScreen.targetGroup.contains(host)&&AbstractDungeon.isScreenUp){phase=4;phaseAt=System.nanoTime();}
  if(phase==4&&seconds(phaseAt)>.6){if(scenes[scene].equals("complete")?click(host.hb):cancel()){phase=5;phaseAt=System.nanoTime();}}
  if(scenes[scene].startsWith("back-reselect")&&phase==5&&seconds(phaseAt)>.6&&AbstractDungeon.screen==AbstractDungeon.CurrentScreen.GRID&&AbstractDungeon.gridSelectScreen.targetGroup.contains(green)){if(click(green.hb)){phase=10;phaseAt=System.nanoTime();}}
  if(phase==10&&seconds(phaseAt)>.6&&AbstractDungeon.screen==AbstractDungeon.CurrentScreen.GRID&&AbstractDungeon.gridSelectScreen.targetGroup.contains(host)){if(click(host.hb)){phase=11;phaseAt=System.nanoTime();}}
  if(scenes[scene].startsWith("cancel-gem-smith")&&phase==5&&!AbstractDungeon.isScreenUp&&seconds(phaseAt)>.2){
   record("followup,id="+scenes[scene]+",time="+seconds(start)+","+state());
   new com.megacrit.cardcrawl.ui.campfire.SmithOption(true).useOption();phase=6;phaseAt=System.nanoTime();
  }
  if(phase==6&&AbstractDungeon.screen==AbstractDungeon.CurrentScreen.GRID&&seconds(phaseAt)>.9){if(click(scenes[scene].contains("guardian")?host.hb:ordinary.hb)){phase=7;phaseAt=System.nanoTime();}}
  if(phase==7&&AbstractDungeon.gridSelectScreen.confirmScreenUp&&seconds(phaseAt)>.5){if(click(AbstractDungeon.gridSelectScreen.confirmButton.hb)){phase=8;phaseAt=System.nanoTime();}}
  if(phase!=9&&((phase==5&&seconds(phaseAt)>2.5)||(phase==8&&seconds(phaseAt)>2.5)||(phase==11&&seconds(phaseAt)>2.5)||(seconds(phaseAt)>15)||seconds(start)>45)){
   robot.mouseRelease(java.awt.event.InputEvent.BUTTON1_DOWN_MASK);robot.keyRelease(java.awt.event.KeyEvent.VK_ESCAPE);pressed=0;
   System.out.println("SOCKET_FIXTURE scene="+scenes[scene]+" phase="+phase+" slowFrames="+slowFrames);
   record("case,id="+scenes[scene]+",phase="+phase+",elapsed="+seconds(start)+","+state());
   phase=9;phaseAt=System.nanoTime();
  }
  if(phase==9){
   if(AbstractDungeon.isScreenUp&&seconds(phaseAt)>.4)cancel();
   if(!AbstractDungeon.isScreenUp&&seconds(phaseAt)>2.0){scene++;if(scene==scenes.length){record("completed=true");System.exit(0);}else fresh();}
   else if(seconds(phaseAt)>8){record("cleanup-incomplete,id="+scenes[scene]);System.exit(3);}
  }
 }
 public void receivePostUpdate(){if(!ready||Gdx.graphics.getDeltaTime()<=0)return;try{
  if(!ran){ran=true;robot=new java.awt.Robot();CardCrawlGame.mode=CardCrawlGame.GameMode.GAMEPLAY;if(Boolean.getBoolean("probe.reverse"))Collections.reverse(Arrays.asList(scenes));record("engine,gl="+(Gdx.gl!=null));fresh();}else step();
 }catch(Throwable failure){failure.printStackTrace();System.exit(2);}}
}
