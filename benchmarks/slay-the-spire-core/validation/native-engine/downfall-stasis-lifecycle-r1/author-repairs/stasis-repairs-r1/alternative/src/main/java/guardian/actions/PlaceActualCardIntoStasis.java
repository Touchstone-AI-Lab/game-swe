package guardian.actions;
import com.megacrit.cardcrawl.actions.AbstractGameAction;
import com.megacrit.cardcrawl.actions.defect.ChannelAction;
import com.megacrit.cardcrawl.actions.utility.WaitAction;
import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.cards.CardGroup;
import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.core.Settings;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.orbs.AbstractOrb;
import guardian.GuardianMod;
import guardian.orbs.StasisOrb;
public class PlaceActualCardIntoStasis extends AbstractGameAction {
    public static final String[] TEXT=CardCrawlGame.languagePack.getUIString("Guardian:UIOptions").TEXT;
    private final AbstractCard card;
    private final CardGroup source;
    private final boolean restoreRetain;
    private final boolean skipWait;
    public PlaceActualCardIntoStasis(AbstractCard card) {this(card,null,false);}
    public PlaceActualCardIntoStasis(AbstractCard card,CardGroup source) {this(card,source,false);}
    public PlaceActualCardIntoStasis(AbstractCard card,CardGroup source,boolean skipWait) {
        this.card=card;this.source=source;this.skipWait=skipWait;restoreRetain=card.retain;
        actionType=ActionType.DAMAGE;
        if(source!=null&&source.type==CardGroup.CardGroupType.HAND)card.retain=true;
    }
    private boolean owns(CardGroup pile) {return pile.group.stream().anyMatch(value->value==card);}
    public void update() {
        if(isDone)return;
        isDone=true;
        if(AbstractDungeon.player.orbs.stream().anyMatch(value->value instanceof StasisOrb&&((StasisOrb)value).stasisCard==card))return;
        boolean valid;
        if(source!=null)valid=owns(source);
        else {
            CardGroup[] groups={AbstractDungeon.player.hand,AbstractDungeon.player.drawPile,AbstractDungeon.player.discardPile,AbstractDungeon.player.exhaustPile,AbstractDungeon.player.limbo};
            valid=true;for(CardGroup group:groups)if(owns(group)){valid=false;break;}
        }
        if(!valid||!GuardianMod.canSpawnStasisOrb()){card.retain=restoreRetain;return;}
        if(!AbstractDungeon.player.hasEmptyOrb()) {
            int victim=-1;
            for(int i=0;i<AbstractDungeon.player.orbs.size();i++)if(!(AbstractDungeon.player.orbs.get(i) instanceof StasisOrb)){victim=i;break;}
            if(victim>=0){AbstractOrb old=AbstractDungeon.player.orbs.remove(victim);AbstractDungeon.player.orbs.add(0,old);AbstractDungeon.player.evokeOrb();}
        }
        if(!skipWait&&!Settings.FAST_MODE)addToTop(new WaitAction(0.1F));
        addToTop(new ChannelAction(new StasisOrb(card,source)));
    }
}
