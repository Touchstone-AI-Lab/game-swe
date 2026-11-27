package guardian.patches;

import com.evacipated.cardcrawl.modthespire.lib.SpirePatch;
import com.evacipated.cardcrawl.modthespire.lib.SpirePrefixPatch;
import com.megacrit.cardcrawl.cards.CardGroup;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.helpers.controller.CInputActionSet;
import com.megacrit.cardcrawl.helpers.input.InputHelper;
import com.megacrit.cardcrawl.rooms.RestRoom;
import com.megacrit.cardcrawl.ui.buttons.CancelButton;
import guardian.GuardianMod;
import guardian.vfx.SocketGemEffect;

@SpirePatch(clz = CancelButton.class, method = "update")
public class SocketGemGridPatchCancelAction {

    @SpirePrefixPatch
    public static com.evacipated.cardcrawl.modthespire.lib.SpireReturn<Void> Prefix(CancelButton obj) {
        if (!obj.isHidden) {
            obj.hb.update();
            if (obj.hb.clicked || (InputHelper.pressedEscape || CInputActionSet.cancel.isJustPressed()) && obj.current_x != CancelButton.HIDE_X) {

                if (AbstractDungeon.screen == AbstractDungeon.CurrentScreen.GRID && GuardianMod.gridScreenForSockets) {
                    if (!AbstractDungeon.gridSelectScreen.confirmScreenUp) {
                        GuardianMod.logger.info("cancel from grid for sockets");
                        CardGroup gemCards = GuardianMod.getGemCards();
                        if (GuardianMod.currSocketGemEffect != null) {
                            GuardianMod.currSocketGemEffect.gemSelect = true;
                            GuardianMod.currSocketGemEffect.socketSelect = false;
                            GuardianMod.currSocketGemEffect.gemChosen = null;
                        }
                        GuardianMod.gridScreenForSockets = false;
                        GuardianMod.gridScreenForGems = true;
                        GuardianMod.gridScreenForGems = true;
                        AbstractDungeon.gridSelectScreen.selectedCards.clear();

                        AbstractDungeon.gridSelectScreen.open(gemCards, 1, SocketGemEffect.TEXT[3], false, false, true, false);
                        // This one cancellation has been handled; do not cancel the newly opened grid.
                        obj.hb.clicked = false;
                        obj.hb.clickStarted = false;
                        InputHelper.pressedEscape = false;
                        CInputActionSet.cancel.unpress();
                        return com.evacipated.cardcrawl.modthespire.lib.SpireReturn.Return(null);

                    }

                }

                if (AbstractDungeon.screen == AbstractDungeon.CurrentScreen.GRID && GuardianMod.gridScreenForGems) {
                    if (!AbstractDungeon.gridSelectScreen.confirmScreenUp) {
                        GuardianMod.logger.info("cancel from grid for gems");
                        if (GuardianMod.currSocketGemEffect != null) {
                            SocketGemEffect abandoned = GuardianMod.currSocketGemEffect;
                            abandoned.gemSelect = false;
                            abandoned.socketSelect = false;
                            abandoned.confirmSelect = false;
                            abandoned.gemChosen = null;
                            abandoned.isDone = true;
                        }
                        GuardianMod.gridScreenForGems = false;
                        GuardianMod.gridScreenForSockets = false;
                        AbstractDungeon.closeCurrentScreen();
                        if (AbstractDungeon.getCurrRoom() instanceof RestRoom) {
                            RestRoom r = (RestRoom) AbstractDungeon.getCurrRoom();
                            r.campfireUI.reopen();
                        }


                    }

                }
            }


        }
        return com.evacipated.cardcrawl.modthespire.lib.SpireReturn.Continue();
    }
}
