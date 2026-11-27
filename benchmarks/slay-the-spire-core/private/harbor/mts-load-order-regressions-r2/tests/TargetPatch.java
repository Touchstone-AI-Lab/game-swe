package gcb;

import com.evacipated.cardcrawl.modthespire.lib.ByRef;

/**
 * A prefix patch that rewrites the argument by reference. The parameter is declared with
 * the WRAPPER type while the patched method takes a primitive -- which is what Kotlin
 * mods always produce, and what this task is about.
 */
public class TargetPatch {
    public static void Prefix(@ByRef Integer[] x) {
        x[0] = 99;
    }
}
