package guardian.actions;
import basemod.BaseMod;
import com.megacrit.cardcrawl.actions.AbstractGameAction;
import com.megacrit.cardcrawl.core.Settings;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import guardian.orbs.StasisOrb;
public class StasisEvokeIfRoomInHandAction extends AbstractGameAction {
    private final StasisOrb orb;
    public StasisEvokeIfRoomInHandAction(StasisOrb orb) {
        this.orb=orb;this.duration=Settings.ACTION_DUR_FAST;this.actionType=ActionType.DAMAGE;
    }
    public void update() {
        if (isDone) return;
        isDone=true;
        if (AbstractDungeon.player.hand.size() >= BaseMod.MAX_HAND_SIZE) return;
        int index=-1;
        for (int i=0;i<AbstractDungeon.player.orbs.size();i++)
            if (AbstractDungeon.player.orbs.get(i)==orb) {index=i;break;}
        if (index<0) return;
        AbstractDungeon.player.orbs.remove(index);
        AbstractDungeon.player.orbs.add(0,orb);
        AbstractDungeon.player.evokeOrb();
    }
}
