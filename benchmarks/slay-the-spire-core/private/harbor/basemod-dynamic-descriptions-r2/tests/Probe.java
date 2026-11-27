package textprobe;
import basemod.BaseMod;
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

    private static int value, calls;
    private void record(String line) throws Exception {
        String result = System.getProperty("sts.verify.nonce", "scout") + "|" + line;
        System.out.println("TEXT_SCOUT " + result);
        Files.write(Paths.get("/logs/probe.txt"), (result + "\n").getBytes(StandardCharsets.UTF_8), StandardOpenOption.CREATE, StandardOpenOption.APPEND);
    }
    private String rendered(AbstractCard card) {
        StringBuilder out = new StringBuilder();
        for (com.megacrit.cardcrawl.cards.DescriptionLine line : card.description) out.append(line.text).append('\n');
        return Base64.getEncoder().encodeToString(out.toString().getBytes(StandardCharsets.UTF_8));
    }
    private void sample(String id, int number, String text) throws Exception {
        AbstractCard card = new Strike_Red();
        value = number; calls = 0;
        card.rawDescription = text;
        String error = "none";
        try { card.initializeDescription(); } catch (Throwable failure) { error = failure.getClass().getName(); }
        record("case,id=" + id + ",error=" + error + ",calls=" + calls + ",text=" + rendered(card));
    }

    static class Generated extends basemod.abstracts.AbstractCardModifier {
        public String modifyDescription(String raw, AbstractCard card) { return raw + " {@@}{!probe:count!|1=one|2=two|@=other}"; }
        public basemod.abstracts.AbstractCardModifier makeCopy() { return new Generated(); }
    }
    private void paint(AbstractCard card) {
        com.badlogic.gdx.graphics.g2d.SpriteBatch batch = new com.badlogic.gdx.graphics.g2d.SpriteBatch();
        try {
            batch.setProjectionMatrix(new com.badlogic.gdx.math.Matrix4().setToOrtho2D(0, 0, Settings.WIDTH, Settings.HEIGHT));
            card.current_x = Settings.WIDTH / 2.0F; card.current_y = Settings.HEIGHT / 2.0F; card.drawScale = 1.0F;
            batch.begin(); card.render(batch); batch.end();
        } finally { batch.dispose(); }
    }
    private void refresh(String id, boolean generated) throws Exception {
        AbstractCard card = new Strike_Red();
        value = 1; calls = 0;
        if (generated) {
            card.rawDescription = "plain";
            basemod.helpers.CardModifierManager.addModifier(card, new Generated());
        } else {
            card.rawDescription = "{@@}{!probe:count!|1=one|2=two|@=other}";
            card.initializeDescription();
        }
        String before = rendered(card); int initializedCalls = calls;
        value = 2; calls = 0;
        String error = "none";
        try { paint(card); } catch (Throwable failure) { error = failure.getClass().getName(); failure.printStackTrace(); }
        record("case,id=" + id + ",error=" + error + ",before=" + before + ",after=" + rendered(card) + ",initializedCalls=" + initializedCalls + ",renderCalls=" + calls);
    }
    private void unmark() throws Exception {
        AbstractCard card = new Strike_Red(); value = 2; calls = 0;
        card.rawDescription = "{@@}{!probe:count!|2=two|@=other}"; card.initializeDescription();
        card.rawDescription = "{!probe:count!|2=two|@=other}"; calls = 0;
        card.initializeDescription();
        record("case,id=unmark,error=none,calls=" + calls + ",text=" + rendered(card));
    }
    private void coherent() throws Exception {
        AbstractCard card = new Strike_Red();
        DynamicTextBlocks.registerCustomCheck("probe:ticking", c -> ++calls);
        card.rawDescription = "{@@}{!probe:ticking!|1=first|2=second|@=later} {!probe:ticking!|1=first|2=second|@=later}";
        calls = 0; card.initializeDescription();
        record("case,id=coherent-initialization,error=none,calls=" + calls + ",text=" + rendered(card));
    }

    interface Scenario { void run() throws Exception; }
    private void safe(String id, Scenario body) throws Exception {
        try { body.run(); } catch (Throwable error) { record("case,id=" + id + ",error=" + error.getClass().getName()); }
    }
    private void tickingRender() throws Exception {
        AbstractCard card = new Strike_Red();
        DynamicTextBlocks.registerCustomCheck("probe:ticking", c -> ++calls);
        card.rawDescription = "{@@}{!probe:ticking!|1=first|2=second|@=later} {!probe:ticking!|1=first|2=second|@=later}";
        calls = 0; card.initializeDescription(); String before = rendered(card);
        paint(card);
        record("case,id=ticking-render,error=none,calls=" + calls + ",before=" + before + ",after=" + rendered(card));
    }
    private void independent() throws Exception {
        AbstractCard left = new Strike_Red(), right = new Strike_Red();
        DynamicTextBlocks.registerCustomCheck("probe:owner", c -> c == left ? 1 : 2);
        left.rawDescription = right.rawDescription = "{@@}{!probe:owner!|1=left|2=right|@=wrong}";
        left.initializeDescription(); right.initializeDescription(); paint(left);
        record("case,id=independent-cards,error=none,left=" + rendered(left) + ",right=" + rendered(right));
    }
    private void nestedCard() throws Exception {
        AbstractCard left = new Strike_Red(), right = new Strike_Red();
        final int[] reads = {0, 0}; final boolean[] entered = {false};
        DynamicTextBlocks.registerCustomCheck("probe:owner", c -> {
            if (c == right) { reads[1]++; return 2; }
            reads[0]++;
            if (!entered[0]) { entered[0] = true; right.initializeDescription(); }
            return 1;
        });
        left.rawDescription = "{@@}{!probe:owner!|1=left|@=wrong} {!probe:owner!|1=left|@=wrong}";
        right.rawDescription = "{@@}{!probe:owner!|2=right|@=wrong}";
        left.initializeDescription();
        record("case,id=nested-card,error=none,left=" + rendered(left) + ",right=" + rendered(right) + ",leftReads=" + reads[0] + ",rightReads=" + reads[1]);
    }
    private void changingGenerated() throws Exception {
        AbstractCard card = new Strike_Red(); final String[] pattern = {"{@@}{!probe:count!|1=old|@=wrong}"};
        card.rawDescription = "plain"; value = 1;
        basemod.helpers.CardModifierManager.addModifier(card, new basemod.abstracts.AbstractCardModifier() {
            public String modifyDescription(String raw, AbstractCard c) { return raw + " " + pattern[0]; }
            public basemod.abstracts.AbstractCardModifier makeCopy() { return this; }
        });
        String before = rendered(card);
        pattern[0] = "{@@}{!probe:count!|1=new|@=wrong}"; paint(card);
        record("case,id=generated-rewrite,error=none,before=" + before + ",after=" + rendered(card));
    }
    private void subscriberText() throws Exception {
        AbstractCard card = new Strike_Red(); card.rawDescription = "plain";
        OnCreateDescriptionSubscriber subscriber = (raw, c) -> c == card ? raw + " {@@}{!probe:count!|1=one|2=two|@=wrong}" : raw;
        BaseMod.subscribe(subscriber);
        try {
            value = 1; card.initializeDescription(); String before = rendered(card);
            value = 2; paint(card);
            record("case,id=subscriber-refresh,error=none,before=" + before + ",after=" + rendered(card));
        } finally { BaseMod.unsubscribe(subscriber); }
    }
    public void receivePostUpdate() {
        if (!ready || ran) return; ran = true;
        try {
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

            DynamicTextBlocks.registerCustomCheck("probe:count", card -> { calls++; return value; });
            DynamicTextBlocks.registerCustomCheck("probe:bomb", c -> { throw new AssertionError("inactive query evaluated"); });
            sample("direct-control", 2, "{@@}{!probe:count!|2=two|@=other}");
            sample("rightmost-control", 2, "{@@}{!probe:count!|>0=positive|2=two|@=other}");
            sample("divisible-control", 12, "{@@}{!probe:count!|%3=multiple|@=other}");
            sample("suffix-negative-control", 13, "{@@}{!probe:count!|&2=ending|@=other}");
            sample("empty-control", 2, "{@@}{!probe:count!|2=|@=other}");
            sample("repeat-control", 3, "{@@}{!probe:count!|repeat=ha}");
            sample("zero-repeat-control", 0, "{@@}{!probe:count!|repeat=x|@=wrong}");
            sample("negative-control", -3, "{@@}{!probe:count!|-3=negative|@=wrong}");
            sample("unmarked-control", 2, "{!probe:count!|2=two|@=other}");
            sample("unknown-control", 2, "{@@}{!probe:missing!|@=wrong}");
            sample("suffix-two", 12, "{@@}{!probe:count!|&2=ending|@=other}");
            sample("suffix-width", 100, "{@@}{!probe:count!|&00=ending|@=other}");
            sample("suffix-leading-width", 10, "{@@}{!probe:count!|&010=wrong|@=short}");
            sample("suffix-minimum", -2147483648, "{@@}{!probe:count!|&648=ending|@=other}");
            sample("zero-divisor", 12, "{@@}{!probe:count!|%0=wrong|@=safe}");
            sample("zero-zero-divisor", 0, "{@@}{!probe:count!|%0=wrong|@=safe}");
            sample("fraction-operand", 2, "{@@}{!probe:count!|1.5=wrong|@=safe}");
            sample("large-operand", 2, "{@@}{!probe:count!|2147483648=wrong|@=safe}");
            sample("decimal-leading-zero", 8, "{@@}{!probe:count!|08=eight|@=wrong}");
            sample("literal-dollar", 2, "{@@}{!probe:count!|2=cost$5|@=wrong}");
            sample("literal-backslash", 2, "{@@}{!probe:count!|2=C:\\save|@=wrong}");
            sample("payload-equals", 2, "{@@}{!probe:count!|2=x=y=z|@=wrong}");
            sample("escaped-pipe", 2, "{@@}{!probe:count!|2=a\\|b|@=wrong}");
            sample("escaped-braces", 2, "{@@}{!probe:count!|2=\\{plain\\}|@=wrong}");
            sample("escaped-backslash", 2, "{@@}{!probe:count!|2=a\\\\b|@=wrong}");
            sample("escaped-open", 2, "{@@}\\{!probe:count!|2=two|@=other}");
            sample("nested-selected", 2, "{@@}{!probe:count!|2={!probe:count!|2=inner|@=wrong}|@=outer}");
            sample("nested-fallback", 2, "{@@}{!probe:count!|1=wrong|@={!probe:count!|2=fallback|@=wrong}}");
            sample("nested-repeat", 2, "{@@}{!probe:count!|repeat={!probe:count!|2=x|@=wrong}}");
            sample("inactive-lazy", 2, "{@@}{!probe:count!|1={!probe:bomb!|@=wrong}|2=safe}");
            sample("overridden-lazy", 2, "{@@}{!probe:count!|2={!probe:bomb!|@=wrong}|>0=safe}");
            sample("zero-repeat-lazy", 0, "{@@}{!probe:count!|repeat={!probe:bomb!|@=wrong}}");
            sample("repeated-key", 2, "{@@}{!probe:count!|2=first|@=wrong} {!probe:count!|2=second|@=wrong}");
            safe("cn-direct-control", () -> { boolean previous = Settings.lineBreakViaCharacter; Settings.lineBreakViaCharacter = true; try { sample("cn-direct-control", 2, "{@@}{!probe:count!|2=two|@=other}"); } finally { Settings.lineBreakViaCharacter = previous; } });
            safe("cn-nested", () -> { boolean previous = Settings.lineBreakViaCharacter; Settings.lineBreakViaCharacter = true; try { sample("cn-nested", 2, "{@@}{!probe:count!|2={!probe:count!|2=inner|@=wrong}|@=outer}"); } finally { Settings.lineBreakViaCharacter = previous; } });
            safe("cn-suffix", () -> { boolean previous = Settings.lineBreakViaCharacter; Settings.lineBreakViaCharacter = true; try { sample("cn-suffix", 12, "{@@}{!probe:count!|&2=ending|@=other}"); } finally { Settings.lineBreakViaCharacter = previous; } });
            safe("raw-refresh", () -> refresh("raw-refresh", false));
            safe("generated-refresh", () -> refresh("generated-refresh", true));
            safe("unmark", () -> unmark());
            safe("coherent-initialization", () -> coherent());
            safe("ticking-render", () -> tickingRender());
            safe("independent-cards", () -> independent());
            safe("nested-card", () -> nestedCard());
            safe("generated-rewrite", () -> changingGenerated());
            safe("subscriber-refresh", () -> subscriberText());
            record("completed=true"); System.exit(0);
        } catch (Throwable error) { error.printStackTrace(); System.exit(2); }
    }
}
