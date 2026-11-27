package blocksettlementprobe;
import basemod.BaseMod;
import com.evacipated.cardcrawl.mod.stslib.actions.tempHp.AddTemporaryHPAction;
import com.evacipated.cardcrawl.mod.stslib.patches.core.AbstractCreature.TempHPField;
import com.megacrit.cardcrawl.core.AbstractCreature;
import com.evacipated.cardcrawl.mod.stslib.damagemods.*;
import com.evacipated.cardcrawl.mod.stslib.blockmods.*;
import com.evacipated.cardcrawl.mod.stslib.powers.interfaces.*;
import com.megacrit.cardcrawl.cards.DamageInfo;
import com.megacrit.cardcrawl.powers.StrengthPower;
import com.evacipated.cardcrawl.mod.stslib.cards.interfaces.MultiUpgradeCard;
import com.megacrit.cardcrawl.helpers.CardLibrary;
import com.megacrit.cardcrawl.screens.runHistory.RunHistoryScreen;
import java.util.Base64;
import basemod.patches.com.megacrit.cardcrawl.cards.AbstractCard.DynamicTextBlocks;
import basemod.interfaces.*;
import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.backends.lwjgl.LwjglApplicationConfiguration;
import com.evacipated.cardcrawl.modthespire.lib.SpireInitializer;
import com.megacrit.cardcrawl.actions.GameActionManager;
import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.cards.red.Strike_Red;
import com.megacrit.cardcrawl.characters.AbstractPlayer;
import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.core.Settings;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.dungeons.Exordium;
import com.megacrit.cardcrawl.map.MapRoomNode;
import com.megacrit.cardcrawl.rooms.MonsterRoom;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
@SpireInitializer
public class Probe implements PostInitializeSubscriber, PostUpdateSubscriber {
    private boolean ready, ran;
    public static void initialize() { LwjglApplicationConfiguration.disableAudio = true; BaseMod.subscribe(new Probe()); }
    public void receivePostInitialize() { ready = true; }

    private void record(String line) throws Exception {
        String result = System.getProperty("sts.verify.nonce", "scout") + "|" + line;
        System.out.println("BLOCK_SETTLEMENT_SCOUT " + result);
        Files.write(Paths.get("/logs/probe.txt"), (result + "\n").getBytes(StandardCharsets.UTF_8), StandardOpenOption.CREATE, StandardOpenOption.APPEND);
    }



    private static String mode, events;
    private static int depth;
    private static AbstractCreature target, other;
    public static class Mod extends AbstractBlockModifier {
        final String id; Mod(String id){this.id=id;}
        public String getName(){return id;} public String getDescription(){return id;}
        public boolean shouldStack(){return false;}
        public Priority priority(){return id.equals("A")?Priority.TOP:id.equals("C")?Priority.BOTTOM:Priority.NORMAL;}
        public AbstractBlockModifier makeCopy(){return new Mod(id);}
        public int onRemove(boolean start,DamageInfo info,int remaining){
            events+=id+"/"+remaining+";";
            if(id.equals("A")&&depth==0){depth++;try{
                if(mode.equals("refund"))owner.addBlock(4);
                if(mode.equals("nested-loss"))owner.loseBlock(2);
                if(mode.equals("nested-specific"))BlockModifierManager.reduceSpecificBlockType(find(owner,"B"),2);
                if(mode.equals("cross-owner"))other.loseBlock(2);
                if(mode.equals("attenuate"))return Math.max(0,remaining-6);
            }finally{depth--;}}
            return remaining;
        }
    }
    private static BlockInstance find(AbstractCreature owner,String id){
        for(BlockInstance b:BlockModifierManager.blockInstances(owner))for(AbstractBlockModifier m:b.getBlockTypes())if(m.getName().equals(id))return b;
        throw new IllegalStateException("Missing "+id);
    }
    private static void add(AbstractCreature owner,String id,int n){BlockModifierManager.addCustomBlock(id,Collections.<AbstractBlockModifier>singletonList(new Mod(id)),owner,n);}
    private static String state(AbstractCreature owner){
        ArrayList<String> parts=new ArrayList<>();
        for(BlockInstance b:BlockModifierManager.blockInstances(owner))parts.add((b.defaultBlock()?"plain":b.getBlockTypes().get(0).getName())+":"+b.getBlockAmount()+";");
        Collections.sort(parts);return String.join("",parts);
    }
    private void sample(String kind,String scenario)throws Exception{
        mode="plain";depth=0;events="";
        AbstractDungeon.player=CardCrawlGame.characterManager.recreateCharacter(AbstractPlayer.PlayerClass.IRONCLAD);
        AbstractDungeon.player.relics.clear();AbstractDungeon.player.powers.clear();
        target=kind.equals("player")?AbstractDungeon.player:new com.megacrit.cardcrawl.monsters.exordium.Cultist(0,0);
        other=new com.megacrit.cardcrawl.monsters.exordium.Cultist(0,0);
        target.powers.clear();other.powers.clear();
        add(target,"A",5);add(target,"B",7);add(target,"C",9);add(other,"B",10);
        mode=scenario;int health=target.currentHealth;String error="none";
        try{
            if(scenario.equals("specific"))BlockModifierManager.reduceSpecificBlockType(find(target,"B"),3);
            else if(scenario.equals("zero-specific")){BlockModifierManager.reduceSpecificBlockType(find(target,"B"),0);target.loseBlock(2);}
            else if(scenario.equals("cross-owner"))BlockModifierManager.removeSpecificBlockType(find(target,"A"));
            else if(scenario.equals("attenuate"))target.damage(new DamageInfo(null,18,DamageInfo.DamageType.NORMAL));
            else target.loseBlock(8);
        }catch(Throwable failure){error=failure.getClass().getName();failure.printStackTrace();}
        record("case,id="+kind+"-"+scenario+",error="+error+",block="+target.currentBlock+",stacks="+state(target)+",otherBlock="+other.currentBlock+",otherStacks="+state(other)+",hpLost="+(health-target.currentHealth)+",events="+events);
        // A fresh public targeted operation prevents one aborted request leaking into another fixture.
        mode="plain";
        AbstractCreature recovery=new com.megacrit.cardcrawl.monsters.exordium.Cultist(0,0);
        recovery.powers.clear();recovery.addBlock(1);
        BlockModifierManager.reduceSpecificBlockType(BlockModifierManager.blockInstances(recovery).get(0),1);
    }
    private void capacity(String kind,String scenario)throws Exception{
        mode="plain";depth=0;events="";
        AbstractDungeon.player=CardCrawlGame.characterManager.recreateCharacter(AbstractPlayer.PlayerClass.IRONCLAD);
        AbstractDungeon.player.relics.clear();AbstractDungeon.player.powers.clear();
        target=kind.equals("player")?AbstractDungeon.player:new com.megacrit.cardcrawl.monsters.exordium.Cultist(0,0);
        target.powers.clear();String error="none";
        try{
            if(scenario.equals("cap-full")){add(target,"A",999);add(target,"B",5);}
            else if(scenario.equals("cap-plain")){add(target,"A",700);target.addBlock(600);}
            else if(scenario.equals("cap-loss")){add(target,"A",700);add(target,"B",600);target.loseBlock(8);}
            else if(scenario.equals("zero-gain")){add(target,"A",7);add(target,"B",0);}
            else {add(target,"A",700);add(target,"B",600);}
        }catch(Throwable failure){error=failure.getClass().getName();failure.printStackTrace();}
        record("case,id="+kind+"-"+scenario+",error="+error+",block="+target.currentBlock+",stacks="+state(target)+",events="+events);
    }
    public void receivePostUpdate(){
        if(!ready||ran)return;ran=true;
        try{
            CardCrawlGame.mode = CardCrawlGame.GameMode.GAMEPLAY;
            AbstractDungeon.player = CardCrawlGame.characterManager.recreateCharacter(AbstractPlayer.PlayerClass.IRONCLAD);
            Settings.seed = 12345L;
            AbstractDungeon.generateSeeds();
            CardCrawlGame.dungeon = new Exordium(AbstractDungeon.player, new ArrayList<String>());
            AbstractDungeon.actionManager = new GameActionManager();
            MapRoomNode node = new MapRoomNode(0, 0);
            node.room = new MonsterRoom();
            node.room.monsters = new com.megacrit.cardcrawl.monsters.MonsterGroup(new com.megacrit.cardcrawl.monsters.AbstractMonster[]{new com.megacrit.cardcrawl.monsters.exordium.Cultist(0.0F, 0.0F)});
            AbstractDungeon.setCurrMapNode(node);
            AbstractDungeon.player.relics.clear();
            record("engine,gl=" + (Gdx.gl != null));




            for(String kind:new String[]{"player","monster"})
                for(String scenario:new String[]{"plain","specific","zero-specific","refund","nested-loss","nested-specific","cross-owner","attenuate"})sample(kind,scenario);
            for(String kind:new String[]{"player","monster"})
                for(String scenario:new String[]{"cap-multiple","cap-full","cap-plain","cap-loss","zero-gain"})capacity(kind,scenario);
            record("completed=true");System.exit(0);
        }catch(Throwable error){error.printStackTrace();System.exit(2);}
    }
}
