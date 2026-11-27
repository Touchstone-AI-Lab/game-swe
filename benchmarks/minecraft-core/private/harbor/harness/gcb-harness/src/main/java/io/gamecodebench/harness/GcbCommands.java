package io.gamecodebench.harness;

import java.util.Arrays;
import java.util.Locale;
import java.util.Objects;
import org.bukkit.Bukkit;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;

/**
 * Dispatches a command line.
 *
 * <p>Paper's {@code Bukkit.dispatchCommand} maps every {@code ConsoleCommandSender} to the real
 * server console before executing, so feedback to a proxy sender would be lost. For harness
 * proxies the command is therefore resolved from the command map and executed directly, while
 * vanilla (Brigadier) commands run through a Paper feedback-forwarding sender whose output is
 * copied into the proxy's message log.
 */
public final class GcbCommands {

    private static final String VANILLA_WRAPPER = "org.bukkit.craftbukkit.command.VanillaCommandWrapper";

    private GcbCommands() {
    }

    public static boolean dispatch(CommandSender sender, String line) {
        Objects.requireNonNull(sender, "sender");
        Objects.requireNonNull(line, "line");
        RecordingHandler handler = RecordingHandler.of(sender);
        if (handler == null) {
            return Bukkit.dispatchCommand(sender, line);
        }
        String[] words = line.strip().replaceFirst("^/", "").split("\\s+");
        if (words.length == 0 || words[0].isEmpty()) {
            return false;
        }
        Command command = Bukkit.getCommandMap().getCommand(words[0].toLowerCase(Locale.ENGLISH));
        if (command == null) {
            return false;
        }
        if (isVanillaWrapper(command.getClass())) {
            CommandSender forwarding = Bukkit.createCommandSender(
                component -> handler.record(RecordingHandler.plain(component)));
            return Bukkit.dispatchCommand(forwarding, String.join(" ", words));
        }
        return command.execute(sender, words[0], Arrays.copyOfRange(words, 1, words.length));
    }

    private static boolean isVanillaWrapper(Class<?> type) {
        for (Class<?> current = type; current != null; current = current.getSuperclass()) {
            if (current.getName().equals(VANILLA_WRAPPER)) {
                return true;
            }
        }
        return false;
    }
}
