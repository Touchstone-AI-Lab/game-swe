package com.example.blocktrail;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/** changes.log and the changes it holds, in id order. */
public final class TrailStore {

    private final File file;
    private final Map<Long, Change> changes = new TreeMap<>();
    private long nextId = 1;

    public TrailStore(File dataFolder) {
        this.file = new File(dataFolder, "changes.log");
    }

    public void load() throws IOException {
        changes.clear();
        List<Long> undone = new ArrayList<>();
        if (file.isFile()) {
            for (String line : Files.readAllLines(file.toPath(), StandardCharsets.UTF_8)) {
                String trimmed = line.trim();
                if (trimmed.isEmpty()) {
                    continue;
                }
                if (trimmed.startsWith("undo;")) {
                    try {
                        undone.add(Long.parseLong(trimmed.substring(5).trim()));
                    } catch (NumberFormatException ignored) {
                        // malformed undo lines are ignored
                    }
                    continue;
                }
                Change change = Change.parse(trimmed);
                if (change != null) {
                    changes.put(change.id(), change);
                }
            }
        }
        for (long id : undone) {
            Change change = changes.get(id);
            if (change != null) {
                change.rolledBack(true);
            }
        }
        nextId = changes.isEmpty() ? 1 : Collections.max(changes.keySet()) + 1;
    }

    public long nextId() {
        return nextId++;
    }

    public List<Change> all() {
        return new ArrayList<>(changes.values());
    }

    public int size() {
        return changes.size();
    }

    public void add(Change change) throws IOException {
        changes.put(change.id(), change);
        append(change.toLine());
    }

    public void markRolledBack(Change change) throws IOException {
        change.rolledBack(true);
        append("undo;" + change.id());
    }

    /** Removes changes recorded before {@code cutoff}; returns how many were removed. */
    public int purgeBefore(long cutoff) throws IOException {
        int removed = 0;
        for (var iterator = changes.values().iterator(); iterator.hasNext(); ) {
            if (iterator.next().time() < cutoff) {
                iterator.remove();
                removed++;
            }
        }
        StringBuilder content = new StringBuilder();
        for (Change change : changes.values()) {
            content.append(change.toLine()).append('\n');
        }
        for (Change change : changes.values()) {
            if (change.rolledBack()) {
                content.append("undo;").append(change.id()).append('\n');
            }
        }
        file.getParentFile().mkdirs();
        Files.writeString(file.toPath(), content.toString(), StandardCharsets.UTF_8);
        return removed;
    }

    private void append(String line) throws IOException {
        file.getParentFile().mkdirs();
        Files.writeString(file.toPath(), line + "\n", StandardCharsets.UTF_8,
            StandardOpenOption.CREATE, StandardOpenOption.APPEND);
    }
}
