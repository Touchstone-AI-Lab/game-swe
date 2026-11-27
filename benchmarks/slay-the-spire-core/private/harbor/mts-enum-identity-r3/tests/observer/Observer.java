package enumobserver;

import com.badlogic.gdx.ApplicationListener;
import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.backends.lwjgl.LwjglApplicationConfiguration;
import com.evacipated.cardcrawl.modthespire.Loader;
import com.evacipated.cardcrawl.modthespire.lib.SpireInitializer;
import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePostfixPatch;
import com.megacrit.cardcrawl.core.CardCrawlGame;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;

/**
 * Runs one unchanged enum fixture inside the game that the submitted ModTheSpire launched.
 *
 * <p>The fixture's {@code run()} executes on the game's render thread once the main menu is
 * live, through the same class loader and observation triple as the r2 loader runner. This
 * class deliberately has no switch statements, anonymous classes or enum declarations, so it
 * adds no switch-map holder or extension declaration of its own.
 */
@SpireInitializer
public class Observer {
    private static final int SETTLE_FRAMES = 3;
    private static boolean observed;
    private static int menuFrames;

    public static void initialize() {
        LwjglApplicationConfiguration.disableAudio = true;
    }

    @SpirePatch(clz = CardCrawlGame.class, method = "render")
    public static class AfterRender {
        @SpirePostfixPatch
        public static void Postfix(CardCrawlGame __instance) {
            Observer.afterRender(__instance);
        }
    }

    static void afterRender(CardCrawlGame game) {
        if (observed || Gdx.gl == null || Gdx.app == null || CardCrawlGame.mainMenuScreen == null) {
            return;
        }
        if (++menuFrames < SETTLE_FRAMES) {
            return;
        }
        observed = true;
        String nonce = System.getProperty("sts.verify.nonce");
        String id = System.getProperty("sts.verify.case");
        ApplicationListener listener = Gdx.app.getApplicationListener();
        String engine = "ENUM_ENGINE " + nonce + "|id=" + id + ",gl=" + (Gdx.gl != null)
            + ",listener=" + (listener == null ? "none" : listener.getClass().getName())
            + ",self=" + (listener == game) + ",menu=" + (CardCrawlGame.mainMenuScreen != null)
            + ",frames=" + menuFrames;
        boolean loaded = Loader.getClassPool() != null && Loader.isModLoaded("enumscout");
        String value = "missing";
        String error = "none";
        if (loaded) {
            try {
                ClassLoader runtime = Loader.getClassPool().getClassLoader();
                value = String.valueOf(runtime.loadClass("enumfixture.Fixture").getMethod("run").invoke(null));
            } catch (Throwable failure) {
                error = failure.getClass().getName();
                failure.printStackTrace();
            }
        }
        String record = "ENUM_OBSERVATION " + nonce + "|id=" + id + ",loaded=" + loaded + ",value=" + value
            + ",error=" + error;
        try {
            Files.write(Paths.get(System.getProperty("sts.verify.output")),
                (engine + "\n" + record + "\n").getBytes(StandardCharsets.UTF_8), StandardOpenOption.CREATE_NEW,
                StandardOpenOption.WRITE);
        } catch (Throwable failure) {
            failure.printStackTrace();
            System.exit(3);
        }
        System.out.println("ENUM_FIXTURE observed id=" + id);
        System.exit(0);
    }
}
