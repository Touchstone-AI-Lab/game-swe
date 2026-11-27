Action Begin(Handle timer)
{
    Reset();
    ServerCommand("sm plugins unload l4d2_hybrid_scoremod_zone");ServerExecute();
    CreateTimer(0.1, FirstLoad);return Plugin_Stop;
}
Action FirstLoad(Handle timer)
{
    Cv("vs_survival_bonus",147.0);Cv("vs_tiebreak_bonus",29.0);
    ServerCommand("sm plugins load l4d2_hybrid_scoremod_zone");ServerExecute();
    CreateTimer(0.1, FirstUnload);return Plugin_Stop;
}
Action FirstUnload(Handle timer)
{
    Cv("vs_survival_bonus",55.0);Cv("vs_tiebreak_bonus",2.0);
    ServerCommand("sm plugins unload l4d2_hybrid_scoremod_zone");ServerExecute();
    CreateTimer(0.1, SecondLoad);return Plugin_Stop;
}
Action SecondLoad(Handle timer)
{
    Case("unload_restores_startup_values",FindConVar("vs_survival_bonus").IntValue==147 && FindConVar("vs_tiebreak_bonus").IntValue==29,"unload restores values captured by this instance, including non-default startup values");
    Cv("vs_survival_bonus",83.0);Cv("vs_tiebreak_bonus",17.0);
    ServerCommand("sm plugins load l4d2_hybrid_scoremod_zone");ServerExecute();
    CreateTimer(0.1, SecondUnload);return Plugin_Stop;
}
Action SecondUnload(Handle timer)
{
    Cv("vs_survival_bonus",4.0);Cv("vs_tiebreak_bonus",0.0);
    ServerCommand("sm plugins unload l4d2_hybrid_scoremod_zone");ServerExecute();
    CreateTimer(0.1, Done);return Plugin_Stop;
}
Action Done(Handle timer)
{
    Case("unload_new_instance_snapshot",FindConVar("vs_survival_bonus").IntValue==83 && FindConVar("vs_tiebreak_bonus").IntValue==17,"next plugin instance captures its own baseline");
    Finish();return Plugin_Stop;
}
