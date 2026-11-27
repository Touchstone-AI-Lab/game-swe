package guardian.actions;

import com.megacrit.cardcrawl.actions.AbstractGameAction;
import com.megacrit.cardcrawl.actions.defect.ChannelAction;
import com.megacrit.cardcrawl.actions.utility.WaitAction;
import com.megacrit.cardcrawl.cards.AbstractCard;
import com.megacrit.cardcrawl.core.CardCrawlGame;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.helpers.CardLibrary;
import com.megacrit.cardcrawl.vfx.ThoughtBubble;
import guardian.GuardianMod;
import guardian.characters.GuardianCharacter;
import guardian.orbs.StasisOrb;

import java.util.ArrayList;
import java.util.Map;


public class PlaceRandom1CostIntoStasis extends AbstractGameAction {
    private int numCards;
    public static final String[] TEXT = CardCrawlGame.languagePack.getUIString("Guardian:UIOptions").TEXT;


    public PlaceRandom1CostIntoStasis(int numCards) {
        this.actionType = ActionType.DAMAGE;
        this.numCards = numCards;
    }

    public void update() {
        if (this.numCards == 0) {
            this.isDone = true;
        }

        ArrayList<String> tmp = new ArrayList<>();

        for (Map.Entry<String, AbstractCard> stringAbstractCardEntry : CardLibrary.cards.entrySet()) {
            Map.Entry<String, AbstractCard> c = (Map.Entry) stringAbstractCardEntry;
            if (c.getValue().cost == 1 && c.getValue().color == AbstractDungeon.player.getCardColor()) {
                tmp.add(c.getKey());
            }
        }

        if (!tmp.isEmpty()) {
            for (int i = 0; i < this.numCards; i++) {
                AbstractCard prototype = CardLibrary.cards.get(tmp.get(AbstractDungeon.cardRng.random(0, tmp.size() - 1)));
                // Admission is evaluated when each transfer reaches the queue head.
                addToTop(new PlaceActualCardIntoStasis(prototype.makeStatEquivalentCopy()));
            }
        }

        this.isDone = true;
    }
}
