package iconlayoutprobe;
import basemod.BaseMod;
import basemod.interfaces.*;
import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.backends.lwjgl.LwjglApplicationConfiguration;
import com.badlogic.gdx.graphics.*;
import com.badlogic.gdx.graphics.g2d.*;
import com.evacipated.cardcrawl.modthespire.lib.SpireInitializer;
import com.evacipated.cardcrawl.mod.stslib.icons.*;
import com.megacrit.cardcrawl.actions.GameActionManager;
import com.megacrit.cardcrawl.characters.AbstractPlayer;
import com.megacrit.cardcrawl.dungeons.*;
import com.megacrit.cardcrawl.map.MapRoomNode;
import com.megacrit.cardcrawl.rooms.MonsterRoom;
import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.cards.red.Strike_Red;
import com.megacrit.cardcrawl.core.*;
import com.megacrit.cardcrawl.helpers.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
@SpireInitializer
public class Probe implements PostInitializeSubscriber,PostUpdateSubscriber {
    boolean ready,ran;
    public static void initialize(){LwjglApplicationConfiguration.disableAudio=true;BaseMod.subscribe(new Probe());}
    public void receivePostInitialize(){ready=true;}
    void record(String line)throws Exception{String t=System.getProperty("sts.verify.nonce","missing")+"|"+line;Files.write(Paths.get("/logs/probe.txt"),(t+"\n").getBytes(StandardCharsets.UTF_8),StandardOpenOption.CREATE,StandardOpenOption.APPEND);}
    static String positions="";static int cardDraws,tipDraws;
    static String f(float v){return String.format(Locale.ROOT,"%.3f",v);}
    static String b64(String s){return Base64.getEncoder().encodeToString(s.getBytes(StandardCharsets.UTF_8));}
    static class Icon extends AbstractCustomIcon {
        Icon(String name,Texture t){super(name,t);}
        public void render(SpriteBatch sb,float x,float y,float ox,float oy,float scale,float angle){tipDraws++;positions+=f((x-100)/Settings.scale)+":"+f((y-400)/Settings.scale)+";";super.render(sb,x,y,ox,oy,scale,angle);}
        public void renderOnCard(SpriteBatch sb,AbstractCard card,float x,float y){cardDraws++;super.renderOnCard(sb,card,x,y);}
    }
    static class Case {
        final String id,mode,text;final boolean chars;final float width,spacing;final int count;
        Case(String id,String mode,String text,boolean chars,float width,float spacing,int count){this.id=id;this.mode=mode;this.text=text;this.chars=chars;this.width=width;this.spacing=spacing;this.count=count;}
    }
    static final Case[] CASES={
        new Case("engine","engine","",false,500f,30f,0),
        new Case("width-one","width","%I%",false,500f,30f,1),
        new Case("width-wide","width","%I% %I% %I%",false,500f,30f,3),
        new Case("width-narrow","width","%I% %I% %I%",false,30f,30f,1),
        new Case("width-after-newline","width","%I% NL %I%",false,500f,30f,1),
        new Case("width-lowercase","width","%L%",false,500f,30f,1),
        new Case("width-short-code","width","%S%",false,500f,30f,1),
        new Case("width-cn","width","%I%",true,500f,30f,1),
        new Case("en-height-three","height","%I% %I% %I%",false,30f,30f,0),
        new Case("en-height-five","height","%I% %I% %I% %I% %I%",false,60f,30f,0),
        new Case("en-height-spacing","height","%I% %I% %I%",false,30f,44f,0),
        new Case("en-height-newline","height","%I% NL %I% %I% %I%",false,30f,30f,0),
        new Case("cn-height-three","height","%I% %I% %I%",true,30f,30f,0),
        new Case("cn-height-five","height","%I% %I% %I% %I% %I%",true,48f,30f,0),
        new Case("cn-height-lowercase","height","%L% %L% %L%",true,30f,44f,0),
        new Case("cn-height-mixed","height","abc %I% xyz %I%",true,70f,30f,0),
        new Case("cn-height-orb","height","[E] %I% [E] %I%",true,70f,30f,0),
        new Case("cn-height-colored","height","#rabc %I% #gxyz %I%",true,70f,30f,0),
        new Case("cn-wrap-three","render","%I% %I% %I%",true,30f,30f,0),
        new Case("cn-wrap-five","render","%I% %I% %I% %I% %I%",true,48f,30f,0),
        new Case("cn-wrap-lowercase","render","%L% %L% %L%",true,30f,44f,0),
        new Case("cn-wrap-newline","render","%I% NL %I% %I%",true,30f,30f,0),
        new Case("header-one","header","Label %I% Tail",false,500f,30f,1),
        new Case("header-multiple","header","Label %I% %S% %I% Tail",false,500f,30f,3),
        new Case("header-lowercase","header","Label %L% Tail",false,500f,30f,1),
        new Case("tint-0","tint","",false,500f,30f,0),
        new Case("tint-1","tint","",false,500f,30f,1),
        new Case("tint-2","tint","",false,500f,30f,2),
        new Case("card-en-1","card","",false,500f,30f,1),
        new Case("card-en-6","card","",false,500f,30f,6),
        new Case("card-en-14","card","",false,500f,30f,14),
        new Case("newline-en","render","%I% NL %I%",false,500f,30f,0),
        new Case("wide-en","render","%I% %I% %I%",false,500f,30f,0),
        new Case("ordinary-height-en","height","abc NL xyz",false,500f,30f,0),
        new Case("unknown-render-en","render","[UnknownIcon]",false,500f,30f,0),
        new Case("card-cn-1","card","",true,500f,30f,1),
        new Case("card-cn-6","card","",true,500f,30f,6),
        new Case("card-cn-14","card","",true,500f,30f,14),
        new Case("newline-cn","render","%I% NL %I%",true,500f,30f,0),
        new Case("wide-cn","render","%I% %I% %I%",true,500f,30f,0),
        new Case("ordinary-height-cn","height","abc NL xyz",true,500f,30f,0),
        new Case("unknown-render-cn","render","[UnknownIcon]",true,500f,30f,0),
        new Case("ordinary-header","header","Label Tail",false,500f,30f,0)
    };
    void sample(Case c,SpriteBatch sb,Icon icon,Icon shortIcon)throws Exception{
        boolean previous=Settings.lineBreakViaCharacter;Settings.lineBreakViaCharacter=c.chars;
        positions="";cardDraws=tipDraws=0;sb.setColor(Color.WHITE);
        String text=c.text.replace("%I%",icon.cardCode()).replace("%L%",icon.cardCode().toLowerCase(Locale.ROOT)).replace("%S%",shortIcon.cardCode());
        try{
            String value="",details="";
            if(c.mode.equals("engine"))value=Boolean.toString(Gdx.gl!=null);
            else if(c.mode.equals("width")){
                float space=new GlyphLayout(FontHelper.tipBodyFont," ").width;
                float measured=FontHelper.getSmartWidth(FontHelper.tipBodyFont,text,c.width*Settings.scale,c.spacing*Settings.scale);
                value=f((measured-space*c.count)/Settings.scale);details=",measured="+f(measured)+",space="+f(space);
            }else if(c.mode.equals("height"))value=f(FontHelper.getSmartHeight(FontHelper.tipBodyFont,text,c.width*Settings.scale,c.spacing*Settings.scale)/Settings.scale);
            else if(c.mode.equals("render")){
                FontHelper.renderSmartText(sb,FontHelper.tipBodyFont,text,100,400,c.width*Settings.scale,c.spacing*Settings.scale,Color.WHITE);
                value=positions;
            }else if(c.mode.equals("header")){
                PowerTip tip=new PowerTip(text,"body");ArrayList<PowerTip> tips=new ArrayList<>();tips.add(tip);
                TipHelper.render(sb);tipDraws=0;
                TipHelper.queuePowerTips(200,500,tips);TipHelper.render(sb);int first=tipDraws;String firstHeader=tip.header;
                tipDraws=0;TipHelper.queuePowerTips(200,500,tips);TipHelper.render(sb);
                value=Boolean.toString(first==c.count&&tipDraws==c.count&&text.equals(firstHeader)&&text.equals(tip.header));
                details=",first="+first+",second="+tipDraws+",original="+b64(text)+",firstHeader="+b64(firstHeader)+",secondHeader="+b64(tip.header);
            }else if(c.mode.equals("tint")){
                Color tint=new Color(.2f,.4f,.6f,.8f);sb.setColor(tint);Color before=new Color(sb.getColor());
                AbstractCard card=new Strike_Red();card.current_x=200;card.current_y=300;card.drawScale=1;
                if(c.count==0)icon.render(sb,100,200,0,0,1,0);
                else if(c.count==1)icon.renderOnCard(sb,card,12,20);
                else icon.renderOnSCV(sb,card,12,20,200,300,2);
                value=Boolean.toString(before.equals(sb.getColor()));details=",before="+before+",after="+new Color(sb.getColor());
            }else if(c.mode.equals("card")){
                AbstractCard card=new Strike_Red();StringBuilder raw=new StringBuilder();for(int i=0;i<c.count;i++)raw.append(icon.cardCode()).append(" ");
                card.rawDescription=raw.toString();card.initializeDescription();card.current_x=Settings.WIDTH/2f;card.current_y=Settings.HEIGHT/2f;card.drawScale=1;cardDraws=0;card.render(sb);
                value=Boolean.toString(cardDraws==c.count);details=",draws="+cardDraws;
            }else throw new IllegalArgumentException(c.mode);
            record("case,id="+c.id+",error=none,value="+value+details);
        }catch(Throwable error){record("case,id="+c.id+",error="+error.getClass().getName());error.printStackTrace();}
        finally{Settings.lineBreakViaCharacter=previous;}
    }
    public void receivePostUpdate(){if(!ready||ran)return;ran=true;try{
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

        Pixmap pixels=new Pixmap(24,24,Pixmap.Format.RGBA8888);pixels.setColor(Color.WHITE);pixels.fill();Texture texture=new Texture(pixels);pixels.dispose();
        Icon icon=new Icon("ProbeDBM",texture),shortIcon=new Icon("Q",texture);CustomIconHelper.addCustomIcon(icon);CustomIconHelper.addCustomIcon(shortIcon);
        SpriteBatch sb=new SpriteBatch();sb.setProjectionMatrix(new com.badlogic.gdx.math.Matrix4().setToOrtho2D(0,0,Settings.WIDTH,Settings.HEIGHT));sb.begin();
        try{for(Case c:CASES)sample(c,sb,icon,shortIcon);}finally{sb.end();sb.dispose();texture.dispose();}
        record("completed=true");System.exit(0);
    }catch(Throwable error){error.printStackTrace();System.exit(2);}}
}
