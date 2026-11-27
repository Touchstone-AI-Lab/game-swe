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
import org.bukkit.plugin.Plugin;
import ru.brikster.chatty.api.ChattyApi;
import ru.brikster.chatty.api.chat.Chat;

/**
 * Live-server grader for the Chatty chat-command reload repair: chat commands declared in
 * chats.yml must follow the file on {@code /chatty reload}. Every case is player-free. The
 * server starts with a seeded chats.yml whose two shipped chats declare commands; later
 * configurations are written into the plugin's data folder and applied through the plugin's
 * own reload command dispatched from a recording console sender.
 */
public final class ChattyChatCommandsSuite implements GcbSuite {

    private static final String PLUGIN = "Chatty";
    private static final String RELOAD_SUCCESS = "Plugin successfully reloaded!";
    private static final String RELOAD_ERROR = "Error while reloading plugin";

    // Declared by tests/seed/Chatty/chats.yml, present before the plugin enables.
    private static final String LOCAL_COMMAND = "gcblocal";
    private static final String LOCAL_ALIAS = "gcbl";
    private static final String GLOBAL_COMMAND = "gcbglobal";
    // Added and renamed by the suite through chats.yml + /chatty reload.
    private static final String ADDED_CHAT = "gcbadded";
    private static final String ADDED_COMMAND = "gcbadd";
    private static final String ADDED_ALIAS = "gcba";
    private static final String RENAMED_GLOBAL_COMMAND = "gcbworld";
    // Declared at start-up and removed by the suite in the last step.
    private static final String STAFF_CHAT = "gcbstaff";
    private static final String STAFF_COMMAND = "gcbstaff";

    /** chats.yml with the seeded commands, optionally an extra chat and a renamed global command. */
    private static String chatsYaml(String globalCommand, boolean withAddedChat) {
        return chatsYaml(globalCommand, withAddedChat, true);
    }

    private static String chatsYaml(String globalCommand, boolean withAddedChat, boolean withStaffChat) {
        StringBuilder yaml = new StringBuilder()
                .append("chats:\n")
                .append("  local:\n")
                .append("    display-name: Local\n")
                .append("    format: '&7[&bLocal&7] &r{prefix}{player}{suffix}&8: &f{message}'\n")
                .append("    symbol: ''\n")
                .append("    range: 200\n")
                .append("    command: ").append(LOCAL_COMMAND).append('\n')
                .append("    aliases:\n")
                .append("      - ").append(LOCAL_ALIAS).append('\n')
                .append("  global:\n")
                .append("    display-name: Global\n")
                .append("    format: '&7[&6Global&7] &r{prefix}{player}{suffix}&8: &f{message}'\n")
                .append("    symbol: '!'\n")
                .append("    range: -2\n")
                .append("    command: ").append(globalCommand).append('\n')
                .append("    aliases: []\n");
        if (withStaffChat) {
            yaml.append("  ").append(STAFF_CHAT).append(":\n")
                    .append("    display-name: Staff\n")
                    .append("    format: '&7[&cStaff&7] &r{prefix}{player}{suffix}&8: &f{message}'\n")
                    .append("    symbol: '%'\n")
                    .append("    range: -2\n")
                    .append("    command: ").append(STAFF_COMMAND).append('\n')
                    .append("    aliases: []\n");
        }
        if (withAddedChat) {
            yaml.append("  ").append(ADDED_CHAT).append(":\n")
                    .append("    display-name: Added\n")
                    .append("    format: '&7[&aAdded&7] &r{prefix}{player}{suffix}&8: &f{message}'\n")
                    .append("    symbol: '#'\n")
                    .append("    range: -2\n")
                    .append("    command: ").append(ADDED_COMMAND).append('\n')
                    .append("    aliases:\n")
                    .append("      - ").append(ADDED_ALIAS).append('\n');
        }
        return yaml.toString();
    }

    // --- helpers -----------------------------------------------------------------------------

    private static Plugin chatty() {
        Plugin plugin = Bukkit.getPluginManager().getPlugin(PLUGIN);
        GcbAssert.notNull(plugin, "the Chatty plugin must be loaded");
        return plugin;
    }

    private static void writeChats(String content) throws IOException {
        Path file = chatty().getDataFolder().toPath().resolve("chats.yml");
        Files.createDirectories(file.getParent());
        Files.writeString(file, content, StandardCharsets.UTF_8);
    }

    private static void reload(String context) {
        RecordingSender sender = GcbSenders.recording();
        GcbCommands.dispatch(sender, "chatty reload");
        List<String> messages = sender.messages();
        GcbAssert.isTrue(messages.stream().anyMatch(m -> m.contains(RELOAD_SUCCESS)),
                "/chatty reload must answer \"" + RELOAD_SUCCESS + "\" " + context + ", got " + messages);
        GcbAssert.isFalse(messages.stream().anyMatch(m -> m.contains(RELOAD_ERROR)),
                "/chatty reload must not report an error " + context + ", got " + messages);
    }

    /** The command registered under {@code name}, or null when the name is not in the command map. */
    private static Command registered(String name) {
        return Bukkit.getCommandMap().getCommand(name);
    }

    private static void assertOwnedByChatty(String name, String context) {
        Command command = registered(name);
        GcbAssert.notNull(command, "/" + name + " must be registered in the server command map " + context);
        GcbAssert.isTrue(command instanceof PluginIdentifiableCommand,
                "/" + name + " must be a plugin command " + context + ", got " + command.getClass().getName());
        Plugin owner = ((PluginIdentifiableCommand) command).getPlugin();
        GcbAssert.isTrue(owner != null && PLUGIN.equals(owner.getName()),
                "/" + name + " must be owned by Chatty " + context + ", got " + (owner == null ? null : owner.getName()));
    }

    /**
     * Dispatches {@code /<name> gcb message} from a console sender. A chat command is player-only,
     * so a handled dispatch returns true and answers the sender; an unregistered name returns
     * false without any reply.
     */
    private static void assertHandled(String name, String context) {
        RecordingSender sender = GcbSenders.recording();
        boolean dispatched = GcbCommands.dispatch(sender, name + " gcb message");
        GcbAssert.isTrue(dispatched, "/" + name + " must be dispatched to a registered command " + context);
        List<String> messages = sender.messages();
        GcbAssert.isFalse(messages.isEmpty(),
                "/" + name + " must answer the console sender through the plugin's chat command " + context);
        GcbAssert.isFalse(messages.stream().anyMatch(m -> m.contains("Unknown command")),
                "/" + name + " must not be reported as unknown " + context + ", got " + messages);
    }

    private static void assertRegisteredAndHandled(String name, String context) {
        assertOwnedByChatty(name, context);
        assertHandled(name, context);
    }

    // --- cases -------------------------------------------------------------------------------

    @GcbCase(value = "plugin is enabled", order = 0)
    public void pluginIsEnabled() {
        GcbAssert.isTrue(Bukkit.getPluginManager().isPluginEnabled(PLUGIN), "Chatty must be enabled");
        Map<String, Chat> chats = ChattyApi.instance().getChats();
        GcbAssert.isTrue(chats.containsKey("local") && chats.containsKey("global"),
                "the seeded chats.yml must register the local and global chats, got " + chats.keySet());
        assertOwnedByChatty("chatty", "at start-up");
    }

    @GcbCase(value = "chat commands declared at startup are registered", order = 1)
    public void startupCommandsAreRegistered() {
        assertRegisteredAndHandled(LOCAL_COMMAND, "at start-up");
        assertRegisteredAndHandled(LOCAL_ALIAS, "at start-up (alias of /" + LOCAL_COMMAND + ")");
        assertRegisteredAndHandled(GLOBAL_COMMAND, "at start-up");
        assertRegisteredAndHandled(STAFF_COMMAND, "at start-up");
    }

    @GcbCase(value = "chat commands survive a reload with an unchanged configuration", order = 2)
    public void unchangedReloadKeepsCommands() {
        reload("with an unchanged chats.yml");
        assertRegisteredAndHandled(LOCAL_COMMAND, "after a reload with an unchanged chats.yml");
        assertRegisteredAndHandled(LOCAL_ALIAS, "after a reload with an unchanged chats.yml (alias)");
        assertRegisteredAndHandled(GLOBAL_COMMAND, "after a reload with an unchanged chats.yml");
    }

    @GcbCase(value = "chat command added in chats.yml is registered by chatty reload", order = 3)
    public void addedCommandIsRegistered() throws IOException {
        writeChats(chatsYaml(GLOBAL_COMMAND, true));
        reload("after adding the " + ADDED_CHAT + " chat to chats.yml");
        assertRegisteredAndHandled(ADDED_COMMAND, "after adding it to chats.yml and reloading");
        assertRegisteredAndHandled(ADDED_ALIAS, "after adding it to chats.yml and reloading (alias)");
        assertRegisteredAndHandled(LOCAL_COMMAND, "after another chat's command was added");
    }

    @GcbCase(value = "chat registry lists the chat added in chats.yml", order = 4)
    public void registryListsAddedChat() {
        Map<String, Chat> chats = ChattyApi.instance().getChats();
        Chat added = chats.get(ADDED_CHAT);
        GcbAssert.notNull(added, "the chat registry must list " + ADDED_CHAT + " after the reload, got " + chats.keySet());
        GcbAssert.notNull(added.getCommand(), "the added chat must expose its command through the API");
        GcbAssert.equals(ADDED_COMMAND, added.getCommand().getName(), "the added chat's command name");
        GcbAssert.isTrue(chats.containsKey("local") && chats.containsKey("global"),
                "the shipped chats must still be registered, got " + chats.keySet());
    }

    @GcbCase(value = "renamed chat command drops its old name after chatty reload", order = 5)
    public void renamedCommandDropsOldName() throws IOException {
        writeChats(chatsYaml(RENAMED_GLOBAL_COMMAND, true));
        reload("after renaming the global chat command");
        assertRegisteredAndHandled(RENAMED_GLOBAL_COMMAND, "after renaming the global chat command and reloading");
        GcbAssert.isNull(registered(GLOBAL_COMMAND),
                "/" + GLOBAL_COMMAND + " must no longer be registered after the global chat command was renamed");
        assertRegisteredAndHandled(LOCAL_COMMAND, "after another chat's command was renamed");
    }

    @GcbCase(value = "removed chat command is unregistered by chatty reload", order = 6)
    public void removedCommandIsUnregistered() throws IOException {
        writeChats(chatsYaml(RENAMED_GLOBAL_COMMAND, true, false));
        reload("after removing the " + STAFF_CHAT + " chat from chats.yml");
        GcbAssert.isFalse(ChattyApi.instance().getChats().containsKey(STAFF_CHAT),
                "the chat registry must no longer list " + STAFF_CHAT);
        GcbAssert.isNull(registered(STAFF_COMMAND),
                "/" + STAFF_COMMAND + " must no longer be registered after its chat was removed from chats.yml");
        RecordingSender sender = GcbSenders.recording();
        GcbAssert.isFalse(GcbCommands.dispatch(sender, STAFF_COMMAND + " gcb message"),
                "/" + STAFF_COMMAND + " must no longer be dispatched to a command after its chat was removed");
        assertRegisteredAndHandled(LOCAL_COMMAND, "after another chat was removed");
        assertRegisteredAndHandled(LOCAL_ALIAS, "after another chat was removed (alias)");
    }
}
