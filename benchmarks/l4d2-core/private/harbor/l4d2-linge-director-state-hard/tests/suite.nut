// Private observable-behavior scenarios; executed only in the pinned engine VM.
::GCB_L4D2 <- {nonce="__GCB_NONCE__",passed=0,total=0,started=false,keep=[],delayed=[],observed=[],serial=0,cleanupFirst=null,cleanupSecond=null};
::GCB_L4D2.Check <- function(ok,message) {if(!ok) throw message;};
::GCB_L4D2.Equal <- function(a,b) {if(a!=b) throw "expected "+b+", got "+a;};
::GCB_L4D2.Case <- function(name,body) {
    total++;local status="PASS",reason="ok";
    try {body();passed++;} catch(e) {status="FAIL";reason=e.tostring();}
    for(local i=0;i<3;i++) printl("@@GCB_L4D2@@"+nonce+":CASE:"+name+":"+status+":"+reason);
}.bindenv(::GCB_L4D2);
::GCB_L4D2.Event <- function() {serial++;return "audit_"+nonce+serial;}.bindenv(::GCB_L4D2);
::GCB_L4D2.Hook <- function(e,cb,owner=null,last=true) {
    keep.append(cb);if(owner!=null)keep.append(owner);return ::LinEventHook(e,cb,owner,last);
}.bindenv(::GCB_L4D2);
::GCB_L4D2.Command <- function(args) {
    ::LinGe.Admin.Config.enabled=false;::LinGe.Admin.CmdExec.call(::LinGe.Admin,args[0],null,args);
};
::GCB_L4D2.ResetSI <- function() {
    local c=::LinGe.MoreSI.Config;
    c.sibase=8;c.siauto=0;c.simin=0;c.sitime=15;c.sionly=[];c.sinoci=false;c.initDelay=-1;
    Command(["sioff"]);
}.bindenv(::GCB_L4D2);
::GCB_L4D2.Config <- function() {
    serial++;local path="gcb_config_"+nonce+serial,m=::LinGe.ConfigManager(path);
    local value={count=7,nested={on=true},order=["a"]};m.Add("Mode",value);
    return {manager=m,value=value,path=path};
}.bindenv(::GCB_L4D2);
::GCB_L4D2.NoOverrides <- function() {
    foreach(key in ["cm_MaxSpecials","cm_BaseSpecialLimit","DominatorLimit","HunterLimit","JockeyLimit",
                   "BoomerLimit","SpitterLimit","SmokerLimit","ChargerLimit","cm_CommonLimit",
                   "cm_SpecialRespawnInterval","SpecialInitialSpawnDelayMin","SpecialInitialSpawnDelayMax"])
        Check(!::SessionOptions.rawin(key),"left override "+key);
}.bindenv(::GCB_L4D2);
::GCB_L4D2.Common <- function() {
    local player=Entities.FindByClassname(null,"player");
    Check(player!=null,"fixture requires real player");
    return SpawnEntityFromTable("infected",{origin=player.GetOrigin()+Vector(30,0,0),
        model="models/infected/common_male_tshirt_cargos.mdl"});
}.bindenv(::GCB_L4D2);
::GCB_L4D2.Run <- function(params) {
    if(started)return;started=true;
    Case("merge-case-input-purity",function() {
        local d={nested={Enabled=false}},s={NESTED={ENABLED=1}},child=d.nested;
        ::LinGe.Merge(d,s);Equal(d.nested.Enabled,true);Equal(s.len(),1);Equal(s.NESTED.len(),1);
        Check(!s.rawin("nested")&&!s.NESTED.rawin("Enabled"),"input keys changed");Equal(d.nested,child);
    }.bindenv(this));
    Case("merge-array-no-alias",function() {
        local s={items=[{v=4}]},d={items=[]};::LinGe.Merge(d,s);s.items[0].v=9;Equal(d.items[0].v,4);
    }.bindenv(this));
    Case("merge-reserved-copy",function() {
        local s={extra={items=[3]}},d={};::LinGe.Merge(d,s,true,true);s.extra.items[0]=10;Equal(d.extra.items[0],3);
    }.bindenv(this));
    Case("merge-replacement-and-guards",function() {
        local d={count=3,enabled=false,nested={x=1}};
        ::LinGe.Merge(d,{count="bad",enabled=2,unknown=8,nested={x=4}});
        Equal(d.count,3);Equal(d.enabled,true);Equal(d.nested.x,4);Check(!d.rawin("unknown"),"unknown key leaked");
        local s={nested=[{x=5}]};::LinGe.Merge(d,s,false);s.nested[0].x=8;Equal(d.nested[0].x,5);
    }.bindenv(this));
    Case("restore-array-numeric-order",function() {
        local s={items={}},d={items=[]};for(local i=11;i>=0;i--)s.items.rawset(i.tostring(),i*3);
        ::LinGe.Merge(d,s);Equal(d.items.len(),12);for(local i=0;i<12;i++)Equal(d.items[i],i*3);
    }.bindenv(this));
    Case("restore-array-invalid-is-atomic",function() {
        foreach(bad in [{[0]="a",[2]="c"},{[0]="a",["0"]="b"},{["00"]="a"},{[-1]="a"},{x="a"}]) {
            local d={items=["keep"],other=1};::LinGe.Merge(d,{items=bad,other=6});
            Equal(d.items.len(),1);Equal(d.items[0],"keep");Equal(d.other,6);
        }
    }.bindenv(this));
    Case("restore-array-copy-and-empty",function() {
        local s={items={[0]={v=2}}},d={items=[]};::LinGe.Merge(d,s);s.items[0].v=99;Equal(d.items[0].v,2);
        ::LinGe.Merge(d,{items={}});Equal(d.items.len(),0);
    }.bindenv(this));
    Case("config-loadall-missing",function() {
        local f=Config();f.manager.filePath=f.path+"_absent";f.manager.LoadAll();Equal(f.value.count,7);
        Equal(::VSLib.FileIO.LoadTable(f.manager.filePath).Mode.count,7);
    }.bindenv(this));
    Case("config-saveall-missing",function() {
        local f=Config();f.manager.filePath=f.path+"_absent";f.manager.SaveAll();
        Equal(::VSLib.FileIO.LoadTable(f.manager.filePath).Mode.count,7);
    }.bindenv(this));
    Case("config-bulk-malformed-roots",function() {
        foreach(text in ["{ broken =","[]","42"]) {
            local f=Config();StringToFile(f.path+".tbl",text);f.manager.LoadAll();Equal(f.value.count,7);
            StringToFile(f.path+".tbl",text);f.manager.SaveAll();Equal(::VSLib.FileIO.LoadTable(f.path).Mode.count,7);
        }
    }.bindenv(this));
    Case("config-sections-identity-and-reserve",function() {
        local f=Config(),nested=f.value.nested;
        ::VSLib.FileIO.SaveTable(f.path,{Mode={count=12,nested={on=0},newkey=[4]},Other={v=6}});
        f.manager.LoadAll(true);Equal(f.value.count,12);Equal(f.value.nested,nested);
        Equal(f.value.nested.on,false);Equal(f.value.newkey[0],4);
        Equal(::VSLib.FileIO.LoadTable(f.path).Other.v,6);
        local threw=false;try{f.manager.Load("Other");}catch(e){threw=true;}Check(threw,"unknown section registered");
        local strict=Config();::VSLib.FileIO.SaveTable(strict.path,{Mode={count=17,extra=4}});
        strict.manager.LoadAll(false);Equal(strict.value.count,17);Check(!strict.value.rawin("extra"),"bulk reserveKey ignored");
    }.bindenv(this));
    Case("config-single-recovery-and-preservation",function() {
        local f=Config();StringToFile(f.path+".tbl","[]");f.manager.Load("Mode");Equal(f.value.count,7);
        StringToFile(f.path+".tbl","[]");f.manager.Save("Mode");
        ::VSLib.FileIO.SaveTable(f.path,{Mode={count=9},Other={v=6}});f.manager.Load("Mode");
        Equal(f.value.count,9);Equal(::VSLib.FileIO.LoadTable(f.path).Other.v,6);
        f.value.count=14;f.manager.Save("Mode");local data=::VSLib.FileIO.LoadTable(f.path);
        Equal(data.Mode.count,14);Equal(data.Other.v,6);
        local second={v=20};f.manager.Add("Second",second);f.value.count=18;second.v=25;
        f.manager.SaveAll();data=::VSLib.FileIO.LoadTable(f.path);
        Equal(data.Mode.count,18);Equal(data.Second.v,25);Equal(data.Other.v,6);
    }.bindenv(this));
    Case("event-remove-current-snapshot",function() {
        local e=Event(),out=[],b=function(p){out.append("b");};
        local a=function(p){out.append("a");::LinEventUnHook(e,b);};
        Hook(e,a);Hook(e,b);::LinEventTrigger(e);Equal(out.len(),2);Equal(out[1],"b");
        ::LinEventTrigger(e);Equal(out.len(),3);
    }.bindenv(this));
    Case("event-prepend-next-dispatch",function() {
        local e=Event(),out=[],first=true,b=function(p){out.append("b");};
        local a=function(p){out.append("a");if(first){first=false;::GCB_L4D2.Hook(e,b,null,false);}};
        Hook(e,a);Hook(e,function(p){out.append("tail");});
        ::LinEventTrigger(e);Equal(out.len(),2);Equal(out[1],"tail");::LinEventTrigger(e);
        Equal(out.len(),5);Equal(out[2],"b");Equal(out[3],"a");Equal(out[4],"tail");
    }.bindenv(this));
    Case("event-nested-sees-current-registration",function() {
        local e=Event(),out=[],b=function(p){out.append("b"+p.depth);},c=function(p){out.append("c"+p.depth);};
        local a=function(p){out.append("a"+p.depth);if(p.depth==0){::LinEventUnHook(e,b);::GCB_L4D2.Hook(e,c);::LinEventTrigger(e,{depth=1});}};
        Hook(e,a);Hook(e,b);::LinEventTrigger(e,{depth=0});Equal(out.len(),4);
        Equal(out[0],"a0");Equal(out[1],"a1");Equal(out[2],"c1");Equal(out[3],"b0");
    }.bindenv(this));
    Case("event-duplicates-binding-index",function() {
        local e=Event(),owner={hits=0},cb=function(p){hits++;};
        Equal(Hook(e,cb,owner),1);Equal(Hook(e,cb,owner),2);
        Equal(::LinEventIndex(e,cb,owner,false),0);Equal(::LinEventIndex(e,cb,owner),1);
        ::LinEventTrigger(e);Equal(owner.hits,2);Equal(::LinEventUnHook(e,cb,owner,false),0);
        ::LinEventTrigger(e);Equal(owner.hits,3);Equal(::LinEventUnHook(e,cb,owner),0);Equal(::LinEventUnHook(e,cb,owner),-2);
    }.bindenv(this));
    Case("event-nested-reset-isolation",function() {
        local e=Event(),input={nested={v=1},items=[2]},seen=[];
        Hook(e,function(p){p.nested.v=8;p.items.append(9);return ACTION_RESETPARAMS;});
        Hook(e,function(p){seen.append(p.nested.v);seen.append(p.items.len());});
        ::LinEventTrigger(e,input);Equal(input.nested.v,1);Equal(input.items.len(),1);Equal(seen[0],1);Equal(seen[1],1);
    }.bindenv(this));
    Case("event-shared-edits-within-dispatch",function() {
        local e=Event(),input={nested={v=1}},out=[];
        Hook(e,function(p){p.nested.v=4;});Hook(e,function(p){out.append(p.nested.v);});
        ::LinEventTrigger(e,input);Equal(out[0],4);Equal(input.nested.v,1);
    }.bindenv(this));
    Case("event-nested-dispatch-payload",function() {
        local outer=Event(),inner=Event(),value={nested={v=1}},out=[];
        Hook(inner,function(p){p.nested.v=9;return ACTION_STOP;});
        Hook(outer,function(p){p.nested.v=4;::LinEventTrigger(inner,p);out.append(p.nested.v);});
        Hook(outer,function(p){out.append(p.nested.v);});::LinEventTrigger(outer,value);
        Equal(out.len(),2);Equal(out[0],4);Equal(out[1],4);Equal(value.nested.v,1);
    }.bindenv(this));
    Case("event-null-and-stop",function() {
        local e=Event(),out=[];Hook(e,function(p){out.append(p);return ACTION_STOP;});
        Hook(e,function(p){out.append("bad");});::LinEventTrigger(e,null);Equal(out.len(),1);Equal(out[0],null);
        local arrayEvent=Event(),value=[{v=3}],seen=[];
        Hook(arrayEvent,function(p){p[0].v=8;return ACTION_RESETPARAMS;});
        Hook(arrayEvent,function(p){seen.append(p[0].v);});::LinEventTrigger(arrayEvent,value);
        Equal(value[0].v,3);Equal(seen[0],3);
    }.bindenv(this));
    Case("director-whitelist-invalid-and-dedup",function() {
        ResetSI();local input=["bad","bad",null,7,"hunter","HUNTER","jockey"];
        ::LinGe.MoreSI.Config.sionly=input;Command(["sion"]);
        Equal(::SessionOptions.HunterLimit,4);Equal(::SessionOptions.JockeyLimit,4);Equal(::SessionOptions.BoomerLimit,0);
        Equal(::LinGe.MoreSI.Config.sionly.len(),2);Equal(::LinGe.MoreSI.Config.sionly[0],"Hunter");
        Equal(input.len(),7);Equal(input[4],"hunter");
    }.bindenv(this));
    Case("director-whitelist-without-quantity",function() {
        ResetSI();local c=::LinGe.MoreSI.Config;c.sibase=-1;c.sionly=["hunter","HUNTER","Hunter","smoker"];
        Command(["sion"]);Equal(::SessionOptions.HunterLimit,2);Equal(::SessionOptions.SmokerLimit,2);
        Equal(::SessionOptions.DominatorLimit,4);Check(!::SessionOptions.rawin("cm_MaxSpecials"),"quantity enabled");
    }.bindenv(this));
    Case("director-nonarray-clears-restriction",function() {
        ResetSI();::LinGe.MoreSI.Config.sionly="hunter";Command(["sion"]);
        Equal(::LinGe.MoreSI.Config.sionly.len(),0);Check(!::SessionOptions.rawin("HunterLimit"),"stale whitelist");
    }.bindenv(this));
    Case("director-minimum-obeys-ceiling",function() {
        ResetSI();local c=::LinGe.MoreSI.Config;c.simin=50;c.sionly=["hunter","jockey"];Command(["sion"]);
        Equal(::SessionOptions.cm_MaxSpecials,31);Equal(::SessionOptions.DominatorLimit,31);
        Equal(::SessionOptions.HunterLimit,16);Equal(::SessionOptions.JockeyLimit,16);
    }.bindenv(this));
    Case("director-independent-controls",function() {
        ResetSI();local c=::LinGe.MoreSI.Config;c.sibase=-1;c.sitime=23;c.initDelay=6;Command(["sion"]);
        Equal(::SessionOptions.cm_SpecialRespawnInterval,23);Equal(::SessionOptions.SpecialInitialSpawnDelayMin,6);
        Equal(::SessionOptions.SpecialInitialSpawnDelayMax,6);Check(!::SessionOptions.rawin("cm_MaxSpecials"),"quantity active");
    }.bindenv(this));
    Case("director-population-expression",function() {
        ResetSI();local c=::LinGe.MoreSI.Config;c.sibase=3;c.siauto=2;c.simin=1;Command(["sion"]);
        local expected=3+2*::LinGe.GetPlayerCount(2);if(expected>31)expected=31;
        Equal(::SessionOptions.cm_MaxSpecials,expected);Equal(::SessionOptions.DominatorLimit,expected);
    }.bindenv(this));
    Case("director-command-survives-round",function() {
        ResetSI();Command(["sion","9","0","11","off","hunter,jockey"]);::LinEventTrigger("OnGameEvent_round_start",{});
        Equal(::LinGe.MoreSI.Config.enabled,true);Equal(::SessionOptions.cm_MaxSpecials,9);
    }.bindenv(this));
    Case("director-disable-survives-round",function() {
        ResetSI();Command(["sion"]);::LinGe.Cache.MoreSI_Config.enabled=true;
        ::LinEventTrigger("cache_restore",{isValidCache=true});::LinEventTrigger("OnGameEvent_round_start",{});
        Command(["sioff"]);::LinEventTrigger("OnGameEvent_round_start",{});Equal(::LinGe.MoreSI.Config.enabled,false);
        Check(!::SessionOptions.rawin("cm_MaxSpecials"),"stale quantity");
    }.bindenv(this));
    Case("director-invalid-cache-preserves-choice",function() {
        ResetSI();::LinGe.Cache.MoreSI_Config.enabled=false;
        ::LinEventTrigger("cache_restore",{isValidCache=true});::LinEventTrigger("OnGameEvent_round_start",{});
        Command(["sion"]);::LinEventTrigger("cache_restore",{isValidCache=false});
        Equal(::LinGe.MoreSI.Config.enabled,false);::LinEventTrigger("OnGameEvent_round_start",{});Equal(::LinGe.MoreSI.Config.enabled,true);
    }.bindenv(this));
    Case("director-valid-cache-defers-activation",function() {
        ResetSI();::LinGe.Cache.MoreSI_Config.enabled=true;::LinEventTrigger("cache_restore",{isValidCache=true});
        Equal(::LinGe.MoreSI.Config.enabled,false);::LinEventTrigger("OnGameEvent_round_start",{});Equal(::LinGe.MoreSI.Config.enabled,true);
        ::LinGe.Cache.MoreSI_Config.enabled=false;::LinEventTrigger("cache_restore",{isValidCache=true});
        ::LinEventTrigger("OnGameEvent_round_start",{});Check(!::SessionOptions.rawin("cm_MaxSpecials"),"disabled round retained override");
    }.bindenv(this));
    Case("director-disable-idempotent",function() {
        ResetSI();local c=::LinGe.MoreSI.Config;c.initDelay=5;c.sionly=["hunter"];
        Command(["sion"]);Command(["sioff"]);Command(["sioff"]);
        NoOverrides();
    }.bindenv(this));
    Case("director-command-preserves-sentinels",function() {
        ResetSI();Command(["sion","9","2","21","off","hunter"]);Command(["sion","-2","-2","-2","-2"]);
        local c=::LinGe.MoreSI.Config;Equal(c.sibase,9);Equal(c.siauto,2);Equal(c.sitime,21);Equal(c.sionly[0],"Hunter");
    }.bindenv(this));
    Case("director-valid-restore-releases-active-overrides",function() {
        ResetSI();local c=::LinGe.MoreSI.Config;c.sinoci=true;c.initDelay=4;c.sionly=["hunter"];
        Command(["sion"]);::LinEventTrigger("cache_restore",{isValidCache=true});
        Equal(c.enabled,false);NoOverrides();
    }.bindenv(this));
    Case("director-invalid-restore-releases-active-overrides",function() {
        ResetSI();local c=::LinGe.MoreSI.Config;c.sinoci=true;c.initDelay=4;c.sionly=["hunter"];
        Command(["sion"]);::LinEventTrigger("cache_restore",{isValidCache=false});
        Equal(c.enabled,false);NoOverrides();
    }.bindenv(this));
    // Schedule using the real library/engine clock; no timer mocking.
    local e=Event(),input={nested={v=2}};
    Hook(e,function(p){::GCB_L4D2.delayed.append(p.nested.v);});
    ::LinEventTrigger(e,input,0.3);input.nested.v=5;::LinEventTrigger(e,input,0.4);input.nested.v=99;
    local e2=Event(),out=observed,old=function(p){out.append("old");};
    Hook(e2,old);::LinEventTrigger(e2,{},0.5);::LinEventUnHook(e2,old);Hook(e2,function(p){out.append("new");});
    ResetSI();Command(["sion","3","1"]);
    local survivor=Entities.FindByClassname(null,"player");
    Check(survivor!=null,"fixture requires a real spawned player");
    ::LinEventTrigger("OnGameEvent_player_team",{userid=survivor.GetPlayerUserId(),team=2,oldteam=1,disconnect=false,isbot=true,silent=true});Command(["sioff"]);
    ::VSLib.Timers.AddTimer(2.5,false,Finish.bindenv(this));
}.bindenv(::GCB_L4D2);
::GCB_L4D2.Finish <- function(params) {
    Case("event-delayed-queue-snapshot",function(){Equal(delayed.len(),2);Equal(delayed[0],2);}.bindenv(this));
    Case("event-delayed-payloads-independent",function(){Equal(delayed.len(),2);Equal(delayed[1],5);}.bindenv(this));
    Case("event-delayed-subscribers-at-delivery",function(){Equal(observed.len(),1);Equal(observed[0],"new");}.bindenv(this));
    Case("director-pending-refresh-after-disable",function(){Equal(::LinGe.MoreSI.Config.enabled,false);Check(!::SessionOptions.rawin("cm_MaxSpecials"),"timer re-enabled");}.bindenv(this));
    Case("director-common-cleanup-fixture",function(){
        ResetSI();::LinGe.MoreSI.Config.sinoci=true;Command(["sion"]);
        cleanupFirst=Common();Check(cleanupFirst!=null&&cleanupFirst.IsValid(),"common spawn failed");
    }.bindenv(this));
    ::VSLib.Timers.AddTimer(1.5,false,AfterCleanup.bindenv(this));
}.bindenv(::GCB_L4D2);
::GCB_L4D2.AfterCleanup <- function(params) {
    Case("director-common-cleanup-enabled",function(){
        Check(cleanupFirst!=null&&!cleanupFirst.IsValid(),"enabled cleanup did not remove common");
    }.bindenv(this));
    Command(["sioff"]);cleanupSecond=Common();
    ::VSLib.Timers.AddTimer(1.5,false,Complete.bindenv(this));
}.bindenv(::GCB_L4D2);
::GCB_L4D2.Complete <- function(params) {
    Case("director-common-cleanup-disabled",function(){
        Check(cleanupSecond!=null&&cleanupSecond.IsValid(),"disabled cleanup removed new common");
        NoOverrides();cleanupSecond.Kill();
    }.bindenv(this));
    local status=passed==total?"passed":"failed";
    for(local i=0;i<3;i++)printl("@@GCB_L4D2@@"+nonce+":FINAL:"+status+":"+passed+":"+total);
    // Source buffers stdout in a headless pipe. Push the complete final record
    // through that buffer before the host terminates the completed server.
    for(local i=0;i<128;i++)printl("GCB_FLUSH_"+nonce+"_"+i+"_completed_suite_output_padding");
}.bindenv(::GCB_L4D2);
::GCB_L4D2.Boot <- function(params) {
    if(!started)::VSLib.Timers.AddTimerByName("gcb_boot",2.0,false,Run.bindenv(this));
}.bindenv(::GCB_L4D2);
::LinEventHook("OnGameEvent_round_start",::GCB_L4D2.Boot,::GCB_L4D2);
