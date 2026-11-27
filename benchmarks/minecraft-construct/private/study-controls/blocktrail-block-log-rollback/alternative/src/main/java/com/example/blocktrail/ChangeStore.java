package com.example.blocktrail;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.SeekableByteChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Iterator;
import java.util.List;
import java.util.NavigableMap;
import java.util.TreeMap;
import java.util.logging.Level;
import java.util.logging.Logger;
import org.bukkit.Material;

/**
 * The in-memory change log and its file {@code changes.log}. Every mutation is written to the
 * file before the method returns.
 */
final class ChangeStore {

    /** A change that is about to be recorded; the store assigns its id and time. */
    record Draft(String actor, ChangeAction action, String world, int x, int y, int z,
                 Material from, Material to, String fromData, String toData) {
    }

    private final Path file;
    private final Logger logger;
    private final NavigableMap<Long, Change> changes = new TreeMap<>();
    private long nextId = 1;

    ChangeStore(Path file, Logger logger) {
        this.file = file;
        this.logger = logger;
    }

    int size() {
        return changes.size();
    }

    /** All changes, highest id first. */
    List<Change> newestFirst() {
        return new ArrayList<>(changes.descendingMap().values());
    }

    /** Replaces the in-memory state with the contents of {@code changes.log}. */
    void load() {
        changes.clear();
        List<Long> undone = new ArrayList<>();
        for (String raw : readLines()) {
            String line = raw.trim();
            if (line.isEmpty()) {
                continue;
            }
            Long undoId = Change.parseUndoId(line);
            if (undoId != null) {
                undone.add(undoId);
                continue;
            }
            Change change = Change.parse(line);
            if (change != null) {
                changes.put(change.id(), change);
            }
        }
        for (Long id : undone) {
            Change change = changes.get(id);
            if (change != null) {
                change.markRolledBack();
            }
        }
        nextId = changes.isEmpty() ? 1 : changes.lastKey() + 1;
    }

    /** Records the drafts in order, with consecutive ids, and appends their log lines. */
    void record(List<Draft> drafts) {
        if (drafts.isEmpty()) {
            return;
        }
        long now = System.currentTimeMillis();
        List<String> lines = new ArrayList<>(drafts.size());
        for (Draft draft : drafts) {
            Change change = new Change(nextId++, now, draft.actor(), draft.action(), draft.world(),
                    draft.x(), draft.y(), draft.z(),
                    Materials.key(draft.from()), Materials.key(draft.to()), draft.fromData(), draft.toData());
            changes.put(change.id(), change);
            lines.add(change.toLogLine());
        }
        append(lines);
    }

    /** Marks the changes rolled back and appends one {@code undo} line each, in the given order. */
    void markRolledBack(Collection<Change> rolledBack) {
        List<String> lines = new ArrayList<>(rolledBack.size());
        for (Change change : rolledBack) {
            change.markRolledBack();
            lines.add(change.toUndoLine());
        }
        append(lines);
    }

    /** Removes every change recorded before {@code cutoff} and rewrites the log; returns the count. */
    int purgeBefore(long cutoff) {
        int removed = 0;
        Iterator<Change> it = changes.values().iterator();
        while (it.hasNext()) {
            if (it.next().time() < cutoff) {
                it.remove();
                removed++;
            }
        }
        List<String> lines = new ArrayList<>();
        for (Change change : changes.values()) {
            lines.add(change.toLogLine());
        }
        for (Change change : changes.values()) {
            if (change.rolledBack()) {
                lines.add(change.toUndoLine());
            }
        }
        rewrite(lines);
        return removed;
    }

    private List<String> readLines() {
        if (!Files.isRegularFile(file)) {
            return List.of();
        }
        try {
            String content = new String(Files.readAllBytes(file), StandardCharsets.UTF_8);
            return content.lines().toList();
        } catch (IOException e) {
            logger.log(Level.SEVERE, "Could not read " + file.getFileName(), e);
            return List.of();
        }
    }

    private void append(List<String> lines) {
        if (lines.isEmpty()) {
            return;
        }
        StringBuilder text = new StringBuilder();
        try {
            Files.createDirectories(file.getParent());
            if (lacksFinalNewline()) {
                text.append('\n');
            }
            for (String line : lines) {
                text.append(line).append('\n');
            }
            Files.write(file, text.toString().getBytes(StandardCharsets.UTF_8),
                    StandardOpenOption.CREATE, StandardOpenOption.WRITE, StandardOpenOption.APPEND);
        } catch (IOException e) {
            logger.log(Level.SEVERE, "Could not append to " + file.getFileName(), e);
        }
    }

    private void rewrite(List<String> lines) {
        StringBuilder text = new StringBuilder();
        for (String line : lines) {
            text.append(line).append('\n');
        }
        try {
            Files.createDirectories(file.getParent());
            Files.write(file, text.toString().getBytes(StandardCharsets.UTF_8),
                    StandardOpenOption.CREATE, StandardOpenOption.WRITE,
                    StandardOpenOption.TRUNCATE_EXISTING);
        } catch (IOException e) {
            logger.log(Level.SEVERE, "Could not rewrite " + file.getFileName(), e);
        }
    }

    /** Whether the file exists, is not empty and does not end with a line break. */
    private boolean lacksFinalNewline() throws IOException {
        if (!Files.isRegularFile(file)) {
            return false;
        }
        try (SeekableByteChannel channel = Files.newByteChannel(file, StandardOpenOption.READ)) {
            long size = channel.size();
            if (size == 0) {
                return false;
            }
            channel.position(size - 1);
            ByteBuffer last = ByteBuffer.allocate(1);
            if (channel.read(last) != 1) {
                return false;
            }
            return last.get(0) != '\n';
        }
    }
}
