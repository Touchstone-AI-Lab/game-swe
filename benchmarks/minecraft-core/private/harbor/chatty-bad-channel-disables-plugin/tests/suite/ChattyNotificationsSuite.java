import io.gamecodebench.harness.GcbAssert;
import io.gamecodebench.harness.GcbCase;
import io.gamecodebench.harness.GcbCommands;
import io.gamecodebench.harness.GcbScript;
import io.gamecodebench.harness.GcbSenders;
import io.gamecodebench.harness.GcbSuite;
import io.gamecodebench.harness.RecordingSender;
import java.io.IOException;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.List;
import java.util.logging.Handler;
import java.util.logging.Level;
import java.util.logging.LogRecord;
import java.util.logging.Logger;
import java.util.logging.SimpleFormatter;
import org.bukkit.Bukkit;
import org.bukkit.event.HandlerList;
import org.bukkit.event.player.AsyncPlayerChatEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.plugin.RegisteredListener;
import org.bukkit.plugin.Plugin;
import ru.brikster.chatty.api.ChattyApi;
import ru.brikster.chatty.notification.Notification;
import ru.brikster.chatty.notification.NotificationTicker;
import ru.brikster.chatty.shaded.com.google.inject.Injector;

/**
 * Live-server grader for the Chatty notification-channel repair: one channel that cannot be
 * built must be skipped and named, not take the plugin down. Every case is player-free; the
 * configuration under test is written into the plugin's data folder and picked up through the
 * plugin's own reload command (Paper closes a plugin's classloader on disable, so a
 * disable/enable cycle cannot exercise the start-up path on a live server).
 */
public final class ChattyNotificationsSuite implements GcbSuite {

    private static final String PLUGIN = "Chatty";
    private static final String RELOAD_SUCCESS = "Plugin successfully reloaded!";
    private static final String RELOAD_ERROR = "Error while reloading plugin";
    private static final String BROKEN = "gcb_broken";
    private static final String HEALTHY = "gcb_healthy";
    private static final String EDGE = "gcb_edge";
    private static final String SHORT = "gcb_short";
    private static final String FIRST_BAD = "gcb_bad_first";
    private static final String LAST_BAD = "gcb_bad_last";
    private static final String MIDDLE = "gcb_middle";
    private static final String TICKING = "gcb_ticking";

    /** An action bar channel whose stay exceeds its period, followed by a valid one. */
    private static final String BROKEN_FILE = ""
            + "actionbar:\n"
            + "  enable: true\n"
            + "  lists:\n"
            + "    default:\n"
            + "      period: 60\n"
            + "      stay: 30\n"
            + "    " + BROKEN + ":\n"
            + "      period: 5\n"
            + "      stay: 10\n"
            + "    " + HEALTHY + ":\n"
            + "      period: 7\n"
            + "      stay: 3\n"
            + "chat:\n"
            + "  enable: true\n"
            + "  lists:\n"
            + "    default:\n"
            + "      period: 60\n"
            + "    " + TICKING + ":\n"
            + "      period: 600\n";

    /** Two offending channels, first and last in their list, around valid ones. */
    private static final String TWO_BAD_FILE = ""
            + "actionbar:\n"
            + "  enable: true\n"
            + "  lists:\n"
            + "    " + FIRST_BAD + ":\n"
            + "      period: 3\n"
            + "      stay: 4\n"
            + "    " + MIDDLE + ":\n"
            + "      period: 12\n"
            + "      stay: 12\n"
            + "    default:\n"
            + "      period: 60\n"
            + "      stay: 30\n"
            + "    " + LAST_BAD + ":\n"
            + "      period: 20\n"
            + "      stay: 45\n";

    /** Only valid channels, one of them at the boundary (stay equal to period). */
    private static final String VALID_FILE = ""
            + "actionbar:\n"
            + "  enable: true\n"
            + "  lists:\n"
            + "    default:\n"
            + "      period: 60\n"
            + "      stay: 60\n"
            + "    " + EDGE + ":\n"
            + "      period: 7\n"
            + "      stay: 7\n"
            + "    " + SHORT + ":\n"
            + "      period: 9\n"
            + "      stay: 2\n"
            + "chat:\n"
            + "  enable: true\n"
            + "  lists:\n"
            + "    default:\n"
            + "      period: 60\n"
            + "    " + TICKING + ":\n"
            + "      period: 600\n";

    // --- helpers -----------------------------------------------------------------------------

    private static Plugin chatty() {
        Plugin plugin = Bukkit.getPluginManager().getPlugin(PLUGIN);
        GcbAssert.notNull(plugin, "the Chatty plugin must be loaded");
        return plugin;
    }

    private static Path notificationsFile() {
        return chatty().getDataFolder().toPath().resolve("notifications.yml");
    }

    private static void writeNotifications(String content) throws IOException {
        Path file = notificationsFile();
        Files.createDirectories(file.getParent());
        Files.writeString(file, content, StandardCharsets.UTF_8);
    }

    /** Removing the file makes the plugin regenerate its shipped defaults on the next load. */
    private static void removeNotifications() throws IOException {
        Files.deleteIfExists(notificationsFile());
    }

    private static RecordingSender reload() {
        RecordingSender sender = GcbSenders.recording();
        GcbCommands.dispatch(sender, "chatty reload");
        return sender;
    }

    private static void assertReloadSucceeded(RecordingSender sender, String context) {
        List<String> messages = sender.messages();
        GcbAssert.isTrue(messages.stream().anyMatch(m -> m.contains(RELOAD_SUCCESS)),
                "/chatty reload must answer \"" + RELOAD_SUCCESS + "\" " + context + ", got " + messages);
        GcbAssert.isFalse(messages.stream().anyMatch(m -> m.contains(RELOAD_ERROR)),
                "/chatty reload must not report an error " + context + ", got " + messages);
    }

    private static Injector injector() throws IllegalAccessException {
        Plugin plugin = chatty();
        for (Class<?> type = plugin.getClass(); type != null; type = type.getSuperclass()) {
            for (Field field : type.getDeclaredFields()) {
                if (Injector.class.isAssignableFrom(field.getType())) {
                    field.setAccessible(true);
                    Object value = field.get(plugin);
                    GcbAssert.notNull(value, "Chatty must hold a Guice injector after initialising");
                    return (Injector) value;
                }
            }
        }
        GcbAssert.fail("Chatty has no Guice injector field");
        return null;
    }

    /** Ids of every notification currently registered with the plugin's NotificationTicker. */
    private static List<String> channelIds() throws IllegalAccessException {
        NotificationTicker ticker = injector().getInstance(NotificationTicker.class);
        GcbAssert.notNull(ticker, "the NotificationTicker must be available from the injector");
        List<String> ids = new ArrayList<>();
        for (Class<?> type = ticker.getClass(); type != null; type = type.getSuperclass()) {
            for (Field field : type.getDeclaredFields()) {
                if (!Collection.class.isAssignableFrom(field.getType())) {
                    continue;
                }
                field.setAccessible(true);
                Object value = field.get(ticker);
                if (!(value instanceof Collection<?> items)) {
                    continue;
                }
                for (Object item : items) {
                    if (item instanceof Notification notification) {
                        ids.add(idOf(notification));
                    }
                }
            }
        }
        return ids;
    }

    private static String idOf(Notification notification) throws IllegalAccessException {
        for (Class<?> type = notification.getClass(); type != null && type != Object.class;
                type = type.getSuperclass()) {
            try {
                Field field = type.getDeclaredField("name");
                field.setAccessible(true);
                Object value = field.get(notification);
                if (value instanceof String id) {
                    return id;
                }
            } catch (NoSuchFieldException ignored) {
                // keep looking up the hierarchy
            }
        }
        return notification.getClass().getSimpleName();
    }

    /** The registered notification with the given id, or null. */
    private static Notification notification(String id) throws IllegalAccessException {
        NotificationTicker ticker = injector().getInstance(NotificationTicker.class);
        for (Class<?> type = ticker.getClass(); type != null; type = type.getSuperclass()) {
            for (Field field : type.getDeclaredFields()) {
                if (!Collection.class.isAssignableFrom(field.getType())) {
                    continue;
                }
                field.setAccessible(true);
                if (field.get(ticker) instanceof Collection<?> items) {
                    for (Object item : items) {
                        if (item instanceof Notification candidate && id.equals(idOf(candidate))) {
                            return candidate;
                        }
                    }
                }
            }
        }
        return null;
    }

    /** The tick counter every notification inherits from {@code Notification}. */
    private static int ticks(Notification notification) throws ReflectiveOperationException {
        Field field = Notification.class.getDeclaredField("tick");
        field.setAccessible(true);
        return field.getInt(notification);
    }

    private static boolean chattyListens(HandlerList handlers) {
        Plugin plugin = chatty();
        for (RegisteredListener listener : handlers.getRegisteredListeners()) {
            if (listener.getPlugin() == plugin) {
                return true;
            }
        }
        return false;
    }

    private static boolean chattyHandlesChat() {
        return chattyListens(io.papermc.paper.event.player.AsyncChatEvent.getHandlerList())
                || chattyListens(AsyncPlayerChatEvent.getHandlerList());
    }

    /** Runs a reload while capturing WARNING-or-higher log records from every relevant logger. */
    private static List<String> reloadCapturingWarnings(RecordingSender[] senderOut) {
        WarningCapture capture = new WarningCapture();
        List<Logger> loggers = capturedLoggers();
        for (Logger logger : loggers) {
            logger.addHandler(capture);
        }
        try {
            senderOut[0] = reload();
        } finally {
            for (Logger logger : loggers) {
                logger.removeHandler(capture);
            }
        }
        return capture.warnings();
    }

    private static int count(List<String> ids, String id) {
        return Collections.frequency(ids, id);
    }

    /** Captures WARNING-or-higher records from every java.util.logging logger. */
    private static final class WarningCapture extends Handler {
        private final List<String> warnings = new ArrayList<>();
        private final SimpleFormatter formatter = new SimpleFormatter();

        @Override
        public void publish(LogRecord record) {
            if (record == null || record.getLevel().intValue() < Level.WARNING.intValue()) {
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

    private static List<Logger> capturedLoggers() {
        List<Logger> loggers = new ArrayList<>();
        loggers.add(Logger.getLogger(""));
        loggers.add(Bukkit.getLogger());
        loggers.add(chatty().getLogger());
        return loggers;
    }

    // --- cases -------------------------------------------------------------------------------

    @GcbCase(value = "plugin is enabled", order = 0)
    public void pluginIsEnabled() throws Exception {
        GcbAssert.isTrue(Bukkit.getPluginManager().isPluginEnabled(PLUGIN), "Chatty must be enabled");
        GcbAssert.notNull(injector().getInstance(NotificationTicker.class),
                "the NotificationTicker must be available");
    }

    @GcbCase(value = "default configuration reloads cleanly", order = 1)
    public void defaultConfigurationReloads() throws Exception {
        removeNotifications();
        assertReloadSucceeded(reload(), "with the generated default notifications.yml");
        List<String> ids = channelIds();
        GcbAssert.isTrue(ids.contains("donate"),
                "the shipped \"donate\" chat channel must be registered, got " + ids);
        GcbAssert.isTrue(count(ids, "default") >= 3,
                "the shipped chat, action bar and title \"default\" channels must be registered, got " + ids);
    }

    @GcbCase(value = "valid notifications.yml loads every channel", order = 2)
    public void validFileLoadsEveryChannel() throws Exception {
        writeNotifications(VALID_FILE);
        assertReloadSucceeded(reload(), "with a valid notifications.yml");
        List<String> ids = channelIds();
        GcbAssert.isTrue(ids.contains(EDGE),
                "a channel whose stay equals its period must be registered, got " + ids);
        GcbAssert.isTrue(ids.contains(SHORT), "the \"" + SHORT + "\" channel must be registered, got " + ids);
        GcbAssert.isTrue(count(ids, "default") >= 3,
                "the default chat, action bar and title channels must be registered, got " + ids);
    }

    @GcbCase(value = "chats stay registered after a reload", order = 3)
    public void chatsStayRegistered() throws Exception {
        removeNotifications();
        assertReloadSucceeded(reload(), "before checking the chat registry");
        var chats = ChattyApi.instance().getChats();
        GcbAssert.isTrue(chats.containsKey("local"), "the shipped \"local\" chat must be registered, got " + chats.keySet());
        GcbAssert.isTrue(chats.containsKey("global"), "the shipped \"global\" chat must be registered, got " + chats.keySet());
    }

    @GcbCase(value = "info command answers from the console", order = 4)
    public void infoCommandAnswers() {
        RecordingSender sender = GcbSenders.recording();
        GcbCommands.dispatch(sender, "chatty");
        List<String> messages = sender.messages();
        GcbAssert.isTrue(messages.stream().anyMatch(m -> m.contains("Chatty") && m.contains("reload")),
                "/chatty must answer with the plugin summary, got " + messages);
    }

    @GcbCase(value = "notifications tick after a clean reload", order = 5, ticks = 200)
    public void notificationsTickAfterCleanReload(GcbScript script) {
        int[] start = new int[1];
        Notification[] watched = new Notification[1];
        script.step(() -> {
            writeNotifications(VALID_FILE);
            assertReloadSucceeded(reload(), "with a valid notifications.yml");
            watched[0] = notification(TICKING);
            GcbAssert.notNull(watched[0], "the \"" + TICKING + "\" chat channel must be registered");
            GcbAssert.isTrue(chattyHandlesChat(), "Chatty must listen to the chat event after a clean reload");
            start[0] = ticks(watched[0]);
        });
        script.waitTicks(80);
        script.step(() -> GcbAssert.isTrue(ticks(watched[0]) != start[0],
                "the \"" + TICKING + "\" notification must keep advancing after a clean reload (tick counter stayed at "
                        + start[0] + ")"));
    }

    @GcbCase(value = "reload survives an action bar channel whose stay exceeds its period", order = 10)
    public void reloadSurvivesBrokenChannel() throws Exception {
        writeNotifications(BROKEN_FILE);
        assertReloadSucceeded(reload(), "with an action bar channel whose stay exceeds its period");
        List<String> ids = channelIds();
        GcbAssert.isTrue(ids.contains(HEALTHY),
                "the valid channel listed after the broken one must be registered, got " + ids);
        GcbAssert.isFalse(ids.contains(BROKEN),
                "the channel whose stay exceeds its period must not be registered, got " + ids);
        GcbAssert.isTrue(count(ids, "default") >= 3,
                "the default chat, action bar and title channels must still be registered, got " + ids);
    }

    @GcbCase(value = "skipped channel is reported by name", order = 11)
    public void skippedChannelIsReported() throws Exception {
        writeNotifications(BROKEN_FILE);
        WarningCapture capture = new WarningCapture();
        List<Logger> loggers = capturedLoggers();
        for (Logger logger : loggers) {
            logger.addHandler(capture);
        }
        try {
            reload();
        } finally {
            for (Logger logger : loggers) {
                logger.removeHandler(capture);
            }
        }
        List<String> warnings = capture.warnings();
        GcbAssert.isTrue(warnings.stream().anyMatch(w -> w.contains(BROKEN)),
                "a warning must name the skipped channel \"" + BROKEN + "\", got " + warnings);
    }

    @GcbCase(value = "every offending channel is skipped and reported", order = 12)
    public void everyOffendingChannelIsSkipped() throws Exception {
        writeNotifications(TWO_BAD_FILE);
        RecordingSender[] sender = new RecordingSender[1];
        List<String> warnings = reloadCapturingWarnings(sender);
        assertReloadSucceeded(sender[0], "with two action bar channels whose stay exceeds their period");
        List<String> ids = channelIds();
        GcbAssert.isFalse(ids.contains(FIRST_BAD) || ids.contains(LAST_BAD),
                "neither offending channel may be registered, got " + ids);
        GcbAssert.isTrue(ids.contains(MIDDLE), "the valid channel between them must be registered, got " + ids);
        GcbAssert.isTrue(count(ids, "default") >= 3,
                "the default chat, action bar and title channels must still be registered, got " + ids);
        GcbAssert.isTrue(warnings.stream().anyMatch(w -> w.contains(FIRST_BAD)),
                "a warning must name \"" + FIRST_BAD + "\", got " + warnings);
        GcbAssert.isTrue(warnings.stream().anyMatch(w -> w.contains(LAST_BAD)),
                "a warning must name \"" + LAST_BAD + "\", got " + warnings);
    }

    @GcbCase(value = "chat keeps being handled after a reload with an offending channel", order = 13)
    public void chatStaysHandled() throws Exception {
        writeNotifications(BROKEN_FILE);
        assertReloadSucceeded(reload(), "with an action bar channel whose stay exceeds its period");
        GcbAssert.isTrue(chattyHandlesChat(),
                "Chatty must still listen to the chat event after the reload");
        GcbAssert.isTrue(chattyListens(PlayerJoinEvent.getHandlerList()),
                "Chatty must still listen to PlayerJoinEvent after the reload");
        var chats = ChattyApi.instance().getChats();
        GcbAssert.isTrue(chats.containsKey("local") && chats.containsKey("global"),
                "the shipped chats must stay registered, got " + chats.keySet());
    }

    @GcbCase(value = "notifications keep ticking after a reload with an offending channel", order = 14, ticks = 200)
    public void notificationsKeepTicking(GcbScript script) {
        int[] start = new int[1];
        Notification[] watched = new Notification[1];
        script.step(() -> {
            writeNotifications(BROKEN_FILE);
            assertReloadSucceeded(reload(), "with an action bar channel whose stay exceeds its period");
            watched[0] = notification(TICKING);
            GcbAssert.notNull(watched[0], "the \"" + TICKING + "\" chat channel must be registered");
            start[0] = ticks(watched[0]);
        });
        script.waitTicks(80);
        script.step(() -> GcbAssert.isTrue(ticks(watched[0]) != start[0],
                "the \"" + TICKING + "\" notification must keep advancing after the reload (tick counter stayed at "
                        + start[0] + ")"));
    }
}
