Action Begin(Handle timer)
{
    Reset(); Adm(g_Client[0],50,30);
    Case("adm_positive_loss",SMPlus_GetDamageBonus()==DamageAfterLoss(20),"valid forward debits the positive difference");
    Adm(g_Client[0],10,30); Adm(g_Client[0],20,20);
    Case("adm_healing_ignored",SMPlus_GetDamageBonus()==DamageAfterLoss(20),"healing/equal values cannot credit damage ledger");
    Adm(g_Client[0],10,-20);
    Case("adm_negative_after_clamped",SMPlus_GetDamageBonus()==DamageAfterLoss(30),"negative new health clamps to zero before subtracting");
    Adm(g_Client[0],-10,-40);
    Case("adm_negative_both_ignored",SMPlus_GetDamageBonus()==DamageAfterLoss(30),"two negative inputs do not create loss");
    Adm(0,90,10); Adm(MaxClients+1,90,10);
    Case("adm_invalid_client",SMPlus_GetDamageBonus()==DamageAfterLoss(30),"invalid client indices are rejected safely");
    for(int state=1;state<=4;state++) {Player(g_Client[0],100,state);Adm(g_Client[0],30,0);}
    Player(g_Client[0]);
    ChangeClientTeam(g_Client[0],1); Adm(g_Client[0],30,0); Player(g_Client[0]);
    Case("adm_ineligible_client",SMPlus_GetDamageBonus()==DamageAfterLoss(30),"dead/incap/ledge/falling/non-survivor forwards do not enter ledger");
    Round();
    Case("round_restart_clears_current",SMPlus_GetDamageBonus()==SMPlus_GetMaxDamageBonus(),"same-half round_start resets current-half accumulated loss");
    Adm(g_Client[0],30,10);
    Round(1); Adm(g_Client[0],40,10);
    GameRules_SetProp("m_bInSecondHalfOfRound",0);
    Case("round_preserves_other_half",SMPlus_GetDamageBonus()==DamageAfterLoss(20),"starting second half retains first-half ledger");
    GameRules_SetProp("m_bInSecondHalfOfRound",1);
    Case("round_independent_half",SMPlus_GetDamageBonus()==DamageAfterLoss(30),"second-half losses remain independent");
    End(); int before=SMPlus_GetDamageBonus(); int survival=FindConVar("vs_survival_bonus").IntValue;
    Adm(g_Client[0],80,0);
    Event e=CreateEvent("player_incapacitated",true);e.SetInt("userid",GetClientUserId(g_Client[0]));e.Fire();
    e=CreateEvent("player_death",true);e.SetInt("userid",GetClientUserId(g_Client[0]));e.Fire();
    Case("round_finalized_ledger_frozen",SMPlus_GetDamageBonus()==before,"late damage and incap/death events cannot mutate finalized loss");
    End();
    Case("round_end_idempotent",FindConVar("vs_survival_bonus").IntValue==survival,"duplicate end-round forward preserves published result");
    for(int i=0;i<4;i++) SetEntProp(g_Client[i],Prop_Send,"m_currentReviveCount",1);
    Round(0);Adm(g_Client[0],500,0);End();
    Round(1);Adm(g_Client[0],600,0);End();
    Case("round_tiebreak_ledgers",GameRules_GetProp("m_iChapterDamage",4,0)==500 && GameRules_GetProp("m_iChapterDamage",4,1)==600,"round reset clears current tiebreak ledger while completed first half survives second-half start");
    Case("adm_tiebreak_compatibility",FindConVar("vs_tiebreak_bonus").IntValue==SMPlus_GetMaxPillsBonus()/4,"valid alternate-damage losses still drive established depleted-bonus tiebreak");
    Reset();L4D_RespawnPlayer(g_Client[0]);Player(g_Client[0],1);Temp(g_Client[0],51.0);
    SetEntProp(g_Client[0],Prop_Data,"m_takedamage",2);
    End();before=SMPlus_GetDamageBonus();
    SDKHooks_TakeDamage(g_Client[0],0,0,10.0,DMG_GENERIC,-1,NULL_VECTOR,NULL_VECTOR,false);
    float actualBuffer=GetEntPropFloat(g_Client[0],Prop_Send,"m_healthBuffer");
    PrintToServer("SDK damage probe: buffer=%f health=%d alive=%d score=%d before=%d",actualBuffer,GetClientHealth(g_Client[0]),IsPlayerAlive(g_Client[0]),SMPlus_GetDamageBonus(),before);
    Case("round_finalized_sdk_damage",actualBuffer<51.0 && SMPlus_GetDamageBonus()==before,"real damage removes temporary health through SDKHooks while finalized score ledger remains frozen");
    e=CreateEvent("player_hurt",true);e.SetInt("userid",GetClientUserId(g_Client[0]));e.SetInt("attacker",GetClientUserId(g_Client[1]));e.SetInt("dmg_health",5);e.SetInt("type",DMG_PLASMA);e.Fire();
    Case("round_finalized_plasma_event",SMPlus_GetDamageBonus()==before,"late manipulated-shotgun hurt event cannot debit finalized ledger");
    Finish();return Plugin_Stop;
}
