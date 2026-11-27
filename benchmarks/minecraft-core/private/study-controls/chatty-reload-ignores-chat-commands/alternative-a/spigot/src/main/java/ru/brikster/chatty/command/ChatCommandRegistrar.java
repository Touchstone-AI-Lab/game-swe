package ru.brikster.chatty.command;

import cloud.commandframework.arguments.standard.StringArgument;
import cloud.commandframework.bukkit.BukkitCommandManager;
import cloud.commandframework.execution.CommandExecutionHandler;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.command.PluginIdentifiableCommand;
import org.bukkit.command.SimpleCommandMap;
import org.bukkit.entity.Player;
import org.bukkit.plugin.Plugin;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;
import ru.brikster.chatty.api.chat.Chat;
import ru.brikster.chatty.api.chat.command.ChatCommand;

import java.lang.reflect.Field;
import java.util.Collection;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.function.Supplier;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Keeps the chat commands declared in {@code chats.yml} registered on the command manager.
 * <p>
 * {@link #apply(Collection)} runs when the plugin enables and again after every
 * {@code /chatty reload}: a command that is no longer declared (or whose aliases changed)
 * is unregistered, a newly declared command is registered, and a command whose
 * declaration did not change is left registered as it is. The chat a command writes
 * into and the handler that executes it are looked up when the command runs, so a
 * command kept across a reload always serves the reloaded configuration.
 */
public final class ChatCommandRegistrar {

    private final Plugin plugin;
    private final Logger logger;
    private final BukkitCommandManager<CommandSender> commandManager;
    private final Supplier<? extends CommandExecutionHandler<CommandSender>> handlerSupplier;

    /** Registered chat commands by command name. */
    private final Map<String, Registration> registrations = new LinkedHashMap<>();

    public ChatCommandRegistrar(@NotNull Plugin plugin,
                                @NotNull BukkitCommandManager<CommandSender> commandManager,
                                @NotNull Supplier<? extends CommandExecutionHandler<CommandSender>> handlerSupplier) {
        this.plugin = plugin;
        this.logger = plugin.getLogger();
        this.commandManager = commandManager;
        this.handlerSupplier = handlerSupplier;
    }

    /**
     * Makes the registered chat commands match the commands declared by {@code chats}.
     */
    public synchronized void apply(@NotNull Collection<? extends Chat> chats) {
        Map<String, Chat> declared = new LinkedHashMap<>();
        for (Chat chat : chats) {
            ChatCommand chatCommand = chat.getCommand();
            if (chatCommand == null) {
                continue;
            }
            Chat owner = declared.putIfAbsent(chatCommand.getName(), chat);
            if (owner != null) {
                logger.log(Level.WARNING, "Chats \"{0}\" and \"{1}\" both declare the command /{2},"
                                + " so it is registered for chat \"{0}\" only",
                        new Object[]{owner.getId(), chat.getId(), chatCommand.getName()});
            }
        }

        // Unregister first, so that a name or alias released by an edit can be taken by another chat.
        Iterator<Registration> iterator = registrations.values().iterator();
        while (iterator.hasNext()) {
            Registration registration = iterator.next();
            Chat chat = declared.get(registration.name);
            if (chat != null && registration.aliases.equals(aliasesOf(chat.getCommand()))) {
                registration.chatId = chat.getId();
                continue;
            }
            unregister(registration);
            iterator.remove();
        }

        for (Chat chat : declared.values()) {
            if (!registrations.containsKey(chat.getCommand().getName())) {
                register(chat);
            }
        }
    }

    private void register(Chat chat) {
        ChatCommand chatCommand = chat.getCommand();
        Registration registration = new Registration(chatCommand.getName(), aliasesOf(chatCommand), chat.getId());
        try {
            commandManager.command(commandManager
                    .commandBuilder(registration.name, registration.aliases.toArray(new String[0]))
                    .senderType(Player.class)
                    .argument(StringArgument.<CommandSender>builder("message").greedy().asOptional().build())
                    .handler(context -> {
                        context.set("chat-id", registration.chatId);
                        handlerSupplier.get().execute(context);
                    })
                    .build());
        } catch (Throwable t) {
            logger.log(Level.SEVERE, "Cannot register chat command /" + registration.name
                    + " for chat \"" + chat.getId() + "\"", t);
            return;
        }
        Map<String, Command> knownCommands = knownCommands();
        if (knownCommands != null) {
            // The namespaced label always points at the command that was registered last.
            registration.bukkitCommand = ownCommand(knownCommands.get(namespaced(registration.name)));
        }
        registrations.put(registration.name, registration);
        logger.log(Level.INFO, "Registered chat command /{0} for chat \"{1}\"",
                new Object[]{registration.name, chat.getId()});
    }

    private void unregister(Registration registration) {
        try {
            commandManager.deleteRootCommand(registration.name);
        } catch (Throwable t) {
            logger.log(Level.WARNING, "Cannot unregister chat command /" + registration.name
                    + " from the command framework", t);
        }
        releaseLabels(registration);
        logger.log(Level.INFO, "Unregistered chat command /{0}", registration.name);
    }

    /**
     * Makes sure that no label of the server command map still points at the removed command,
     * in case the command framework could not detach every label itself.
     */
    private void releaseLabels(Registration registration) {
        Command command = registration.bukkitCommand;
        if (command == null) {
            return;
        }
        Map<String, Command> knownCommands = knownCommands();
        if (knownCommands == null) {
            return;
        }
        Set<String> labels = new LinkedHashSet<>();
        labels.add(registration.name);
        labels.addAll(registration.aliases);
        for (String label : registration.aliases) {
            labels.add(namespaced(label));
        }
        labels.add(namespaced(registration.name));
        for (String label : labels) {
            try {
                if (knownCommands.get(label) == command) {
                    knownCommands.remove(label);
                    logger.log(Level.FINE, "Released command label {0} of the removed chat command /{1}",
                            new Object[]{label, registration.name});
                }
            } catch (Throwable t) {
                logger.log(Level.FINE, "Cannot release command label " + label, t);
            }
        }
    }

    private @Nullable Command ownCommand(@Nullable Command command) {
        if (command instanceof PluginIdentifiableCommand
                && ((PluginIdentifiableCommand) command).getPlugin() == plugin) {
            return command;
        }
        return null;
    }

    private String namespaced(String label) {
        return plugin.getName().toLowerCase(Locale.ROOT) + ":" + label;
    }

    @SuppressWarnings("unchecked")
    private @Nullable Map<String, Command> knownCommands() {
        try {
            Object server = plugin.getServer();
            Object commandMap = server.getClass().getMethod("getCommandMap").invoke(server);
            if (!(commandMap instanceof SimpleCommandMap)) {
                return null;
            }
            Field field = SimpleCommandMap.class.getDeclaredField("knownCommands");
            field.setAccessible(true);
            return (Map<String, Command>) field.get(commandMap);
        } catch (Throwable t) {
            logger.log(Level.FINE, "Cannot access the server command map", t);
            return null;
        }
    }

    private static Set<String> aliasesOf(ChatCommand chatCommand) {
        return new LinkedHashSet<>(chatCommand.getAliases());
    }

    private static final class Registration {

        private final String name;
        private final Set<String> aliases;
        private volatile String chatId;
        private volatile Command bukkitCommand;

        private Registration(String name, Set<String> aliases, String chatId) {
            this.name = name;
            this.aliases = aliases;
            this.chatId = chatId;
        }

    }

}
