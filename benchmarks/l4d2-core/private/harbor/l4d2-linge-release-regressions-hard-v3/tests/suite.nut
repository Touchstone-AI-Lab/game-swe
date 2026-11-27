// Private behavior suite. It is injected only into the evaluator's temporary addon copy.
::GCB_L4D2 <- {
    nonce = "__GCB_NONCE__",
    passed = 0,
    total = 0,
    players = {},
    logicalPlayers = {},
    caseUserBase = 0,
    timerCalls = 0,
    timerSerial = 0,
    pendingTimers = {},
    printedMessages = [],
    hintMarkers = []
};

::GCB_L4D2.Emit <- function(kind, name, status, message)
{
    printl("@@GCB_L4D2@@" + nonce + ":" + kind + ":" + name + ":" + status + ":" + message);
}.bindenv(::GCB_L4D2);

::GCB_L4D2.Assert <- function(condition, message)
{
    if (!condition)
        throw message;
}.bindenv(::GCB_L4D2);

::GCB_L4D2.Equal <- function(actual, expected, message)
{
    if (actual != expected)
        throw message + " (expected " + expected + ", got " + actual + ")";
}.bindenv(::GCB_L4D2);

::GCB_L4D2.Case <- function(name, body)
{
    total++;
    try
    {
        body();
        passed++;
        Emit("CASE", name, "PASS", "ok");
        Emit("CASE", name, "PASS", "ok");
        Emit("CASE", name, "PASS", "ok");
    }
    catch (error)
    {
        Emit("CASE", name, "FAIL", error.tostring());
        Emit("CASE", name, "FAIL", error.tostring());
        Emit("CASE", name, "FAIL", error.tostring());
    }
}.bindenv(::GCB_L4D2);

::GCB_L4D2_Player <- class
{
    index = 0;
    survivor = false;
    health = 0;
    buffer = 0;
    incapacitated = false;
    dying = false;
    dead = false;
    zombieType = 0;
    lastDamageAmount = 0;
    team = 0;
    dominator = null;
    reviveOwner = null;
    ledge = false;
    targetname = "";
    name = "mock";
    origin = null;

    constructor(_index, _survivor, _health, _buffer, _incapacitated, _dying, _dead, _zombieType)
    {
        index = _index;
        survivor = _survivor;
        health = _health;
        buffer = _buffer;
        incapacitated = _incapacitated;
        dying = _dying;
        dead = _dead;
        zombieType = _zombieType;
        lastDamageAmount = 0;
        team = _survivor ? 2 : 3;
        dominator = null;
        reviveOwner = null;
        ledge = false;
        targetname = "LinGe_GCB_mock" + _index;
        name = "mock" + _index;
        origin = Vector(_index * 128.0, 0.0, 0.0);
    }

    function GetEntityIndex() { return index; }
    function GetIndex() { return index; }
    function GetClassname() { return "player"; }
    function IsPlayer() { return true; }
    function IsSurvivor() { return survivor; }
    function GetHealth() { return health; }
    function GetHealthBuffer() { return buffer; }
    function SetHealth(value) { health = value; }
    function SetHealthBuffer(value) { buffer = value; }
    function IsIncapacitated() { return incapacitated; }
    function IsDying() { return dying; }
    function IsDead() { return dead; }
    function GetZombieType() { return zombieType; }
    function GetSpecialInfectedDominatingMe() { return dominator; }
    function IsHangingFromLedge() { return ledge; }
    function GetNetworkIDString() { return survivor ? "STEAM_1:1:" + index : "BOT"; }
    function GetPlayerName() { return name; }
    function GetName() { return targetname; }
    function GetOrigin() { return origin; }
    function EyePosition() { return origin + Vector(0.0, 0.0, 64.0); }
    function EyeAngles() { return QAngle(0.0, 180.0, 0.0); }
    function GetMoveParent() { return null; }
    function GetActiveWeapon() { return null; }
    function __KeyValueFromString(key, value)
    {
        if (key == "targetname")
            targetname = value;
    }
    function IsValid() { return true; }
}

::GCB_L4D2.ResetStats <- function(index)
{
    local data = ::LinGe.HUD.hurtData[index];
    foreach (key, value in data)
    {
        if (typeof value == "integer" || typeof value == "float")
            data[key] = 0;
    }
}.bindenv(::GCB_L4D2);

::GCB_L4D2.ClearTable <- function(value)
{
    local keys = [];
    foreach (key, item in value)
        keys.append(key);
    foreach (key in keys)
        value.rawdelete(key);
}.bindenv(::GCB_L4D2);

::GCB_L4D2.ResetCase <- function()
{
    for (local index = 1; index <= 32; index++)
        ResetStats(index);
    ClearTable(::LinGe.HUD.tempTeamHurt);
    ClearTable(players);
    ClearTable(logicalPlayers);
    caseUserBase = 1000 + total * 10;
    timerCalls = 0;
    timerSerial = 0;
    ClearTable(pendingTimers);
    printedMessages.clear();
    hintMarkers.clear();
    ::LinGe.HUD.Config.hurt.teamHurtInfo = 0;
}.bindenv(::GCB_L4D2);

::GCB_L4D2.Player <- function(logicalID, survivor, health, buffer=0, incapacitated=false,
    dying=false, dead=false, zombieType=0)
{
    // The attacker keeps slot 1. Each case gets a fresh victim slot (2..31),
    // while logical player 3 is slot 32 only when it is a second attacker.
    local entityIndex = 1;
    if (logicalID == 2)
        entityIndex = total + 1;
    else if (logicalID == 3)
        entityIndex = logicalPlayers.rawin(2) ? 32 : total + 1;
    else if (logicalID != 1)
        entityIndex = logicalID;

    local actualUserID = caseUserBase + logicalID;
    local player = ::GCB_L4D2_Player(entityIndex, survivor, health, buffer, incapacitated,
        dying, dead, zombieType);
    players.rawset(actualUserID, player);
    logicalPlayers.rawset(logicalID, { userid=actualUserID, player=player });
    return player;
}.bindenv(::GCB_L4D2);

::GCB_L4D2.UserID <- function(logicalID)
{
    return logicalPlayers.rawin(logicalID) ? logicalPlayers[logicalID].userid : logicalID;
}.bindenv(::GCB_L4D2);

::GCB_L4D2.TeamKey <- function(attacker, victim)
{
    return UserID(attacker) + "_" + UserID(victim);
}.bindenv(::GCB_L4D2);

::GCB_L4D2.EventParams <- function(params)
{
    local actual = clone params;
    foreach (key in ["userid", "attacker", "victim", "subject", "bot", "player"])
    {
        if (actual.rawin(key))
            actual[key] = UserID(actual[key]);
    }
    return actual;
}.bindenv(::GCB_L4D2);

::GCB_L4D2.DispatchOwner <- function(event, owner, params)
{
    if (!::LinGe.Events.trigger.rawin(event))
        return 0;

    local called = 0;
    local actual = EventParams(params);
    foreach (entry in ::LinGe.Events.trigger[event].callback)
    {
        // Exercise whatever implementation the submission registered for this
        // module, without requiring a particular private helper name.
        if (entry.func != null && entry.callOf == owner)
        {
            entry.func.call(entry.callOf, actual);
            called++;
        }
    }
    return called;
}.bindenv(::GCB_L4D2);

::GCB_L4D2.DispatchHUD <- function(event, params)
{
    return DispatchOwner(event, ::LinGe.HUD, params);
}.bindenv(::GCB_L4D2);

::GCB_L4D2.DispatchHint <- function(event, params)
{
    return DispatchOwner(event, ::LinGe.Hint, params);
}.bindenv(::GCB_L4D2);

::GCB_L4D2.Hurt <- function(attacker, victim, damage, damageType=2, weapon="rifle")
{
    local victimUserID = UserID(victim);
    if (players.rawin(victimUserID))
        players[victimUserID].lastDamageAmount = damage;
    if (attacker == victim && logicalPlayers.rawin(victim))
        logicalPlayers[victim].player.index = total + 1;
    DispatchHUD("OnGameEvent_player_hurt", {
        userid=victim,
        attacker=attacker,
        dmg_health=damage,
        type=damageType,
        weapon=weapon
    });
}.bindenv(::GCB_L4D2);

::GCB_L4D2.PreDamage <- function(attacker, victim, damage, damageType=2, weapon="rifle")
{
    local attackerEntity = logicalPlayers[attacker].player;
    local victimEntity = logicalPlayers[victim].player;
    local damageTable = {
        Attacker=attackerEntity,
        Victim=victimEntity,
        DamageDone=damage,
        DamageType=damageType,
        Weapon=weapon
    };
    foreach (name, callback in ::VSLib.EasyLogic.OnTakeDamage)
    {
        if (callback != null)
            callback(damageTable);
    }
}.bindenv(::GCB_L4D2);

::GCB_L4D2.SurvivorDeath <- function(attacker, victim, damage, postHealth)
{
    local victimEntity = logicalPlayers[victim].player;
    victimEntity.health = postHealth;
    Hurt(attacker, victim, damage);
    victimEntity.dead = true;
    DispatchHUD("OnGameEvent_player_death", {
        victimname="survivor", entityid=0, userid=victim, attacker=attacker,
        headshot=false, type=2
    });
}.bindenv(::GCB_L4D2);

::GCB_L4D2.FlushTimers <- function()
{
    local queued = [];
    foreach (key, entry in pendingTimers)
        queued.append(entry);
    ClearTable(pendingTimers);
    foreach (entry in queued)
        entry.callback(entry.params);
}.bindenv(::GCB_L4D2);

::GCB_L4D2.PrintCountFor <- function(player)
{
    local count = 0;
    foreach (entry in printedMessages)
    {
        if (entry.target == player)
            count++;
    }
    return count;
}.bindenv(::GCB_L4D2);

::GCB_L4D2.PrintForContains <- function(player, fragment)
{
    foreach (entry in printedMessages)
    {
        if (entry.target == player && entry.message.find(fragment) != null)
            return true;
    }
    return false;
}.bindenv(::GCB_L4D2);

::GCB_L4D2.PrintedContains <- function(fragment)
{
    foreach (entry in printedMessages)
    {
        if (entry.message.find(fragment) != null)
            return true;
    }
    return false;
}.bindenv(::GCB_L4D2);

::GCB_L4D2.RecordHintAction <- function(action, viewer, entity)
{
    if (entity == null)
        return;
    if (action == "ShowHint")
    {
        hintMarkers.append({ entity=entity, viewer=viewer, alive=true });
        return;
    }
    if (action != "Kill")
        return;
    foreach (marker in hintMarkers)
    {
        if (marker.entity == entity)
            marker.alive = false;
    }
}.bindenv(::GCB_L4D2);

::GCB_L4D2.LiveHintCount <- function(viewer)
{
    local count = 0;
    foreach (marker in hintMarkers)
    {
        if (marker.viewer == viewer && marker.alive)
            count++;
    }
    return count;
}.bindenv(::GCB_L4D2);

::GCB_L4D2.CompleteTankTransition <- function(terminalHealth, rawDamage)
{
    local attacker = Player(1, true, 100);
    local tank = Player(3, false, terminalHealth, 0, false, false, false, 8);
    tank.lastDamageAmount = rawDamage;
    PreDamage(1, 3, rawDamage);
    tank.incapacitated = true;
    DispatchHUD("OnGameEvent_player_incapacitated", { userid=3, attacker=1 });
    tank.health = 0;
    Hurt(1, 3, rawDamage);
    return { attacker=attacker, tank=tank };
}.bindenv(::GCB_L4D2);

::GCB_L4D2.HintJoin <- function(logicalID)
{
    return DispatchHint("OnGameEvent_player_team", {
        userid=UserID(logicalID), oldteam=1, team=2
    });
}.bindenv(::GCB_L4D2);

::GCB_L4D2.HintLeave <- function(logicalID)
{
    return DispatchHint("OnGameEvent_player_team", {
        userid=UserID(logicalID), oldteam=2, team=1
    });
}.bindenv(::GCB_L4D2);

::GCB_L4D2.Counter <- function(index, key)
{
    local entityIndex = logicalPlayers.rawin(index)
        ? logicalPlayers[index].player.GetEntityIndex()
        : index;
    return ::LinGe.HUD.hurtData[entityIndex][key];
}.bindenv(::GCB_L4D2);

::GCB_L4D2.AssertFriendlyFire <- function(attacker, victim, expected, label)
{
    Equal(Counter(attacker, "atk"), expected, label + " attacker cumulative");
    Equal(Counter(attacker, "t_atk"), expected, label + " attacker round");
    Equal(Counter(victim, "vct"), expected, label + " victim cumulative");
    Equal(Counter(victim, "t_vct"), expected, label + " victim round");
}.bindenv(::GCB_L4D2);

::GCB_L4D2.SecretValue <- function(offset, minimum, span)
{
    return minimum + (nonce[offset % nonce.len()] % span);
}.bindenv(::GCB_L4D2);

::GCB_L4D2.CacheLifecycleValue <- function(failedAttempts)
{
    local savedBak = {};
    foreach (key, value in ::LinGe.HUD.hurtData_bak)
        savedBak.rawset(key, value);
    local originalHurtData = ::LinGe.HUD.hurtData;
    local originalPlayersIndex = ::LinGe.HUD.playersIndex;
    local originalPlayerInstance = ::PlayerInstanceFromIndex;
    local originalDiscard = ::LinGe.HUD.Config.hurt.discardLostRound;
    local actual = null;
    local caught = null;

    try
    {
        ClearTable(::LinGe.HUD.hurtData_bak);
        local firstMap = [];
        for (local index = 0; index <= 32; index++)
        {
            local row = clone originalHurtData[index];
            foreach (key, value in row)
            {
                if (typeof value == "integer" || typeof value == "float")
                    row[key] = 0;
            }
            firstMap.append(row);
        }
        local survivor = Player(1, true, 100);
        local data = firstMap[survivor.GetEntityIndex()];
        data.si = 5;
        data.t_si = 71;
        data.o_si = 19;
        ::LinGe.HUD.hurtData = firstMap;
        ::LinGe.HUD.playersIndex = [survivor.GetEntityIndex()];
        ::LinGe.HUD.Config.hurt.discardLostRound = true;

        // Complete map A. HUD's transition callback runs before Base saves the
        // cache, so advancing o_* here or during the next restore are both valid.
        Assert(DispatchHUD("OnGameEvent_map_transition", {}) > 0,
            "map-transition handler missing");

        ::LinGe.HUD.hurtData = [];
        ::LinGe.HUD.playersIndex = [];
        Assert(DispatchHUD("cache_restore", { isValidCache=true }) > 0,
            "cache-restore handler missing");

        for (local attempt = 0; attempt < failedAttempts; attempt++)
        {
            local restored = ::LinGe.HUD.hurtData[survivor.GetEntityIndex()];
            restored.t_si = 80 + attempt;
            Assert(DispatchHUD("OnGameEvent_round_end", {}) > 0,
                "round-end handler missing");
            local id = ::LinGe.SteamIDCastUniqueID(survivor.GetNetworkIDString());
            actual = ::LinGe.HUD.hurtData_bak[id].t_si;
            if (attempt + 1 < failedAttempts)
            {
                ::LinGe.HUD.hurtData = [];
                ::LinGe.HUD.playersIndex = [];
                Assert(DispatchHUD("cache_restore", { isValidCache=true }) > 0,
                    "replay cache-restore handler missing");
            }
        }
    }
    catch (error)
    {
        caught = error;
    }

    ::PlayerInstanceFromIndex = originalPlayerInstance;
    ::LinGe.HUD.hurtData = originalHurtData;
    ::LinGe.HUD.playersIndex = originalPlayersIndex;
    ::LinGe.HUD.Config.hurt.discardLostRound = originalDiscard;
    ClearTable(::LinGe.HUD.hurtData_bak);
    foreach (key, value in savedBak)
        ::LinGe.HUD.hurtData_bak.rawset(key, value);
    if (caught != null)
        throw caught;
    return actual;
}.bindenv(::GCB_L4D2);

::GCB_L4D2.Run <- function(params)
{
    local originalGetPlayer = ::GetPlayerFromUserID;
    local originalPlayerFromIndex = ::PlayerInstanceFromIndex;
    local originalNetProps = ::NetProps;
    local originalClientPrint = ::ClientPrint;
    local originalDoEntFire = ::DoEntFire;
    local originalNamedTimer = ::VSLib.Timers.AddTimerByName;
    local originalAnonymousTimer = ::VSLib.Timers.AddTimer;
    local originalRemoveTimer = ::VSLib.Timers.RemoveTimer;
    local originalRemoveNamedTimer = ::VSLib.Timers.RemoveTimerByName;
    local originalInfoMode = ::LinGe.HUD.Config.hurt.teamHurtInfo;
    ::GetPlayerFromUserID = function(userid) {
        return ::GCB_L4D2.players.rawin(userid) ? ::GCB_L4D2.players[userid] : null;
    };
    ::PlayerInstanceFromIndex = function(index) {
        foreach (userid, player in ::GCB_L4D2.players)
        {
            if (player.GetEntityIndex() == index)
                return player;
        }
        return null;
    };
    ::ClientPrint = function(target, destination, message) {
        ::GCB_L4D2.printedMessages.append({ target=target, message=message });
    };
    ::DoEntFire = function(target, action, value="", delay=0.0, activator=null, caller=null) {
        ::GCB_L4D2.RecordHintAction(action, activator, caller);
        return originalDoEntFire(target, action, value, delay, activator, caller);
    };
    ::NetProps = {
        original = originalNetProps,
        function GetPropInt(entity, property)
        {
            if (entity instanceof ::GCB_L4D2_Player && property == "m_lastDamageAmount")
                return entity.lastDamageAmount;
            if (entity instanceof ::GCB_L4D2_Player && property == "m_iTeamNum")
                return entity.team;
            if (property == "m_lifeState")
                return entity instanceof ::GCB_L4D2_Player && !entity.dead ? 0 : 1;
            if (entity instanceof ::GCB_L4D2_Player && property == "m_currentReviveCount")
                return 0;
            return this.original.GetPropInt(entity, property);
        },
        function GetPropEntity(entity, property)
        {
            if (entity instanceof ::GCB_L4D2_Player && property == "m_reviveOwner")
                return entity.reviveOwner;
            if (entity instanceof ::GCB_L4D2_Player && property == "m_useActionOwner")
                return null;
            return null;
        }
    };
    ::VSLib.Timers.AddTimerByName = function(name, delay, repeat, callback,
        callbackParams=null, flags=0, value=null) {
        ::GCB_L4D2.timerCalls++;
        ::GCB_L4D2.pendingTimers.rawset(name, {
            callback=callback, params=callbackParams, delay=delay, repeat=repeat
        });
        return name;
    };
    ::VSLib.Timers.AddTimer = function(delay, repeat, callback, callbackParams=null,
        flags=0, value=null) {
        ::GCB_L4D2.timerCalls++;
        ::GCB_L4D2.timerSerial++;
        local name = "anonymous_" + ::GCB_L4D2.timerSerial;
        ::GCB_L4D2.pendingTimers.rawset(name, {
            callback=callback, params=callbackParams, delay=delay, repeat=repeat
        });
        return name;
    };
    ::VSLib.Timers.RemoveTimerByName = function(name) {
        if (::GCB_L4D2.pendingTimers.rawin(name))
            ::GCB_L4D2.pendingTimers.rawdelete(name);
    };
    ::VSLib.Timers.RemoveTimer = function(name) {
        if (typeof name == "string" && ::GCB_L4D2.pendingTimers.rawin(name))
            ::GCB_L4D2.pendingTimers.rawdelete(name);
    };

    Case("ordinary-friendly-fire-updates-all-counters", function()
    {
        ResetCase();
        Player(1, true, 100);
        Player(2, true, 80);
        Hurt(1, 2, 20);
        AssertFriendlyFire(1, 2, 20, "ordinary hit");
        Equal(Counter(1, "si"), 0, "ordinary hit changed SI damage");
        Equal(Counter(1, "tank"), 0, "ordinary hit changed Tank damage");
    });

    Case("notifications-disabled-create-no-temporary-state", function()
    {
        ResetCase();
        Player(1, true, 100);
        Player(2, true, 80);
        Hurt(1, 2, 20);
        FlushTimers();
        Equal(printedMessages.len(), 0, "disabled notification produced delayed output");
    });

    Case("ordinary-delayed-message-preserves-pair-and-state", function()
    {
        ResetCase();
        ::LinGe.HUD.Config.hurt.teamHurtInfo = 2;
        local attacker = Player(1, true, 100);
        local victim = Player(2, true, 80);
        Hurt(1, 2, 20);
        FlushTimers();
        Equal(PrintCountFor(attacker), 1, "ordinary attacker message count");
        Equal(PrintCountFor(victim), 1, "ordinary victim message count");
        Assert(PrintForContains(attacker, "20") && PrintForContains(victim, "20"),
            "ordinary delayed damage changed");
        Assert(!PrintedContains("杀死") && !PrintedContains("倒"),
            "ordinary delayed message gained a terminal label");
    });

    Case("repeated-pair-accumulates-without-duplicating-state", function()
    {
        ResetCase();
        ::LinGe.HUD.Config.hurt.teamHurtInfo = 2;
        local attacker = Player(1, true, 100);
        local victim = Player(2, true, 80);
        Hurt(1, 2, 7);
        Hurt(1, 2, 9);
        AssertFriendlyFire(1, 2, 16, "repeated pair");
        FlushTimers();
        Equal(PrintCountFor(attacker), 1, "repeated attacker message count");
        Equal(PrintCountFor(victim), 1, "repeated victim message count");
        Assert(PrintForContains(attacker, "16") && PrintForContains(victim, "16"),
            "repeated delayed damage did not aggregate");
    });

    Case("multiple-attackers-remain-independent", function()
    {
        ResetCase();
        ::LinGe.HUD.Config.hurt.teamHurtInfo = 2;
        local first = Player(1, true, 100);
        local victim = Player(2, true, 80);
        local second = Player(3, true, 100);
        Hurt(1, 2, 11);
        Hurt(3, 2, 13);
        Equal(Counter(1, "atk"), 11, "first attacker total");
        Equal(Counter(3, "atk"), 13, "second attacker total");
        Equal(Counter(2, "vct"), 24, "victim combined total");
        FlushTimers();
        Equal(PrintCountFor(first), 1, "first attacker delayed message count");
        Equal(PrintCountFor(second), 1, "second attacker delayed message count");
        Equal(PrintCountFor(victim), 2, "victim independent delayed message count");
        Assert(PrintForContains(first, "11") && PrintForContains(second, "13"),
            "attacker/victim pairs were mixed");
    });

    Case("self-damage-does-not-change-friendly-fire-counters", function()
    {
        ResetCase();
        Player(1, true, 75);
        Hurt(1, 1, 25);
        AssertFriendlyFire(1, 1, 0, "self damage");
    });

    Case("invalid-attacker-is-ignored", function()
    {
        ResetCase();
        Player(2, true, 80);
        Hurt(99, 2, 20);
        Equal(Counter(2, "vct"), 0, "invalid attacker changed victim total");
    });

    Case("non-survivor-attacker-is-ignored", function()
    {
        ResetCase();
        Player(1, false, 50, 0, false, false, false, 3);
        Player(2, true, 80);
        Hurt(1, 2, 20);
        Equal(Counter(2, "vct"), 0, "infected attacker changed friendly-fire total");
    });

    Case("already-incapacitated-survivor-is-ignored", function()
    {
        ResetCase();
        Player(1, true, 100);
        Player(2, true, 300, 0, true);
        Hurt(1, 2, 15);
        AssertFriendlyFire(1, 2, 0, "already incapacitated");
    });

    Case("dying-survivor-is-ignored", function()
    {
        ResetCase();
        Player(1, true, 100);
        Player(2, true, 1, 0, false, true);
        Hurt(1, 2, 15);
        AssertFriendlyFire(1, 2, 0, "dying survivor");
    });

    Case("dead-survivor-is-ignored", function()
    {
        ResetCase();
        Player(1, true, 100);
        Player(2, true, 0, 0, false, false, true);
        Hurt(1, 2, 15);
        AssertFriendlyFire(1, 2, 0, "dead survivor");
    });

    Case("zero-damage-type-is-ignored", function()
    {
        ResetCase();
        Player(1, true, 100);
        Player(2, true, 80);
        Hurt(1, 2, 20, 0);
        AssertFriendlyFire(1, 2, 0, "zero damage type");
    });

    Case("temporary-health-nonterminal-hit-remains-ordinary", function()
    {
        ResetCase();
        Player(1, true, 100);
        Player(2, true, 1, 5);
        Hurt(1, 2, 15);
        AssertFriendlyFire(1, 2, 15, "temporary-health ordinary hit");
    });

    Case("lethal-overflow-full-transition-clamps-real-health", function()
    {
        ResetCase();
        ::LinGe.HUD.Config.hurt.teamHurtInfo = 2;
        local permanent = SecretValue(0, 5, 73);
        local temporary = SecretValue(13, 1, 12);
        local overflow = SecretValue(7, 1, 29);
        local rawDamage = permanent + temporary + overflow;
        local attacker = Player(1, true, 100);
        local victim = Player(2, true, permanent, temporary);
        PreDamage(1, 2, rawDamage);
        SurvivorDeath(1, 2, rawDamage, -(temporary + overflow));
        local expected = permanent + temporary;
        AssertFriendlyFire(1, 2, expected, "seeded lethal hit");
        FlushTimers();
        Assert(PrintForContains(attacker, expected.tostring())
            && PrintForContains(victim, expected.tostring()),
            "seeded lethal delayed damage");
        Assert(PrintedContains("杀死"), "seeded lethal delayed message lacks death label");
    });

    Case("stale-terminal-event-cannot-create-negative-accounting", function()
    {
        ResetCase();
        local attacker = Player(1, true, 100);
        local victim = Player(2, true, -50);
        local attackerData = ::LinGe.HUD.hurtData[attacker.GetEntityIndex()];
        local victimData = ::LinGe.HUD.hurtData[victim.GetEntityIndex()];
        attackerData.atk = 41;
        attackerData.t_atk = 17;
        victimData.vct = 53;
        victimData.t_vct = 29;
        Hurt(1, 2, 40);
        Equal(Counter(1, "atk"), 41, "stale terminal event changed attacker cumulative");
        Equal(Counter(1, "t_atk"), 17, "stale terminal event changed attacker round");
        Equal(Counter(2, "vct"), 53, "stale terminal event changed victim cumulative");
        Equal(Counter(2, "t_vct"), 29, "stale terminal event changed victim round");
    });

    Case("exact-zero-delayed-output-is-terminal", function()
    {
        ResetCase();
        ::LinGe.HUD.Config.hurt.teamHurtInfo = 2;
        local attacker = Player(1, true, 100);
        local victim = Player(2, true, 17);
        PreDamage(1, 2, 17);
        SurvivorDeath(1, 2, 17, 0);
        AssertFriendlyFire(1, 2, 17, "exact-zero lethal hit");
        FlushTimers();
        Assert(PrintForContains(attacker, "17") && PrintForContains(victim, "17"),
            "exact-zero delayed damage changed");
        Assert(PrintedContains("杀死"), "exact-zero delayed output lacks death label");
    });

    Case("incapacitation-full-transition-captures-effective-health", function()
    {
        ResetCase();
        ::LinGe.HUD.Config.hurt.teamHurtInfo = 2;
        local permanent = SecretValue(3, 1, 31);
        local temporary = SecretValue(11, 0, 19);
        local attacker = Player(1, true, 100);
        local victim = Player(2, true, permanent, temporary);
        local rawDamage = permanent + temporary + 17;
        victim.lastDamageAmount = rawDamage;
        PreDamage(1, 2, rawDamage);
        DispatchHUD("OnGameEvent_player_incapacitated_start", { userid=2, attacker=1 });
        victim.incapacitated = true;
        Hurt(1, 2, rawDamage);
        DispatchHUD("OnGameEvent_player_incapacitated", { userid=2, attacker=1 });
        local expected = permanent + temporary;
        AssertFriendlyFire(1, 2, expected, "seeded incapacitation");
        FlushTimers();
        Assert(PrintForContains(attacker, expected.tostring())
            && PrintForContains(victim, expected.tostring()),
            "incapacitation delayed damage");
        Assert(PrintedContains("倒"), "incapacitation delayed output lacks terminal label");
    });

    Case("incapacitation-with-notifications-disabled-still-counts", function()
    {
        ResetCase();
        Player(1, true, 100);
        local victim = Player(2, true, 12, 8);
        victim.lastDamageAmount = 45;
        PreDamage(1, 2, 45);
        DispatchHUD("OnGameEvent_player_incapacitated_start", { userid=2, attacker=1 });
        victim.incapacitated = true;
        Hurt(1, 2, 45);
        DispatchHUD("OnGameEvent_player_incapacitated", { userid=2, attacker=1 });
        AssertFriendlyFire(1, 2, 20, "notification-disabled incapacitation");
        FlushTimers();
        Equal(printedMessages.len(), 0, "disabled incap notification produced output");
    });

    Case("self-incapacitation-does-not-change-friendly-fire-counters", function()
    {
        ResetCase();
        local victim = Player(1, true, 12, 8);
        victim.lastDamageAmount = 45;
        victim.index = total + 1;
        DispatchHUD("OnGameEvent_player_incapacitated_start", { userid=1, attacker=1 });
        AssertFriendlyFire(1, 1, 0, "self incapacitation");
    });

    Case("ordinary-tank-damage-remains-counted", function()
    {
        ResetCase();
        Player(1, true, 100);
        Player(3, false, 500, 0, false, false, false, 8);
        Hurt(1, 3, 40);
        Equal(Counter(1, "tank"), 40, "ordinary Tank damage");
    });

    Case("tank-zero-type-is-ignored", function()
    {
        ResetCase();
        Player(1, true, 100);
        Player(3, false, 0, 0, true, false, false, 8);
        Hurt(1, 3, 40, 0);
        Equal(Counter(1, "tank"), 0, "zero-type Tank damage");
    });

    Case("tank-synthetic-after-transition-adds-zero", function()
    {
        ResetCase();
        local state = CompleteTankTransition(37, 50);
        local before = Counter(1, "tank");
        Hurt(1, 3, 40, 131072);
        Equal(Counter(1, "tank"), before, "synthetic Tank transition damage");
    });

    Case("tank-terminal-with-invalid-attacker-is-ignored", function()
    {
        ResetCase();
        Player(1, true, 100);
        Player(3, false, 37, 0, true, false, false, 8);
        DispatchHUD("OnGameEvent_player_incapacitated", { userid=3, attacker=99 });
        Equal(Counter(1, "tank"), 0, "invalid attacker changed Tank total");
    });

    Case("tank-terminal-transition-counts-real-health-once", function()
    {
        ResetCase();
        CompleteTankTransition(37, 50);
        Equal(Counter(1, "tank"), 37, "Tank terminal health");
    });

    Case("non-tank-incapacitation-does-not-change-tank-total", function()
    {
        ResetCase();
        Player(1, true, 100);
        Player(3, false, 37, 0, true, false, false, 3);
        DispatchHUD("OnGameEvent_player_incapacitated", { userid=3, attacker=1 });
        Equal(Counter(1, "tank"), 0, "non-Tank terminal health was counted");
    });

    Case("ordinary-shots-after-complete-tank-transition-are-ignored", function()
    {
        ResetCase();
        CompleteTankTransition(37, 50);
        local before = Counter(1, "tank");
        Hurt(1, 3, 23, 2, "rifle");
        Equal(Counter(1, "tank"), before, "post-incapacitation Tank shot was counted");
    });

    Case("ordinary-special-infected-damage-remains-counted", function()
    {
        ResetCase();
        Player(1, true, 100);
        Player(3, false, 70, 0, false, false, false, 3);
        Hurt(1, 3, 20);
        Equal(Counter(1, "si"), 20, "SI cumulative damage");
        Equal(Counter(1, "t_si"), 20, "SI round damage");
    });

    Case("qualified-entityflame-tick-uses-real-health-loss", function()
    {
        ResetCase();
        Player(1, true, 100);
        Player(3, false, 70, 0, false, false, false, 3);
        Hurt(1, 3, 4, 268435464, "entityflame");
        Equal(Counter(1, "si"), 12, "qualified flame cumulative damage");
        Equal(Counter(1, "t_si"), 12, "qualified flame round damage");
    });

    Case("ordinary-entityflame-type-is-not-multiplied", function()
    {
        ResetCase();
        Player(1, true, 100);
        Player(3, false, 70, 0, false, false, false, 3);
        Hurt(1, 3, 4, 2, "entityflame");
        Equal(Counter(1, "si"), 4, "ordinary flame damage");
        Equal(Counter(1, "t_si"), 4, "ordinary flame round damage");
    });

    Case("qualified-fire-type-on-other-weapon-is-not-multiplied", function()
    {
        ResetCase();
        Player(1, true, 100);
        Player(3, false, 70, 0, false, false, false, 3);
        Hurt(1, 3, 4, 268435464, "rifle");
        Equal(Counter(1, "si"), 4, "non-flame qualified-type damage");
        Equal(Counter(1, "t_si"), 4, "non-flame qualified-type round damage");
    });

    Case("special-infected-terminal-overflow-remains-clamped", function()
    {
        ResetCase();
        Player(1, true, 100);
        local victim = Player(3, false, 25, 0, false, false, false, 3);
        PreDamage(1, 3, 35);
        victim.health = -10;
        Hurt(1, 3, 35);
        victim.dead = true;
        DispatchHUD("OnGameEvent_player_death", {
            victimname="Hunter", entityid=0, userid=3,
            attacker=1, headshot=false, type=2
        });
        Equal(Counter(1, "si"), 25, "SI terminal overflow");
        Equal(Counter(1, "t_si"), 25, "SI round terminal overflow");
    });

    Case("stale-special-infected-event-cannot-subtract-damage", function()
    {
        ResetCase();
        local attacker = Player(1, true, 100);
        Player(3, false, -50, 0, false, false, false, 3);
        local data = ::LinGe.HUD.hurtData[attacker.GetEntityIndex()];
        data.si = 61;
        data.t_si = 23;
        Hurt(1, 3, 40);
        Equal(Counter(1, "si"), 61, "stale SI event subtracted cumulative damage");
        Equal(Counter(1, "t_si"), 23, "stale SI event subtracted round damage");
    });

    Case("common-infected-kill-and-headshot-counters-remain-intact", function()
    {
        ResetCase();
        Player(1, true, 100);
        DispatchHUD("OnGameEvent_player_death", {
            victimname="Infected", entityid=40, userid=0, attacker=1, headshot=true, type=2
        });
        Equal(Counter(1, "kci"), 1, "common kill");
        Equal(Counter(1, "t_kci"), 1, "round common kill");
        Equal(Counter(1, "hci"), 1, "common headshot");
        Equal(Counter(1, "t_hci"), 1, "round common headshot");
    });

    Case("special-infected-kill-and-headshot-counters-remain-intact", function()
    {
        ResetCase();
        Player(1, true, 100);
        Player(3, false, 0, 0, false, false, true, 3);
        DispatchHUD("OnGameEvent_player_death", {
            victimname="Hunter", entityid=0, userid=3, attacker=1, headshot=true, type=2
        });
        Equal(Counter(1, "ksi"), 1, "special kill");
        Equal(Counter(1, "t_ksi"), 1, "round special kill");
        Equal(Counter(1, "hsi"), 1, "special headshot");
        Equal(Counter(1, "t_hsi"), 1, "round special headshot");
    });

    Case("survivor-death-does-not-change-infected-kill-counters", function()
    {
        ResetCase();
        Player(1, true, 100);
        Player(2, true, 0, 0, false, false, true);
        DispatchHUD("OnGameEvent_player_death", {
            victimname="survivor", entityid=0, userid=2, attacker=1, headshot=false, type=2
        });
        Equal(Counter(1, "kci"), 0, "survivor death changed common kills");
        Equal(Counter(1, "ksi"), 0, "survivor death changed special kills");
    });

    Case("revive-marker-survives-domination-cleanup-tick", function()
    {
        ResetCase();
        local originalDuration = ::LinGe.Hint.Config.help.duration;
        local caught = null;
        local viewer = Player(1, true, 100);
        local survivor = Player(2, true, 20, 0, true);
        HintJoin(1);
        HintJoin(2);
        try
        {
            ::LinGe.Hint.Config.help.duration = 8;
            Assert(DispatchHint("OnGameEvent_player_incapacitated", { userid=2 }) > 0,
                "incapacitation event handler missing");
            FlushTimers();
            Assert(LiveHintCount(viewer) > 0,
                "revive marker entered domination cleanup");

            Assert(DispatchHint("OnGameEvent_revive_success", { subject=2 }) > 0,
                "revive-success event handler missing");
            Equal(LiveHintCount(viewer), 0, "revive marker survived revive completion");
            survivor.incapacitated = false;
            survivor.dominator = Player(3, false, 50, 0, false, false, false, 3);
            Assert(DispatchHint("OnGameEvent_lunge_pounce", { victim=2, userid=3 }) > 0,
                "domination-start event handler missing");
            Assert(LiveHintCount(viewer) > 0, "domination marker was not created");
            survivor.dominator = null;
            Assert(DispatchHint("OnGameEvent_pounce_stopped", { victim=2 }) > 0,
                "domination-end event handler missing");
            Equal(LiveHintCount(viewer), 0,
                "domination marker survived domination cleanup");
        }
        catch (error)
        {
            caught = error;
        }
        ::LinGe.Hint.Config.help.duration = originalDuration;
        HintLeave(2);
        HintLeave(1);
        if (caught != null)
            throw caught;
    });

    Case("incapacitated-and-ledge-hints-share-revive-cleanup", function()
    {
        ResetCase();
        local originalDuration = ::LinGe.Hint.Config.help.duration;
        local caught = null;
        local viewer = Player(1, true, 100);
        local survivor = Player(2, true, 20, 0, true);
        HintJoin(1);
        HintJoin(2);
        try
        {
            ::LinGe.Hint.Config.help.duration = 8;
            Assert(DispatchHint("OnGameEvent_player_incapacitated", { userid=2 }) > 0,
                "incapacitation event handler missing");
            FlushTimers();
            Assert(LiveHintCount(viewer) > 0, "incapacitated marker missing");
            Assert(DispatchHint("OnGameEvent_revive_success", { subject=2 }) > 0,
                "incapacitated revive-success handler missing");
            Equal(LiveHintCount(viewer), 0,
                "revive success did not clean incapacitated marker");

            survivor.incapacitated = false;
            survivor.ledge = true;
            Assert(DispatchHint("OnGameEvent_player_ledge_grab", { userid=2 }) > 0,
                "ledge-grab event handler missing");
            Assert(LiveHintCount(viewer) > 0, "ledge marker missing");
            Assert(DispatchHint("OnGameEvent_revive_success", { subject=2 }) > 0,
                "ledge revive-success handler missing");
            Equal(LiveHintCount(viewer), 0,
                "revive success did not clean ledge marker");
        }
        catch (error)
        {
            caught = error;
        }
        ::LinGe.Hint.Config.help.duration = originalDuration;
        HintLeave(2);
        HintLeave(1);
        if (caught != null)
            throw caught;
    });

    Case("successful-map-baseline-survives-next-failed-map", function()
    {
        ResetCase();
        Equal(CacheLifecycleValue(1), 71, "restored cumulative baseline");
    });

    Case("replayed-failed-map-keeps-last-successful-baseline", function()
    {
        ResetCase();
        Equal(CacheLifecycleValue(2), 71, "replayed failed-round rollback baseline");
    });

    Case("rewardhp-temporary-only-mode-clamps-at-limit", function()
    {
        ResetCase();
        local config = ::LinGe.RewardHP.Config;
        local oldMode = config.mode, oldLimit = config.limit;
        local oldPermanent = config.permanent.special, oldTemporary = config.temporary.special;
        local caught = null;
        local attacker = null;
        try
        {
            config.mode = 2;
            config.limit = 100;
            config.permanent.special = 2;
            config.temporary.special = 4;
            attacker = Player(1, true, 95, 3);
            Player(3, false, 0, 0, false, false, true, 3);
            DispatchOwner("OnGameEvent_player_death", ::LinGe.RewardHP, {
                victimname="Hunter", userid=3, attacker=1
            });
        }
        catch (error)
        {
            caught = error;
        }
        config.mode = oldMode;
        config.limit = oldLimit;
        config.permanent.special = oldPermanent;
        config.temporary.special = oldTemporary;
        if (caught != null)
            throw caught;
        Equal(attacker.GetHealth(), 95, "temporary-only mode changed permanent health");
        Equal(attacker.GetHealthBuffer(), 5, "temporary-only clamped reward");
    });

    Case("rewardhp-temporary-only-mode-keeps-full-fitting-reward", function()
    {
        ResetCase();
        local config = ::LinGe.RewardHP.Config;
        local oldMode = config.mode, oldLimit = config.limit;
        local oldPermanent = config.permanent.special, oldTemporary = config.temporary.special;
        local caught = null;
        local attacker = null;
        try
        {
            config.mode = 2;
            config.limit = 100;
            config.permanent.special = 2;
            config.temporary.special = 4;
            attacker = Player(1, true, 90, 3);
            Player(3, false, 0, 0, false, false, true, 3);
            DispatchOwner("OnGameEvent_player_death", ::LinGe.RewardHP, {
                victimname="Hunter", userid=3, attacker=1
            });
        }
        catch (error)
        {
            caught = error;
        }
        config.mode = oldMode;
        config.limit = oldLimit;
        config.permanent.special = oldPermanent;
        config.temporary.special = oldTemporary;
        if (caught != null)
            throw caught;
        Equal(attacker.GetHealth(), 90, "fitting temporary reward changed permanent health");
        Equal(attacker.GetHealthBuffer(), 7, "full fitting temporary reward");
    });

    Case("rewardhp-hybrid-mode-preserves-permanent-fallback", function()
    {
        ResetCase();
        local config = ::LinGe.RewardHP.Config;
        local oldMode = config.mode, oldLimit = config.limit;
        local oldPermanent = config.permanent.special, oldTemporary = config.temporary.special;
        local caught = null;
        local attacker = null;
        try
        {
            config.mode = 3;
            config.limit = 100;
            config.permanent.special = 2;
            config.temporary.special = 4;
            attacker = Player(1, true, 95, 3);
            Player(3, false, 0, 0, false, false, true, 3);
            DispatchOwner("OnGameEvent_player_death", ::LinGe.RewardHP, {
                victimname="Hunter", userid=3, attacker=1
            });
        }
        catch (error)
        {
            caught = error;
        }
        config.mode = oldMode;
        config.limit = oldLimit;
        config.permanent.special = oldPermanent;
        config.temporary.special = oldTemporary;
        if (caught != null)
            throw caught;
        Equal(attacker.GetHealth(), 97, "hybrid permanent fallback health");
        Equal(attacker.GetHealthBuffer(), 3, "hybrid permanent fallback buffer");
    });

    ::GetPlayerFromUserID = originalGetPlayer;
    ::PlayerInstanceFromIndex = originalPlayerFromIndex;
    ::NetProps = originalNetProps;
    ::ClientPrint = originalClientPrint;
    ::DoEntFire = originalDoEntFire;
    ::VSLib.Timers.AddTimerByName = originalNamedTimer;
    ::VSLib.Timers.AddTimer = originalAnonymousTimer;
    ::VSLib.Timers.RemoveTimer = originalRemoveTimer;
    ::VSLib.Timers.RemoveTimerByName = originalRemoveNamedTimer;
    ::LinGe.HUD.Config.hurt.teamHurtInfo = originalInfoMode;
    local status = passed == total ? "passed" : "failed";
    printl("@@GCB_L4D2@@" + nonce + ":FINAL:" + status + ":" + passed + ":" + total);
    printl("@@GCB_L4D2@@" + nonce + ":FINAL:" + status + ":" + passed + ":" + total);
    printl("@@GCB_L4D2@@" + nonce + ":FINAL:" + status + ":" + passed + ":" + total);
}.bindenv(::GCB_L4D2);

::LinEventHook("OnGameEvent_round_start", ::GCB_L4D2.Run, ::GCB_L4D2);
