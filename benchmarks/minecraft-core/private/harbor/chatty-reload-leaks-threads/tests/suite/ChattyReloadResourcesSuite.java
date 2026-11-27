import io.gamecodebench.harness.GcbAssert;
import io.gamecodebench.harness.GcbCase;
import io.gamecodebench.harness.GcbCommands;
import io.gamecodebench.harness.GcbScript;
import io.gamecodebench.harness.GcbSenders;
import io.gamecodebench.harness.GcbSuite;
import io.gamecodebench.harness.RecordingSender;
import java.io.IOException;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.regex.Pattern;
import org.bukkit.Bukkit;
import org.bukkit.plugin.Plugin;
import ru.brikster.chatty.notification.Notification;
import ru.brikster.chatty.notification.NotificationTicker;
import ru.brikster.chatty.shaded.com.google.inject.Injector;

/**
 * Live-server grader for the Chatty reload resource leak: a reload must release the previous
 * ticker's executor and the previous bStats instance instead of leaving one more thread of each
 * behind. Every case is player-free; reloads go through the plugin's own console command and
 * threads are identified by name from the main thread.
 */
public final class ChattyReloadResourcesSuite implements GcbSuite {

    private static final String PLUGIN = "Chatty";
    private static final String RELOAD_SUCCESS = "Plugin successfully reloaded!";
    private static final String RELOAD_ERROR = "Error while reloading plugin";
    private static final Pattern DEFAULT_POOL_THREAD = Pattern.compile("pool-\\d+-thread-\\d+");
    private static final String BSTATS_THREAD = "bStats-Metrics";
    private static final int RELOADS = 3;

    // --- plugin access -----------------------------------------------------------------------

    private static Plugin chatty() {
        Plugin plugin = Bukkit.getPluginManager().getPlugin(PLUGIN);
        GcbAssert.notNull(plugin, "the Chatty plugin must be loaded");
        return plugin;
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

    private static NotificationTicker ticker() throws IllegalAccessException {
        NotificationTicker ticker = injector().getInstance(NotificationTicker.class);
        GcbAssert.notNull(ticker, "the NotificationTicker must be available from the injector");
        return ticker;
    }

    /** Every Notification held in a Collection field of the ticker. */
    private static List<Notification> notificationsOf(NotificationTicker ticker) throws IllegalAccessException {
        List<Notification> notifications = new ArrayList<>();
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
                for (Object item : new ArrayList<>(items)) {
                    if (item instanceof Notification notification) {
                        notifications.add(notification);
                    }
                }
            }
        }
        return notifications;
    }

    /** Every ExecutorService held in a field of the ticker (null fields are skipped). */
    private static List<ExecutorService> executorsOf(NotificationTicker ticker) throws IllegalAccessException {
        List<ExecutorService> executors = new ArrayList<>();
        for (Class<?> type = ticker.getClass(); type != null; type = type.getSuperclass()) {
            for (Field field : type.getDeclaredFields()) {
                if (!ExecutorService.class.isAssignableFrom(field.getType())) {
                    continue;
                }
                field.setAccessible(true);
                Object value = field.get(ticker);
                if (value instanceof ExecutorService executor) {
                    executors.add(executor);
                }
            }
        }
        return executors;
    }

    private static String idOf(Notification notification) throws IllegalAccessException {
        Object value = fieldValue(notification, "name");
        return value instanceof String id ? id : notification.getClass().getSimpleName();
    }

    /** The inherited per-second tick counter of a notification. */
    private static int tickOf(Notification notification) throws IllegalAccessException {
        Object value = fieldValue(notification, "tick");
        GcbAssert.isTrue(value instanceof Integer, "the notification must carry its tick counter, got " + value);
        return (Integer) value;
    }

    private static Object fieldValue(Object target, String name) throws IllegalAccessException {
        for (Class<?> type = target.getClass(); type != null && type != Object.class; type = type.getSuperclass()) {
            try {
                Field field = type.getDeclaredField(name);
                field.setAccessible(true);
                return field.get(target);
            } catch (NoSuchFieldException ignored) {
                // keep looking up the hierarchy
            }
        }
        return null;
    }

    private static List<String> channelIds(NotificationTicker ticker) throws IllegalAccessException {
        List<String> ids = new ArrayList<>();
        for (Notification notification : notificationsOf(ticker)) {
            ids.add(idOf(notification));
        }
        return ids;
    }

    private static Notification channel(NotificationTicker ticker, String id) throws IllegalAccessException {
        for (Notification notification : notificationsOf(ticker)) {
            if (id.equals(idOf(notification))) {
                return notification;
            }
        }
        GcbAssert.fail("the \"" + id + "\" channel must be registered with the ticker, got " + channelIds(ticker));
        return null;
    }

    /** A never-started ticker of the class bound to NotificationTicker, built through its constructor. */
    private static NotificationTicker freshTicker(Class<?> type) throws Exception {
        Constructor<?> chosen = null;
        for (Constructor<?> constructor : type.getDeclaredConstructors()) {
            if (chosen == null || constructor.getParameterCount() < chosen.getParameterCount()) {
                chosen = constructor;
            }
        }
        GcbAssert.notNull(chosen, "the ticker class " + type.getName() + " must have a constructor");
        chosen.setAccessible(true);
        Class<?>[] parameters = chosen.getParameterTypes();
        Object[] arguments = new Object[parameters.length];
        Injector injector = injector();
        for (int i = 0; i < parameters.length; i++) {
            arguments[i] = injector.getInstance(parameters[i]);
        }
        Object instance = chosen.newInstance(arguments);
        GcbAssert.isTrue(instance instanceof NotificationTicker,
                type.getName() + " must implement NotificationTicker");
        return (NotificationTicker) instance;
    }

    // --- configuration and commands ----------------------------------------------------------

    /** notifications.yml with the shipped chat channel plus one extra chat channel (600 s period). */
    private static String notificationsFile(String channel) {
        return ""
                + "chat:\n"
                + "  enable: true\n"
                + "  lists:\n"
                + "    default:\n"
                + "      period: 60\n"
                + "    " + channel + ":\n"
                + "      period: 600\n";
    }

    private static void writeNotifications(String content) throws IOException {
        Path file = chatty().getDataFolder().toPath().resolve("notifications.yml");
        Files.createDirectories(file.getParent());
        Files.writeString(file, content, StandardCharsets.UTF_8);
    }

    /** bStats is disabled by the runtime; the plugin re-reads plugins/bStats/config.yml on every reload. */
    private static void enableBStats() throws IOException {
        Path file = chatty().getDataFolder().toPath().resolveSibling("bStats").resolve("config.yml");
        Files.createDirectories(file.getParent());
        Files.writeString(file, ""
                + "enabled: true\n"
                + "serverUuid: 00000000-0000-0000-0000-000000000000\n"
                + "logFailedRequests: false\n"
                + "logSentData: false\n"
                + "logResponseStatusText: false\n", StandardCharsets.UTF_8);
    }

    /** Sets send-metrics in plugins/Chatty/settings.yml, keeping the rest of the file. */
    private static void setSendMetrics(boolean value) throws IOException {
        Path file = chatty().getDataFolder().toPath().resolve("settings.yml");
        String content = Files.isRegularFile(file) ? Files.readString(file, StandardCharsets.UTF_8) : "";
        Pattern key = Pattern.compile("(?m)^send-metrics:[^\\n]*$");
        String line = "send-metrics: " + value;
        content = key.matcher(content).find()
                ? key.matcher(content).replaceAll(line)
                : content + (content.isEmpty() || content.endsWith("\n") ? "" : "\n") + line + "\n";
        Files.writeString(file, content, StandardCharsets.UTF_8);
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

    // --- threads -----------------------------------------------------------------------------

    private static boolean isPluginThreadName(String name) {
        if (name == null) {
            return false;
        }
        String lower = name.toLowerCase(Locale.ROOT);
        return DEFAULT_POOL_THREAD.matcher(name).matches()
                || BSTATS_THREAD.equals(name)
                || lower.contains("notification")
                || lower.contains("ticker")
                || lower.contains("metrics");
    }

    /** Live threads whose names mark them as the plugin's ticker or bStats threads. */
    private static Set<Thread> pluginThreads() {
        Set<Thread> threads = new LinkedHashSet<>();
        for (Thread thread : Thread.getAllStackTraces().keySet()) {
            if (thread.isAlive() && isPluginThreadName(thread.getName())) {
                threads.add(thread);
            }
        }
        return threads;
    }

    private static List<String> names(Collection<Thread> threads) {
        List<String> names = new ArrayList<>();
        for (Thread thread : threads) {
            names.add(thread.getName());
        }
        names.sort(null);
        return names;
    }

    private static long countNamed(Collection<Thread> threads, String name) {
        return threads.stream().filter(t -> name.equals(t.getName())).count();
    }

    // --- cases -------------------------------------------------------------------------------

    @GcbCase(value = "plugin is enabled", order = 0)
    public void pluginIsEnabled() throws Exception {
        GcbAssert.isTrue(Bukkit.getPluginManager().isPluginEnabled(PLUGIN), "Chatty must be enabled");
        GcbAssert.notNull(ticker(), "the NotificationTicker must be available");
    }

    @GcbCase(value = "reload picks up a changed notifications.yml", order = 1)
    public void reloadPicksUpChangedFile() throws Exception {
        writeNotifications(notificationsFile("gcb_reloaded"));
        assertReloadSucceeded(reload(), "after a channel was added to notifications.yml");
        List<String> ids = channelIds(ticker());
        GcbAssert.isTrue(ids.contains("gcb_reloaded"),
                "the channel added before the reload must be registered with the new ticker, got " + ids);
        GcbAssert.isTrue(ids.contains("default"), "the shipped default channels must still be registered, got " + ids);
    }

    @GcbCase(value = "notifications keep ticking after a reload", order = 2)
    public void notificationsKeepTicking(GcbScript script) {
        Notification[] channel = new Notification[1];
        int[] before = new int[1];
        script.step(() -> {
            writeNotifications(notificationsFile("gcb_ticking"));
            assertReloadSucceeded(reload(), "before observing the ticker");
            channel[0] = channel(ticker(), "gcb_ticking");
            before[0] = tickOf(channel[0]);
        });
        script.waitTicks(80);
        script.step(() -> {
            int after = tickOf(channel[0]);
            GcbAssert.isTrue(after > before[0],
                    "a notification registered by the reload must keep ticking (counter " + before[0]
                            + " before, " + after + " four seconds later)");
        });
    }

    @GcbCase(value = "bStats metrics stay scheduled after a reload", order = 3)
    public void metricsStayScheduled(GcbScript script) {
        script.step(() -> {
            enableBStats();
            setSendMetrics(true);
            assertReloadSucceeded(reload(), "with bStats enabled");
        });
        script.waitTicks(40);
        script.step(() -> {
            Set<Thread> threads = pluginThreads();
            GcbAssert.isTrue(countNamed(threads, BSTATS_THREAD) >= 1,
                    "a reload with bStats enabled must leave a live " + BSTATS_THREAD
                            + " thread, plugin threads: " + names(threads));
        });
    }

    @GcbCase(value = "previous ticker is stopped by a reload", order = 10)
    public void previousTickerIsStopped(GcbScript script) {
        NotificationTicker[] previous = new NotificationTicker[1];
        Notification[] channel = new Notification[1];
        List<ExecutorService> executors = new ArrayList<>();
        int[] reads = new int[2];
        script.step(() -> {
            writeNotifications(notificationsFile("gcb_previous"));
            assertReloadSucceeded(reload(), "before capturing the ticker");
            previous[0] = ticker();
            channel[0] = channel(previous[0], "gcb_previous");
            executors.addAll(executorsOf(previous[0]));
        });
        script.waitTicks(50);
        script.step(() -> {
            GcbAssert.isTrue(tickOf(channel[0]) > 0,
                    "the captured ticker must have been ticking before the reload replaced it");
            assertReloadSucceeded(reload(), "to replace the captured ticker");
            GcbAssert.isTrue(ticker() != previous[0], "the reload must build a new ticker instance");
        });
        script.waitTicks(20);
        script.step(() -> reads[0] = tickOf(channel[0]));
        script.waitTicks(60);
        script.step(() -> {
            reads[1] = tickOf(channel[0]);
            GcbAssert.equals(reads[0], reads[1],
                    "the notifications of the replaced ticker must stop advancing after the reload (counter "
                            + reads[0] + " then " + reads[1] + ")");
            for (ExecutorService executor : executors) {
                GcbAssert.isTrue(executor.isShutdown(),
                        "the ticker replaced by the reload must have shut its executor down, but "
                                + executor + " is still accepting work");
            }
        });
    }

    @GcbCase(value = "cancelling a ticker that never started does not throw", order = 11)
    public void cancellingBeforeStartDoesNotThrow() throws Exception {
        NotificationTicker fresh = freshTicker(ticker().getClass());
        try {
            fresh.cancelTicking();
        } catch (Throwable failure) {
            GcbAssert.fail("cancelTicking() on a ticker that never started must return normally, got " + failure);
        }
    }

    @GcbCase(value = "reloads do not leak ticker or bStats threads", order = 12)
    public void reloadsDoNotLeakThreads(GcbScript script) {
        Set<Thread> before = new LinkedHashSet<>();
        script.step(() -> {
            enableBStats();
            setSendMetrics(true);
            writeNotifications(notificationsFile("gcb_leak"));
            assertReloadSucceeded(reload(), "before the thread snapshot");
        });
        script.waitTicks(60);
        script.step(() -> before.addAll(pluginThreads()));
        for (int i = 1; i <= RELOADS; i++) {
            String context = "on reload " + i + " of " + RELOADS;
            script.step(() -> assertReloadSucceeded(reload(), context));
            script.waitTicks(20);
        }
        script.waitTicks(80);
        script.step(() -> {
            Set<Thread> after = pluginThreads();
            Set<Thread> added = new LinkedHashSet<>(after);
            added.removeAll(before);
            Set<Thread> gone = new LinkedHashSet<>(before);
            gone.removeAll(after);
            int growth = added.size() - gone.size();
            GcbAssert.isTrue(growth <= 0,
                    RELOADS + " reloads left " + growth + " extra plugin-owned thread(s) alive: new "
                            + names(added) + ", gone " + names(gone) + " (before " + names(before)
                            + ", after " + names(after) + ")");
        });
    }

    @GcbCase(value = "turning metrics off stops the bStats thread on reload", order = 13, ticks = 400)
    public void metricsOffStopsBStats(GcbScript script) {
        script.step(() -> {
            enableBStats();
            setSendMetrics(true);
            assertReloadSucceeded(reload(), "with bStats enabled");
        });
        // Whether bStats runs at this point is the preserved bStats case's concern; this case only
        // requires that switching send-metrics off leaves no bStats thread behind.
        script.waitTicks(40);
        script.step(() -> {
            setSendMetrics(false);
            assertReloadSucceeded(reload(), "after send-metrics was switched off");
        });
        script.waitTicks(80);
        script.step(() -> {
            Set<Thread> threads = pluginThreads();
            setSendMetrics(true);
            GcbAssert.equals(0L, countNamed(threads, BSTATS_THREAD),
                    "after send-metrics was switched off and the plugin reloaded, no " + BSTATS_THREAD
                            + " thread may remain, plugin threads: " + names(threads));
        });
    }
}
