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
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;
import java.util.stream.Stream;
import org.bukkit.Bukkit;
import org.bukkit.command.Command;
import org.bukkit.command.PluginIdentifiableCommand;
import org.bukkit.event.HandlerList;
import org.bukkit.plugin.RegisteredListener;
import org.bukkit.event.player.AsyncPlayerChatEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.plugin.Plugin;
import ru.brikster.chatty.api.ChattyApi;
import ru.brikster.chatty.api.chat.Chat;

/**
 * Live-server grader for the Chatty failed-migration repair. The server starts with a v2
 * config.yml (tests/seed/Chatty/config.yml) whose advertisement ip pattern is an invalid regular
 * expression, so the migration fails while the plugin enables. Every case is player-free and
 * observes the state that enable left behind: the folders next to the plugin's data folder, the
 * server log, the event handler lists, the chat registry and the plugin's own console commands.
 * No disable/enable cycle is used (Paper closes the plugin classloader on disable).
 */
public final class ChattyFailedMigrationSuite implements GcbSuite {

    private static final String PLUGIN = "Chatty";
    private static final String BACKUP_PREFIX = "Chatty_old_";
    private static final String QUARANTINE_PREFIX = "Chatty_failed_migration_";
    private static final String RELOAD_SUCCESS = "Plugin successfully reloaded!";
    private static final String RELOAD_ERROR = "Error while reloading plugin";
    private static final String DEFAULTS_PHRASE = "started with a default configuration";
    /** A distinctive fragment of the seeded v2 file (the invalid ip pattern). */
    private static final String SEEDED_PATTERN_FRAGMENT = "\\d{1,3}[";
    /** The server's own log file, relative to the server working directory. */
    private static final Path SERVER_LOG = Path.of("logs", "latest.log");

    // --- helpers -----------------------------------------------------------------------------

    private static Plugin chatty() {
        Plugin plugin = Bukkit.getPluginManager().getPlugin(PLUGIN);
        GcbAssert.notNull(plugin, "the Chatty plugin must be loaded");
        return plugin;
    }

    private static Path dataFolder() {
        return chatty().getDataFolder().toPath().toAbsolutePath();
    }

    /** Sibling directories of the data folder whose name starts with {@code prefix}. */
    private static List<Path> siblings(String prefix) throws IOException {
        Path parent = dataFolder().getParent();
        List<Path> found = new ArrayList<>();
        try (Stream<Path> entries = Files.list(parent)) {
            entries.filter(Files::isDirectory)
                    .filter(p -> p.getFileName().toString().startsWith(prefix))
                    .sorted()
                    .forEach(found::add);
        }
        return found;
    }

    private static List<String> names(List<Path> paths) {
        List<String> names = new ArrayList<>();
        for (Path path : paths) {
            names.add(path.getFileName().toString());
        }
        return names;
    }

    private static String read(Path file) throws IOException {
        return new String(Files.readAllBytes(file), StandardCharsets.UTF_8);
    }

    private static String serverLog() throws IOException {
        GcbAssert.isTrue(Files.isRegularFile(SERVER_LOG),
                "the server log must exist at " + SERVER_LOG.toAbsolutePath());
        return read(SERVER_LOG);
    }

    /** Lines of the server log logged at WARN or ERROR that contain {@code needle}. */
    private static List<String> warningsContaining(String log, String needle) {
        Pattern level = Pattern.compile("/(WARN|ERROR)\\]: ");
        List<String> hits = new ArrayList<>();
        for (String line : log.split("\\R")) {
            if (line.contains(needle) && level.matcher(line).find()) {
                hits.add(line);
            }
        }
        return hits;
    }

    /** Simple names of the listeners registered on {@code handlers} that belong to Chatty. */
    private static List<String> chattyListeners(HandlerList handlers) {
        List<String> owners = new ArrayList<>();
        for (RegisteredListener registered : handlers.getRegisteredListeners()) {
            if (PLUGIN.equals(registered.getPlugin().getName())) {
                owners.add(registered.getListener().getClass().getSimpleName());
            }
        }
        return owners;
    }

    private static void assertListenersRegistered(String context) {
        List<String> chat = chattyListeners(AsyncPlayerChatEvent.getHandlerList());
        GcbAssert.isFalse(chat.isEmpty(),
                "Chatty must have a listener registered for AsyncPlayerChatEvent " + context);
        List<String> join = chattyListeners(PlayerJoinEvent.getHandlerList());
        GcbAssert.isFalse(join.isEmpty(),
                "Chatty must have a listener registered for PlayerJoinEvent " + context);
    }

    private static void assertShippedChats(String context) {
        Map<String, Chat> chats = ChattyApi.instance().getChats();
        GcbAssert.isTrue(chats.containsKey("local") && chats.containsKey("global"),
                "the shipped local and global chats must be registered " + context + ", got " + chats.keySet());
    }

    private static void assertOwnedByChatty(String name, String context) {
        Command command = Bukkit.getCommandMap().getCommand(name);
        GcbAssert.notNull(command, "/" + name + " must be registered in the server command map " + context);
        GcbAssert.isTrue(command instanceof PluginIdentifiableCommand,
                "/" + name + " must be a plugin command " + context + ", got " + command.getClass().getName());
        Plugin owner = ((PluginIdentifiableCommand) command).getPlugin();
        GcbAssert.isTrue(owner != null && PLUGIN.equals(owner.getName()),
                "/" + name + " must be owned by Chatty " + context + ", got " + (owner == null ? null : owner.getName()));
    }

    // --- cases -------------------------------------------------------------------------------

    @GcbCase(value = "plugin is enabled", order = 0)
    public void pluginIsEnabled() {
        GcbAssert.isTrue(Bukkit.getPluginManager().isPluginEnabled(PLUGIN), "Chatty must be enabled");
        assertOwnedByChatty("chatty", "after the plugin enabled");
        GcbAssert.notNull(ChattyApi.instance(), "ChattyApi must be initialised");
    }

    @GcbCase(value = "legacy configuration is moved aside before migrating", order = 1)
    public void legacyFolderIsMovedAside() throws IOException {
        List<Path> backups = siblings(BACKUP_PREFIX);
        GcbAssert.equals(1, backups.size(),
                "exactly one " + BACKUP_PREFIX + "<timestamp> folder must sit next to the data folder, got " + names(backups));
        Path legacy = backups.get(0).resolve("config.yml");
        GcbAssert.isTrue(Files.isRegularFile(legacy),
                "the backup folder must keep the v2 config.yml, missing " + legacy.getFileName());
        String legacyText = read(legacy);
        GcbAssert.isTrue(legacyText.contains(SEEDED_PATTERN_FRAGMENT),
                "the backup folder's config.yml must be the seeded v2 file (its ip pattern is missing)");
        GcbAssert.isTrue(legacyText.contains("length: 0") && legacyText.contains("percent: 150"),
                "the backup folder's config.yml must keep the v2 caps values as written (length 0, percent 150)");
        GcbAssert.isFalse(Files.exists(dataFolder().resolve("config.yml")),
                "no config.yml may be left in the data folder after the legacy folder was moved aside");
    }

    @GcbCase(value = "info command answers from the console", order = 2)
    public void infoCommandAnswers() {
        RecordingSender sender = GcbSenders.recording();
        GcbCommands.dispatch(sender, "chatty");
        List<String> messages = sender.messages();
        GcbAssert.isTrue(messages.stream().anyMatch(m -> m.contains("Chatty") && m.contains("reload")),
                "/chatty must answer with the plugin summary, got " + messages);
    }

    @GcbCase(value = "chat pipeline is live after a failed migration", order = 3)
    public void chatPipelineIsLive() {
        assertListenersRegistered("after the failed migration (the enabled plugin must process events)");
        assertShippedChats("after the failed migration");
    }

    @GcbCase(value = "failed migration is quarantined and reported", order = 4)
    public void failedMigrationIsQuarantinedAndReported() throws IOException {
        List<Path> quarantines = siblings(QUARANTINE_PREFIX);
        GcbAssert.equals(1, quarantines.size(),
                "exactly one " + QUARANTINE_PREFIX + "<timestamp> folder must sit next to the data folder, got "
                        + names(quarantines));
        Path quarantine = quarantines.get(0);
        Path quarantinedModeration = quarantine.resolve("moderation.yml");
        GcbAssert.isTrue(Files.isRegularFile(quarantinedModeration),
                "the quarantine folder must hold the half-migrated files, missing moderation.yml in "
                        + quarantine.getFileName());
        GcbAssert.isTrue(read(quarantinedModeration).contains(SEEDED_PATTERN_FRAGMENT),
                "the quarantined moderation.yml must be the migrated file carrying the invalid ip pattern");
        Path regenerated = dataFolder().resolve("moderation.yml");
        GcbAssert.isTrue(Files.isRegularFile(regenerated),
                "the data folder must hold a regenerated default moderation.yml");
        GcbAssert.isFalse(read(regenerated).contains(SEEDED_PATTERN_FRAGMENT),
                "the regenerated moderation.yml must not carry the invalid ip pattern");

        String log = serverLog();
        GcbAssert.isFalse(warningsContaining(log, BACKUP_PREFIX).isEmpty(),
                "a WARNING or SEVERE log line must name the " + BACKUP_PREFIX + "<timestamp> backup folder");
        String quarantineName = quarantine.getFileName().toString();
        GcbAssert.isFalse(warningsContaining(log, quarantineName).isEmpty(),
                "a WARNING or SEVERE log line must name the quarantine folder " + quarantineName);
        GcbAssert.isFalse(warningsContaining(log, DEFAULTS_PHRASE).isEmpty(),
                "a WARNING or SEVERE log line must say the plugin \"" + DEFAULTS_PHRASE + "\"");
    }

    @GcbCase(value = "chatty reload works after a failed migration", order = 6)
    public void reloadWorks() {
        RecordingSender sender = GcbSenders.recording();
        GcbCommands.dispatch(sender, "chatty reload");
        List<String> messages = sender.messages();
        GcbAssert.isTrue(messages.stream().anyMatch(m -> m.contains(RELOAD_SUCCESS)),
                "/chatty reload must answer \"" + RELOAD_SUCCESS + "\" after the failed migration, got " + messages);
        GcbAssert.isFalse(messages.stream().anyMatch(m -> m.contains(RELOAD_ERROR)),
                "/chatty reload must not report an error after the failed migration, got " + messages);
        assertShippedChats("after the reload");
        assertListenersRegistered("after the reload");
    }

    @GcbCase(value = "migrated caps limits are clamped to the v3 range", order = 5)
    public void migratedCapsAreClamped() throws IOException {
        List<Path> quarantines = siblings(QUARANTINE_PREFIX);
        GcbAssert.equals(1, quarantines.size(),
                "exactly one " + QUARANTINE_PREFIX + "<timestamp> folder must hold the migrated files, got "
                        + names(quarantines));
        Path migrated = quarantines.get(0).resolve("moderation.yml");
        GcbAssert.isTrue(Files.isRegularFile(migrated), "the migrated moderation.yml must be in the quarantine folder");
        org.bukkit.configuration.file.YamlConfiguration yaml =
                org.bukkit.configuration.file.YamlConfiguration.loadConfiguration(migrated.toFile());
        GcbAssert.isTrue(yaml.isInt("caps.length") && yaml.isInt("caps.percent"),
                "the migrated moderation.yml must carry caps.length and caps.percent, got " + yaml.getValues(true).keySet());
        GcbAssert.equals(1, yaml.getInt("caps.length"),
                "the v2 caps length 0 must be migrated as the smallest length v3 accepts (1)");
        GcbAssert.equals(100, yaml.getInt("caps.percent"),
                "the v2 caps percent 150 must be migrated as the largest percent v3 accepts (100)");
        String log = serverLog();
        GcbAssert.isTrue(log.contains("caps.length") && log.contains("caps.percent"),
                "the migration notes in the server log must name caps.length and caps.percent as adjusted");
    }
}
