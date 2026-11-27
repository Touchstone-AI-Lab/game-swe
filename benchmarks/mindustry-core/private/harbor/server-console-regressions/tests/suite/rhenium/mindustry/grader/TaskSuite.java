package rhenium.mindustry.grader;

import arc.*;
import arc.util.*;
import mindustry.core.GameState.*;
import mindustry.maps.Maps.*;
import mindustry.net.*;
import mindustry.net.Administration.*;
import rhenium.mindustry.harness.*;

import static mindustry.Vars.*;

/** Hidden grader suite: dedicated-server console regressions on the pinned v159.7 server. */
public class TaskSuite implements HarnessSuite{
    static final String MAP = "Ancient_Caldera";

    static void host(Ctx ctx){
        String out = ctx.command("host " + MAP);
        Check.isTrue(state.isGame(), "host " + MAP + " did not start a game: " + out);
    }

    @Override
    public void define(Suite suite){
        suite.test("the server console answers status", ctx -> {
            String out = ctx.command("status");
            Check.isTrue(out.contains("Status"), "status output: " + out);
            Check.isTrue(state.isMenu(), "the server should start without a running game");
        });

        suite.test("host with a map name starts that map", ctx -> {
            ctx.command("shuffle all");
            host(ctx);
            Check.equal("Ancient Caldera", state.map.plainName(), "hosted map");
            Check.isTrue(net.server(), "the server socket is not open");
            String out = ctx.command("stop");
            Check.isTrue(state.isMenu(), "stop did not return to the menu: " + out);
        });

        suite.test("pause refuses to run without a game", ctx -> {
            String out = ctx.command("pause on");
            Check.isTrue(out.contains("Cannot pause without a game running."), "pause output: " + out);
            Check.isTrue(state.isMenu(), "pause changed the state without a game");
        });

        suite.test("pause on and pause off set the requested state", ctx -> {
            host(ctx);
            ctx.command("pause on");
            Check.equal(State.paused, state.getState(), "state after the first 'pause on'");
            ctx.command("pause on");
            Check.equal(State.paused, state.getState(), "state after a repeated 'pause on'");
            ctx.command("pause off");
            Check.equal(State.playing, state.getState(), "state after the first 'pause off'");
            ctx.command("pause off");
            Check.equal(State.playing, state.getState(), "state after a repeated 'pause off'");
            ctx.command("stop");
        });

        suite.test("shuffle reports the selected mode", ctx -> {
            ctx.command("shuffle custom");
            String out = ctx.command("shuffle");
            Check.isTrue(out.contains("'custom'"), "shuffle output: " + out);
            Check.equal(ShuffleMode.custom, maps.getShuffleMode(), "shuffle mode");
            ctx.command("shuffle all");
        });

        suite.test("host without a map while shuffling is off keeps the console working", ctx -> {
            ctx.command("shuffle none");
            String out;
            try{
                out = ctx.command("host");
            }catch(Throwable error){
                ctx.command("shuffle all");
                Check.fail("host threw " + error.getClass().getSimpleName() + ": " + error.getMessage());
                return;
            }
            Check.isTrue(state.isMenu(), "host without a map should leave the server stopped: " + out);
            Check.isFalse(net.server(), "host without a map should not open the server");
            ctx.command("shuffle all");
            host(ctx);
            Check.equal("Ancient Caldera", state.map.plainName(), "hosted map after the failed host");
            ctx.command("stop");
        });

        suite.test("pardon of an unknown ID reports an error", ctx -> {
            String out = ctx.command("pardon no-such-player-id");
            Check.isTrue(out.contains("That ID can't be found."), "pardon output: " + out);
        });

        suite.test("pardon lets a kicked player connect again", ctx -> {
            Administration admins = netServer.admins;
            String id = "rheniumPardonId0000001==", ip = "10.20.30.40";
            admins.updatePlayerJoined(id, ip, "Kicked Player");
            admins.handleKicked(id, ip, 30L * 60L * 1000L);
            Check.isTrue(admins.getKickTime(id, ip) > Time.millis(), "the kick was not recorded");
            String out = ctx.command("pardon " + id);
            Check.isTrue(out.contains("Pardoned player"), "pardon output: " + out);
            Check.isTrue(admins.getKickTime(id, ip) <= Time.millis(),
                "the pardoned player is still kicked until " + admins.getKickTime(id, ip) + " (now " + Time.millis() + ")");
        });

        suite.test("bans can be listed and lifted in one session", ctx -> {
            ctx.command("ban ip 10.9.8.7");
            String listed = ctx.command("bans");
            Check.isTrue(listed.contains("10.9.8.7"), "bans output: " + listed);
            String out = ctx.command("unban 10.9.8.7");
            Check.isTrue(out.contains("Unbanned player: 10.9.8.7"), "unban output: " + out);
            Check.isFalse(netServer.admins.isIPBanned("10.9.8.7"), "the IP is still banned");
        });

        suite.test("player records survive a server restart", ctx -> {
            Administration admins = netServer.admins;
            String id = "rheniumRestartId000001==", ip = "10.1.2.3";
            admins.updatePlayerJoined(id, ip, "Remembered Player");
            ctx.command("ban id " + id);
            Check.isTrue(admins.isIDBanned(id), "the ID was not banned");
            admins.forceSave();
            Core.settings.forceSave();
            Core.settings.load();
            Administration restarted = new Administration();
            PlayerInfo info = restarted.getInfoOptional(id);
            Check.notNull(info, "the player record is missing after a restart");
            Check.equal("Remembered Player", info.plainLastName(), "last known name after a restart");
            Check.isTrue(restarted.isIDBanned(id), "the ID ban is missing after a restart");
        });
    }
}
