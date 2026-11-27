package suiteobserver;

import com.badlogic.gdx.ApplicationListener;
import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.backends.lwjgl.LwjglApplicationConfiguration;
import com.evacipated.cardcrawl.modthespire.lib.SpireInitializer;
import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePostfixPatch;
import com.megacrit.cardcrawl.core.CardCrawlGame;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.List;
import org.junit.platform.engine.DiscoverySelector;
import org.junit.platform.engine.TestExecutionResult;
import org.junit.platform.engine.discovery.DiscoverySelectors;
import org.junit.platform.engine.support.descriptor.MethodSource;
import org.junit.platform.launcher.Launcher;
import org.junit.platform.launcher.TestExecutionListener;
import org.junit.platform.launcher.TestIdentifier;
import org.junit.platform.launcher.core.LauncherDiscoveryRequestBuilder;
import org.junit.platform.launcher.core.LauncherFactory;

/**
 * Runs the unchanged private JUnit suite inside the game that the submitted ModTheSpire
 * launched.
 *
 * <p>The suite and JUnit sit on the game's system class path, as Surefire placed them on the
 * test JVM's. Once the main menu is live, the JUnit Platform launcher executes the selected
 * test classes on the game's render thread with the system class loader as context loader,
 * Surefire's default. Every outcome is recorded under the run nonce, then the game exits.
 */
@SpireInitializer
public class Observer {
    private static final int SETTLE_FRAMES = 3;
    private static boolean observed;
    private static int menuFrames;
    private static final StringBuilder RECORDS = new StringBuilder();

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

    /** Collects each test's terminal status; containers are recorded only when they fail. */
    public static class Recorder implements TestExecutionListener {
        int tests;

        @Override
        public void executionSkipped(TestIdentifier identifier, String reason) {
            if (identifier.isTest()) {
                tests++;
                record("SUITE_CASE", "id=" + name(identifier) + ",status=SKIPPED");
            } else {
                record("SUITE_CONTAINER", "id=" + identifier.getUniqueId() + ",status=SKIPPED");
            }
        }

        @Override
        public void executionFinished(TestIdentifier identifier, TestExecutionResult result) {
            if (result.getThrowable().isPresent()) {
                System.out.println("SUITE_FIXTURE outcome " + identifier.getDisplayName() + " " + result.getStatus());
                result.getThrowable().get().printStackTrace(System.out);
            }
            if (identifier.isTest()) {
                tests++;
                record("SUITE_CASE", "id=" + name(identifier) + ",status=" + result.getStatus());
            } else if (result.getStatus() != TestExecutionResult.Status.SUCCESSFUL) {
                record("SUITE_CONTAINER", "id=" + identifier.getUniqueId() + ",status=" + result.getStatus());
            }
        }

        private static String name(TestIdentifier identifier) {
            if (identifier.getSource().isPresent() && identifier.getSource().get() instanceof MethodSource) {
                MethodSource source = (MethodSource) identifier.getSource().get();
                return source.getClassName() + "." + source.getMethodName();
            }
            return identifier.getUniqueId();
        }
    }

    static void record(String tag, String payload) {
        RECORDS.append(tag).append(' ').append(System.getProperty("sts.verify.nonce")).append('|')
            .append(payload).append('\n');
    }

    static void afterRender(CardCrawlGame game) {
        if (observed || Gdx.gl == null || Gdx.app == null || CardCrawlGame.mainMenuScreen == null) {
            return;
        }
        if (++menuFrames < SETTLE_FRAMES) {
            return;
        }
        observed = true;
        ApplicationListener listener = Gdx.app.getApplicationListener();
        record("SUITE_ENGINE", "gl=" + (Gdx.gl != null)
            + ",listener=" + (listener == null ? "none" : listener.getClass().getName())
            + ",self=" + (listener == game) + ",menu=" + (CardCrawlGame.mainMenuScreen != null)
            + ",frames=" + menuFrames);
        Thread thread = Thread.currentThread();
        ClassLoader previous = thread.getContextClassLoader();
        Recorder recorder = new Recorder();
        try {
            thread.setContextClassLoader(ClassLoader.getSystemClassLoader());
            List<DiscoverySelector> selectors = new ArrayList<>();
            for (String name : System.getProperty("sts.verify.classes").split(",")) {
                selectors.add(DiscoverySelectors.selectClass(name));
            }
            Launcher launcher = LauncherFactory.create();
            launcher.execute(LauncherDiscoveryRequestBuilder.request().selectors(selectors).build(), recorder);
            record("SUITE_DONE", "tests=" + recorder.tests);
        } catch (Throwable failure) {
            failure.printStackTrace();
            record("SUITE_ERROR", "error=" + failure.getClass().getName());
        } finally {
            thread.setContextClassLoader(previous);
        }
        try {
            Files.write(Paths.get(System.getProperty("sts.verify.output")),
                RECORDS.toString().getBytes(StandardCharsets.UTF_8), StandardOpenOption.CREATE_NEW,
                StandardOpenOption.WRITE);
        } catch (Throwable failure) {
            failure.printStackTrace();
            System.exit(3);
        }
        System.out.println("SUITE_FIXTURE observed tests=" + recorder.tests);
        System.exit(0);
    }
}
