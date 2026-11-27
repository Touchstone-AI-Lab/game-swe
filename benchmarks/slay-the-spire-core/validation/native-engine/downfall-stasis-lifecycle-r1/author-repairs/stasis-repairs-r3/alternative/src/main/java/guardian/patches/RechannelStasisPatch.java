package guardian.patches;
import com.evacipated.cardcrawl.modthespire.lib.ByRef;
import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePrefixPatch;
import com.megacrit.cardcrawl.characters.AbstractPlayer;
import com.megacrit.cardcrawl.orbs.AbstractOrb;
import guardian.orbs.StasisOrb;
@SpirePatch(clz=AbstractPlayer.class, method="channelOrb")
public class RechannelStasisPatch {
    @SpirePrefixPatch
    public static void before(AbstractPlayer __instance, @ByRef AbstractOrb[] orbToSet) {
        if (orbToSet[0] instanceof StasisOrb && ((StasisOrb) orbToSet[0]).hasDeparted())
            orbToSet[0] = orbToSet[0].makeCopy();
    }
}
