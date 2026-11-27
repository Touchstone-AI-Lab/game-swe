package io.gamecodebench.harness;

import java.util.Objects;
import org.bukkit.Bukkit;
import org.bukkit.event.Event;

/** Fires an event through the plugin manager and hands it back for inspection. */
public final class GcbEvents {

    private GcbEvents() {
    }

    public static <E extends Event> E call(E event) {
        Bukkit.getPluginManager().callEvent(Objects.requireNonNull(event, "event"));
        return event;
    }
}
