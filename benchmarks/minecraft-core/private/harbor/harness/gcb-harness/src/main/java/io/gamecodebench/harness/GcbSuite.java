package io.gamecodebench.harness;

import org.bukkit.plugin.java.JavaPlugin;

/** Marker for a grader suite; one instance is created per suite class. */
public interface GcbSuite {

    /** Called once with the grader plugin before the suite's cases are registered. */
    default void onEnable(JavaPlugin grader) {
    }
}
