package com.example.towncrier;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Random;
import org.bukkit.Bukkit;
import org.bukkit.scheduler.BukkitTask;

/** One valid announcement group with its runtime state (position, pause, timer). */
public final class Group {

    private static final Random RANDOM = new Random();

    private final String name;
    private final boolean enabled;
    private final boolean shuffle;
    private final String permission;
    private final List<String> messages;
    private int interval;
    private List<Integer> cycle = List.of();
    private int position;
    private boolean paused;
    private BukkitTask task;
    private long remainingTicks;
    private long scheduledAtTick;

    public Group(String name, boolean enabled, int interval, boolean shuffle, String permission, List<String> messages) {
        this.name = name;
        this.enabled = enabled;
        this.interval = interval;
        this.shuffle = shuffle;
        this.permission = permission;
        this.messages = new ArrayList<>(messages);
        resetPosition();
    }

    public String name() {
        return name;
    }

    public boolean enabled() {
        return enabled;
    }

    public int interval() {
        return interval;
    }

    public void interval(int seconds) {
        this.interval = seconds;
        this.remainingTicks = seconds * 20L;
    }

    public String order() {
        return shuffle ? "shuffle" : "sequential";
    }

    public String permission() {
        return permission.isEmpty() ? "bukkit.broadcast.user" : permission;
    }

    public List<String> messages() {
        return Collections.unmodifiableList(messages);
    }

    public void addMessage(String message) {
        messages.add(message);
        resetPosition();
    }

    public void removeMessage(int index) {
        messages.remove(index);
        resetPosition();
    }

    public boolean paused() {
        return paused;
    }

    public void paused(boolean paused) {
        this.paused = paused;
    }

    public String state() {
        return !enabled ? "disabled" : paused ? "paused" : "running";
    }

    /** Starts a new cycle: list order, or a fresh random order for shuffle groups. */
    public void resetPosition() {
        List<Integer> order = new ArrayList<>();
        for (int i = 0; i < messages.size(); i++) {
            order.add(i);
        }
        if (shuffle) {
            Collections.shuffle(order, RANDOM);
        }
        cycle = order;
        position = 0;
    }

    /** The 0-based index of the next message; advances the position. */
    public int next() {
        if (position >= cycle.size()) {
            resetPosition();
        }
        return cycle.get(position++);
    }

    public void task(BukkitTask task) {
        task(task, interval * 20L);
    }

    public long remainingTicks() {
        return remainingTicks;
    }

    public void task(BukkitTask task, long delayTicks) {
        cancel();
        this.task = task;
        this.remainingTicks = delayTicks;
        this.scheduledAtTick = Bukkit.getCurrentTick();
    }

    public void pauseTimer() {
        if (task != null) {
            long elapsed = Math.max(0, Bukkit.getCurrentTick() - scheduledAtTick);
            remainingTicks = Math.max(1, remainingTicks - elapsed);
            cancel();
        }
    }

    public void timerFired() {
        remainingTicks = interval * 20L;
        scheduledAtTick = Bukkit.getCurrentTick();
    }

    public void cancel() {
        if (task != null) {
            task.cancel();
            task = null;
        }
    }
}
