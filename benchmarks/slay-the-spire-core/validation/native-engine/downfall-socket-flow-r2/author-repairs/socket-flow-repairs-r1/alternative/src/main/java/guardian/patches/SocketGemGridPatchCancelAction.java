package guardian.patches;
import com.evacipated.cardcrawl.modthespire.lib.*;
import com.megacrit.cardcrawl.dungeons.AbstractDungeon;
import com.megacrit.cardcrawl.helpers.controller.CInputActionSet;
import com.megacrit.cardcrawl.helpers.input.InputHelper;
import com.megacrit.cardcrawl.rooms.RestRoom;
import com.megacrit.cardcrawl.ui.buttons.CancelButton;
import guardian.GuardianMod;
import guardian.vfx.SocketGemEffect;
@SpirePatch(clz=CancelButton.class,method="update")
public class SocketGemGridPatchCancelAction {
 private static final ThreadLocal<java.util.ArrayDeque<Integer>> requests=ThreadLocal.withInitial(java.util.ArrayDeque::new);
 @SpirePrefixPatch
 public static void Prefix(CancelButton obj){
  int request=0;
  if(!obj.isHidden&&AbstractDungeon.screen==AbstractDungeon.CurrentScreen.GRID&&!AbstractDungeon.gridSelectScreen.confirmScreenUp){
   obj.hb.update();
   boolean clicked=obj.hb.clicked||((InputHelper.pressedEscape||CInputActionSet.cancel.isJustPressed())&&obj.current_x!=CancelButton.HIDE_X);
   if(clicked)request=GuardianMod.gridScreenForSockets?2:GuardianMod.gridScreenForGems?1:0;
  }
  requests.get().push(request);
 }
 @SpirePostfixPatch
 public static void Postfix(CancelButton obj){
  int request=requests.get().pop();
  if(request==0)return;
  SocketGemEffect current=GuardianMod.currSocketGemEffect;
  GuardianMod.gridScreenForSockets=false;
  AbstractDungeon.gridSelectScreen.selectedCards.clear();
  if(request==2){
   if(current!=null)current.returnToGemChoice();
   GuardianMod.gridScreenForGems=true;
   AbstractDungeon.gridSelectScreen.open(GuardianMod.getGemCards(),1,SocketGemEffect.TEXT[3],false,false,true,false);
  }else{
   GuardianMod.gridScreenForGems=false;
   if(current!=null)current.abandonSelection();
   if(AbstractDungeon.getCurrRoom() instanceof RestRoom)((RestRoom)AbstractDungeon.getCurrRoom()).campfireUI.reopen();
  }
 }
}
