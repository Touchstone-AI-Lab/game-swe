Action Begin(Handle timer)
{
    Reset();
    int total=SMPlus_GetMaxHealthBonus()+SMPlus_GetMaxDamageBonus();
    Cv("sm2_permament_health_proportion",0.0);
    Adm(g_Client[0],50,30);
    Case("bounds_zero_proportion",SMPlus_GetMaxHealthBonus()==0 && SMPlus_GetMaxDamageBonus()==total && SMPlus_GetDamageBonus()==RoundToFloor(float(total)*0.95),"all-damage endpoint has 100 temporary-health units per player");
    Cv("sm2_permament_health_proportion",1.0);
    Case("bounds_one_proportion",SMPlus_GetMaxHealthBonus()==total && SMPlus_GetDamageBonus()==0,"all-health endpoint has finite zero damage budget");
    Event event=CreateEvent("player_incapacitated",true);event.SetInt("userid",GetClientUserId(g_Client[0]));event.Fire();
    event=CreateEvent("player_death",true);event.SetInt("userid",GetClientUserId(g_Client[0]));event.Fire();
    Case("bounds_endpoint_events",SMPlus_GetDamageBonus()==0 && SMPlus_GetHealthBonus()==total,"incap and death callbacks do not divide by zero at all-health endpoint");
    Cv("sm2_permament_health_proportion",1.8);
    Case("bounds_high_proportion",SMPlus_GetMaxHealthBonus()==total && SMPlus_GetMaxDamageBonus()==0,"proportions above one clamp to one");
    Cv("sm2_permament_health_proportion",-0.5);
    Case("bounds_negative_proportion",SMPlus_GetMaxHealthBonus()==0 && SMPlus_GetMaxDamageBonus()==total,"negative proportions clamp to zero");
    Reset(); Cv("sm2_pills_hp_factor",0.0);
    Case("bounds_zero_factor",SMPlus_GetMaxPillsBonus()==0,"zero pills factor disables pills");
    Cv("sm2_pills_hp_factor",-2.0);
    Case("bounds_negative_factor",SMPlus_GetMaxPillsBonus()==0,"negative pills factor disables pills");
    Cv("sm2_pills_hp_factor",6.0); Cv("sm2_pills_max_bonus",0.0);
    Case("bounds_zero_cap",SMPlus_GetMaxPillsBonus()==0,"zero cap disables pills");
    Cv("sm2_pills_max_bonus",-4.0);
    Case("bounds_negative_cap",SMPlus_GetMaxPillsBonus()==0,"negative cap disables pills");
    Reset(); Cv("sm2_bonus_per_survivor_multiplier",0.0);
    Case("bounds_zero_budget",SMPlus_GetMaxHealthBonus()==0 && SMPlus_GetDamageBonus()==0 && SMPlus_GetMaxPillsBonus()==0,"zero map bonus cannot manufacture a pills minimum");
    Cv("sm2_bonus_per_survivor_multiplier",-1.0);
    Case("bounds_negative_multiplier",SMPlus_GetMaxHealthBonus()==0 && SMPlus_GetMaxDamageBonus()==0 && SMPlus_GetMaxPillsBonus()==0,"negative multiplier normalizes to zero");
    Reset(); Cv("survivor_limit",0.0);
    for(int i=0;i<4;i++) Player(g_Client[i]);
    Case("bounds_zero_team",SMPlus_GetMaxHealthBonus()==RoundToFloor(float(total)*0.75/4.0) && SMPlus_GetHealthBonus()==SMPlus_GetMaxHealthBonus(),"nonpositive team size uses one-player effective roster");
    Finish(); return Plugin_Stop;
}
