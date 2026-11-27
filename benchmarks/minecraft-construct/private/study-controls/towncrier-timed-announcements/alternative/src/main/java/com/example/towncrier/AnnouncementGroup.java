package com.example.towncrier;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Random;
import org.bukkit.scheduler.BukkitTask;

/**
 * A valid announcement group together with its in-memory state: the position of the next
 * message, the pause flag and the repeating timer.
 */
final class AnnouncementGroup {

    /** Permission used for delivery when a group does not name one. */
    static final String DEFAULT_BROADCAST_PERMISSION = "bukkit.broadcast.user";

    private final String name;
    private final boolean enabled;
    private final GroupOrder order;
    private final String permission;
    private final List<String> messages;
    private final Random random;
    private long intervalSeconds;
    private boolean paused;
    private BukkitTask timer;

    /** Message indices (0-based) of the current cycle, and the cursor of the next one. */
    private List<Integer> cycle = List.of();
    private int cursor;

    AnnouncementGroup(GroupDefinition definition, Random random) {
        this.name = definition.name();
        this.enabled = definition.enabled();
        this.order = definition.order();
        this.permission = definition.permission();
        this.messages = new ArrayList<>(definition.messages());
        this.intervalSeconds = definition.intervalSeconds();
        this.random = random;
    }

    String name() {
        return name;
    }

    boolean enabled() {
        return enabled;
    }

    GroupOrder order() {
        return order;
    }

    boolean paused() {
        return paused;
    }

    void setPaused(boolean paused) {
        this.paused = paused;
    }

    /** Whether this group should currently own a repeating timer. */
    boolean shouldRun() {
        return enabled && !paused;
    }

    long intervalSeconds() {
        return intervalSeconds;
    }

    void setIntervalSeconds(long intervalSeconds) {
        this.intervalSeconds = intervalSeconds;
    }

    /** The timer period in server ticks, clamped so the scheduler never overflows. */
    long periodTicks() {
        long maxSeconds = Integer.MAX_VALUE / 20L;
        return Math.min(intervalSeconds, maxSeconds) * 20L;
    }

    String broadcastPermission() {
        return permission.isEmpty() ? DEFAULT_BROADCAST_PERMISSION : permission;
    }

    List<String> messages() {
        return Collections.unmodifiableList(messages);
    }

    int messageCount() {
        return messages.size();
    }

    String message(int zeroBasedIndex) {
        return messages.get(zeroBasedIndex);
    }

    /** Appends a message and starts a new cycle; returns the new message count. */
    int addMessage(String text) {
        messages.add(text);
        restartCycle();
        return messages.size();
    }

    /** Removes the message at a 0-based index and starts a new cycle. */
    void removeMessage(int zeroBasedIndex) {
        messages.remove(zeroBasedIndex);
        restartCycle();
    }

    /** Returns the 0-based index of the message to announce now and moves the position on. */
    int advance() {
        if (cursor >= cycle.size()) {
            cycle = newCycle();
            cursor = 0;
        }
        return cycle.get(cursor++);
    }

    /** Makes the next announcement the start of a fresh cycle. */
    void restartCycle() {
        cycle = List.of();
        cursor = 0;
    }

    private List<Integer> newCycle() {
        List<Integer> indices = new ArrayList<>(messages.size());
        for (int i = 0; i < messages.size(); i++) {
            indices.add(i);
        }
        if (order == GroupOrder.SHUFFLE) {
            Collections.shuffle(indices, random);
        }
        return indices;
    }

    void replaceTimer(BukkitTask newTimer) {
        cancelTimer();
        this.timer = newTimer;
    }

    void cancelTimer() {
        if (timer != null) {
            timer.cancel();
            timer = null;
        }
    }
}
