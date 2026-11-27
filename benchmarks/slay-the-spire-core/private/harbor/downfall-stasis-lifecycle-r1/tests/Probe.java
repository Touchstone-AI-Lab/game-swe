package stasisprobe;
import automaton.AutomatonChar;
import guardian.actions.PlaceActualCardIntoStasis;
import guardian.actions.PlaceRandomCardIntoStasisAction;
import guardian.actions.PlaceRandom1CostIntoStasis;
import guardian.actions.PlaceTopCardIntoStasisAction;
import com.megacrit.cardcrawl.orbs.Lightning;
import guardian.cards.ChargeCore;
import guardian.GuardianMod;
import com.megacrit.cardcrawl.cards.blue.Dualcast;
import com.megacrit.cardcrawl.cards.blue.Recursion;
import com.megacrit.cardcrawl.cards.CardGroup;
import com.megacrit.cardcrawl.orbs.AbstractOrb;
import com.megacrit.cardcrawl.rooms.AbstractRoom;
import collector.CollectorCollection;
import collector.relics.BottledCollectible;
import collector.util.CollectibleCardReward;
import basemod.abstracts.CustomSavableRaw;
import com.google.gson.JsonElement;
import com.megacrit.cardcrawl.cards.red.SearingBlow;
import com.megacrit.cardcrawl.cards.red.Strike_Red;
import com.megacrit.cardcrawl.cards.colorless.RitualDagger;
import com.megacrit.cardcrawl.helpers.CardLibrary;
import com.megacrit.cardcrawl.vfx.FastCardObtainEffect;
import guardian.orbs.StasisOrb;
import guardian.cards.InStasisCard;
import guardian.actions.StasisEvokeIfRoomInHandAction;
import automaton.FunctionHelper;
import automaton.cards.*;
import automaton.powers.CleanCodePower;
import automaton.cardmods.CardEffectsCardMod;
import basemod.BaseMod;
import basemod.abstracts.AbstractCardModifier;
import basemod.helpers.CardModifierManager;
import basemod.interfaces.*;
import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.backends.lwjgl.LwjglApplicationConfiguration;
import com.evacipated.cardcrawl.modthespire.lib.SpireInitializer;
import com.megacrit.cardcrawl.actions.GameActionManager;
import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.characters.AbstractPlayer;
import com.megacrit.cardcrawl.core.*;
import com.megacrit.cardcrawl.dungeons.*;
import com.megacrit.cardcrawl.map.MapRoomNode;
import com.megacrit.cardcrawl.rooms.MonsterRoom;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;

@SpireInitializer
public class Probe implements PostInitializeSubscriber, PostUpdateSubscriber {
 boolean ready, ran;
 public static void initialize(){LwjglApplicationConfiguration.disableAudio=true;BaseMod.subscribe(new Probe());}
 public void receivePostInitialize(){ready=true;}
 interface Sample {String run() throws Exception;}
 void record(String value) throws Exception {
  String line=System.getProperty("sts.verify.nonce")+"|"+value;
  System.out.println("STASIS_SCOUT "+line);
  Files.write(Paths.get("/logs/probe.txt"),(line+"\n").getBytes(StandardCharsets.UTF_8),StandardOpenOption.CREATE,StandardOpenOption.APPEND);
 }
 void sample(String id,Sample action)throws Exception {
  String value="",error="none";
  try{fresh();value=action.run();}catch(Throwable failure){error=failure.getClass().getName();failure.printStackTrace();}
  record("case,id="+id+",error="+error+","+value);
 }
 void fresh(){
  AbstractDungeon.player=CardCrawlGame.characterManager.recreateCharacter(AbstractPlayer.PlayerClass.IRONCLAD);
  AbstractDungeon.actionManager=new GameActionManager();
  MapRoomNode roomNode=new MapRoomNode(0,0);roomNode.room=new MonsterRoom();
  roomNode.room.monsters=new com.megacrit.cardcrawl.monsters.MonsterGroup(new com.megacrit.cardcrawl.monsters.AbstractMonster[]{new com.megacrit.cardcrawl.monsters.exordium.Cultist(0,0)});
  AbstractDungeon.setCurrMapNode(roomNode);
  AbstractDungeon.getCurrRoom().phase=AbstractRoom.RoomPhase.COMBAT;
  AbstractDungeon.player.increaseMaxOrbSlots(2,true);
 }
 void drain(){
  int ticks=0;
  while((!AbstractDungeon.actionManager.actions.isEmpty()||AbstractDungeon.actionManager.currentAction!=null)&&ticks++<20000){
   AbstractDungeon.actionManager.update();AbstractDungeon.getCurrRoom().souls.update();
  }
  if(ticks>=20000)throw new IllegalStateException("Native action manager did not settle");
 }
 int count(CardGroup group,AbstractCard card){int n=0;for(AbstractCard c:group.group)if(c==card)n++;return n;}
 String ownership(AbstractCard card){
  int held=0;for(AbstractOrb o:AbstractDungeon.player.orbs)if(o instanceof StasisOrb&&((StasisOrb)o).stasisCard==card)held++;
  return "hand="+count(AbstractDungeon.player.hand,card)+"/draw="+count(AbstractDungeon.player.drawPile,card)+"/discard="+count(AbstractDungeon.player.discardPile,card)+"/exhaust="+count(AbstractDungeon.player.exhaustPile,card)+"/limbo="+count(AbstractDungeon.player.limbo,card)+"/held="+held+"/orbs="+AbstractDungeon.player.orbs.size()+"/max="+AbstractDungeon.player.maxOrbs+"/retain="+card.retain+"/handSize="+AbstractDungeon.player.hand.size();
 }
 String eviction(boolean volatileCard,boolean stale,boolean full){
  AbstractCard card=volatileCard?new ChargeCore():new Strike_Red();AbstractDungeon.player.hand.addToTop(card);
  StasisOrb orb=new StasisOrb(card,AbstractDungeon.player.hand);AbstractDungeon.player.channelOrb(orb);
  StasisEvokeIfRoomInHandAction delayed=new StasisEvokeIfRoomInHandAction(orb);
  if(stale)AbstractDungeon.player.evokeOrb();
  if(full)for(int i=0;i<10;i++)AbstractDungeon.player.hand.addToTop(new Strike_Red());
  String before=ownership(card);AbstractDungeon.actionManager.addToBottom(delayed);drain();
  return "before="+before+",after="+ownership(card);
 }
 String placement(String mode){
  AbstractCard card=new Strike_Red();AbstractDungeon.player.hand.addToTop(card);
  PlaceActualCardIntoStasis delayed=new PlaceActualCardIntoStasis(card,AbstractDungeon.player.hand,true);
  if(mode.equals("moved"))AbstractDungeon.player.hand.moveToDiscardPile(card);
  if(mode.equals("already"))AbstractDungeon.player.channelOrb(new StasisOrb(card,AbstractDungeon.player.hand));
  String before=ownership(card);AbstractDungeon.actionManager.addToBottom(delayed);drain();
  return "before="+before+",after="+ownership(card);
 }
 String random(int amount,boolean empty){
  AbstractCard card=new Strike_Red();if(!empty)AbstractDungeon.player.drawPile.addToTop(card);
  String before=ownership(card);AbstractDungeon.actionManager.addToBottom(new PlaceRandomCardIntoStasisAction(amount));drain();
  return "before="+before+",after="+ownership(card);
 }

 String queuedReturn(boolean volatileCard,int copies){
  AbstractCard card=volatileCard?new ChargeCore():new Strike_Red();
  AbstractDungeon.player.hand.addToTop(card);
  StasisOrb orb=new StasisOrb(card,AbstractDungeon.player.hand);AbstractDungeon.player.channelOrb(orb);
  for(int i=0;i<copies;i++)AbstractDungeon.actionManager.addToBottom(new StasisEvokeIfRoomInHandAction(orb));
  drain();return "after="+ownership(card);
 }
 String placementMore(String mode,boolean retain){
  AbstractCard card=new Strike_Red();card.retain=retain;
  CardGroup source=mode.equals("discard")?AbstractDungeon.player.discardPile:AbstractDungeon.player.hand;
  source.addToTop(card);
  PlaceActualCardIntoStasis first=new PlaceActualCardIntoStasis(card,source,true);
  PlaceActualCardIntoStasis second=mode.equals("duplicate")?new PlaceActualCardIntoStasis(card,source,true):null;
  if(mode.equals("blocked")){
   AbstractDungeon.player.channelOrb(new StasisOrb(new Strike_Red()));
   AbstractDungeon.player.channelOrb(new StasisOrb(new Strike_Red()));
  }
  if(mode.equals("moved"))source.moveToDiscardPile(card);
  AbstractDungeon.actionManager.addToBottom(first);
  if(mode.equals("duplicate"))AbstractDungeon.actionManager.addToBottom(second);
  drain();return "after="+ownership(card);
 }
 String generated(int amount,String mode){
  AbstractCard original=new Strike_Red();
  if(!mode.equals("empty"))AbstractDungeon.player.channelOrb(new StasisOrb(original));
  if(mode.equals("mixed"))AbstractDungeon.player.channelOrb(new Lightning());
  if(mode.equals("full"))AbstractDungeon.player.channelOrb(new StasisOrb(new Strike_Red()));
  AbstractDungeon.actionManager.addToBottom(new PlaceRandom1CostIntoStasis(amount));drain();
  int held=0;for(AbstractOrb orb:AbstractDungeon.player.orbs)if(orb instanceof StasisOrb)held++;
  return "after="+ownership(original)+",heldTotal="+held;
 }
 String randomMany(int amount,boolean discard){
  CardGroup source=discard?AbstractDungeon.player.discardPile:AbstractDungeon.player.drawPile;
  AbstractCard a=new Strike_Red(),b=new Strike_Red(),c=new Strike_Red();
  source.addToTop(a);source.addToTop(b);source.addToTop(c);
  AbstractDungeon.actionManager.addToBottom(new PlaceRandomCardIntoStasisAction(amount));drain();
  int held=0;for(AbstractOrb orb:AbstractDungeon.player.orbs)if(orb instanceof StasisOrb)held++;
  return "heldTotal="+held+",drawSize="+AbstractDungeon.player.drawPile.size()+",discardSize="+AbstractDungeon.player.discardPile.size()+",handSize="+AbstractDungeon.player.hand.size()+",orbs="+AbstractDungeon.player.orbs.size();
 }
 String generatedSingle(){
  AbstractCard card=new Strike_Red();AbstractDungeon.actionManager.addToBottom(new PlaceActualCardIntoStasis(card));drain();return "after="+ownership(card);
 }
 public static class HookCard extends Strike_Red implements InStasisCard {
  public int entered,evoked,returned;
  public void whenEnteredStasis(StasisOrb orb){entered++;}
  public void onEvoke(StasisOrb orb){evoked++;}
  public void whenReturnedFromStasis(){returned++;}
  public AbstractCard makeCopy(){return new HookCard();}
 }
 String nativeOrb(String kind,boolean recursion,boolean upgraded){
  AbstractCard card=kind.equals("hook")?new HookCard():kind.equals("volatile")?new ChargeCore():new Strike_Red();
  if(kind.equals("hook")&&!recursion)card.tags.add(GuardianMod.VOLATILE);
  if(upgraded)card.upgrade();
  AbstractDungeon.player.hand.addToTop(card);
  StasisOrb orb=new StasisOrb(card,AbstractDungeon.player.hand);AbstractDungeon.player.channelOrb(orb);
  if(upgraded)orb.onStartOfTurn();
  if(recursion)new Recursion().use(AbstractDungeon.player,null);else new Dualcast().use(AbstractDungeon.player,null);
  drain();
  int held=0,remaining=-1;AbstractCard other=null;
  for(AbstractOrb current:AbstractDungeon.player.orbs)if(current instanceof StasisOrb){held++;other=((StasisOrb)current).stasisCard;remaining=current.passiveAmount;}
  String hooks=card instanceof HookCard?"/entered="+((HookCard)card).entered+"/evoked="+((HookCard)card).evoked+"/returned="+((HookCard)card).returned:"";
  String copied=other==null?"none":"same="+(card==other)+"/damage="+other.baseDamage+"/upgraded="+other.upgraded+"/entered="+(other instanceof HookCard?((HookCard)other).entered:-1)+"/remaining="+remaining;
  return "after="+ownership(card)+hooks+",heldTotal="+held+",copy="+copied+",sourceDamage="+card.baseDamage;
 }
 String nativeLightning(){
  AbstractDungeon.player.channelOrb(new Lightning());new Dualcast().use(AbstractDungeon.player,null);drain();
  int lightning=0;for(AbstractOrb orb:AbstractDungeon.player.orbs)if(orb instanceof Lightning)lightning++;
  return "lightning="+lightning+",orbs="+AbstractDungeon.player.orbs.size()+",max="+AbstractDungeon.player.maxOrbs;
 }
 public void receivePostUpdate(){if(!ready||ran||Gdx.graphics.getDeltaTime()<=0)return;ran=true;try{
  CardCrawlGame.mode=CardCrawlGame.GameMode.GAMEPLAY;
  AbstractDungeon.player=CardCrawlGame.characterManager.recreateCharacter(AbstractPlayer.PlayerClass.IRONCLAD);
  Settings.seed=12345L;AbstractDungeon.generateSeeds();
  CardCrawlGame.dungeon=new Exordium(AbstractDungeon.player,new ArrayList<String>());
  MapRoomNode node=new MapRoomNode(0,0);node.room=new MonsterRoom();
  node.room.monsters=new com.megacrit.cardcrawl.monsters.MonsterGroup(new com.megacrit.cardcrawl.monsters.AbstractMonster[]{new com.megacrit.cardcrawl.monsters.exordium.Cultist(0,0)});
  AbstractDungeon.setCurrMapNode(node);
  record("engine,gl="+(Gdx.gl!=null)+",delta="+Gdx.graphics.getDeltaTime());
  sample("normal-return",()->eviction(false,false,false));
  sample("stale-return",()->eviction(false,true,false));
  sample("normal-volatile",()->eviction(true,false,false));
  sample("stale-volatile",()->eviction(true,true,false));
  sample("full-hand",()->eviction(false,false,true));
  sample("placement-normal",()->placement("normal"));
  sample("placement-moved",()->placement("moved"));
  sample("placement-already-held",()->placement("already"));
  sample("random-one",()->random(1,false));
  sample("random-zero",()->random(0,false));
  sample("random-empty",()->random(1,true));
  sample("return-queued-twice",()->queuedReturn(false,2));
  sample("volatile-queued-twice",()->queuedReturn(true,2));
  sample("placement-duplicate",()->placementMore("duplicate",false));
  sample("placement-discard",()->placementMore("discard",false));
  sample("placement-blocked-unretained",()->placementMore("blocked",false));
  sample("placement-blocked-retained",()->placementMore("blocked",true));
  sample("placement-moved-unretained",()->placementMore("moved",false));
  sample("placement-moved-retained",()->placementMore("moved",true));
  sample("placement-generated",()->generatedSingle());
  sample("generated-zero",()->generated(0,"empty"));
  sample("generated-one",()->generated(1,"empty"));
  sample("generated-two",()->generated(2,"empty"));
  sample("generated-overflow",()->generated(3,"empty"));
  sample("generated-existing",()->generated(2,"existing"));
  sample("generated-mixed",()->generated(2,"mixed"));
  sample("generated-blocked",()->generated(2,"full"));
  sample("random-three-draw",()->randomMany(3,false));
  sample("random-three-discard",()->randomMany(3,true));
  sample("native-dualcast-normal",()->nativeOrb("normal",false,false));
  sample("native-dualcast-volatile",()->nativeOrb("volatile",false,false));
  sample("native-dualcast-hook",()->nativeOrb("hook",false,false));
  sample("native-recursion-normal",()->nativeOrb("normal",true,false));
  sample("native-recursion-volatile",()->nativeOrb("volatile",true,false));
  sample("native-recursion-hook",()->nativeOrb("hook",true,false));
  sample("native-recursion-upgraded",()->nativeOrb("normal",true,true));
  sample("native-dualcast-lightning",()->nativeLightning());
  record("completed=true");System.exit(0);
 }catch(Throwable failure){failure.printStackTrace();System.exit(2);}}
}
