import io.gamecodebench.harness.GcbAssert;
import io.gamecodebench.harness.GcbCase;
import io.gamecodebench.harness.GcbCommands;
import io.gamecodebench.harness.GcbScript;
import io.gamecodebench.harness.GcbSuite;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.function.Consumer;
import java.util.function.Supplier;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.serializer.legacy.LegacyComponentSerializer;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;
import org.bukkit.Bukkit;
import org.bukkit.command.CommandSender;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.server.BroadcastMessageEvent;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.plugin.Plugin;

/**
 * Live-server grader for the {@code /team help} pager repair in BetterTeams.
 *
 * <p>BetterTeams sends chat through its shaded adventure-platform-bukkit, which maps every
 * {@link org.bukkit.command.ConsoleCommandSender} (the harness recording sender included) to the
 * real server console. The suite therefore talks to the plugin through Paper's feedback-forwarding
 * sender ({@link Bukkit#createCommandSender}), a console-type operator whose messages are handed to
 * a consumer, and dispatches through {@link GcbCommands}. Sub-commands run off the main thread, so
 * every case is a ticked script that waits for the footer (or the plugin's internal-error line).
 */
public final class HelpPageSuite implements GcbSuite, Listener {

    private static final String PLUGIN = "BetterTeams";
    private static final int PER_PAGE = 7;
    private static final Pattern FOOTER = Pattern.compile("Page (\\d+)/(\\d+) - /team help <page>");
    private static final Pattern LEGACY_CODE = Pattern.compile("§[0-9a-fk-orx]", Pattern.CASE_INSENSITIVE);
    private static final String HEADER_TEXT = "BetterTeams Help";
    private static final String ERROR_TEXT = "Something went wrong";
    private static final Pattern AMPERSAND_CODE = Pattern.compile("&([0-9a-fk-orx])", Pattern.CASE_INSENSITIVE);

    /** Plain text of every server broadcast seen since the suite was enabled. */
    private static final List<String> BROADCASTS = Collections.synchronizedList(new ArrayList<>());

    @Override
    public void onEnable(JavaPlugin grader) {
        Bukkit.getPluginManager().registerEvents(this, grader);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onBroadcast(BroadcastMessageEvent event) {
        BROADCASTS.add(PlainTextComponentSerializer.plainText().serialize(event.message()));
    }

    /** Plain text with legacy section codes and ampersand codes removed. */
    private static String visible(String text) {
        return LEGACY_CODE.matcher(AMPERSAND_CODE.matcher(text).replaceAll("\u00a7$1")).replaceAll("");
    }

    private static List<String> broadcastsContaining(String needle) {
        synchronized (BROADCASTS) {
            return BROADCASTS.stream().filter(line -> visible(line).contains(needle)).toList();
        }
    }

    /** A console-type sender whose feedback is collected as plain text. */
    private static final class Console {
        final List<String> lines = Collections.synchronizedList(new ArrayList<>());
        final CommandSender sender = Bukkit.createCommandSender(component -> lines.add(plain(component)));

        List<String> snapshot() {
            synchronized (lines) {
                return List.copyOf(lines);
            }
        }
    }

    /** What one {@code /team help ...} invocation produced. */
    private static final class HelpOutput {
        final String command;
        final List<String> lines;

        HelpOutput(String command, List<String> lines) {
            this.command = command;
            this.lines = lines;
        }

        boolean hasError() {
            return lines.stream().anyMatch(line -> line.contains(ERROR_TEXT));
        }

        String footer() {
            return lines.stream().filter(line -> FOOTER.matcher(line).find()).findFirst().orElse(null);
        }

        int page() {
            return footerGroup(1);
        }

        int maxPage() {
            return footerGroup(2);
        }

        /** Command lines: everything that is neither header, footer nor error. */
        List<String> entries() {
            List<String> entries = new ArrayList<>();
            for (String line : lines) {
                if (line.contains(HEADER_TEXT) || FOOTER.matcher(line).find() || line.contains(ERROR_TEXT)) {
                    continue;
                }
                entries.add(line);
            }
            return entries;
        }

        private int footerGroup(int group) {
            String footer = footer();
            GcbAssert.notNull(footer, "/" + command + " must end with the page footer: " + lines);
            Matcher matcher = FOOTER.matcher(footer);
            GcbAssert.isTrue(matcher.find(), "footer must name the page: " + footer);
            return Integer.parseInt(matcher.group(group));
        }
    }

    private static String plain(Component component) {
        return LEGACY_CODE.matcher(PlainTextComponentSerializer.plainText().serialize(component)).replaceAll("");
    }

    private static boolean finished(List<String> lines) {
        synchronized (lines) {
            if (lines.isEmpty()) {
                return false;
            }
            boolean paged = lines.stream().anyMatch(line -> line.contains(HEADER_TEXT));
            if (!paged) {
                return true;
            }
            return lines.stream().anyMatch(line -> FOOTER.matcher(line).find() || line.contains(ERROR_TEXT));
        }
    }

    /** Dispatches {@code /team help <args>} and hands the collected output to {@code then}. */
    private static void help(GcbScript script, Console console, Supplier<String> args, Consumer<HelpOutput> then) {
        String[] line = new String[1];
        script.step(() -> {
            String request = args.get();
            line[0] = request.isEmpty() ? "team help" : "team help " + request;
            console.lines.clear();
            GcbAssert.isTrue(GcbCommands.dispatch(console.sender, line[0]), "/" + line[0] + " must be dispatched");
        });
        script.waitUntil(() -> finished(console.lines), "output of the help command");
        script.waitTicks(2);
        script.step(() -> then.accept(new HelpOutput(line[0], console.snapshot())));
    }

    private static void help(GcbScript script, Console console, String args, Consumer<HelpOutput> then) {
        help(script, console, () -> args, then);
    }

    private static void expectPage(HelpOutput out, int page) {
        GcbAssert.isFalse(out.hasError(), "/" + out.command + " must not report an internal error: " + out.lines);
        GcbAssert.notNull(out.footer(), "/" + out.command + " must end with the page footer: " + out.lines);
        GcbAssert.equals(page, out.page(), "/" + out.command + " shows page " + page + " (" + out.footer() + ")");
        GcbAssert.isTrue(out.page() <= out.maxPage(),
                "/" + out.command + " must not name a page past the last one: " + out.footer());
    }

    private static String configuredPrefix() {
        Plugin plugin = Bukkit.getPluginManager().getPlugin(PLUGIN);
        GcbAssert.notNull(plugin, "BetterTeams must be loaded");
        String raw = plugin.getConfig().getString("prefixFormat", "");
        return plain(LegacyComponentSerializer.legacyAmpersand().deserialize(raw));
    }

    @GcbCase(value = "plugin is enabled", order = 0)
    public void pluginIsEnabled() {
        GcbAssert.isTrue(Bukkit.getPluginManager().isPluginEnabled(PLUGIN), "BetterTeams must be enabled");
        GcbAssert.notNull(Bukkit.getCommandMap().getCommand("team"), "the /team command must be registered");
    }

    @GcbCase(value = "help without a page shows the first page", order = 1, ticks = 200)
    public void firstPage(GcbScript script) {
        Console console = new Console();
        help(script, console, "", out -> {
            expectPage(out, 1);
            GcbAssert.isTrue(out.maxPage() >= 2, "the help must span at least two pages: " + out.footer());
            GcbAssert.equals(PER_PAGE, out.entries().size(),
                    "/team help lists seven commands on its first page: " + out.lines);
            for (String entry : out.entries()) {
                GcbAssert.isTrue(entry.contains("/team ") && entry.contains(" - "),
                        "each line names a command and its description: " + entry);
            }
        });
    }

    @GcbCase(value = "an explicit page number selects that page", order = 2, ticks = 300)
    public void explicitPage(GcbScript script) {
        Console console = new Console();
        List<String> first = new ArrayList<>();
        help(script, console, "", out -> {
            expectPage(out, 1);
            first.addAll(out.entries());
        });
        help(script, console, "1", out -> {
            expectPage(out, 1);
            GcbAssert.equals(first, out.entries(), "/team help 1 lists the same commands as /team help");
        });
        help(script, console, "2", out -> {
            expectPage(out, 2);
            int size = out.entries().size();
            GcbAssert.isTrue(size >= 1 && size <= PER_PAGE, "page 2 lists between one and seven commands: " + out.lines);
            for (String entry : out.entries()) {
                GcbAssert.isFalse(first.contains(entry), "page 2 must not repeat a page 1 command: " + entry);
            }
        });
    }

    @GcbCase(value = "the last page shows the remaining commands", order = 3, ticks = 300)
    public void lastPage(GcbScript script) {
        Console console = new Console();
        List<String> first = new ArrayList<>();
        int[] last = new int[1];
        help(script, console, "", out -> {
            expectPage(out, 1);
            last[0] = out.maxPage();
            first.addAll(out.entries());
        });
        help(script, console, () -> Integer.toString(last[0]), out -> {
            expectPage(out, last[0]);
            GcbAssert.equals(last[0], out.maxPage(), "the last page keeps the page count: " + out.footer());
            int size = out.entries().size();
            GcbAssert.isTrue(size >= 1 && size <= PER_PAGE,
                    "the last page lists between one and seven commands: " + out.lines);
            for (String entry : out.entries()) {
                GcbAssert.isFalse(first.contains(entry), "the last page must not repeat a page 1 command: " + entry);
            }
        });
    }

    @GcbCase(value = "help for one command is unchanged", order = 4, ticks = 200)
    public void singleCommandHelp(GcbScript script) {
        Console console = new Console();
        help(script, console, "create", out -> {
            GcbAssert.isFalse(out.hasError(), "/team help create must not report an internal error: " + out.lines);
            GcbAssert.isNull(out.footer(), "/team help create prints no page footer: " + out.lines);
            GcbAssert.equals(1, out.lines.size(), "/team help create prints exactly one line: " + out.lines);
            String line = out.lines.get(0);
            GcbAssert.isTrue(line.startsWith("/team create "), "the line starts with the command: " + line);
            GcbAssert.isTrue(line.endsWith(" - Create a team with the specified name"),
                    "the line ends with the command description: " + line);
        });
    }

    @GcbCase(value = "help entries carry the plugin prefix", order = 5, ticks = 200)
    public void entriesCarryPrefix(GcbScript script) {
        String prefix = configuredPrefix();
        GcbAssert.isTrue(!prefix.isBlank(), "prefixFormat must render to a visible prefix: <" + prefix + ">");
        Console console = new Console();
        help(script, console, "", out -> {
            expectPage(out, 1);
            GcbAssert.isTrue(!out.entries().isEmpty(), "the first page lists commands: " + out.lines);
            for (String entry : out.entries()) {
                GcbAssert.isFalse(entry.startsWith("null"), "a help line must not start with null: " + entry);
                GcbAssert.isTrue(entry.startsWith(prefix + "/team "),
                        "each help line starts with the configured prefix <" + prefix + ">: " + entry);
            }
        });
    }

    @GcbCase(value = "page zero and negative pages fall back to the first page", order = 6, ticks = 300)
    public void pageZeroAndNegative(GcbScript script) {
        Console console = new Console();
        List<String> first = new ArrayList<>();
        help(script, console, "", out -> {
            expectPage(out, 1);
            first.addAll(out.entries());
        });
        for (String request : List.of("0", "-1")) {
            help(script, console, request, out -> {
                GcbAssert.isFalse(out.hasError(),
                        "/team help " + request + " must not fail with an internal error: " + out.lines);
                expectPage(out, 1);
                GcbAssert.equals(first, out.entries(), "/team help " + request + " lists the first page's commands");
            });
        }
    }

    @GcbCase(value = "pages past the end show the last page", order = 7, ticks = 300)
    public void pagesPastTheEnd(GcbScript script) {
        Console console = new Console();
        List<String> lastEntries = new ArrayList<>();
        int[] last = new int[1];
        help(script, console, "", out -> {
            expectPage(out, 1);
            last[0] = out.maxPage();
        });
        help(script, console, () -> Integer.toString(last[0]), out -> {
            expectPage(out, last[0]);
            lastEntries.addAll(out.entries());
            GcbAssert.isTrue(!lastEntries.isEmpty(), "the last page lists commands: " + out.lines);
        });
        List<Supplier<String>> requests = List.of(() -> Integer.toString(last[0] + 1), () -> "99");
        for (Supplier<String> request : requests) {
            help(script, console, request, out -> {
                GcbAssert.isFalse(out.hasError(), "/" + out.command + " must not fail with an internal error: " + out.lines);
                GcbAssert.notNull(out.footer(), "/" + out.command + " must end with the page footer: " + out.lines);
                GcbAssert.equals(last[0], out.page(), "/" + out.command + " shows the last page (" + out.footer() + ")");
                GcbAssert.equals(last[0], out.maxPage(), "/" + out.command + " keeps the page count (" + out.footer() + ")");
                GcbAssert.equals(lastEntries, out.entries(), "/" + out.command + " lists the last page's commands");
            });
        }
    }

    @GcbCase(value = "a page argument that is not a number shows the first page", order = 8, ticks = 300)
    public void nonNumericPage(GcbScript script) {
        Console console = new Console();
        List<String> first = new ArrayList<>();
        help(script, console, "", out -> {
            expectPage(out, 1);
            first.addAll(out.entries());
        });
        help(script, console, "notapage", out -> {
            GcbAssert.isFalse(out.hasError(), "/team help notapage must not report an internal error: " + out.lines);
            expectPage(out, 1);
            GcbAssert.equals(first, out.entries(), "/team help notapage lists the first page's commands");
        });
    }

    @GcbCase(value = "chest claim broadcasts carry the plugin prefix", order = 9, ticks = 400)
    public void chestClaimBroadcasts(GcbScript script) {
        String prefix = configuredPrefix();
        Console console = new Console();
        String disabled = "All claimed chests are able to be opened";
        String enabled = "All claimed chests are locked";
        script.step(() -> {
            BROADCASTS.clear();
            GcbAssert.isTrue(GcbCommands.dispatch(console.sender, "teama chest disableclaims"),
                    "/teama chest disableclaims must be dispatched");
        });
        script.waitUntil(() -> !broadcastsContaining(disabled).isEmpty(), "the disable-claims broadcast");
        script.step(() -> GcbAssert.isTrue(GcbCommands.dispatch(console.sender, "teama chest enableclaims"),
                "/teama chest enableclaims must be dispatched"));
        script.waitUntil(() -> !broadcastsContaining(enabled).isEmpty(), "the enable-claims broadcast");
        script.step(() -> {
            for (String text : List.of(disabled, enabled)) {
                for (String line : broadcastsContaining(text)) {
                    String shown = visible(line);
                    GcbAssert.isFalse(shown.startsWith("null"), "a broadcast must not start with null: " + line);
                    GcbAssert.isTrue(shown.startsWith(prefix),
                            "the broadcast starts with the configured prefix <" + prefix + ">: " + line);
                }
            }
        });
    }
}
