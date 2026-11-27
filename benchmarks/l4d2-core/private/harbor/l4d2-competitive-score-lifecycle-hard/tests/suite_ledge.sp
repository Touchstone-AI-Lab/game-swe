int g_Stage;
void HalfOne(any unused=0) {GameRules_SetProp("m_bInSecondHalfOfRound",1);}
Action Begin(Handle timer)
{
    Reset();Grab(g_Client[0],0);Grab(g_Client[0],30);Player(g_Client[0]);
    Case("ledge_zero_debit_episode",SMPlus_GetDamageBonus()==SMPlus_GetMaxDamageBonus(),"zero debit still establishes an outstanding episode and duplicate grab cannot charge it");
    Reset();Grab(g_Client[0],-20);Grab(g_Client[0],25);Player(g_Client[0]);
    Case("ledge_negative_debit_episode",SMPlus_GetDamageBonus()==SMPlus_GetMaxDamageBonus(),"negative pre-incap value normalizes to zero without losing episode identity");
    Reset(); Grab(g_Client[0],30); Grab(g_Client[0],30);
    Player(g_Client[0]);
    Case("ledge_duplicate_grab",SMPlus_GetDamageBonus()==DamageAfterLoss(30),"one outstanding episode debits pre-incap buffer exactly once");
    Temp(g_Client[0],1.0); Revive(g_Client[0]); Revive(g_Client[0]);Temp(g_Client[0],21.0);
    RequestFrame(Next); return Plugin_Stop;
}
void Next(any unused=0)
{
    switch(g_Stage++)
    {
        case 0:
        {
            Case("ledge_duplicate_revive",SMPlus_GetDamageBonus()==DamageAfterLoss(10),"duplicate revive has one quantized 20-unit refund");
            Reset(); Adm(g_Client[0],40,0); Grab(g_Client[0],10);Temp(g_Client[0],71.0);Revive(g_Client[0]);
        }
        case 1:
        {
            Case("ledge_refund_capped",SMPlus_GetDamageBonus()==DamageAfterLoss(40),"large restored buffer cannot refund unrelated losses");
            Reset(); Grab(g_Client[0],30);Temp(g_Client[0],21.0);Revive(g_Client[0],false);
        }
        case 2:
        {
            Case("ledge_ground_revive",SMPlus_GetDamageBonus()==DamageAfterLoss(30),"ground revive does not settle a ledge refund");
            Reset(); Grab(g_Client[0],30);Temp(g_Client[0],21.0);Revive(g_Client[0]);Round();Adm(g_Client[0],20,0);
        }
        case 3:
        {
            Case("ledge_round_epoch",SMPlus_GetDamageBonus()==DamageAfterLoss(20),"queued refund cannot credit a restarted round");
            Reset();Round(1);Adm(g_Client[0],25,0);Round(0);
            Grab(g_Client[0],30);Temp(g_Client[0],21.0);RequestFrame(HalfOne);Revive(g_Client[0]);
        }
        case 4:
        {
            Case("ledge_half_binding",SMPlus_GetDamageBonus()==DamageAfterLoss(25),"queued first-half refund cannot modify second-half losses");
            Reset(); Grab(g_Client[0],30);Temp(g_Client[0],21.0);Revive(g_Client[0]);Grab(g_Client[0],15);Player(g_Client[0]);
        }
        case 5:
        {
            Case("ledge_new_episode",SMPlus_GetDamageBonus()==DamageAfterLoss(45),"later ledge episode invalidates old pending work even if currently upright");
            Reset(); Grab(g_Client[0],30);Temp(g_Client[0],21.0);Revive(g_Client[0]);ChangeClientTeam(g_Client[0],1);Player(g_Client[0]);
        }
        case 6:
        {
            Case("ledge_team_transition",SMPlus_GetDamageBonus()==DamageAfterLoss(30),"leaving survivor team invalidates refund even after return");
            Reset(); Grab(g_Client[0],30);Temp(g_Client[0],21.0);Revive(g_Client[0]);
            SetEntProp(g_Client[0],Prop_Send,"m_currentReviveCount",2);
            Event e=CreateEvent("player_death",true);e.SetInt("userid",GetClientUserId(g_Client[0]));e.Fire();Player(g_Client[0]);
        }
        case 7:
        {
            Case("ledge_death_transition",SMPlus_GetDamageBonus()==DamageAfterLoss(30),"death invalidates pending refund even after restoration to an alive fixture");
            Reset(); Grab(g_Client[0],30);Temp(g_Client[0],21.0);Revive(g_Client[0]);End();
        }
        case 8:
        {
            Case("ledge_finalization",SMPlus_GetDamageBonus()==DamageAfterLoss(30),"end-round invalidates queued refund");
            Reset(); Grab(g_Client[0],30);Temp(g_Client[0],21.0);Revive(g_Client[0]);
            KickClientEx(g_Client[0]); g_Client[0]=CreateFakeClient("gcb-replacement");Player(g_Client[0]);
        }
        case 9:
        {
            Case("ledge_client_disconnect",SMPlus_GetDamageBonus()==DamageAfterLoss(30),"initiated client disconnect cancels pending refund while replacement connects");
            Reset(); Grab(g_Client[0],30);Temp(g_Client[0],0.0);Revive(g_Client[0]);
        }
        case 10:
        {
            Case("ledge_zero_buffer",SMPlus_GetDamageBonus()==DamageAfterLoss(30),"zero restored buffer does not create negative refund");
            Finish();return;
        }
    }
    RequestFrame(Next);
}
