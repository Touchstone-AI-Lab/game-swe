package io.gamecodebench.harness;

import java.util.List;
import org.bukkit.command.ConsoleCommandSender;

/**
 * A console-like command sender that records everything sent to it. Instances are
 * {@link java.lang.reflect.Proxy} objects created by {@link GcbSenders#recording()};
 * {@code getName()} is {@code "GCB"}, every permission check passes and {@code isOp()} is true.
 */
public interface RecordingSender extends ConsoleCommandSender {

    /** Messages recorded so far, as plain text, in order. */
    List<String> messages();

    /** Forgets every recorded message. */
    void clear();
}
