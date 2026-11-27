package gcb;

import com.evacipated.cardcrawl.modthespire.patcher.PrefixPatchInfo;
import javassist.*;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/** A patch that can decide to answer on the method's behalf. */
public class EarlyReturnTest {

    private static Class<?> patch(String method, String patchClass) throws Exception {
        ClassPool pool = new ClassPool(true);
        pool.appendClassPath(new ClassClassPath(EarlyReturnTarget.class));
        CtClass target = pool.get("gcb.EarlyReturnTarget");
        CtBehavior toPatch = target.getDeclaredMethod(method);
        CtMethod patchMethod = pool.get(patchClass).getDeclaredMethod("Prefix");
        new PrefixPatchInfo(toPatch, patchMethod).doPatch();

        javassist.Loader loader = new javassist.Loader(pool);
        loader.delegateLoadingOf("com.evacipated.");
        loader.delegateLoadingOf("org.junit.");
        loader.delegateLoadingOf("javassist.");
        return loader.loadClass("gcb.EarlyReturnTarget");
    }

    /** Positive control: an observing patch that never answers on the method's behalf.
     *  It does not involve the early-answer machinery at all, so it holds either way. */
    @Test
    public void control_anObservingPatchLeavesTheAnswerAlone() throws Exception {
        Class<?> c = patch("amount", "gcb.PlainPrefix");
        Method m = c.getMethod("amount", int.class);
        assertEquals(30, (int) (Integer) m.invoke(null, 3),
                "an observing patch must not change the answer");
        @SuppressWarnings("unchecked")
        List<String> trace = (List<String>) c.getField("trace").get(null);
        assertTrue(trace.contains("prefix:3"), "the observing patch must still run, got " + trace);
    }

    /** A: when the patch answers, its answer is used and the body does not run. */
    @Test
    public void takingOverReplacesTheAnswer() throws Exception {
        Class<?> c = patch("amount", "gcb.TakeOverPatch");
        Method m = c.getMethod("amount", int.class);
        assertEquals(999, (int) (Integer) m.invoke(null, 7),
                "the patch answered, so its value must be the one returned");
    }

    /** A: and the original work is genuinely skipped. */
    @Test
    public void takingOverSkipsTheOriginalWork() throws Exception {
        Class<?> c = patch("amount", "gcb.TakeOverPatch");
        Method m = c.getMethod("amount", int.class);
        @SuppressWarnings("unchecked")
        List<String> trace = (List<String>) c.getField("trace").get(null);
        trace.clear();
        m.invoke(null, 7);
        assertFalse(trace.contains("body"), "the method's own work must not run, got " + trace);
    }

    /** B: a method whose result is a single character can be taken over too. */
    @Test
    public void aSingleCharacterResultCanBeTakenOver() throws Exception {
        Class<?> c = assertDoesNotThrow(() -> patch("grade", "gcb.GradePatch"),
                "patching a method that answers with one character must be possible");
        Method m = c.getMethod("grade", int.class);
        assertEquals('A', (char) (Character) m.invoke(null, 1),
                "the patch answered, so its character must come through");
    }

    /** A patch may take over a method that produces no value at all. */
    @Test
    public void takingOverAValuelessMethodSkipsItsWork() throws Exception {
        Class<?> c = patch("record", "gcb.SilencePatch");
        Method m = c.getMethod("record", int.class);
        @SuppressWarnings("unchecked")
        List<String> trace = (List<String>) c.getField("trace").get(null);
        trace.clear();
        m.invoke(null, 5);
        assertFalse(trace.contains("recorded:5"),
                "the patch answered, so the method's own work must not run, got " + trace);
        trace.clear();
        m.invoke(null, 6);
        assertTrue(trace.contains("recorded:6"),
                "with the patch standing aside the method must still do its work, got " + trace);
    }
}
