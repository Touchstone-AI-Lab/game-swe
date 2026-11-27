import io.gamecodebench.harness.GcbAssert;
import io.gamecodebench.harness.GcbCase;
import io.gamecodebench.harness.GcbCommands;
import io.gamecodebench.harness.GcbSenders;
import io.gamecodebench.harness.GcbSuite;
import io.gamecodebench.harness.RecordingSender;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import org.bukkit.Bukkit;
import org.bukkit.command.Command;
import org.bukkit.command.PluginIdentifiableCommand;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.plugin.Plugin;
import ru.brikster.chatty.api.ChattyApi;
import ru.brikster.chatty.api.chat.Chat;
import ru.brikster.chatty.shaded.net.kyori.adventure.text.Component;
import ru.brikster.chatty.shaded.net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;

/**
 * Live-server grader for the Chatty v2-migration spy-format repair. The server starts with a
 * legacy v2 config.yml (tests/seed/Chatty/config.yml) that declares chats but has no "spy"
 * section, so Chatty migrates it on its first enable. Every case is player-free: the plugin's
 * public API ({@link ChattyApi}), the chats.yml the migration wrote into the plugin's data
 * folder, and console commands dispatched from a recording sender are the only observation
 * points. Later configurations are written into the data folder and applied through the
 * plugin's own /chatty reload.
 */
public final class ChattyV2SpyFormatSuite implements GcbSuite {

    private static final String PLUGIN = "Chatty";
    private static final String RELOAD_SUCCESS = "Plugin successfully reloaded!";
    /** The reload success message of every bundled language, as shipped in lang/<language>.yml. */
    private static final Map<String, String> RELOAD_SUCCESS_BY_LANGUAGE = Map.of(
            "en-US", RELOAD_SUCCESS,
            "ru-RU", "Плагин успешно перезагружен!",
            "de-DE", "Plugin erfolgreich neu geladen!",
            "es-ES", "¡Plugin recargado correctamente!",
            "zh-CN", "插件重载成功！");
    private static final String RELOAD_ERROR = "Error while reloading plugin";

    // Declared by tests/seed/Chatty/config.yml (Chatty v2 layout, no top-level "spy" section).
    private static final String LOCAL_FORMAT = "&e[GCB Local] &r{player}: {message}";
    private static final String GLOBAL_FORMAT = "&a[GCB Global] &r{player}: {message}";
    private static final String STAFF_CHAT = "gcbstaff";
    private static final String RETIRED_CHAT = "gcbretired";
    // Chatty v2's default spy template; a v2 config without spy.format.chat used exactly this.
    private static final String V2_DEFAULT_SPY_TEMPLATE = "&6[Spy] &r{format}";

    // Written by the suite through chats.yml + /chatty reload.
    private static final String LOCAL_WATCH = "&c[Watch local] &r{player}: {message}";
    private static final String GLOBAL_WATCH = "&c[Watch global] &r{player}: {message}";
    private static final String MINIMAL_CHAT = "gcbminimal";
    private static final String MINIMAL_FORMAT = "&b[GCB Minimal] &r{player}: {message}";

    /** chats.yml with every chat fully specified, including an explicit spy format. */
    private static String explicitChatsYaml() {
        return "chats:\n"
                + "  local:\n"
                + "    display-name: Local\n"
                + "    format: '" + LOCAL_FORMAT + "'\n"
                + "    symbol: ''\n"
                + "    range: 100\n"
                + "    spy:\n"
                + "      enable: true\n"
                + "      format: '" + LOCAL_WATCH + "'\n"
                + "  global:\n"
                + "    display-name: Global\n"
                + "    format: '" + GLOBAL_FORMAT + "'\n"
                + "    symbol: '!'\n"
                + "    range: -1\n"
                + "    spy:\n"
                + "      enable: true\n"
                + "      format: '" + GLOBAL_WATCH + "'\n"
                + "  " + STAFF_CHAT + ":\n"
                + "    display-name: Staff\n"
                + "    format: '<{player}>: {message}'\n"
                + "    symbol: ''\n"
                + "    range: -2\n"
                + "    spy:\n"
                + "      enable: false\n"
                + "      format: ''\n";
    }

    /** chats.yml where one chat's spy block declares only "enable" (no format key at all). */
    private static String minimalSpyChatsYaml() {
        return "chats:\n"
                + "  local:\n"
                + "    display-name: Local\n"
                + "    format: '" + LOCAL_FORMAT + "'\n"
                + "    symbol: ''\n"
                + "    range: 100\n"
                + "    spy:\n"
                + "      enable: true\n"
                + "      format: '" + LOCAL_WATCH + "'\n"
                + "  " + MINIMAL_CHAT + ":\n"
                + "    display-name: Minimal\n"
                + "    format: '" + MINIMAL_FORMAT + "'\n"
                + "    symbol: '#'\n"
                + "    range: -2\n"
                + "    spy:\n"
                + "      enable: true\n";
    }

    // --- helpers -----------------------------------------------------------------------------

    private static Plugin chatty() {
        Plugin plugin = Bukkit.getPluginManager().getPlugin(PLUGIN);
        GcbAssert.notNull(plugin, "the Chatty plugin must be loaded");
        return plugin;
    }

    private static Path chatsFile() {
        return chatty().getDataFolder().toPath().resolve("chats.yml");
    }

    private static void writeChats(String content) throws IOException {
        Path file = chatsFile();
        Files.createDirectories(file.getParent());
        Files.writeString(file, content, StandardCharsets.UTF_8);
    }

    private static YamlConfiguration readChats() {
        Path file = chatsFile();
        GcbAssert.isTrue(Files.isRegularFile(file), "chats.yml must exist in the plugin's data folder");
        return YamlConfiguration.loadConfiguration(file.toFile());
    }

    private static Map<String, Chat> chats() {
        Map<String, Chat> chats = ChattyApi.instance().getChats();
        GcbAssert.notNull(chats, "ChattyApi must expose the chat registry");
        return chats;
    }

    private static Chat chat(String id, String context) {
        Chat chat = chats().get(id);
        GcbAssert.notNull(chat, "chat \"" + id + "\" must be registered " + context + ", got " + chats().keySet());
        return chat;
    }

    private static String plain(Component component) {
        return PlainTextComponentSerializer.plainText().serialize(component);
    }

    private static List<String> reloadReplies() {
        RecordingSender sender = GcbSenders.recording();
        GcbCommands.dispatch(sender, "chatty reload");
        return sender.messages();
    }

    /** Reloads and requires the success message of any bundled language and no error. */
    private static void reload(String context) {
        List<String> messages = reloadReplies();
        GcbAssert.isFalse(messages.stream().anyMatch(m -> m.contains(RELOAD_ERROR)),
                "/chatty reload must not report an error " + context + ", got " + messages);
        GcbAssert.isTrue(messages.stream().anyMatch(m -> RELOAD_SUCCESS_BY_LANGUAGE.values().stream().anyMatch(m::contains)),
                "/chatty reload must answer its success message " + context + ", got " + messages);
    }

    /** Requires the success message of {@code language} among the replies. */
    private static void assertRepliedIn(List<String> messages, String language, String context) {
        String expected = RELOAD_SUCCESS_BY_LANGUAGE.get(language);
        GcbAssert.isFalse(messages.stream().anyMatch(m -> m.contains(RELOAD_ERROR)),
                "/chatty reload must not report an error " + context + ", got " + messages);
        GcbAssert.isTrue(messages.stream().anyMatch(m -> m.contains(expected)),
                "/chatty reload must answer in " + language + " (\"" + expected + "\") " + context + ", got " + messages);
    }

    private static Path settingsFile() {
        return chatty().getDataFolder().toPath().resolve("settings.yml");
    }

    /** Rewrites the top-level language key of settings.yml, keeping the rest of the file. */
    private static void setLanguage(String language) throws IOException {
        Path file = settingsFile();
        String content = Files.isRegularFile(file) ? Files.readString(file, StandardCharsets.UTF_8) : "";
        java.util.regex.Pattern key = java.util.regex.Pattern.compile("(?m)^language:[^\\n]*$");
        String line = "language: '" + language + "'";
        content = key.matcher(content).find()
                ? key.matcher(content).replaceAll(line)
                : content + (content.isEmpty() || content.endsWith("\n") ? "" : "\n") + line + "\n";
        Files.writeString(file, content, StandardCharsets.UTF_8);
    }

    /** Captures WARNING-or-higher records from the root, server and plugin loggers. */
    private static final class WarningCapture extends java.util.logging.Handler {
        private final List<String> warnings = new java.util.ArrayList<>();
        private final java.util.logging.SimpleFormatter formatter = new java.util.logging.SimpleFormatter();

        @Override
        public void publish(java.util.logging.LogRecord record) {
            if (record == null || record.getLevel().intValue() < java.util.logging.Level.WARNING.intValue()) {
                return;
            }
            String text;
            try {
                text = formatter.formatMessage(record);
            } catch (RuntimeException failure) {
                text = String.valueOf(record.getMessage());
            }
            synchronized (warnings) {
                warnings.add(text);
            }
        }

        List<String> warnings() {
            synchronized (warnings) {
                return List.copyOf(warnings);
            }
        }

        @Override
        public void flush() {
        }

        @Override
        public void close() {
        }
    }

    private static String spyFormatInFile(YamlConfiguration yaml, String chatId) {
        return yaml.getString("chats." + chatId + ".spy.format");
    }

    private static void assertSpyFormatWritten(YamlConfiguration yaml, String chatId, String expected) {
        String actual = spyFormatInFile(yaml, chatId);
        GcbAssert.isTrue(actual != null && !actual.isBlank(),
                "chats.yml must carry a non-blank spy.format for the migrated chat \"" + chatId + "\", got " + actual);
        if (expected != null) {
            GcbAssert.equals(expected, actual, "spy.format written for chat \"" + chatId + "\"");
        } else {
            GcbAssert.isTrue(actual.contains("[Spy]"),
                    "spy.format for chat \"" + chatId + "\" must be built from the v2 default template, got " + actual);
            GcbAssert.isFalse(actual.contains("{format}"),
                    "spy.format for chat \"" + chatId + "\" must have {format} replaced, got " + actual);
        }
    }

    // --- cases -------------------------------------------------------------------------------

    @GcbCase(value = "plugin is enabled", order = 0)
    public void pluginIsEnabled() {
        GcbAssert.isTrue(Bukkit.getPluginManager().isPluginEnabled(PLUGIN), "Chatty must be enabled");
        Command command = Bukkit.getCommandMap().getCommand("chatty");
        GcbAssert.notNull(command, "/chatty must be registered in the server command map");
        GcbAssert.isTrue(command instanceof PluginIdentifiableCommand
                        && PLUGIN.equals(((PluginIdentifiableCommand) command).getPlugin().getName()),
                "/chatty must be owned by Chatty");
        GcbAssert.notNull(ChattyApi.instance(), "ChattyApi must be available");
    }

    @GcbCase(value = "chatty command answers the console", order = 1)
    public void chattyCommandAnswers() {
        RecordingSender sender = GcbSenders.recording();
        boolean dispatched = GcbCommands.dispatch(sender, "chatty");
        GcbAssert.isTrue(dispatched, "/chatty must be dispatched to the plugin's command");
        List<String> messages = sender.messages();
        GcbAssert.isTrue(messages.stream().anyMatch(m -> m.contains("Chatty")),
                "/chatty must answer with the plugin's info message, got " + messages);
        GcbAssert.isTrue(messages.stream().anyMatch(m -> m.contains("/chatty reload")),
                "/chatty must mention /chatty reload, got " + messages);
    }

    @GcbCase(value = "chats from the legacy config are registered at start-up", order = 2)
    public void legacyChatsAreRegistered() {
        Map<String, Chat> chats = chats();
        String context = "after the v2 config.yml was migrated at start-up";
        Chat local = chat("local", context);
        Chat global = chat("global", context);
        Chat staff = chat(STAFF_CHAT, context);
        GcbAssert.isFalse(chats.containsKey(RETIRED_CHAT),
                "the chat disabled in v2 must not be migrated, got " + chats.keySet());
        GcbAssert.equals(100, local.getRange(), "range of the migrated local chat");
        GcbAssert.equals("!", global.getSymbol(), "symbol of the migrated global chat");
        GcbAssert.equals("Staff", staff.getDisplayName(), "display name of the migrated staff chat");
        GcbAssert.isTrue(staff.isPermissionRequired(), "the staff chat must keep its v2 permission flag");
        GcbAssert.isTrue(local.isEnableSpy() && global.isEnableSpy() && staff.isEnableSpy(),
                "spy must be enabled on every migrated chat (the v2 default)");
        GcbAssert.isTrue(plain(local.getFormat()).contains("[GCB Local]"),
                "the migrated local chat must keep its v2 format, got " + plain(local.getFormat()));
    }

    @GcbCase(value = "migrated chats carry a spy format", order = 3)
    public void migratedChatsCarrySpyFormat() {
        YamlConfiguration yaml = readChats();
        assertSpyFormatWritten(yaml, "local", V2_DEFAULT_SPY_TEMPLATE.replace("{format}", LOCAL_FORMAT));
        assertSpyFormatWritten(yaml, "global", V2_DEFAULT_SPY_TEMPLATE.replace("{format}", GLOBAL_FORMAT));
        assertSpyFormatWritten(yaml, STAFF_CHAT, null);
        String context = "after the v2 config.yml was migrated at start-up";
        Chat local = chat("local", context);
        GcbAssert.notNull(local.getSpyFormat(), "the migrated local chat must expose a spy format");
        String rendered = plain(local.getSpyFormat());
        GcbAssert.isTrue(rendered.contains("[Spy]") && rendered.contains("[GCB Local]"),
                "the local chat's spy format must render the v2 default template around its own format, got " + rendered);
        Chat staff = chat(STAFF_CHAT, context);
        GcbAssert.notNull(staff.getSpyFormat(), "the migrated staff chat must expose a spy format");
        GcbAssert.isFalse(plain(staff.getSpyFormat()).isBlank(),
                "the staff chat (no v2 format) must still get a non-blank spy format");
    }

    @GcbCase(value = "chatty reload succeeds on the migrated configuration", order = 4)
    public void reloadOnMigratedConfiguration() {
        reload("on the configuration migrated from v2");
        String context = "after reloading the migrated configuration";
        chat("local", context);
        Chat global = chat("global", context);
        chat(STAFF_CHAT, context);
        String rendered = plain(global.getSpyFormat());
        GcbAssert.isTrue(rendered.contains("[Spy]") && rendered.contains("[GCB Global]"),
                "the global chat's spy format must survive the reload, got " + rendered);
    }

    @GcbCase(value = "explicit spy formats survive a reload", order = 6)
    public void explicitSpyFormatsSurviveReload() throws IOException {
        writeChats(explicitChatsYaml());
        reload("after writing a chats.yml with explicit spy formats");
        String context = "after reloading a chats.yml with explicit spy formats";
        Chat local = chat("local", context);
        Chat global = chat("global", context);
        Chat staff = chat(STAFF_CHAT, context);
        GcbAssert.isTrue(plain(local.getSpyFormat()).contains("[Watch local]"),
                "the explicit local spy format must be used, got " + plain(local.getSpyFormat()));
        GcbAssert.isTrue(plain(global.getSpyFormat()).contains("[Watch global]"),
                "the explicit global spy format must be used, got " + plain(global.getSpyFormat()));
        GcbAssert.isFalse(staff.isEnableSpy(), "spy must stay disabled where chats.yml disables it");
        YamlConfiguration yaml = readChats();
        GcbAssert.equals(LOCAL_WATCH, spyFormatInFile(yaml, "local"), "explicit local spy.format kept in chats.yml");
        GcbAssert.equals(GLOBAL_WATCH, spyFormatInFile(yaml, "global"), "explicit global spy.format kept in chats.yml");
    }

    @GcbCase(value = "spy section with only enable reloads", order = 10)
    public void minimalSpySectionReloads() throws IOException {
        writeChats(minimalSpyChatsYaml());
        reload("after writing a chats.yml whose " + MINIMAL_CHAT + " chat has a spy block with only enable");
        String context = "after reloading a chats.yml with a spy block that only declares enable";
        Chat minimal = chat(MINIMAL_CHAT, context);
        GcbAssert.isTrue(minimal.isEnableSpy(), "spy must be enabled on " + MINIMAL_CHAT);
        GcbAssert.notNull(minimal.getSpyFormat(), MINIMAL_CHAT + " must expose a (possibly empty) spy format");
        GcbAssert.isTrue(plain(minimal.getFormat()).contains("[GCB Minimal]"),
                "the minimal chat must keep its own format, got " + plain(minimal.getFormat()));
        chat("local", context);
    }

    @GcbCase(value = "the v2 locale is migrated to the v3 language", order = 5)
    public void v2LocaleIsMigrated() {
        Path file = settingsFile();
        GcbAssert.isTrue(Files.isRegularFile(file), "settings.yml must exist in the plugin's data folder");
        YamlConfiguration settings = YamlConfiguration.loadConfiguration(file.toFile());
        GcbAssert.equals("ru-RU", settings.getString("language"),
                "the v2 general.locale ru must be migrated to language ru-RU in settings.yml");
        assertRepliedIn(reloadReplies(), "ru-RU", "on the configuration migrated from a Russian v2 server");
    }

    @GcbCase(value = "a supported language tag in settings.yml is applied", order = 7)
    public void supportedLanguageIsApplied() throws IOException {
        setLanguage("de-DE");
        assertRepliedIn(reloadReplies(), "de-DE", "after settings.yml was set to language de-DE");
    }

    @GcbCase(value = "a v2 spelling of a language is accepted", order = 8)
    public void v2SpellingIsAccepted() throws IOException {
        setLanguage("zh_CN");
        assertRepliedIn(reloadReplies(), "zh-CN", "after settings.yml was set to language zh_CN");
    }

    @GcbCase(value = "an unsupported language is reported and falls back to English", order = 9)
    public void unsupportedLanguageIsReported() throws IOException {
        setLanguage("kl-GL");
        WarningCapture capture = new WarningCapture();
        List<java.util.logging.Logger> loggers = List.of(java.util.logging.Logger.getLogger(""),
                Bukkit.getLogger(), chatty().getLogger());
        for (java.util.logging.Logger logger : loggers) {
            logger.addHandler(capture);
        }
        List<String> replies;
        try {
            replies = reloadReplies();
        } finally {
            for (java.util.logging.Logger logger : loggers) {
                logger.removeHandler(capture);
            }
        }
        assertRepliedIn(replies, "en-US", "after settings.yml was set to the unsupported language kl-GL");
        List<String> warnings = capture.warnings();
        GcbAssert.isTrue(warnings.stream().anyMatch(w -> w.contains("kl-GL")),
                "a WARNING-or-higher record must name the unsupported language kl-GL, got " + warnings);
    }
}
