package guardian.actions;
import com.megacrit.cardcrawl.actions.AbstractGameAction;
import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.helpers.CardLibrary;
import guardian.GuardianMod;
import java.util.ArrayList;
public class PlaceRandom1CostIntoStasis extends AbstractGameAction {
    public static final String[] TEXT=CardCrawlGame.languagePack.getUIString("Guardian:UIOptions").TEXT;
    private final int remaining;
    public PlaceRandom1CostIntoStasis(int numCards){remaining=numCards;actionType=ActionType.DAMAGE;}
    public void update(){
        if(isDone)return;
        isDone=true;
        if(remaining<=0||!GuardianMod.canSpawnStasisOrb())return;
        ArrayList<AbstractCard> choices=new ArrayList<>();
        for(AbstractCard card:CardLibrary.cards.values())if(card.cost==1&&card.color==AbstractDungeon.player.getCardColor())choices.add(card);
        if(choices.isEmpty())return;
        AbstractCard chosen=choices.get(AbstractDungeon.cardRng.random(0,choices.size()-1)).makeStatEquivalentCopy();
        if(remaining>1)addToTop(new PlaceRandom1CostIntoStasis(remaining-1));
        addToTop(new PlaceActualCardIntoStasis(chosen));
    }
}
