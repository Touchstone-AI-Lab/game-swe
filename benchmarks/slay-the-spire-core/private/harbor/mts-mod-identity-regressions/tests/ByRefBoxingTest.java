package gcb;

import com.evacipated.cardcrawl.modthespire.patcher.PrefixPatchInfo;
import javassist.ClassPool;
import javassist.CtBehavior;
import javassist.CtClass;
import javassist.CtMethod;
import javassist.Loader;
import org.junit.jupiter.api.Test;

import java.lang.reflect.Method;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * A prefix patch that takes its argument by reference must be able to write back through
 * a WRAPPER-typed array even though the patched method declares a primitive.
 *
 * The target class is never named directly, so it is not loaded before it is patched.
 */
public class ByRefBoxingTest {
    @Test
    public void byRefWritesBackThroughAWrapperArray() throws Exception {
        ClassPool pool = ClassPool.getDefault();
        CtClass ctTarget = pool.get("gcb.Target");
        CtBehavior toPatch = ctTarget.getDeclaredMethod("take");
        CtMethod patchMethod = pool.get("gcb.TargetPatch").getDeclaredMethod("Prefix");

        new PrefixPatchInfo(toPatch, patchMethod).doPatch();

        Loader loader = new Loader(pool);
        loader.delegateLoadingOf("com.evacipated.");
        loader.delegateLoadingOf("org.junit.");
        Class<?> patched = loader.loadClass("gcb.Target");

        Method take = patched.getMethod("take", int.class);
        take.invoke(null, 1);

        int lastSeen = patched.getField("lastSeen").getInt(null);
        assertEquals(99, lastSeen, "the by-reference write should have reached the method body");
    }
}
