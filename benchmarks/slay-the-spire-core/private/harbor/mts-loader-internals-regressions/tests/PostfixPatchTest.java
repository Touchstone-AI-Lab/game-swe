package gcb;

import com.evacipated.cardcrawl.modthespire.patcher.PostfixPatchInfo;
import javassist.ClassPool;
import javassist.CtBehavior;
import javassist.CtClass;
import javassist.CtMethod;
import javassist.Loader;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/** How a postfix patch is woven into the method it decorates. */
public class PostfixPatchTest {

    private static Class<?> patch(String patchClass) throws Exception {
        ClassPool pool = new ClassPool(true);
        pool.appendClassPath(new javassist.ClassClassPath(PostfixTarget.class));
        CtClass target = pool.get("gcb.PostfixTarget");
        CtBehavior toPatch = target.getDeclaredMethod("doubled");
        CtMethod patchMethod = pool.get(patchClass).getDeclaredMethod("Postfix");
        new PostfixPatchInfo(toPatch, patchMethod).doPatch();

        Loader loader = new Loader(pool);
        loader.delegateLoadingOf("com.evacipated.");
        loader.delegateLoadingOf("org.junit.");
        loader.delegateLoadingOf("javassist.");
        return loader.loadClass("gcb.PostfixTarget");
    }

    /** Positive control: the original body still runs and still computes its own result. */
    @Test
    public void control_theOriginalBodyStillRuns() throws Exception {
        Class<?> c = patch("gcb.PostfixObserve");
        Method m = c.getMethod("doubled", int.class);
        m.invoke(null, 5);
        @SuppressWarnings("unchecked")
        List<String> trace = (List<String>) c.getField("trace").get(null);
        assertTrue(trace.contains("body"), "the method being decorated must still run");
    }

    /** A: a postfix that returns a value replaces the result. */
    @Test
    public void aReturningPostfixReplacesTheResult() throws Exception {
        Class<?> c = patch("gcb.PostfixReplace");
        Method m = c.getMethod("doubled", int.class);
        assertEquals(11, (int) (Integer) m.invoke(null, 5),
                "5 doubled is 10 and the postfix adds one, so the caller must see 11");
    }

    /** B: a postfix runs after the body, not before it. */
    @Test
    public void aPostfixRunsAfterTheBody() throws Exception {
        Class<?> c = patch("gcb.PostfixObserve");
        Method m = c.getMethod("doubled", int.class);
        m.invoke(null, 5);
        @SuppressWarnings("unchecked")
        List<String> trace = (List<String>) c.getField("trace").get(null);
        assertTrue(trace.indexOf("body") < trace.indexOf("postfix:10"),
                "the postfix must observe the finished result, got " + trace);
    }

    /** C: a postfix is handed the result the body produced. */
    @Test
    public void aPostfixSeesTheResult() throws Exception {
        Class<?> c = patch("gcb.PostfixObserve");
        Method m = c.getMethod("doubled", int.class);
        m.invoke(null, 5);
        @SuppressWarnings("unchecked")
        List<String> trace = (List<String>) c.getField("trace").get(null);
        assertTrue(trace.contains("postfix:10"),
                "the postfix must receive 10, got " + trace);
    }
}
