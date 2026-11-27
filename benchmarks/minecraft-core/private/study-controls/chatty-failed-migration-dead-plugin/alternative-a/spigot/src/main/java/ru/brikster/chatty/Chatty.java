package ru.brikster.chatty;

import cloud.commandframework.Command;
import cloud.commandframework.Command.Builder;
import cloud.commandframework.CommandManager.ManagerSettings;
import cloud.commandframework.CommandTree.Node;
import cloud.commandframework.arguments.CommandArgument;
import cloud.commandframework.arguments.standard.BooleanArgument;
import cloud.commandframework.arguments.standard.StringArgument;
import cloud.commandframework.bukkit.BukkitCommandManager;
import cloud.commandframework.exceptions.ArgumentParseException;
import cloud.commandframework.exceptions.InvalidSyntaxException;
import cloud.commandframework.execution.AsynchronousCommandExecutionCoordinator;
import cloud.commandframework.execution.CommandExecutionCoordinator;
import cloud.commandframework.execution.CommandExecutionHandler;
import cloud.commandframework.meta.CommandMeta;
import cloud.commandframework.minecraft.extras.MinecraftExceptionHandler;
import cloud.commandframework.minecraft.extras.MinecraftExceptionHandler.ExceptionType;
import com.google.inject.Guice;
import com.google.inject.Injector;
import lombok.SneakyThrows;
import net.kyori.adventure.platform.bukkit.BukkitAudiences;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.minimessage.MiniMessage;
import org.bukkit.Bukkit;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.event.Event;
import org.bukkit.event.EventPriority;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.player.AsyncPlayerChatEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.plugin.java.JavaPlugin;
import org.jetbrains.annotations.Nullable;
import ru.brikster.chatty.adventure.NativeBukkitAudienceProvider;
import ru.brikster.chatty.api.ChattyApiImpl;
import ru.brikster.chatty.api.event.ChattyInitEvent;
import ru.brikster.chatty.chat.executor.LegacyEventExecutor;
import ru.brikster.chatty.chat.registry.ChatRegistry;
import ru.brikster.chatty.command.CommandSuggestionsProvider;
import ru.brikster.chatty.command.ProxyingCommandHandler;
import ru.brikster.chatty.command.ProxyingCommandSuggestionsProvider;
import ru.brikster.chatty.command.handler.ClearChatCommandHandler;
import ru.brikster.chatty.command.handler.SpyCommandHandler;
import ru.brikster.chatty.config.file.MessagesConfig;
import ru.brikster.chatty.config.file.PmConfig;
import ru.brikster.chatty.config.file.SettingsConfig;
import ru.brikster.chatty.config.migration.V2ConfigMigrator;
import ru.brikster.chatty.guice.ConfigsLoader;
import ru.brikster.chatty.guice.GeneralGuiceModule;
import ru.brikster.chatty.metrics.MetricsSender;
import ru.brikster.chatty.misc.VanillaListener;
import ru.brikster.chatty.notification.NotificationTicker;
import ru.brikster.chatty.papi.PapiExpansionInstaller;
import ru.brikster.chatty.pm.MsgCommandHandler;
import ru.brikster.chatty.pm.PrivateMessageSuggestionsProvider;
import ru.brikster.chatty.pm.ReplyCommandHandler;
import ru.brikster.chatty.pm.ignore.AddIgnoreCommandHandler;
import ru.brikster.chatty.pm.ignore.IgnoreListCommandHandler;
import ru.brikster.chatty.pm.ignore.RemoveIgnoreCommandHandler;
import ru.brikster.chatty.proxy.ProxyService;
import ru.brikster.chatty.repository.player.PlayerDataRepository;
import ru.brikster.chatty.util.AdventureUtil;
import ru.brikster.chatty.util.EventUtil;
import ru.brikster.chatty.util.PaperUtil;

import java.io.IOException;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.StandardCopyOption;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Function;
import java.util.logging.Level;

public final class Chatty extends JavaPlugin {

    private static final String FAILED_MIGRATION_FOLDER_PREFIX = "Chatty_failed_migration_";

    private final Map<String, ProxyingCommandHandler<CommandSender>> proxyingCommandHandlerMap = new ConcurrentHashMap<>();

    private Injector injector;

    /** The injector whose repositories {@link #tearDownQuietly()} already closed. */
    private Injector closedInjector;

    private NotificationTicker notificationTicker;
    private BukkitCommandManager<CommandSender> syncCommandManager;
    private BukkitCommandManager<CommandSender> asyncCommandManager;

    private ProxyingCommandSuggestionsProvider<CommandSender> commandSuggestionsProvider;

    @SneakyThrows
    @Override
    public void onEnable() {
        Path dataFolderPath = Chatty.this.getDataFolder().toPath();

        Map<String, Object> legacyConfig = null;
        String backupTimestamp = null;
        String backupFolderName = null;
        if (Files.exists(dataFolderPath.resolve("config.yml"))) {
            backupTimestamp = String.valueOf(System.currentTimeMillis());
            backupFolderName = "Chatty_old_" + backupTimestamp;
            Path backupFolder = dataFolderPath.resolveSibling(backupFolderName);
            Files.move(dataFolderPath, backupFolder);
            getLogger().log(Level.WARNING, "Found legacy \"config.yml\" file in plugin directory. \"Chatty\" folder was renamed to \"{0}\".", backupFolderName);
            legacyConfig = V2ConfigMigrator.readLegacyConfig(backupFolder.resolve("config.yml"));
            if (legacyConfig == null) {
                getLogger().warning("Could not read the legacy config.yml — starting with a default configuration.");
            }
        }

        initialize();

        if (legacyConfig != null) {
            switchToMigratedConfig(legacyConfig, dataFolderPath, backupFolderName, backupTimestamp);
        }

        registerChattyCommand();
    }

    /**
     * Migrates the legacy config into the v3 files generated with defaults and switches the
     * running plugin to them. When the migrated configuration cannot be loaded, the plugin is
     * recovered with a fresh default configuration instead of staying enabled without its
     * listeners, notifications and a working reload.
     */
    private void switchToMigratedConfig(Map<String, Object> legacyConfig,
                                        Path dataFolderPath,
                                        String backupFolderName,
                                        String timestamp) throws Exception {
        try {
            // Fresh v3 defaults were generated above: overwrite the migrated keys, then reload.
            new V2ConfigMigrator(getLogger()).migrate(legacyConfig, dataFolderPath);
            tearDownQuietly();
            initialize();
            return;
        } catch (Throwable t) {
            getLogger().log(Level.SEVERE, "Could not load the migrated legacy configuration: "
                    + describeRootCause(t), t);
        }
        recoverFromFailedMigration(dataFolderPath, backupFolderName, timestamp);
    }

    /**
     * Moves the half-migrated files out of the data folder, so they cannot break the plugin
     * (or every reload) again, and starts the plugin with a freshly generated default
     * configuration. Teardown and clean-up failures are logged and never stop the recovery.
     */
    private void recoverFromFailedMigration(Path dataFolderPath,
                                            String backupFolderName,
                                            String timestamp) throws Exception {
        String dataFolderName = String.valueOf(dataFolderPath.getFileName());

        // Whatever the failed start left behind (listeners, ticker, open repositories) goes first.
        tearDownQuietly();

        Path quarantineFolder = quarantineDataFolder(dataFolderPath, timestamp);
        if (quarantineFolder != null) {
            getLogger().log(Level.WARNING, "The half-migrated configuration files were moved out of \""
                    + dataFolderName + "\" to \"" + quarantineFolder.getFileName() + "\" ("
                    + quarantineFolder.toAbsolutePath() + ") for review.");
        }

        String backupAdvice = "Your Chatty v2 configuration is kept unchanged in \"" + backupFolderName
                + "\". To migrate it again, fix the reported problem, move its config.yml back into the \""
                + dataFolderName + "\" folder and restart the server.";
        try {
            initialize();
        } catch (Throwable t) {
            getLogger().log(Level.SEVERE, "Chatty could not start with a default configuration either. "
                    + backupAdvice, t);
            throw t;
        }

        getLogger().log(Level.WARNING, "The legacy configuration could not be migrated: Chatty started with "
                + "a default configuration instead of the migrated one.");
        getLogger().log(Level.WARNING, backupAdvice);
    }

    /**
     * Moves the whole data folder to a sibling {@code Chatty_failed_migration_<timestamp>}
     * folder, falling back to moving its entries one by one.
     *
     * @return the quarantine folder, or {@code null} when nothing was moved
     */
    private @Nullable Path quarantineDataFolder(Path dataFolderPath, String timestamp) {
        if (!Files.exists(dataFolderPath)) {
            return null;
        }

        Path target = dataFolderPath.resolveSibling(FAILED_MIGRATION_FOLDER_PREFIX + timestamp);
        long fallbackTimestamp = System.currentTimeMillis();
        while (Files.exists(target)) {
            target = dataFolderPath.resolveSibling(FAILED_MIGRATION_FOLDER_PREFIX + fallbackTimestamp++);
        }

        try {
            Files.move(dataFolderPath, target);
            return target;
        } catch (IOException | RuntimeException e) {
            getLogger().log(Level.WARNING, "Could not move the \"" + dataFolderPath.getFileName()
                    + "\" folder to \"" + target.getFileName() + "\" at once, moving its files one by one", e);
        }

        try {
            moveTreeQuietly(dataFolderPath, target);
        } catch (IOException | RuntimeException e) {
            getLogger().log(Level.SEVERE, "Could not move the half-migrated configuration files to \""
                    + target.getFileName() + "\"", e);
        }
        return Files.exists(target) ? target : null;
    }

    /** Moves every entry of {@code source} below {@code target}; failures are logged and skipped. */
    private void moveTreeQuietly(Path source, Path target) throws IOException {
        Files.walkFileTree(source, new SimpleFileVisitor<>() {

            @Override
            public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) {
                try {
                    Files.createDirectories(target.resolve(source.relativize(dir).toString()));
                    return FileVisitResult.CONTINUE;
                } catch (IOException | RuntimeException e) {
                    getLogger().log(Level.WARNING, "Could not move \"" + source.relativize(dir)
                            + "\" out of the \"" + source.getFileName() + "\" folder", e);
                    return FileVisitResult.SKIP_SUBTREE;
                }
            }

            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) {
                Path destination = target.resolve(source.relativize(file).toString());
                try {
                    Files.move(file, destination, StandardCopyOption.REPLACE_EXISTING);
                } catch (IOException | RuntimeException moveFailure) {
                    try {
                        Files.copy(file, destination, StandardCopyOption.REPLACE_EXISTING);
                        Files.delete(file);
                    } catch (IOException | RuntimeException copyFailure) {
                        copyFailure.addSuppressed(moveFailure);
                        getLogger().log(Level.WARNING, "Could not move \"" + source.relativize(file)
                                + "\" out of the \"" + source.getFileName() + "\" folder", copyFailure);
                    }
                }
                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult visitFileFailed(Path file, IOException e) {
                getLogger().log(Level.WARNING, "Could not move \"" + source.relativize(file)
                        + "\" out of the \"" + source.getFileName() + "\" folder", e);
                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult postVisitDirectory(Path dir, @Nullable IOException e) {
                try {
                    Files.deleteIfExists(dir);
                } catch (IOException | RuntimeException ignored) {
                    // Not empty: an entry could not be moved and was reported above.
                }
                return FileVisitResult.CONTINUE;
            }
        });
    }

    private static String describeRootCause(Throwable throwable) {
        Throwable root = throwable;
        for (int depth = 0; depth < 32 && root.getCause() != null && root.getCause() != root; depth++) {
            root = root.getCause();
        }
        String message = root.getMessage();
        if (message == null || message.isBlank()) {
            return root.getClass().getSimpleName();
        }
        int lineEnd = message.indexOf('\n');
        return root.getClass().getSimpleName() + ": "
                + (lineEnd >= 0 ? message.substring(0, lineEnd).trim() : message);
    }

    private void registerChattyCommand() throws Exception {
        this.syncCommandManager = new BukkitCommandManager<>(this,
                CommandExecutionCoordinator.simpleCoordinator(),
                Function.identity(),
                Function.identity());

        Builder<CommandSender> chattyBuilder = syncCommandManager.commandBuilder("chatty");

        Command<CommandSender> infoCommand = Command
                .<CommandSender>newBuilder("chatty", CommandMeta.simple().build())
                .handler(handler -> {
                    Component component = MiniMessage.miniMessage().deserialize(
                            "<gold><bold>Chatty</bold></gold> <gray>(v" + getDescription().getVersion() + ")</gray> - chat management system by <green>@Brikster</green>.<newline>" +
                            "Links: <click:open_url:'https://github.com/Brikster/Chatty'><aqua>GitHub</aqua></click><newline>" +
                            "Use <yellow>/chatty reload</yellow> to reload configuration.");

                    injector.getInstance(BukkitAudiences.class)
                            .sender(handler.getSender())
                            .sendMessage(component);
                }).build();

        Command<CommandSender> reloadCommand = chattyBuilder
                .literal("reload")
                .permission("chatty.command.reload")
                .handler(handler -> {
                    try {
                        closeResources();
                        initialize();
                        injector.getInstance(BukkitAudiences.class)
                                .sender(handler.getSender())
                                .sendMessage(injector.getInstance(MessagesConfig.class).getReloadCommandSuccess());
                    } catch (Throwable t) {
                        getLogger().log(Level.SEVERE, "Error while reloading Chatty", t);
                        handler.getSender().sendMessage("§cError while reloading plugin: " + t.getClass().getSimpleName() + ". See console for more details.");
                    }
                })
                .build();

        syncCommandManager
                .command(infoCommand)
                .command(reloadCommand);
    }

    private void initialize() throws Exception {
        BukkitAudiences audiences;
        if (isUseNativeAdventurePlatform()) {
            getLogger().log(Level.INFO, "Using native Adventure audience provider");
            audiences = new NativeBukkitAudienceProvider();
        } else {
            getLogger().log(Level.INFO, "Using bundled Adventure audience provider");
            audiences = BukkitAudiences.create(this);
        }

        ChattyInitEvent initEvent = new ChattyInitEvent(audiences);
        getServer().getPluginManager().callEvent(initEvent);

        this.injector = Guice.createInjector(new GeneralGuiceModule(
                        Chatty.this,
                        initEvent.getAudienceProvider(),
                        getDataFolder().toPath()));

        injector.injectMembers(new ConfigsLoader());

        EventPriority priority = injector.getInstance(SettingsConfig.class).getListenerPriority();
        if (priority == EventPriority.MONITOR) {
            priority = EventPriority.HIGHEST;
            getLogger().log(Level.WARNING, "Cannot use monitor priority for listener. HIGHEST priority usage will be forced");
        }

        LegacyEventExecutor chatListener = injector.getInstance(LegacyEventExecutor.class);

        this.getServer().getPluginManager().registerEvents(chatListener, this);
        this.getServer().getPluginManager().registerEvent(AsyncPlayerChatEvent.class, chatListener, priority, chatListener, this, true);

        VanillaListener miscListener = injector.getInstance(VanillaListener.class);
        this.getServer().getPluginManager().registerEvents(miscListener, this);

        this.notificationTicker = injector.getInstance(NotificationTicker.class);
        notificationTicker.startTicking();

        if (Bukkit.getServer().getPluginManager().isPluginEnabled("PlaceholderAPI")) {
            PapiExpansionInstaller.install(injector);
        }

        PmConfig pmConfig = injector.getInstance(PmConfig.class);

        PrivateMessageSuggestionsProvider pmSuggestionsProvider = injector.getInstance(PrivateMessageSuggestionsProvider.class);
        if (commandSuggestionsProvider == null) {
            commandSuggestionsProvider = new ProxyingCommandSuggestionsProvider<>(pmSuggestionsProvider);
        } else {
            commandSuggestionsProvider.setBackendProvider(pmSuggestionsProvider);
        }

        AddIgnoreCommandHandler addIgnoreCommandHandler = injector.getInstance(AddIgnoreCommandHandler.class);
        RemoveIgnoreCommandHandler removeIgnoreCommandHandler = injector.getInstance(RemoveIgnoreCommandHandler.class);
        IgnoreListCommandHandler ignoreListCommandHandler = injector.getInstance(IgnoreListCommandHandler.class);
        registerProxyingHandler("ignore add", addIgnoreCommandHandler);
        registerProxyingHandler("ignore remove", removeIgnoreCommandHandler);
        registerProxyingHandler("ignore list", ignoreListCommandHandler);

        if (pmConfig.isEnable()) {
            MsgCommandHandler msgCommandHandler = injector.getInstance(MsgCommandHandler.class);
            ReplyCommandHandler replyCommandHandler = injector.getInstance(ReplyCommandHandler.class);
            registerProxyingHandler("msg", msgCommandHandler);
            registerProxyingHandler("reply", replyCommandHandler);
        }

        ClearChatCommandHandler clearChatCommandHandler = injector.getInstance(ClearChatCommandHandler.class);
        registerProxyingHandler("clearchat", clearChatCommandHandler);

        SpyCommandHandler spyCommandHandler = injector.getInstance(SpyCommandHandler.class);
        registerProxyingHandler("spy", spyCommandHandler);

        if (this.asyncCommandManager == null) {
            initAsyncCommandManager();
            if (pmConfig.isEnable()) {
                registerPmCommands(commandSuggestionsProvider);
            }
            registerIgnoreCommand(commandSuggestionsProvider);
            registerMiscCommands();
        }

        ChattyApiImpl.updateInstance(new ChattyApiImpl(injector.getInstance(ChatRegistry.class).getChats()));

        MetricsSender metricsSender = new MetricsSender();
        injector.injectMembers(metricsSender);
        metricsSender.run();
    }

    private void closeResources() throws IOException {
        if (!isUseNativeAdventurePlatform()) {
            BukkitAudiences.create(this).close();
        }
        injector.getInstance(PlayerDataRepository.class).close();
        injector.getInstance(ProxyService.class).close();
        EventUtil.unregisterListeners(PlayerJoinEvent.class, this);
        EventUtil.unregisterListeners(PlayerQuitEvent.class, this);
        EventUtil.unregisterListeners(PlayerDeathEvent.class, this);
        EventUtil.unregisterListeners(AsyncPlayerChatEvent.class, this);
        notificationTicker.cancelTicking();
    }

    /**
     * Best-effort {@link #closeResources()} for switching configurations while enabling: every
     * step runs even when an earlier one fails, and failures are only logged. It also copes
     * with the state an {@link #initialize()} that failed half-way leaves behind.
     */
    private void tearDownQuietly() {
        if (!isUseNativeAdventurePlatform()) {
            runQuietly("close the Adventure audiences", () -> BukkitAudiences.create(this).close());
        }

        Injector currentInjector = this.injector;
        if (currentInjector != null && currentInjector != closedInjector) {
            runQuietly("close the player data repository",
                    () -> currentInjector.getInstance(PlayerDataRepository.class).close());
            runQuietly("close the proxy service",
                    () -> currentInjector.getInstance(ProxyService.class).close());
            closedInjector = currentInjector;
        }

        List<Class<? extends Event>> listenedEvents = List.of(PlayerJoinEvent.class, PlayerQuitEvent.class,
                PlayerDeathEvent.class, AsyncPlayerChatEvent.class);
        for (Class<? extends Event> eventClass : listenedEvents) {
            runQuietly("unregister the " + eventClass.getSimpleName() + " listeners",
                    () -> EventUtil.unregisterListeners(eventClass, this));
        }

        NotificationTicker currentTicker = this.notificationTicker;
        if (currentTicker != null) {
            runQuietly("stop the notifications", currentTicker::cancelTicking);
        }
    }

    private interface TeardownStep {
        void run() throws Exception;
    }

    private void runQuietly(String description, TeardownStep step) {
        try {
            step.run();
        } catch (Throwable t) {
            getLogger().log(Level.WARNING, "Could not " + description + ", continuing anyway", t);
        }
    }

    private void initAsyncCommandManager() throws Exception {
        this.asyncCommandManager = new BukkitCommandManager<>(this,
                AsynchronousCommandExecutionCoordinator.<CommandSender>builder()
                        .withAsynchronousParsing()
                        .build(),
                Function.identity(),
                Function.identity());

        MessagesConfig messagesConfig = injector.getInstance(MessagesConfig.class);

        new MinecraftExceptionHandler<CommandSender>()
                .withHandler(ExceptionType.ARGUMENT_PARSING, (e) -> {
                    String argument = ((ArgumentParseException) e).getCause().toString();
                    return messagesConfig.getCmdArgumentParsingError()
                            .replaceText(AdventureUtil.createReplacement("{argument}", argument));
                })
                .withHandler(ExceptionType.INVALID_SYNTAX, (e) -> {
                    String correctSyntax = ((InvalidSyntaxException) e).getCorrectSyntax();
                    return messagesConfig.getCmdUsageError()
                            .replaceText(AdventureUtil.createReplacement("{usage}", "/" + correctSyntax));
                })
                .withHandler(ExceptionType.INVALID_SENDER, (e) -> messagesConfig.getCmdSenderTypeError())
                .withHandler(ExceptionType.NO_PERMISSION, (e) -> messagesConfig.getCmdNoPermissionError())
                .withHandler(ExceptionType.COMMAND_EXECUTION, (e) -> {
                    //noinspection CallToPrintStackTrace
                    e.printStackTrace();
                    return messagesConfig.getCmdExecutionError();
                })
                .apply(asyncCommandManager, injector.getInstance(BukkitAudiences.class)::sender);

        asyncCommandManager.setSetting(ManagerSettings.ALLOW_UNSAFE_REGISTRATION, true);
    }

    private void registerMiscCommands() {
        var clearChatCommand = asyncCommandManager
                .commandBuilder("clearchat")
                .permission("chatty.command.clearchat")
                .handler(proxyingCommandHandlerMap.get("clearchat"))
                .build();
        asyncCommandManager.command(clearChatCommand);

        var spyCommand = asyncCommandManager
                .commandBuilder("spy")
                .senderType(Player.class)
                .permission("chatty.command.spy")
                .argument(BooleanArgument.<CommandSender>builder("state")
                        .withLiberal(true)
                        .build())
                .handler(proxyingCommandHandlerMap.get("spy"))
                .build();
        asyncCommandManager.command(spyCommand);
    }

    private void registerIgnoreCommand(CommandSuggestionsProvider<CommandSender> pmSuggestionsProvider) {
        Builder<CommandSender> ignoreCommandBuilder = asyncCommandManager
                 .commandBuilder("ignore")
                 .permission("chatty.command.ignore");

        Command<CommandSender> ignoreAddCommand = ignoreCommandBuilder
                .literal("add")
                .argument(StringArgument.<CommandSender>builder("target")
                        .single()
                        .withSuggestionsProvider(pmSuggestionsProvider)
                        .build())
                .handler(proxyingCommandHandlerMap.get("ignore add"))
                .build();

        Command<CommandSender> ignoreRemoveCommand = ignoreCommandBuilder
                .literal("remove", "rem", "rm", "delete")
                .argument(StringArgument.<CommandSender>builder("target")
                        .single()
                        .withSuggestionsProvider(pmSuggestionsProvider)
                        .build())
                .handler(proxyingCommandHandlerMap.get("ignore remove"))
                .build();

        Command<CommandSender> ignoreListCommand = ignoreCommandBuilder
                .handler(proxyingCommandHandlerMap.get("ignore list"))
                .build();

        asyncCommandManager
                .command(ignoreAddCommand)
                .command(ignoreRemoveCommand)
                .command(ignoreListCommand);
    }

    private void registerPmCommands(CommandSuggestionsProvider<CommandSender> pmSuggestionsProvider) {
        Command<CommandSender> msgCommand = asyncCommandManager.commandBuilder("msg", "message", "m", "w", "pm", "dm")
                .permission("chatty.pm")
                .argument(StringArgument.<CommandSender>builder("target")
                        .single()
                        .withSuggestionsProvider(pmSuggestionsProvider)
                        .build())
                .argument(StringArgument.greedy("message"))
                .handler(proxyingCommandHandlerMap.get("msg"))
                .build();

        Command<CommandSender> replyCommand = asyncCommandManager.commandBuilder("reply", "r")
                .permission("chatty.pm")
                .argument(StringArgument.greedy("message"))
                .handler(proxyingCommandHandlerMap.get("reply"))
                .build();

        asyncCommandManager
                .command(msgCommand)
                .command(replyCommand);
    }

    private void registerProxyingHandler(String commandName, CommandExecutionHandler<CommandSender> executionHandler) {
        proxyingCommandHandlerMap.compute(commandName, (k, v) -> {
            if (v == null) {
                return new ProxyingCommandHandler<>(executionHandler);
            } else {
                v.setBackendHandler(executionHandler);
                return v;
            }
        });
    }

    @Override
    public void onDisable() {
        unregisterAllCommands(syncCommandManager);
        unregisterAllCommands(asyncCommandManager);
        try {
            closeResources();
        } catch (IOException e) {
            getLogger().log(Level.SEVERE, "Cannot gracefully shutdown Chatty", e);
        }
    }

    private static void unregisterAllCommands(BukkitCommandManager<CommandSender> commandManager) {
        for (Node<CommandArgument<CommandSender, ?>> node : commandManager.commandTree().getRootNodes()) {
            //noinspection DataFlowIssue
            commandManager.deleteRootCommand(node.getValue().getName());
        }
    }

    private static boolean isUseNativeAdventurePlatform() {
        return PaperUtil.isPaper() && PaperUtil.isSupportAdventure();
    }

}
