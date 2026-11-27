package gcb;

import com.evacipated.cardcrawl.modthespire.lib.SpireReturn;

/** Takes over the method entirely when the input is special, otherwise stands aside. */
public class TakeOverPatch {
    public static SpireReturn<Integer> Prefix(int x) {
        if (x == 7) {
            return SpireReturn.Return(999);
        }
        return SpireReturn.Continue();
    }
}
