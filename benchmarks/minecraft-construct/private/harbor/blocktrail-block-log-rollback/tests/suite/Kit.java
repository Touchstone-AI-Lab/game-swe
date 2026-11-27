package gcbtest.blocktrail;

import io.gamecodebench.harness.GcbAssert;
import io.gamecodebench.harness.GcbHarnessApi;
import java.io.File;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import org.bukkit.Bukkit;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.plugin.Plugin;

/** Grader helpers: command dispatch, data-folder files and line comparison. */
public final class Kit {

    private Kit() {
    }

    public static Plugin plugin() {
        return GcbHarnessApi.candidate();
    }

    /** Looks the command up in the server's command map and executes it as {@code sender}. */
    public static void dispatch(CommandSender sender, String line) {
        String[] words = line.strip().split(" +");
        String label = words[0].toLowerCase(Locale.ROOT);
        Command command = Bukkit.getCommandMap().getCommand(label);
        GcbAssert.notNull(command, "command /" + label + " is not registered");
        command.execute(sender, label, Arrays.copyOfRange(words, 1, words.length));
    }

    public static File file(String name) {
        return new File(plugin().getDataFolder(), name);
    }

    public static boolean exists(String name) {
        return file(name).isFile();
    }

    public static String read(String name) {
        try {
            return Files.readString(file(name).toPath(), StandardCharsets.UTF_8);
        } catch (IOException failure) {
            throw new UncheckedIOException(failure);
        }
    }

    public static byte[] bytes(String name) {
        try {
            File file = file(name);
            return file.isFile() ? Files.readAllBytes(file.toPath()) : new byte[0];
        } catch (IOException failure) {
            throw new UncheckedIOException(failure);
        }
    }

    /** Non-blank lines of a data file, or an empty list when it does not exist. */
    public static List<String> lines(String name) {
        if (!exists(name)) {
            return List.of();
        }
        return read(name).lines().filter(line -> !line.isBlank()).toList();
    }

    public static void write(String name, String content) {
        try {
            File file = file(name);
            file.getParentFile().mkdirs();
            Files.writeString(file.toPath(), content, StandardCharsets.UTF_8);
        } catch (IOException failure) {
            throw new UncheckedIOException(failure);
        }
    }

    public static void delete(String name) {
        File file = file(name);
        if (file.exists() && !file.delete()) {
            throw new IllegalStateException("could not delete " + file);
        }
    }

    public static YamlConfiguration yaml(String name) {
        GcbAssert.isTrue(exists(name), name + " exists in the data folder");
        YamlConfiguration yaml = new YamlConfiguration();
        try {
            yaml.loadFromString(read(name));
        } catch (org.bukkit.configuration.InvalidConfigurationException invalid) {
            GcbAssert.fail(name + " is not valid YAML: " + invalid.getMessage());
        }
        return yaml;
    }

    /** Asserts that {@code actual} equals the expected lines, in order. */
    public static void lines(List<String> actual, String what, String... expected) {
        GcbAssert.equals(List.of(expected), actual, what);
    }
}
