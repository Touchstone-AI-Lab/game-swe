import io.gamecodebench.harness.GcbAssert;
import io.gamecodebench.harness.GcbCase;
import io.gamecodebench.harness.GcbCommands;
import io.gamecodebench.harness.GcbScript;
import io.gamecodebench.harness.GcbSuite;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.function.Consumer;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.TextComponent;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.text.format.TextColor;
import net.kyori.adventure.text.format.TextDecoration;
import net.kyori.adventure.text.serializer.gson.GsonComponentSerializer;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;
import org.bukkit.Bukkit;
import org.bukkit.command.CommandSender;

/**
 * Live-server grader for the team-description tag injection repair in BetterTeams.
 *
 * <p>BetterTeams sends chat through its shaded adventure-platform-bukkit, which maps every
 * {@link org.bukkit.command.ConsoleCommandSender} (the harness recording sender included) to the
 * real server console and hands every other player-free sender legacy text (its Spigot facet is
 * disabled because the relocated BungeeCord serializer is not native). The suite therefore talks
 * to the plugin through Paper's feedback-forwarding sender ({@link Bukkit#createCommandSender}),
 * an operator-level sender whose messages arrive as native {@link Component}s with the colours
 * and decorations of that text; click and hover events cannot survive the legacy path, so the
 * discriminating assertion of the target cases is the literal tag text, and the event walk is a
 * guard for component-preserving paths. Sub-commands run off the main thread, so every case is a
 * ticked script that waits for the plugin's reply.
 */
public final class DescriptionTagSuite implements GcbSuite {

    private static final String PLUGIN = "BetterTeams";
    private static final String DESCRIPTION_LABEL = "Description: ";
    private static final String CLICK_TAG = "<click:run_command:/say injected>CLICKME</click>";
    private static final String HOVER_TAG = "<hover:show_text:'secret'>HOVERME</hover>";
    private static final String INSERTION_TAG = "<insertion:/team join gcb>INSERTME</insertion>";
    private static final String LANG_TAG = "<lang:block.minecraft.stone>";

    /** A console-type sender whose feedback is collected as native components. */
    private static final class Console {
        final List<Component> lines = Collections.synchronizedList(new ArrayList<>());
        final CommandSender sender = Bukkit.createCommandSender(lines::add);

        List<Component> snapshot() {
            synchronized (lines) {
                return List.copyOf(lines);
            }
        }

        boolean any(String text) {
            synchronized (lines) {
                return lines.stream().anyMatch(line -> plain(line).contains(text));
            }
        }
    }

    /** The info screen of one team as received by the sender. */
    private static final class InfoScreen {
        final String team;
        final List<Component> lines;

        InfoScreen(String team, List<Component> lines) {
            this.team = team;
            this.lines = lines;
        }

        List<String> plainLines() {
            List<String> result = new ArrayList<>();
            for (Component line : lines) {
                result.add(plain(line));
            }
            return result;
        }

        Component descriptionLine() {
            for (Component line : lines) {
                if (plain(line).contains(DESCRIPTION_LABEL)) {
                    return line;
                }
            }
            GcbAssert.fail("/team info " + team + " must print a Description: line: " + plainLines());
            return null;
        }

        /** The text after {@code Description: }, with the surrounding whitespace removed. */
        String description() {
            String text = plain(descriptionLine());
            return text.substring(text.indexOf(DESCRIPTION_LABEL) + DESCRIPTION_LABEL.length()).strip();
        }
    }

    /** Colour and decorations that apply to one text node after inheriting from its parents. */
    private static final class Effective {
        TextColor colour;
        final List<TextDecoration> decorations = new ArrayList<>();
        boolean found;
    }

    private static String plain(Component component) {
        return PlainTextComponentSerializer.plainText().serialize(component);
    }

    private static String json(Component component) {
        return GsonComponentSerializer.gson().serialize(component);
    }

    /** Every component of the tree, parents before children. */
    private static List<Component> flatten(Component root) {
        List<Component> result = new ArrayList<>();
        collect(root, result);
        return result;
    }

    private static void collect(Component node, List<Component> into) {
        into.add(node);
        for (Component child : node.children()) {
            collect(child, into);
        }
    }

    private static boolean hasClickEvent(Component root) {
        return flatten(root).stream().anyMatch(node -> node.clickEvent() != null);
    }

    private static boolean hasHoverEvent(Component root) {
        return flatten(root).stream().anyMatch(node -> node.hoverEvent() != null);
    }

    private static Effective styleOf(Component node, String text, Effective inherited) {
        Effective current = new Effective();
        current.colour = node.color() != null ? node.color() : (inherited == null ? null : inherited.colour);
        if (inherited != null) {
            current.decorations.addAll(inherited.decorations);
        }
        for (TextDecoration decoration : TextDecoration.values()) {
            TextDecoration.State state = node.decoration(decoration);
            if (state == TextDecoration.State.TRUE && !current.decorations.contains(decoration)) {
                current.decorations.add(decoration);
            } else if (state == TextDecoration.State.FALSE) {
                current.decorations.remove(decoration);
            }
        }
        if (node instanceof TextComponent textNode && textNode.content().contains(text)) {
            current.found = true;
            return current;
        }
        for (Component child : node.children()) {
            Effective inChild = styleOf(child, text, current);
            if (inChild.found) {
                return inChild;
            }
        }
        return current;
    }

    /** The effective style of the first text node whose own content contains {@code text}. */
    private static Effective styleOf(Component root, String text) {
        Effective effective = styleOf(root, text, null);
        GcbAssert.isTrue(effective.found, "the line must contain a text node with <" + text + ">: " + json(root));
        return effective;
    }

    /** Dispatches one command and waits until the plugin has replied with {@code expected}. */
    private static void command(GcbScript script, Console console, String line, String expected) {
        script.step(() -> {
            console.lines.clear();
            GcbAssert.isTrue(GcbCommands.dispatch(console.sender, line), "/" + line + " must be dispatched");
        });
        script.waitUntil(() -> console.any(expected), "reply to /" + line);
        script.waitTicks(2);
    }

    /** Creates {@code team} with {@code description} through the admin commands. */
    private static void createTeam(GcbScript script, Console console, String team, String description) {
        command(script, console, "teama create " + team, "created");
        command(script, console, "teama description " + team + " " + description, "changed");
    }

    /** Runs {@code /team info <team>} and hands the received screen to {@code then}. */
    private static void info(GcbScript script, Console console, String team, Consumer<InfoScreen> then) {
        // The tag line is the last field printed for a team without members; the anchor line may follow it.
        command(script, console, "team info " + team, "Tag: ");
        script.waitTicks(3);
        script.step(() -> then.accept(new InfoScreen(team, console.snapshot())));
    }

    @GcbCase(value = "plugin is enabled", order = 0)
    public void pluginIsEnabled() {
        GcbAssert.isTrue(Bukkit.getPluginManager().isPluginEnabled(PLUGIN), "BetterTeams must be enabled");
        GcbAssert.notNull(Bukkit.getCommandMap().getCommand("team"), "the /team command must be registered");
        GcbAssert.notNull(Bukkit.getCommandMap().getCommand("teama"), "the /teama command must be registered");
    }

    @GcbCase(value = "a plain description is shown verbatim", order = 1, ticks = 400)
    public void plainDescription(GcbScript script) {
        Console console = new Console();
        createTeam(script, console, "gcbplain", "Just a plain team");
        info(script, console, "gcbplain", screen -> {
            GcbAssert.equals("Just a plain team", screen.description(),
                    "the description is shown as typed: " + screen.plainLines());
            Component line = screen.descriptionLine();
            GcbAssert.isFalse(hasClickEvent(line), "a plain description carries no click event: " + json(line));
            GcbAssert.isFalse(hasHoverEvent(line), "a plain description carries no hover event: " + json(line));
        });
    }

    @GcbCase(value = "the info screen keeps its prefix and template formatting", order = 2, ticks = 400)
    public void screenFormatting(GcbScript script) {
        Console console = new Console();
        createTeam(script, console, "gcbformat", "Formatted team");
        info(script, console, "gcbformat", screen -> {
            List<String> lines = screen.plainLines();
            GcbAssert.isTrue(lines.size() >= 5, "the info screen prints several lines: " + lines);
            for (String line : lines) {
                GcbAssert.isTrue(line.startsWith("[BetterTeams] "),
                        "every info line starts with the plugin prefix: <" + line + ">");
            }
            GcbAssert.isTrue(lines.stream().anyMatch(line -> line.contains("Name: gcbformat")),
                    "the screen names the team: " + lines);
            GcbAssert.isTrue(lines.stream().anyMatch(line -> line.contains("Tag: gcbformat")),
                    "the screen shows the team tag: " + lines);
            Component line = screen.descriptionLine();
            GcbAssert.equals(NamedTextColor.GOLD, styleOf(line, "Description:").colour,
                    "the Description: label keeps the template's &6 colour: " + json(line));
            GcbAssert.equals(NamedTextColor.AQUA, styleOf(line, "Formatted team").colour,
                    "the description value keeps the template's &b colour: " + json(line));
            GcbAssert.equals("Formatted team", screen.description(), "the description is shown as typed");
        });
    }

    @GcbCase(value = "a colour tag in a description still colours the text", order = 3, ticks = 400)
    public void colourTag(GcbScript script) {
        Console console = new Console();
        createTeam(script, console, "gcbcolour", "<red>hello</red> <bold>team</bold> &aok");
        info(script, console, "gcbcolour", screen -> {
            GcbAssert.equals("hello team ok", screen.description(),
                    "colour and decoration tags are applied, not shown: " + screen.plainLines());
            Component line = screen.descriptionLine();
            GcbAssert.equals(NamedTextColor.RED, styleOf(line, "hello").colour, "<red> colours hello: " + json(line));
            GcbAssert.isTrue(styleOf(line, "team").decorations.contains(TextDecoration.BOLD),
                    "<bold> decorates team: " + json(line));
            GcbAssert.equals(NamedTextColor.GREEN, styleOf(line, "ok").colour, "&a colours ok: " + json(line));
        });
    }

    @GcbCase(value = "a click tag in a description is shown as text without a click event", order = 4, ticks = 400)
    public void clickTag(GcbScript script) {
        Console console = new Console();
        createTeam(script, console, "gcbclick", CLICK_TAG + " <red>hello");
        info(script, console, "gcbclick", screen -> {
            Component line = screen.descriptionLine();
            GcbAssert.isTrue(screen.description().contains(CLICK_TAG),
                    "the click tag must appear literally in the description: " + screen.plainLines());
            GcbAssert.isFalse(hasClickEvent(line),
                    "the Description: line must not carry a click event: " + json(line));
            GcbAssert.isTrue(screen.description().endsWith("hello"),
                    "the text after the tag is still shown: " + screen.plainLines());
        });
    }

    @GcbCase(value = "a hover tag in a description is shown as text without a hover event", order = 5, ticks = 400)
    public void hoverTag(GcbScript script) {
        Console console = new Console();
        createTeam(script, console, "gcbhover", HOVER_TAG + " done");
        info(script, console, "gcbhover", screen -> {
            Component line = screen.descriptionLine();
            GcbAssert.isTrue(screen.description().contains(HOVER_TAG),
                    "the hover tag must appear literally in the description: " + screen.plainLines());
            GcbAssert.isFalse(hasHoverEvent(line),
                    "the Description: line must not carry a hover event: " + json(line));
            GcbAssert.isTrue(screen.description().endsWith("done"),
                    "the text after the tag is still shown: " + screen.plainLines());
        });
    }

    @GcbCase(value = "decoration tags and reset still format a description", order = 6, ticks = 400)
    public void decorationTags(GcbScript script) {
        Console console = new Console();
        createTeam(script, console, "gcbdecor",
                "<italic>slanted</italic> <gold><underlined>gilded</underlined> <reset>plain &lstrong");
        info(script, console, "gcbdecor", screen -> {
            GcbAssert.equals("slanted gilded plain strong", screen.description(),
                    "decoration, colour and reset tags are applied, not shown: " + screen.plainLines());
            Component line = screen.descriptionLine();
            GcbAssert.isTrue(styleOf(line, "slanted").decorations.contains(TextDecoration.ITALIC),
                    "<italic> decorates slanted: " + json(line));
            Effective gilded = styleOf(line, "gilded");
            GcbAssert.equals(NamedTextColor.GOLD, gilded.colour, "<gold> colours gilded: " + json(line));
            GcbAssert.isTrue(gilded.decorations.contains(TextDecoration.UNDERLINED),
                    "<underlined> decorates gilded: " + json(line));
            Effective plainStyle = styleOf(line, "plain");
            GcbAssert.isFalse(NamedTextColor.GOLD.equals(plainStyle.colour)
                            || plainStyle.decorations.contains(TextDecoration.ITALIC)
                            || plainStyle.decorations.contains(TextDecoration.UNDERLINED),
                    "<reset> ends the colour and decorations before plain: " + json(line));
            GcbAssert.isTrue(styleOf(line, "strong").decorations.contains(TextDecoration.BOLD),
                    "&l makes strong bold: " + json(line));
        });
    }

    @GcbCase(value = "an insertion tag in a description is shown as text", order = 7, ticks = 400)
    public void insertionTag(GcbScript script) {
        Console console = new Console();
        createTeam(script, console, "gcbinsert", INSERTION_TAG + " after");
        info(script, console, "gcbinsert", screen -> {
            Component line = screen.descriptionLine();
            GcbAssert.isTrue(screen.description().contains(INSERTION_TAG),
                    "the insertion tag must appear literally in the description: " + screen.plainLines());
            GcbAssert.isFalse(flatten(line).stream().anyMatch(node -> node.insertion() != null),
                    "the Description: line must not carry an insertion: " + json(line));
            GcbAssert.isTrue(screen.description().endsWith("after"),
                    "the text after the tag is still shown: " + screen.plainLines());
        });
    }

    @GcbCase(value = "a translatable tag in a description is shown as text", order = 8, ticks = 400)
    public void translatableTag(GcbScript script) {
        Console console = new Console();
        createTeam(script, console, "gcblang", "rock " + LANG_TAG + " end");
        info(script, console, "gcblang", screen -> {
            GcbAssert.equals("rock " + LANG_TAG + " end", screen.description(),
                    "the translatable tag must appear literally in the description: " + screen.plainLines());
            Component line = screen.descriptionLine();
            GcbAssert.isFalse(flatten(line).stream().anyMatch(node -> !(node instanceof TextComponent)),
                    "the Description: line must consist of text only: " + json(line));
        });
    }
}
