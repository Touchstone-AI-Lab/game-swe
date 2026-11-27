char g_Path[PLATFORM_MAX_PATH];
int g_Player;
public APLRes AskPluginLoad2(Handle myself,bool late,char[] error,int maxlen)
{
    RegPluginLibrary("confogl");CreateNative("LGO_BuildConfigPath",BuildMapPath);
    return APLRes_Success;
}
public int BuildMapPath(Handle plugin,int argc)
{
    SetNativeString(1,g_Path,GetNativeCell(2));return 1;
}
void WriteData(int version)
{
    BuildPath(Path_SM,g_Path,sizeof(g_Path),"configs/gcb-map.txt");
    KeyValues kv=new KeyValues("MapInfo");
    kv.SetNum("answer",900);kv.JumpToKey(version==3?"not_this_map":"c1m1_hotel",true);
    kv.SetNum("answer",version==2?84:42);kv.SetFloat("ratio",1.25);
    kv.SetString("label",version==2?"new-label":"abcdefghi");
    float start[3]={100.0,200.0,300.0},end[3]={140.0,200.0,300.0};
    kv.SetVector("start_point",start);kv.SetVector("end_point",end);kv.SetVector("vector",end);
    kv.SetFloat("start_dist",20.0);kv.SetFloat("start_extra_dist",40.0);kv.SetFloat("end_dist",40.0);
    kv.JumpToKey("outer",true);kv.SetNum("value",17);kv.JumpToKey("inner",true);kv.SetNum("value",23);
    kv.Rewind();kv.ExportToFile(g_Path);delete kv;
}
void Reload()
{
    Handle f=CreateGlobalForward("OnLibraryAdded",ET_Ignore,Param_String);
    Call_StartForward(f);Call_PushString("confogl");Call_Finish();delete f;
}
public void OnPluginStart(){WriteData(1);}
public void OnMapStart()
{
    Wake();g_Player=CreateFakeClient("gcb-map-player");if(g_Player)ChangeClientTeam(g_Player,2);
    CreateTimer(1.0,Begin);
}
bool Vec(float a[3],float b[3]){return GetVectorDistance(a,b)<0.001;}
public Action Begin(Handle timer)
{
    WriteData(1);Reload();
    Case("reload-selects-current-map",L4D2_IsMapDataAvailable()&&L4D2_GetMapValueInt("answer",-1)==42,"map view selected immediately");
    float v[3],expected[3]={100.0,200.0,300.0};L4D2_GetMapStartOrigin(v);
    Case("reload-refreshes-geometry",Vec(v,expected)&&L4D2_GetMapStartDistance()==20.0,"cached data agrees with new map");
    KeyValues copy=new KeyValues("Copy");copy.SetNum("keep",5);
    L4D2_CopyMapSubsection(copy,"outer/inner");
    PrintToServer("GCB copied value=%d keep=%d",copy.GetNum("value"),copy.GetNum("keep"));
    Case("nested-subsection-copied",copy.GetNum("value")==23&&copy.GetNum("keep",-999)==-999,"subsection children replace caller node children");
    Case("lookup-after-nested-copy",L4D2_GetMapValueInt("answer",-1)==42,"cursor restored to current map");
    copy.SetNum("keep",5);L4D2_CopyMapSubsection(copy,"absent");
    Case("missing-copy-does-not-mutate",copy.GetNum("value")==23&&copy.GetNum("keep")==5,"missing subsection no-op");delete copy;
    char buffer[12];for(int i=0;i<12;i++)buffer[i]='Z';
    L4D2_GetMapValueString("label",buffer,4,"fallback");
    Case("string-capacity-includes-nul",StrEqual(buffer,"abc")&&buffer[4]=='Z',"sentinel after declared capacity");
    buffer[0]='Z';L4D2_GetMapValueString("label",buffer,0,"fallback");
    Case("string-zero-capacity",buffer[0]=='Z',"no output write");
    buffer[0]='Z';buffer[1]='Z';L4D2_GetMapValueString("label",buffer,1,"fallback");
    Case("string-one-capacity",buffer[0]==0&&buffer[1]=='Z',"only terminator");
    float def[3]={9.0,8.0,7.0};L4D2_GetMapValueVector("absent",v,def);
    Case("vector-default-preserved",Vec(v,def)&&def[0]==9.0&&def[2]==7.0,"default unchanged");
    Case("scalar-key-defaults",L4D2_GetMapValueInt("absent",73)==73&&L4D2_GetMapValueFloat("absent",2.5)==2.5,"explicit defaults");
    float boundary[3]={140.0,200.0,300.0};TeleportEntity(g_Player,boundary,NULL_VECTOR,NULL_VECTOR);
    Case("saferoom-inclusive-overlap",L4D2_IsEntityInSaferoom(g_Player)==3,"boundary belongs to both rooms");
    boundary[0]=181.0;TeleportEntity(g_Player,boundary,NULL_VECTOR,NULL_VECTOR);
    Case("saferoom-outside",L4D2_IsEntityInSaferoom(g_Player)==0,"outside both spheres");
    Case("saferoom-invalid-safe",L4D2_IsEntityInSaferoom(0)==0&&L4D2_IsEntityInSaferoom(-1)==0&&L4D2_IsEntityInSaferoom(GetMaxEntities()+5)==0,"invalid indices never throw");
    WriteData(2);Reload();
    Case("reload-replaces-values",L4D2_GetMapValueInt("answer",-1)==84,"new valid image");
    File f=OpenFile(g_Path,"w");f.WriteString("\"MapInfo\" { broken {",false);delete f;Reload();
    Case("failed-reload-keeps-image",L4D2_IsMapDataAvailable()&&L4D2_GetMapValueInt("answer",-1)==84,"failed parse preserves prior image");
    // Establish an independent valid baseline: a malformed-file failure must not cascade into the missing-file case.
    WriteData(2);Reload();
    Case("missing-reload-valid-baseline",L4D2_IsMapDataAvailable()&&L4D2_GetMapValueInt("answer",-1)==84,"fresh valid image before missing-file reload");
    DeleteFile(g_Path);Reload();
    Case("missing-reload-keeps-image",L4D2_GetMapValueInt("answer",-1)==84,"missing file preserves prior image");
    WriteData(3);Reload();
    Case("valid-missing-map-unavailable",!L4D2_IsMapDataAvailable(),"valid replacement deliberately removes current map");
    Case("missing-map-no-root-leak",L4D2_GetMapValueInt("answer",73)==73,"root answer 900 is not map data");
    Case("missing-map-float-default",L4D2_GetMapValueFloat("ratio",2.5)==2.5,"no stale float");
    L4D2_GetMapValueString("label",buffer,sizeof(buffer),"fallback");
    Case("missing-map-string-default",StrEqual(buffer,"fallback"),"no stale string");
    L4D2_GetMapValueVector("vector",v,def);
    Case("missing-map-vector-default",Vec(v,def),"no stale vector");
    Case("missing-map-clears-end",L4D2_GetMapEndDistance()<0.0,"end room disabled");
    Finish();return Plugin_Stop;
}
