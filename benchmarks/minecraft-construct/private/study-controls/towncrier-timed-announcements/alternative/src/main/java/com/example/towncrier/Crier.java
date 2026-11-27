package com.example.towncrier;

import java.util.Collection;
import java.util.Collections;
import java.util.Optional;
import java.util.Random;
import java.util.TreeMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.minimessage.MiniMessage;
import org.bukkit.Server;
import org.bukkit.plugin.Plugin;

/** Owns the loaded groups, their timers and the rendering and delivery of announcements. */
final class Crier {

    /** Outcome of {@link #pause} and {@link #resume}. */
    enum ToggleResult {
        DONE,
        UNCHANGED,
        DISABLED
    }

    private static final Pattern PLACEHOLDER = Pattern.compile("\\{(group|index|count|online|max)}");

    private final Plugin plugin;
    private final AnnouncementStore store;
    private final Random random = new Random();
    private final TreeMap<String, AnnouncementGroup> groups = new TreeMap<>();
    private String prefix = "";

    Crier(Plugin plugin, AnnouncementStore store) {
        this.plugin = plugin;
        this.store = store;
    }

    /**
     * Cancels every timer, re-reads the file, forgets every pause and position and starts every
     * enabled valid group again.
     */
    LoadResult reload() {
        stopAll();
        groups.clear();
        LoadResult result = store.load();
        prefix = result.prefix();
        // Timers are created in file order, so groups due on the same tick announce in file order.
        for (GroupDefinition definition : result.groups()) {
            AnnouncementGroup group = new AnnouncementGroup(definition, random);
            groups.put(group.name(), group);
            if (group.shouldRun()) {
                startTimer(group);
            }
        }
        return result;
    }

    /** Cancels the timer of every loaded group. */
    void stopAll() {
        for (AnnouncementGroup group : groups.values()) {
            group.cancelTimer();
        }
    }

    Optional<AnnouncementGroup> group(String name) {
        return Optional.ofNullable(groups.get(name));
    }

    /** Valid groups sorted by name. */
    Collection<AnnouncementGroup> groups() {
        return Collections.unmodifiableCollection(groups.values());
    }

    /** Broadcasts the group's next message and returns its 1-based index. */
    int announceNext(AnnouncementGroup group) {
        int index = group.advance();
        plugin.getServer().broadcast(render(group, index), group.broadcastPermission());
        return index + 1;
    }

    /** The announcement of the message at a 0-based index: prefix, message, placeholders, MiniMessage. */
    Component render(AnnouncementGroup group, int zeroBasedIndex) {
        Server server = plugin.getServer();
        String raw = prefix + group.message(zeroBasedIndex);
        Matcher matcher = PLACEHOLDER.matcher(raw);
        String text = matcher.replaceAll(match -> Matcher.quoteReplacement(switch (match.group(1)) {
            case "group" -> group.name();
            case "index" -> Integer.toString(zeroBasedIndex + 1);
            case "count" -> Integer.toString(group.messageCount());
            case "online" -> Integer.toString(server.getOnlinePlayers().size());
            case "max" -> Integer.toString(server.getMaxPlayers());
            default -> throw new IllegalStateException("Unexpected placeholder " + match.group());
        }));
        return MiniMessage.miniMessage().deserialize(text);
    }

    ToggleResult pause(AnnouncementGroup group) {
        if (!group.enabled()) {
            return ToggleResult.DISABLED;
        }
        if (group.paused()) {
            return ToggleResult.UNCHANGED;
        }
        group.setPaused(true);
        group.cancelTimer();
        return ToggleResult.DONE;
    }

    ToggleResult resume(AnnouncementGroup group) {
        if (!group.enabled()) {
            return ToggleResult.DISABLED;
        }
        if (!group.paused()) {
            return ToggleResult.UNCHANGED;
        }
        group.setPaused(false);
        startTimer(group);
        return ToggleResult.DONE;
    }

    /** Appends a message, saves the file and returns the new message count. */
    int addMessage(AnnouncementGroup group, String text) {
        int count = group.addMessage(text);
        store.saveMessages(group);
        return count;
    }

    /** Removes the message at a 1-based index (already validated) and saves the file. */
    void removeMessage(AnnouncementGroup group, int index) {
        group.removeMessage(index - 1);
        store.saveMessages(group);
    }

    /** Changes the interval, saves the file and restarts the timer of a running group. */
    void setInterval(AnnouncementGroup group, long seconds) {
        group.setIntervalSeconds(seconds);
        store.saveInterval(group);
        if (group.shouldRun()) {
            startTimer(group);
        }
    }

    private void startTimer(AnnouncementGroup group) {
        long period = group.periodTicks();
        group.replaceTimer(plugin.getServer().getScheduler()
                .runTaskTimer(plugin, () -> announceNext(group), period, period));
    }
}
