package gcb;

import com.evacipated.cardcrawl.modthespire.lib.SpireReturn;

/** Takes over a method that produces no value, so the original work is skipped. */
public class SilencePatch {
    public static SpireReturn<Void> Prefix(int x) {
        if (x == 5) {
            return SpireReturn.Return();
        }
        return SpireReturn.Continue();
    }
}
