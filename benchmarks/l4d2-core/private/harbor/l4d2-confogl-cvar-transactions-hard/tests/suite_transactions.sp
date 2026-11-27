bool g_Cross, g_Drift, g_Back;
char g_Long[256],g_63[64],g_64[65],g_NamePrefix[64];
bool g_LateCross, g_BoundedCross, g_BoundedBack;
public void OnMapStart()
{
    FindConVar("sv_hibernate_when_empty").BoolValue=false;
    FindConVar("sb_all_bot_game").BoolValue=true;
    FindConVar("allow_all_bot_survivor_team").BoolValue=true;
    int bot=CreateFakeClient("gcb-cvar-observer");if(bot)ChangeClientTeam(bot,2);
    for(int i=0;i<255;i++)g_Long[i]='q';g_Long[255]=0;
    for(int i=0;i<63;i++)g_63[i]='x';g_63[63]=0;
    for(int i=0;i<64;i++)g_64[i]='y';g_64[64]=0;
    strcopy(g_NamePrefix,sizeof(g_NamePrefix),g_64);
    CreateTimer(1.0,Start);
}
public Action Start(Handle timer)
{
    Cvar("gcb_a","1");Cvar("gcb_b","2");Cvar("gcb_empty","old");
    Cvar("gcb_string","initial");Cvar("gcb_long",g_Long);
    Cvar("gcb_width","keep");Cvar("gcb_drop","dropbase");
    Cvar(g_63,"namebase");Cvar(g_NamePrefix,"prefixbase");Cvar("gcb_oversized","untouched");
    CreateConVar("gcb_bound","3","",0,true,0.0,true,10.0);
    CreateConVar("gcb_inrange","3","",0,true,0.0,true,10.0);
    FindConVar("gcb_inrange").AddChangeHook(BoundedCross);
    FindConVar("gcb_a").AddChangeHook(Cross);
    FindConVar("gcb_b").AddChangeHook(Back);
    Load();CreateTimer(0.15,Stage);return Plugin_Stop;
}
public void Cross(ConVar c,const char[] before,const char[] after)
{
    if(g_Cross&&StrEqual(after,"7")){g_Cross=false;FindConVar("gcb_b").SetString("99");}
    if(g_Drift&&StrEqual(after,"7")){g_Drift=false;FindConVar("gcb_b").SetString("44");}
}
public void BoundedCross(ConVar c,const char[] before,const char[] after)
{
    if(g_BoundedCross&&StrEqual(after,"01")){g_BoundedCross=false;FindConVar("gcb_b").SetString("44");}
}
public void Back(ConVar c,const char[] before,const char[] after)
{
    if(g_BoundedBack&&StrEqual(after,"8")){g_BoundedBack=false;FindConVar("gcb_inrange").SetString("1.0");}
    if(g_Back&&StrEqual(after,"8")){g_Back=false;FindConVar("gcb_a").SetString("99");}
}
public void LateCross(ConVar c,const char[] before,const char[] after)
{
    if(g_LateCross){g_LateCross=false;FindConVar("gcb_late_b").SetString("99");}
}
public Action Stage(Handle timer)
{
    Cmd("confogl_addcvar gcb_a 6");Cmd("confogl_addcvar GCB_A 7");
    Cmd("confogl_addcvar gcb_b 8");Cmd("confogl_addcvar gcb_empty \"\"");
    Cmd("confogl_addcvar gcb_string \"two words\"");Cmd("confogl_addcvar gcb_long short");
    Cmd("confogl_addcvar gcb_bound 20");
    Cmd("confogl_addcvar gcb_inrange 01");
    Cmd("confogl_addcvar gcb_pending 11");Cmd("confogl_addcvar GCB_PENDING 12");
    Cmd("confogl_addcvar gcb_unknown 14");
    Cmd("confogl_addcvar gcb_late_a 15");Cmd("confogl_addcvar gcb_late_b 16");
    ServerCommand("confogl_addcvar %s 7",g_63);ServerExecute();
    ServerCommand("confogl_addcvar %s 9",g_64);ServerExecute();
    ServerCommand("confogl_addcvar gcb_oversized %s",g_Long);ServerExecute();
    Cmd("confogl_addcvar gcb_width valid");
    ServerCommand("confogl_addcvar gcb_width %s",g_64);ServerExecute();
    ServerCommand("confogl_addcvar gcb_max %s",g_63);ServerExecute();Cvar("gcb_max","widthbase");
    Cmd("confogl_addcvar gcb_pending_pre 13");Cvar("gcb_pending_pre","5");
    ConfigCallback();
    Case("stage-known-passive",Value("gcb_a","1")&&Value("gcb_b","2"),"staging does not write");
    Case("stage-resolved-passive",Value("gcb_pending_pre","5"),"inactive config resolution does not apply");
    Cvar("gcb_a","21");Cvar("gcb_b","22");g_Cross=true;
    Cmd("confogl_setcvars");
    Case("duplicate-known-last-wins",Value("gcb_a","7"),"case-insensitive layered assignment");
    Case("activation-cross-write-corrected",Value("gcb_b","8"),"finite cross callback settles target");
    Case("empty-value-valid",Value("gcb_empty",""),"empty quoted value");
    Case("spaces-value-valid",Value("gcb_string","two words"),"quoted value");
    Case("bounded-activation",FindConVar("gcb_bound").FloatValue==10.0,"engine upper bound");
    Case("oversize-duplicate-rejected",Value("gcb_width","valid"),"no truncated override");
    Case("maximum-value-accepted",Value("gcb_max",g_63),"63 byte desired value");
    Case("maximum-name-accepted",Value(g_63,"7"),"63 byte name");
    Case("oversize-name-not-truncated",Value(g_NamePrefix,"prefixbase"),"64 byte name must not alias its valid prefix");
    Case("oversize-new-value-rejected",Value("gcb_oversized","untouched"),"255 byte value does not create a truncated assignment");
    Case("pending-resolved-before-start",Value("gcb_pending_pre","13"),"same activation rules");
    Cmd("confogl_addcvar gcb_a 900");Cmd("confogl_setcvars");
    Case("active-add-ignored",Value("gcb_a","7"),"freeze active profile");
    g_Drift=true;FindConVar("gcb_a").SetString("33");
    Case("external-drift-corrected",Value("gcb_a","7"),"synchronous correction");
    Case("cross-entry-enforcement",Value("gcb_b","8"),"guard is not global");
    g_Drift=true;g_Back=true;FindConVar("gcb_a").SetString("55");
    Case("finite-cross-callback-return",Value("gcb_a","7")&&Value("gcb_b","8")&&!g_Back,"A correction causes B correction which writes back A once");
    FindConVar("gcb_bound").SetString("4");
    Case("bounded-drift-corrected",FindConVar("gcb_bound").FloatValue==10.0,"bounded canonical enforcement terminates");
    FindConVar("gcb_inrange").SetString("1.0");
    Case("bounded-inrange-string-preserved",Value("gcb_inrange","01"),"in-range desired retains engine string representation");
    // Correction of bounded A invokes B, whose finite correction writes numeric-equivalent drift back to A.
    g_BoundedCross=true;g_BoundedBack=true;FindConVar("gcb_inrange").SetString("4");
    Case("bounded-string-finite-writeback",Value("gcb_inrange","01")&&Value("gcb_b","8")&&!g_BoundedCross&&!g_BoundedBack,"in-range string identity survives bounded A to B to A correction");
    FindConVar("gcb_string").SetString("different");
    Case("string-drift-corrected",Value("gcb_string","two words"),"string enforcement");
    Cvar("gcb_pending","31");ConfigCallback();
    Case("late-duplicate-last-wins",Value("gcb_pending","12"),"pending overlay retains latest");
    Cvar("gcb_unknown","41");ConfigCallback();
    Case("unresolved-survives-callbacks",Value("gcb_unknown","14"),"second delayed resolution");
    FindConVar("gcb_pending").SetString("32");
    Case("late-enforcement",Value("gcb_pending","12"),"late entry receives hook");
    Cvar("gcb_late_a","51");Cvar("gcb_late_b","52");
    FindConVar("gcb_late_a").AddChangeHook(LateCross);g_LateCross=true;ConfigCallback();
    Case("late-batch-enforced",Value("gcb_late_a","15")&&Value("gcb_late_b","16"),"new delayed batch uses same transaction");
    ConfigCallback();Cmd("confogl_setcvars");Cmd("confogl_resetcvars");
    Case("active-reset-rejected",Value("gcb_a","7")&&Value("gcb_pending","12"),"match gate preserves ownership");
    Cmd("confogl_cvarsettings -1");Cmd("confogl_cvarsettings 999");
    Cmd("confogl_cvardiff -1");Cmd("confogl_cvardiff 999");
    Cmd("confogl_cvarsettings 15");Cmd("confogl_cvardiff 15");
    Case("diagnostics-preserve-profile",Value("gcb_a","7"),"runtime log must also contain no exception");
    Cmd("sm_resetmatch");Cmd("confogl_resetcvars");
    Case("restore-activation-baseline",Value("gcb_a","21"),"registration-time 1 must not win");
    Case("restore-batch-baseline",Value("gcb_b","22"),"cross-callback 99 must not become baseline");
    Case("restore-late-baseline",Value("gcb_pending","31"),"callbacks never recapture enforced value");
    Case("restore-second-late-baseline",Value("gcb_unknown","41"),"independent delayed binding");
    Case("restore-late-batch-baselines",Value("gcb_late_a","51")&&Value("gcb_late_b","52"),"late snapshot precedes any callback write");
    Case("restore-long-baseline",Value("gcb_long",g_Long),"255 byte baseline preserved");
    Case("restore-bound-baseline",Value("gcb_bound","3"),"actual preactivation value");
    FindConVar("gcb_a").SetString("54");
    Case("released-hooks-removed",Value("gcb_a","54"),"released cvar accepts external writes");
    Cmd("confogl_addcvar gcb_drop 9");FindConVar("gcb_drop").SetString("newbase");
    Cmd("confogl_addcvar gcb_never 18");Cmd("confogl_resetcvars");
    Case("unactivated-release-no-write",Value("gcb_drop","newbase"),"discard passive staging");
    Cmd("confogl_addcvar gcb_drop 19");FindConVar("gcb_drop").SetString("unloadbase");
    Cmd("sm plugins unload disabled/02_confogl.smx");CreateTimer(0.15,Reload);return Plugin_Stop;
}
public Action Reload(Handle timer)
{
    Case("unactivated-unload-no-write",Value("gcb_drop","unloadbase"),"unload passive profile");
    Cvar("gcb_never","61");Load();CreateTimer(0.15,Again);return Plugin_Stop;
}
public Action Again(Handle timer)
{
    Cmd("confogl_addcvar gcb_a 71");Cmd("confogl_addcvar gcb_pending 72");
    Cmd("confogl_setcvars");ConfigCallback();
    Case("next-cycle-enforces",Value("gcb_a","71")&&Value("gcb_pending","72"),"new plugin profile");
    Case("discarded-pending-not-revived",Value("gcb_never","61"),"previous inactive pending cleared");
    Cmd("sm plugins unload disabled/02_confogl.smx");CreateTimer(0.15,End);return Plugin_Stop;
}
public Action End(Handle timer)
{
    Case("active-unload-restores-fresh",Value("gcb_a","54"),"fresh cycle baseline");
    Case("active-unload-restores-late",Value("gcb_pending","31"),"previous binding now early");
    FindConVar("gcb_a").SetString("88");
    Case("unload-hooks-gone",Value("gcb_a","88"),"no residual correction");
    Finish();return Plugin_Stop;
}
