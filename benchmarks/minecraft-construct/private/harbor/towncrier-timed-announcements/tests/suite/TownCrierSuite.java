package gcbtest.towncrier;

import io.gamecodebench.harness.GcbAssert;
import io.gamecodebench.harness.GcbCase;
import io.gamecodebench.harness.GcbScript;
import io.gamecodebench.harness.GcbSuite;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import org.bukkit.Bukkit;
import org.bukkit.command.PluginCommand;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.permissions.Permission;
import org.bukkit.permissions.PermissionDefault;
import org.bukkit.plugin.PluginManager;
import org.bukkit.plugin.java.JavaPlugin;

/** Hidden live-server cases for the TownCrier construct task. */
public final class TownCrierSuite implements GcbSuite {

    private static final String DENIED = "You do not have permission to do that.";
    private static final String USAGE = "Usage: /crier <list|now|pause|resume|add|remove|interval|preview|reload>";

    /** Receives what Server#broadcast sends to holders of bukkit.broadcast.user. */
    private final Actor user = Actor.limited("receiver_user", "bukkit.broadcast.user");
    /** Also holds towncrier.staff. */
    private final Actor staff = Actor.limited("receiver_staff", "bukkit.broadcast.user", "towncrier.staff");

    @Override
    public void onEnable(JavaPlugin grader) {
        PluginManager plugins = Bukkit.getPluginManager();
        plugins.subscribeToPermission("bukkit.broadcast.user", user.sender());
        plugins.subscribeToPermission("bukkit.broadcast.user", staff.sender());
        plugins.subscribeToPermission("towncrier.staff", staff.sender());
    }

    // --- helpers -------------------------------------------------------------------------

    private static List<String> crier(String arguments) {
        return Actor.console().run("crier " + arguments);
    }

    private static void expect(String arguments, String... expected) {
        Kit.lines(crier(arguments), "/crier " + arguments, expected);
    }

    /** Writes announcements.yml, reloads and checks the first reply line. */
    private void seed(String yaml, String loaded) {
        Kit.write("announcements.yml", yaml);
        List<String> reply = crier("reload");
        GcbAssert.isTrue(!reply.isEmpty() && reply.get(0).equals(loaded), "reload reply " + reply + ", expected " + loaded);
        user.clear();
        staff.clear();
    }

    private void heard(Actor receiver, String what, String... expected) {
        GcbAssert.equals(List.of(expected), receiver.lines(), what);
    }

    private static int count(List<String> lines, String line) {
        return Collections.frequency(lines, line);
    }

    // --- cases ---------------------------------------------------------------------------

    @GcbCase(value = "TownCrier is enabled", order = 0)
    public void sentinel() {
        GcbAssert.isTrue(Kit.plugin().isEnabled(), "TownCrier is enabled");
        GcbAssert.equals("TownCrier", Kit.plugin().getName(), "plugin name");
    }

    @GcbCase(value = "default announcements.yml is written on first enable", order = 1)
    public void defaultFile() {
        YamlConfiguration yaml = Kit.yaml("announcements.yml");
        GcbAssert.equals("<gray>[<gold>Crier</gold>]</gray> ", yaml.getString("prefix"), "prefix");
        GcbAssert.isTrue(yaml.getBoolean("groups.tips.enabled", false), "tips is enabled");
        GcbAssert.equals(300, yaml.getInt("groups.tips.interval"), "tips interval");
        GcbAssert.equals("sequential", yaml.getString("groups.tips.order"), "tips order");
        GcbAssert.equals("", yaml.getString("groups.tips.permission"), "tips permission");
        GcbAssert.equals(List.of("Use <yellow>/spawn</yellow> to return to spawn.", "Be kind to other players!"),
            yaml.getStringList("groups.tips.messages"), "tips messages");
    }

    @GcbCase(value = "plugin.yml declares the crier command and permissions", order = 2)
    public void declarations() {
        PluginCommand command = Bukkit.getPluginCommand("crier");
        GcbAssert.notNull(command, "/crier is a plugin command");
        GcbAssert.equals("TownCrier", command.getPlugin().getName(), "/crier belongs to TownCrier");
        GcbAssert.isNull(command.getPermission(), "/crier has no permission key");
        for (String name : List.of("towncrier.admin", "towncrier.staff")) {
            Permission permission = Bukkit.getPluginManager().getPermission(name);
            GcbAssert.notNull(permission, name + " is registered");
            GcbAssert.equals(PermissionDefault.OP, permission.getDefault(), name + " default");
        }
    }

    @GcbCase(value = "list shows the default group", order = 3)
    public void listDefault() {
        expect("list", "Groups:", "tips: 2 messages every 300s, sequential, running");
    }

    @GcbCase(value = "preview renders placeholders and MiniMessage", order = 4)
    public void preview() {
        seed("""
            prefix: "<gray>[TC]</gray> "
            groups:
              info:
                interval: 300
                messages:
                  - "Group {group} message {index}/{count}, online {online}/{max}"
                  - "<red>Red</red> and <bold>bold</bold> text"
            """, "Loaded 1 groups (0 disabled, 0 invalid).");
        expect("preview info 1", "[TC] Group info message 1/2, online 0/1");
        expect("preview info 2", "[TC] Red and bold text");
        expect("preview info 3", "Invalid index: 3");
        expect("preview info x", "Invalid index: x");
        heard(user, "a preview is not broadcast");
    }

    @GcbCase(value = "a sequential group announces at every interval and wraps", order = 5, ticks = 300)
    public void sequentialTimer(GcbScript script) {
        script.step(() -> seed("""
            prefix: "[TC] "
            groups:
              fast:
                interval: 2
                messages:
                  - "Alpha {index}"
                  - "Beta {index}"
                  - "Gamma {index}"
            """, "Loaded 1 groups (0 disabled, 0 invalid)."));
        script.waitTicks(30);
        script.step(() -> heard(user, "nothing before the first interval (30 ticks)"));
        script.waitTicks(20);
        script.step(() -> heard(user, "one announcement after 50 ticks", "[TC] Alpha 1"));
        script.waitTicks(40);
        script.step(() -> heard(user, "two announcements after 90 ticks", "[TC] Alpha 1", "[TC] Beta 2"));
        script.waitTicks(80);
        script.step(() -> {
            heard(user, "four announcements after 170 ticks, wrapping around",
                "[TC] Alpha 1", "[TC] Beta 2", "[TC] Gamma 3", "[TC] Alpha 1");
            heard(staff, "every receiver of bukkit.broadcast.user hears them",
                "[TC] Alpha 1", "[TC] Beta 2", "[TC] Gamma 3", "[TC] Alpha 1");
        });
    }

    @GcbCase(value = "groups keep separate timers", order = 6, ticks = 300)
    public void separateTimers(GcbScript script) {
        script.step(() -> seed("""
            prefix: "[TC] "
            groups:
              a:
                interval: 2
                messages: ["Every two"]
              b:
                interval: 3
                messages: ["Every three"]
            """, "Loaded 2 groups (0 disabled, 0 invalid)."));
        script.waitTicks(70);
        script.step(() -> {
            List<String> heard = user.lines();
            GcbAssert.equals(1, count(heard, "[TC] Every two"), "group a after 70 ticks: " + heard);
            GcbAssert.equals(1, count(heard, "[TC] Every three"), "group b after 70 ticks: " + heard);
        });
        script.waitTicks(60);
        script.step(() -> {
            List<String> heard = user.lines();
            GcbAssert.equals(3, count(heard, "[TC] Every two"), "group a after 130 ticks: " + heard);
            GcbAssert.equals(2, count(heard, "[TC] Every three"), "group b after 130 ticks: " + heard);
            GcbAssert.equals(5, heard.size(), "nothing else was announced: " + heard);
        });
    }

    @GcbCase(value = "announcements reach only receivers with the group permission", order = 7)
    public void permissionDelivery() {
        seed("""
            prefix: "[TC] "
            groups:
              staffonly:
                interval: 300
                permission: towncrier.staff
                messages: ["Staff only"]
              everyone:
                interval: 300
                messages: ["For all"]
            """, "Loaded 2 groups (0 disabled, 0 invalid).");
        expect("now staffonly", "Announced staffonly #1.");
        expect("now everyone", "Announced everyone #1.");
        heard(user, "bukkit.broadcast.user receiver", "[TC] For all");
        heard(staff, "towncrier.staff receiver, each announcement once", "[TC] Staff only", "[TC] For all");
    }

    @GcbCase(value = "disabled groups never announce on their own", order = 8, ticks = 200)
    public void disabledGroups(GcbScript script) {
        script.step(() -> seed("""
            prefix: "[TC] "
            groups:
              quiet:
                enabled: false
                interval: 1
                messages: ["Quiet"]
              loud:
                interval: 1
                messages: ["Loud"]
            """, "Loaded 2 groups (1 disabled, 0 invalid)."));
        script.waitTicks(50);
        script.step(() -> {
            heard(user, "only the enabled group announced", "[TC] Loud", "[TC] Loud");
            expect("list", "Groups:", "loud: 1 messages every 1s, sequential, running",
                "quiet: 1 messages every 1s, sequential, disabled");
            expect("pause quiet", "quiet is disabled.");
            expect("resume quiet", "quiet is disabled.");
            user.clear();
            expect("now quiet", "Announced quiet #1.");
            heard(user, "now works for a disabled group", "[TC] Quiet");
            seed("prefix: \"\"\ngroups: {}\n", "Loaded 0 groups (0 disabled, 0 invalid).");
        });
    }

    @GcbCase(value = "shuffle announces every message once per cycle", order = 9, ticks = 300)
    public void shuffle(GcbScript script) {
        script.step(() -> seed("""
            prefix: "[TC] "
            groups:
              mix:
                interval: 1
                order: shuffle
                messages: ["m1", "m2", "m3", "m4"]
            """, "Loaded 1 groups (0 disabled, 0 invalid)."));
        script.waitTicks(170);
        script.step(() -> {
            List<String> heard = new ArrayList<>(user.lines());
            GcbAssert.equals(8, heard.size(), "eight announcements after 170 ticks: " + heard);
            Set<String> all = Set.of("[TC] m1", "[TC] m2", "[TC] m3", "[TC] m4");
            GcbAssert.equals(all, new HashSet<>(heard.subList(0, 4)), "first cycle: " + heard);
            GcbAssert.equals(all, new HashSet<>(heard.subList(4, 8)), "second cycle: " + heard);
            expect("list", "Groups:", "mix: 4 messages every 1s, shuffle, running");
            seed("prefix: \"\"\ngroups: {}\n", "Loaded 0 groups (0 disabled, 0 invalid).");
        });
    }

    @GcbCase(value = "now announces the next message immediately", order = 10)
    public void now() {
        seed("""
            prefix: "[TC] "
            groups:
              seq:
                interval: 300
                messages: ["x1", "x2", "x3"]
            """, "Loaded 1 groups (0 disabled, 0 invalid).");
        expect("now seq", "Announced seq #1.");
        expect("now seq", "Announced seq #2.");
        expect("NOW seq", "Announced seq #3.");
        expect("now seq", "Announced seq #1.");
        heard(user, "the announcements", "[TC] x1", "[TC] x2", "[TC] x3", "[TC] x1");
    }

    @GcbCase(value = "pause stops a group and resume restarts its timer", order = 11, ticks = 400)
    public void pauseResume(GcbScript script) {
        script.step(() -> seed("""
            prefix: "[TC] "
            groups:
              p:
                interval: 2
                messages: ["P1", "P2", "P3"]
            """, "Loaded 1 groups (0 disabled, 0 invalid)."));
        script.waitTicks(50);
        script.step(() -> {
            heard(user, "the first announcement", "[TC] P1");
            expect("pause p", "Paused p.");
            expect("pause p", "p is already paused.");
            expect("list", "Groups:", "p: 3 messages every 2s, sequential, paused");
        });
        script.waitTicks(100);
        script.step(() -> {
            heard(user, "a paused group stays silent", "[TC] P1");
            expect("resume p", "Resumed p.");
        });
        script.waitTicks(30);
        script.step(() -> heard(user, "a resumed group waits a full interval", "[TC] P1"));
        script.waitTicks(20);
        script.step(() -> {
            heard(user, "the resumed group continues with the next message", "[TC] P1", "[TC] P2");
            expect("resume p", "p is not paused.");
            expect("pause p", "Paused p.");
            expect("reload", "Loaded 1 groups (0 disabled, 0 invalid).");
            expect("list", "Groups:", "p: 3 messages every 2s, sequential, running");
            seed("prefix: \"\"\ngroups: {}\n", "Loaded 0 groups (0 disabled, 0 invalid).");
        });
    }

    @GcbCase(value = "reload restarts timers without leaving old ones", order = 12, ticks = 300)
    public void reloadTimers(GcbScript script) {
        String file = """
            prefix: "[TC] "
            groups:
              r:
                interval: 2
                messages: ["R1", "R2"]
            """;
        script.step(() -> {
            seed(file, "Loaded 1 groups (0 disabled, 0 invalid).");
            seed(file, "Loaded 1 groups (0 disabled, 0 invalid).");
            seed(file, "Loaded 1 groups (0 disabled, 0 invalid).");
        });
        script.waitTicks(50);
        script.step(() -> {
            heard(user, "three reloads still give one announcement per interval", "[TC] R1");
            expect("reload", "Loaded 1 groups (0 disabled, 0 invalid).");
        });
        script.waitTicks(50);
        script.step(() -> heard(user, "a reload starts over with the first message", "[TC] R1", "[TC] R1"));
        script.waitTicks(40);
        script.step(() -> {
            heard(user, "then the second", "[TC] R1", "[TC] R1", "[TC] R2");
            seed("prefix: \"\"\ngroups: {}\n", "Loaded 0 groups (0 disabled, 0 invalid).");
        });
    }

    @GcbCase(value = "reload reports invalid groups", order = 13)
    public void invalidGroups() {
        Kit.write("announcements.yml", """
            prefix: "[TC] "
            groups:
              good:
                interval: 300
                messages: ["Good"]
              idle:
                enabled: false
                interval: 300
                messages: ["Idle"]
              Bad Name:
                interval: 300
                messages: ["x"]
              zero:
                interval: 0
                messages: ["x"]
              weird:
                interval: 5
                order: random
                messages: ["x"]
              empty:
                interval: 5
                messages: []
              text:
                interval: soon
                messages: ["x"]
              nointerval:
                messages: ["x"]
            """);
        expect("reload",
            "Loaded 2 groups (1 disabled, 6 invalid).",
            "Skipped Bad Name: invalid name.",
            "Skipped zero: interval must be a whole number of at least 1.",
            "Skipped weird: order must be sequential or shuffle.",
            "Skipped empty: no messages.",
            "Skipped text: interval must be a whole number of at least 1.",
            "Skipped nointerval: interval must be a whole number of at least 1.");
        expect("list", "Groups:", "good: 1 messages every 300s, sequential, running",
            "idle: 1 messages every 300s, sequential, disabled");
        expect("now zero", "Unknown group: zero");
        seed("prefix: \"\"\ngroups: {}\n", "Loaded 0 groups (0 disabled, 0 invalid).");
        expect("list", "No groups.");
    }

    @GcbCase(value = "add appends a message and saves the file", order = 14)
    public void add() {
        seed("""
            prefix: "[TC] "
            groups:
              g1:
                interval: 300
                messages: ["one"]
              keep:
                interval: 42
                permission: towncrier.staff
                messages: ["k"]
            """, "Loaded 2 groups (0 disabled, 0 invalid).");
        expect("now g1", "Announced g1 #1.");
        expect("add g1 Hello <green>world</green> {index}", "Added message #2 to g1.");
        YamlConfiguration yaml = Kit.yaml("announcements.yml");
        GcbAssert.equals(List.of("one", "Hello <green>world</green> {index}"), yaml.getStringList("groups.g1.messages"),
            "the saved messages");
        GcbAssert.equals(300, yaml.getInt("groups.g1.interval"), "g1 keeps its interval");
        GcbAssert.equals("[TC] ", yaml.getString("prefix"), "the prefix is kept");
        GcbAssert.equals(42, yaml.getInt("groups.keep.interval"), "another group is kept");
        GcbAssert.equals("towncrier.staff", yaml.getString("groups.keep.permission"), "its permission is kept");
        GcbAssert.equals(List.of("k"), yaml.getStringList("groups.keep.messages"), "its messages are kept");
        expect("preview g1 2", "[TC] Hello world 2");
        user.clear();
        expect("now g1", "Announced g1 #1.");
        heard(user, "add starts a new cycle", "[TC] one");
    }

    @GcbCase(value = "remove deletes a message and saves the file", order = 15)
    public void remove() {
        seed("""
            prefix: "[TC] "
            groups:
              g2:
                interval: 300
                messages: ["a", "b", "c"]
            """, "Loaded 1 groups (0 disabled, 0 invalid).");
        expect("now g2", "Announced g2 #1.");
        expect("remove g2 2", "Removed message #2 from g2.");
        GcbAssert.equals(List.of("a", "c"), Kit.yaml("announcements.yml").getStringList("groups.g2.messages"), "saved");
        expect("now g2", "Announced g2 #1.");
        expect("remove g2 0", "Invalid index: 0");
        expect("remove g2 3", "Invalid index: 3");
        expect("remove g2 x", "Invalid index: x");
        expect("remove g2 1", "Removed message #1 from g2.");
        GcbAssert.equals(List.of("c"), Kit.yaml("announcements.yml").getStringList("groups.g2.messages"), "saved");
        expect("remove g2 1", "Cannot remove the last message of g2.");
        GcbAssert.equals(List.of("c"), Kit.yaml("announcements.yml").getStringList("groups.g2.messages"), "unchanged");
    }

    @GcbCase(value = "interval changes the period and is saved", order = 16, ticks = 200)
    public void interval(GcbScript script) {
        script.step(() -> {
            seed("""
                prefix: "[TC] "
                groups:
                  g3:
                    interval: 300
                    messages: ["I1", "I2"]
                """, "Loaded 1 groups (0 disabled, 0 invalid).");
            expect("interval g3 2", "Interval of g3 set to 2s.");
            GcbAssert.equals(2, Kit.yaml("announcements.yml").getInt("groups.g3.interval"), "the saved interval");
            expect("interval g3 0", "Invalid interval: 0");
            expect("interval g3 x", "Invalid interval: x");
            expect("list", "Groups:", "g3: 2 messages every 2s, sequential, running");
        });
        script.waitTicks(30);
        script.step(() -> heard(user, "nothing before the new interval"));
        script.waitTicks(20);
        script.step(() -> {
            heard(user, "the new interval applies", "[TC] I1");
            seed("prefix: \"\"\ngroups: {}\n", "Loaded 0 groups (0 disabled, 0 invalid).");
        });
    }

    @GcbCase(value = "unknown groups are reported", order = 17)
    public void unknownGroups() {
        seed("""
            prefix: "[TC] "
            groups:
              real:
                interval: 300
                messages: ["r"]
            """, "Loaded 1 groups (0 disabled, 0 invalid).");
        for (String line : List.of("now ghost", "pause ghost", "resume ghost", "add ghost hi there", "remove ghost 1",
                "interval ghost 5", "preview ghost 1", "remove ghost x", "preview ghost x", "interval ghost x")) {
            expect(line, "Unknown group: ghost");
        }
        heard(user, "nothing was announced");
    }

    @GcbCase(value = "permissions are enforced", order = 18)
    public void permissions() {
        seed("""
            prefix: "[TC] "
            groups:
              guarded:
                interval: 300
                messages: ["g"]
            """, "Loaded 1 groups (0 disabled, 0 invalid).");
        Actor nobody = Actor.limited("nobody_18");
        for (String line : List.of("list", "now guarded", "pause guarded", "resume guarded", "add guarded x",
                "remove guarded 1", "interval guarded 5", "preview guarded 1", "reload", "now ghost")) {
            Kit.lines(nobody.run("crier " + line), "/crier " + line + " without permission", DENIED);
        }
        heard(user, "a denied now announces nothing");
        GcbAssert.equals(List.of("g"), Kit.yaml("announcements.yml").getStringList("groups.guarded.messages"),
            "a denied add changes nothing");
        Actor admin = Actor.limited("admin_18", "towncrier.admin");
        Kit.lines(admin.run("crier list"), "towncrier.admin lists", "Groups:",
            "guarded: 1 messages every 300s, sequential, running");
        Kit.lines(admin.run("crier now guarded"), "towncrier.admin announces", "Announced guarded #1.");
    }

    @GcbCase(value = "malformed commands show usage", order = 19)
    public void usage() {
        expect("", USAGE);
        expect("bogus", USAGE);
        expect("list all", "Usage: /crier list");
        expect("now", "Usage: /crier now <group>");
        expect("pause a b", "Usage: /crier pause <group>");
        expect("resume", "Usage: /crier resume <group>");
        expect("add a", "Usage: /crier add <group> <text...>");
        expect("remove a", "Usage: /crier remove <group> <index>");
        expect("interval a 1 2", "Usage: /crier interval <group> <seconds>");
        expect("preview a", "Usage: /crier preview <group> <index>");
        expect("reload now", "Usage: /crier reload");
        Kit.lines(Actor.limited("nobody_19").run("crier now"), "usage comes before the permission check",
            "Usage: /crier now <group>");
    }

}
