::GCB_L4D2 <- {nonce="__GCB_NONCE__",passed=0,total=0,started=false,phase=0,at=0.0,
    serial=0,counts={},saved={},keep=[],done=false};
::GCB_L4D2.Check <- function(ok,why="condition failed") {if(!ok)throw why;};
::GCB_L4D2.Equal <- function(a,b) {if(a!=b)throw "expected "+b+", got "+a;};
::GCB_L4D2.Case <- function(name,body) {
    printl("GCB_BEGIN "+name);
    total++;local status="PASS",reason="ok";
    try{body();passed++;}catch(e){status="FAIL";reason=e.tostring();}
    for(local i=0;i<3;i++)printl("@@GCB_L4D2@@"+nonce+":CASE:"+name+":"+status+":"+reason);
}.bindenv(::GCB_L4D2);
::GCB_L4D2.Path <- function(){return "gcb_data_"+nonce+"_"+(++serial);}.bindenv(::GCB_L4D2);
::GCB_L4D2.RoundTrip <- function(value){local p=Path();Check(::VSLib.FileIO.SaveTable(p,value),"save rejected supported data");return ::VSLib.FileIO.LoadTable(p);}.bindenv(::GCB_L4D2);
::GCB_L4D2.Count <- function(name){if(!(name in counts))counts[name]<-0;counts[name]++;}.bindenv(::GCB_L4D2);
::GCB_L4D2.Callback <- function(name){local cb=function(p){::GCB_L4D2.Count(name);};keep.append(cb);return cb;}.bindenv(::GCB_L4D2);
::GCB_L4D2.Run <- function(params)
{
    if(started)return;started=true;
    for(local i=0;i<128;i++)printl("GCB_RUN_START_"+i+"..............................................");
    Case("data-control-characters",function(){local v="a\nb\rc\td\\e\"f";Equal(RoundTrip({v=v}).v,v);}.bindenv(this));
    Case("data-literal-legacy-markers",function(){local v="{VSQUOTE}:{VSSLASH}:\\{VSQUOTE}";Equal(RoundTrip({v=v}).v,v);}.bindenv(this));
    Case("data-arbitrary-string-keys",function(){local v={};v[""]<-1;v["space key!"]<-2;v["a\nb"]<-3;local r=RoundTrip(v);Equal(r[""],1);Equal(r["space key!"],2);Equal(r["a\nb"],3);}.bindenv(this));
    Case("data-key-type-separation",function(){local v={};v[1]<-"integer";v["1"]<-"string";v[-7]<-"negative";v["_vslInt_1"]<-"literal";local r=RoundTrip(v);Equal(r.len(),4);foreach(k,x in v)Equal(r[k],x);}.bindenv(this));
    Case("data-nested-array-order",function(){local r=RoundTrip({a=[{v="{VSQUOTE}"},[3,2,1],[],{}]});Equal(r.a[0].v,"{VSQUOTE}");Equal(r.a[1][0],3);Equal(r.a[1][2],1);Equal(typeof r.a[2],"array");Equal(typeof r.a[3],"table");}.bindenv(this));
    Case("data-null-bool-integer",function(){local r=RoundTrip([null,true,false,-17,0,2147483647]);Equal(r.len(),6);Equal(r[0],null);Equal(r[1],true);Equal(r[2],false);Equal(r[3],-17);Equal(r[5],2147483647);}.bindenv(this));
    Case("data-float-precision",function(){local r=RoundTrip({a=1.0,b=1.234567,c=0.00000125,d=-12345.25});Equal(typeof r.a,"float");Check(fabs(r.b-1.234567)<0.000001);Check(fabs(r.c-0.00000125)<0.000000001);Check(fabs(r.d+12345.25)<0.01);}.bindenv(this));
    Case("data-shared-noncyclic",function(){local child={v=3},src={a=child,b=child};local r=RoundTrip(src);r.a.v=9;Equal(r.b.v,3);Equal(src.a.v,3);Equal(src.a,src.b);}.bindenv(this));
    Case("data-save-input-purity",function(){local a={};a["9"]<-[{v="x\ny"},null];RoundTrip(a);Equal(a.len(),1);Check(a.rawin("9")&&!a.rawin(9));Equal(a["9"][0].v,"x\ny");Equal(a["9"].len(),2);}.bindenv(this));
    Case("data-function-atomic-rejection",function(){local p=Path();Check(::VSLib.FileIO.SaveTable(p,{old=9}));local before=FileToString(p+".tbl");Equal(::VSLib.FileIO.SaveTable(p,{a=1,b=function(){}}),false);Equal(FileToString(p+".tbl"),before);}.bindenv(this));
    Case("data-instance-atomic-rejection",function(){local p=Path();StringToFile(p+".tbl","sentinel");local C=class{};Equal(::VSLib.FileIO.SaveTable(p,{bad=C()}),false);Equal(FileToString(p+".tbl"),"sentinel");}.bindenv(this));
    Case("data-cycle-atomic-rejection",function(){local p=Path(),a={};a.self<-a;StringToFile(p+".tbl","sentinel");Equal(::VSLib.FileIO.SaveTable(p,a),false);Equal(FileToString(p+".tbl"),"sentinel");}.bindenv(this));
    Case("data-invalid-key-rejection",function(){local p=Path(),a={};a[true]<-1;StringToFile(p+".tbl","sentinel");Equal(::VSLib.FileIO.SaveTable(p,a),false);Equal(FileToString(p+".tbl"),"sentinel");}.bindenv(this));
    Case("legacy-clean-data",function(){local p=Path();StringToFile(p+".tbl","{ foo = 7 bar = true nest = { x = -2.5 } }\n");local r=::VSLib.FileIO.LoadTable(p);Equal(r.foo,7);Equal(r.bar,true);Equal(r.nest.x,-2.5);}.bindenv(this));
    Case("legacy-recursive-numeric-keys",function(){local p=Path();StringToFile(p+".tbl","{ nest = { _vslInt_2 = 8 } arr = [ { _vslInt_0 = 9 } ] }");local r=::VSLib.FileIO.LoadTable(p);Equal(r.nest[2],8);Equal(r.arr[0][0],9);}.bindenv(this));
    Case("legacy-recursive-markers",function(){local p=Path();StringToFile(p+".tbl","{ arr = [ \"{VSQUOTE}\" { x = \"{VSSLASH}\" } ] }");local r=::VSLib.FileIO.LoadTable(p);Equal(r.arr[0],"\"");Equal(r.arr[1].x,"\\");}.bindenv(this));
    Case("legacy-prefix-not-substring",function(){local p=Path();StringToFile(p+".tbl","{ x_vslInt_2 = 3 _vslInt_02 = 4 _vslInt_3x = 5 }");local r=::VSLib.FileIO.LoadTable(p);Equal(r.x_vslInt_2,3);Equal(r._vslInt_02,4);Equal(r._vslInt_3x,5);}.bindenv(this));
    Case("data-missing-file",function(){Equal(::VSLib.FileIO.LoadTable(Path()),null);}.bindenv(this));
    Case("data-malformed-input",function(){foreach(raw in ["{ x = ","[ 1 2", "{ x = \"unterminated }", "not data"]){local p=Path();StringToFile(p+".tbl",raw);Equal(::VSLib.FileIO.LoadTable(p),null);}}.bindenv(this));
    Case("data-trailing-garbage",function(){local p=Path();StringToFile(p+".tbl","{ x = 1 } junk");Equal(::VSLib.FileIO.LoadTable(p),null);}.bindenv(this));
    Case("data-no-expression-execution",function(){::GCB_DATA_SIDE_EFFECT<-0;local p=Path();StringToFile(p+".tbl","(function(){ ::GCB_DATA_SIDE_EFFECT = 1; return {x=1}; })()");Equal(::VSLib.FileIO.LoadTable(p),null);Equal(::GCB_DATA_SIDE_EFFECT,0);}.bindenv(this));
    Case("data-wrapper-roundtrip",function(){local map=Path();Check(::VSLib.FileIO.SaveTableFileName(map,"mode",{x=[null,"{VSQUOTE}"]}));local r=::VSLib.FileIO.LoadTableFileName(map,"mode");Equal(r.x[0],null);Equal(r.x[1],"{VSQUOTE}");}.bindenv(this));
    Case("data-configmanager-integration",function(){local p=Path(),cfg={text="a\nb",n=4};local m=::LinGe.ConfigManager(p);m.Add("Mode",cfg);m.SaveAll();cfg.text="changed";cfg.n=0;m.LoadAll();Equal(cfg.text,"a\nb");Equal(cfg.n,4);}.bindenv(this));

    local t=::VSLib.Timers;
    // Exercise opaque callback payloads without inspecting scheduler internals.
    saved.scalarExpected <- [17, "timer payload", false, 2.5];saved.scalars <- [];
    foreach (payload in saved.scalarExpected)
        t.AddTimer(0.1,false,function(p){::GCB_L4D2.saved.scalars.append(p);},payload);
    saved.arrayPayload <- [3,{value=7}];
    t.AddTimer(0.1,false,function(p){::GCB_L4D2.saved.arrayReceived<-p;p[1].value=11;},saved.arrayPayload);
    saved.variantPayload <- [19];
    t.AddTimer(0.1,false,function(p){::GCB_L4D2.saved.variantReceived<-p;},saved.variantPayload,16,{duration=1.0});

    // Call the real Base event dispatcher, including its delayed deep-copy path.
    saved.eventPayload <- [5,{value=9}];saved.eventCalls<-0;
    local eventCallback=function(p){::GCB_L4D2.saved.eventCalls++;::GCB_L4D2.saved.eventReceived<-p;};
    keep.append(eventCallback);::LinGe.Events.EventHook("gcb_delayed_array",eventCallback);
    ::LinGe.Events.EventTrigger("gcb_delayed_array",saved.eventPayload,0.1);
    saved.eventPayload[1].value=99;

    // Real MoreSI handler -> AddTimerByName(integer) -> Delay_siauto -> ExecConfig.
    saved.moreConfig <- clone ::LinGe.MoreSI.Config;
    local config=::LinGe.MoreSI.Config;
    config.enabled=true;config.sibase=3;config.simin=0;config.siauto=2;
    config.sitime=-1;config.sionly=[];config.sinoci=false;config.initDelay=-1;
    ::LinGe.MoreSI.ExecConfig();::SessionOptions.cm_MaxSpecials=1;
    ::LinGe.MoreSI.OnGameEvent_player_team({userid=1,team=2,oldteam=1});
    saved.options <- {count=2};saved.a<-[];saved.b<-[];
    t.AddTimer(0.1,true,function(p){::GCB_L4D2.saved.a.append(p.TimerCount);},null,4,saved.options);
    t.AddTimer(0.1,true,function(p){::GCB_L4D2.saved.b.append(p.TimerCount);},null,4,saved.options);
    saved.duration <- {duration=0.35};
    t.AddTimer(0.1,true,Callback("duration"),null,8,saved.duration);
    t.AddTimer(0.1,true,Callback("durationzero"),null,8,{duration=0.02});
    t.AddTimerByName("gcb_done",0.1,false,Callback("once"));
    t.AddTimerByName("gcb_error",0.1,true,function(p){::GCB_L4D2.Count("error");throw "intentional callback failure";});
    t.AddTimerByName("gcb_peer",0.1,false,Callback("peer"));
    t.AddTimerByName("gcb_replace",0.1,true,function(p){::GCB_L4D2.Count("old");::VSLib.Timers.AddTimerByName("gcb_replace",0.1,false,::GCB_L4D2.Callback("replacement"));return false;});
    local remove=t.AddTimerByName("gcb_remove",0.1,true,Callback("removed"));t.RemoveTimerByName(remove);
    saved.explicit <- t.AddTimerByName("gcb_explicit",0.1,true,Callback("explicit"));
    t.RemoveTimer(t.TimersID[saved.explicit]);
    t.AddTimerByName("gcb_atomic",0.2,false,Callback("valid"));
    saved.invalid <- t.AddTimerByName("gcb_atomic",0.1,true,Callback("invalid"),null,4,{count=0});
    saved.params <- {v=1};t.AddTimer(0.1,false,function(p){p.v=9;},saved.params);
    t.AddTimer(0.1,true,function(p){::GCB_L4D2.Count("stop");return false;});
    saved.peerA <- t.AddTimer(0.1,false,function(p){::GCB_L4D2.Count("peerRemoved");::VSLib.Timers.RemoveTimer(::GCB_L4D2.saved.peerB);});
    saved.peerB <- t.AddTimer(0.1,false,function(p){::GCB_L4D2.Count("peerRemoved");::VSLib.Timers.RemoveTimer(::GCB_L4D2.saved.peerA);});
    t.AddTimer(0.1,false,function(p){::GCB_L4D2.saved.parentTime<-Time();::VSLib.Timers.AddTimer(0.1,false,function(q){::GCB_L4D2.saved.childTime<-Time();});});
    t.ManageTimer("gcb_up",1,2.0);saved.clockStart<-Time();
    t.ManageTimer("gcb_down",2,0.01,false);t.ManageTimer("gcb_negative",2,0.01,true);
    at=Time();phase=1;
}.bindenv(::GCB_L4D2);

::GCB_L4D2.Tick <- function()
{
    if(!started||done)return;
    local t=::VSLib.Timers;
    if(phase==1 && Time()-at>=0.85)
    {
        Case("timer-opaque-scalar-payloads",function(){Equal(saved.scalars.len(),saved.scalarExpected.len());foreach(value in saved.scalarExpected){local hits=0;foreach(actual in saved.scalars)if(typeof actual==typeof value && actual==value)hits++;Equal(hits,1);}}.bindenv(this));
        Case("timer-array-payload-identity",function(){Equal(saved.arrayReceived,saved.arrayPayload);Equal(saved.arrayPayload[1].value,11);Equal(saved.variantReceived,saved.variantPayload);}.bindenv(this));
        Case("timer-countdown-payload-atomic-rejection",function(){local v=::VSLib.Timers;foreach(flag in [4,8])foreach(payload in [7,[1]]){v.AddTimerByName("gcb_payload_atomic",10.0,false,Callback("payload_old"));local old=v.TimersID["gcb_payload_atomic"];Equal(v.AddTimerByName("gcb_payload_atomic",0.1,true,Callback("payload_bad"),payload,flag,{count=2,duration=1.0}),-1);Equal(v.TimersID["gcb_payload_atomic"],old);v.RemoveTimerByName("gcb_payload_atomic");}}.bindenv(this));
        Case("timer-base-delayed-array-event",function(){Equal(saved.eventCalls,1);Equal(typeof saved.eventReceived,"array");Equal(saved.eventReceived[0],5);Equal(saved.eventReceived[1].value,9);Equal(saved.eventPayload[1].value,99);}.bindenv(this));
        Case("timer-count-isolation",function(){Equal(saved.a.len(),2);Equal(saved.b.len(),2);Equal(saved.a[0],2);Equal(saved.a[1],1);Equal(saved.b[0],2);Equal(saved.b[1],1);}.bindenv(this));
        Case("timer-options-input-purity",function(){Equal(saved.options.count,2);Equal(saved.duration.len(),1);Equal(saved.duration.duration,0.35);}.bindenv(this));
        Case("timer-duration-count",function(){Equal(counts.duration,3);}.bindenv(this));
        Case("timer-subinterval-duration",function(){Check(!counts.rawin("durationzero"));}.bindenv(this));
        Case("timer-once-and-retirement",function(){Equal(counts.once,1);Check(!::VSLib.Timers.TimersID.rawin("gcb_done"));}.bindenv(this));
        Case("timer-exception-once",function(){Equal(counts.error,1);Check(!::VSLib.Timers.TimersID.rawin("gcb_error"));}.bindenv(this));
        Case("timer-exception-peer-survives",function(){Equal(counts.peer,1);}.bindenv(this));
        Case("timer-self-replacement",function(){Equal(counts.old,1);Equal(counts.replacement,1);Check(!::VSLib.Timers.TimersID.rawin("gcb_replace"));}.bindenv(this));
        Case("timer-explicit-removal",function(){Check(!counts.rawin("removed")&&!counts.rawin("explicit"));Check(!::VSLib.Timers.TimersID.rawin("gcb_explicit"));}.bindenv(this));
        Case("timer-invalid-replace-atomic",function(){Equal(saved.invalid,-1);Equal(counts.valid,1);Check(!counts.rawin("invalid"));}.bindenv(this));
        Case("timer-shared-params-preserved",function(){Equal(saved.params.v,9);}.bindenv(this));
        Case("timer-false-stops-repeat",function(){Equal(counts.stop,1);}.bindenv(this));
        Case("timer-remove-due-peer",function(){Equal(counts.peerRemoved,1);}.bindenv(this));
        Case("timer-new-work-own-delay",function(){Check(saved.childTime-saved.parentTime>=0.09);}.bindenv(this));
        Case("timer-reject-invalid-options",function(){local v=::VSLib.Timers,cb=Callback("bad");foreach(n in [0,-2,1.5,"2"])Equal(v.AddTimer(0.1,true,cb,null,4,{count=n}),-1);Equal(v.AddTimer("x",true,cb),-1);Equal(v.AddTimer(0.1,true,3),-1);Equal(v.AddTimer(0.1,true,cb,null,8,{duration=-1}),-1);Equal(v.AddTimer(0.1,true,cb,null,12,{count=2,duration=1}),-1);}.bindenv(this));
        Case("clock-current-read",function(){Check(fabs(::VSLib.Timers.ReadTimer("gcb_up")-(2+Time()-saved.clockStart))<0.006,"read did not settle current engine time");}.bindenv(this));
        Case("clock-nonnegative-clamp",function(){Equal(::VSLib.Timers.ReadTimer("gcb_down"),0);}.bindenv(this));
        Case("clock-negative-allowed",function(){Check(::VSLib.Timers.ReadTimer("gcb_negative")< -0.5);}.bindenv(this));
        Case("clock-unknown-null",function(){Equal(::VSLib.Timers.ReadTimer("gcb_unknown"),null);}.bindenv(this));
        t.ManageTimer("gcb_up",0);saved.paused<-2+Time()-saved.clockStart;
        at=Time();phase=2;
    }
    else if(phase==2 && Time()-at>=0.45)
    {
        Case("clock-pause-settles",function(){Check(fabs(::VSLib.Timers.ReadTimer("gcb_up")-saved.paused)<0.006);}.bindenv(this));
        t.ManageTimer("gcb_up",1);saved.resumedAt<-Time();
        t.ManageTimer("gcb_reset",1,99.0);t.ManageTimer("gcb_reset",0,7.0);
        at=Time();phase=3;
    }
    else if(phase==3 && Time()-at>=0.35)
    {
        Case("timer-moresi-team-refresh",function(){local expected=3+2*::LinGe.GetPlayerCount(2);if(expected>31)expected=31;Equal(::SessionOptions.cm_MaxSpecials,expected);Check(!::VSLib.Timers.TimersID.rawin("SIAUTO"));}.bindenv(this));
        foreach(key,value in saved.moreConfig)::LinGe.MoreSI.Config[key]=value;
        ::LinGe.MoreSI.ExecConfig();
        Case("clock-resume-no-paused-time",function(){Check(fabs(::VSLib.Timers.ReadTimer("gcb_up")-(saved.paused+Time()-saved.resumedAt))<0.006);}.bindenv(this));
        Case("clock-explicit-reset",function(){Equal(::VSLib.Timers.ReadTimer("gcb_reset"),7.0);}.bindenv(this));
        t.AddTimerByName("gcb_round_normal",0.1,false,Callback("roundnormal"));
        t.AddTimerByName("gcb_round_keep",0.1,false,Callback("roundkeep"),null,2);
        Case("timer-round-name-retirement",function(){::VSLib_RemoveDeadTimers();Check(!::VSLib.Timers.TimersID.rawin("gcb_round_normal"));Check(::VSLib.Timers.TimersID.rawin("gcb_round_keep"));}.bindenv(this));
        at=Time();phase=4;
    }
    else if(phase==4 && Time()-at>=0.4)
    {
        Case("timer-round-keepalive",function(){Check(!counts.rawin("roundnormal"));Equal(counts.roundkeep,1);Check(!::VSLib.Timers.TimersID.rawin("gcb_round_keep"));}.bindenv(this));
        done=true;
        for(local i=0;i<3;i++)printl("@@GCB_L4D2@@"+nonce+":FINAL:"+(passed==total?"passed":"failed")+":"+passed+":"+total);
        for(local i=0;i<128;i++)printl("GCB_FLUSH_"+i+".................................................................");
    }
}.bindenv(::GCB_L4D2);
