Action Begin(Handle timer)
{
    Reset();
    int h=SMPlus_GetMaxHealthBonus(), d=SMPlus_GetMaxDamageBonus();
    Case("score_normal_budget",h>0 && d>0 && SMPlus_GetHealthBonus()==h && SMPlus_GetDamageBonus()==d,"full upright roster earns ordinary health and damage budgets");
    Player(g_Client[0],100,1);
    Case("score_dead_excluded",SMPlus_GetDamageBonus()==RoundToFloor(float(d)*0.75),"dead survivor does not count as upright");
    Player(g_Client[0],100,2);
    Case("score_incap_excluded",SMPlus_GetDamageBonus()==RoundToFloor(float(d)*0.75),"incap survivor excluded from damage multiplier");
    Player(g_Client[0],100,4);
    Case("score_falling_excluded",SMPlus_GetHealthBonus()==RoundToFloor(float(h)*0.5625),"falling survivor contributes neither health nor multiplier");
    Player(g_Client[0]);
    SetEntProp(g_Client[0],Prop_Send,"m_currentReviveCount",1);
    Case("score_revived_health_policy",SMPlus_GetHealthBonus()==RoundToFloor(float(h)*0.75),"existing zero permanent-health contribution after incap preserved");
    Player(g_Client[0]);
    for(int i=0;i<4;i++)
    {
        int item=GetPlayerWeaponSlot(g_Client[i],4);
        if(item>MaxClients) {RemovePlayerItem(g_Client[i],item);RemoveEntity(item);}
    }
    int pills=GivePlayerItem(g_Client[0],"weapon_pain_pills");
    Case("score_upright_pills",pills>MaxClients && SMPlus_GetPillsBonus()==SMPlus_GetMaxPillsBonus()/4,"actual carried pills earn normal per-player bonus");
    Player(g_Client[0],100,3);
    Case("score_ledge_pills_excluded",SMPlus_GetPillsBonus()==0,"ledge hanging player cannot contribute pills");
    Player(g_Client[0],100,4);
    Case("score_falling_pills_excluded",SMPlus_GetPillsBonus()==0,"falling player cannot contribute pills");
    Reset();
    Adm(g_Client[0],40,20);
    Cv("sm2_bonus_per_survivor_multiplier",0.8);
    Case("live_multiplier_preserves_loss",SMPlus_GetDamageBonus()==DamageAfterLoss(20),"multiplier update reprices existing loss without clearing ledger");
    Cv("sm2_permament_health_proportion",0.5);
    int maxD=SMPlus_GetMaxDamageBonus();
    Case("live_proportion_reprices",SMPlus_GetDamageBonus()==RoundToFloor(float(maxD)*0.95),"p=.5 uses 400 temporary-health units and retains 20 lost units");
    Cv("sm2_pills_hp_factor",1000.0);
    Case("live_pill_factor",SMPlus_GetMaxPillsBonus()==20,"live factor update recalculates nearest-five minimum");
    Cv("sm2_pills_max_bonus",3.0);
    Case("live_pill_cap",SMPlus_GetMaxPillsBonus()==12,"live cap below five is itself the cap");
    Cv("survivor_limit",2.0);
    Case("live_team_size",SMPlus_GetMaxPillsBonus()==6 && SMPlus_GetMaxHealthBonus()==h*8/15,"live team-size update recalculates all coefficients");
    Player(g_Client[0],100,1);
    Case("score_roster_limit",SMPlus_GetHealthBonus()==SMPlus_GetMaxHealthBonus()/4,"dead player still occupies first-two roster slot; extra survivors do not replace it");
    Finish(); return Plugin_Stop;
}
