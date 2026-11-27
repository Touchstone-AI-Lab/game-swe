package gcb;

import com.evacipated.cardcrawl.modthespire.lib.SpireReturn;

/** Same, for a method whose result is a single character. */
public class GradePatch {
    public static SpireReturn<Character> Prefix(int x) {
        if (x == 1) {
            return SpireReturn.Return('A');
        }
        return SpireReturn.Continue();
    }
}
