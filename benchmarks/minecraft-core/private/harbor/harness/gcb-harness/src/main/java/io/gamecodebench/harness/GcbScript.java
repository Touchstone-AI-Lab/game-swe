package io.gamecodebench.harness;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.function.BooleanSupplier;

/**
 * Script built by a ticked case. The runner advances it once per server tick: at most one
 * {@link #step} body runs per tick, while waits only consume ticks. Steps may append further
 * steps while running.
 */
public final class GcbScript {

    private sealed interface Item permits Step, Wait, Until {
    }

    private record Step(GcbRunnable body) implements Item {
    }

    private static final class Wait implements Item {
        private int remaining;

        private Wait(int ticks) {
            this.remaining = ticks;
        }
    }

    private record Until(BooleanSupplier condition, String description) implements Item {
    }

    private final List<Item> items = new ArrayList<>();
    private int cursor;

    GcbScript() {
    }

    public void step(GcbRunnable body) {
        items.add(new Step(Objects.requireNonNull(body, "body")));
    }

    public void waitTicks(int ticks) {
        if (ticks < 0) {
            throw new IllegalArgumentException("ticks must be >= 0, got " + ticks);
        }
        items.add(new Wait(ticks));
    }

    public void waitUntil(BooleanSupplier condition, String description) {
        items.add(new Until(Objects.requireNonNull(condition, "condition"), String.valueOf(description)));
    }

    /**
     * Advances by one tick. Returns true once every item has completed.
     * A wait that ends on this tick lets the following step run in the same tick.
     */
    boolean advance() throws Exception {
        while (cursor < items.size()) {
            Item item = items.get(cursor);
            if (item instanceof Step step) {
                cursor++;
                step.body().run();
                return cursor >= items.size();
            }
            if (item instanceof Wait wait) {
                if (--wait.remaining > 0) {
                    return false;
                }
                cursor++;
            } else if (item instanceof Until until) {
                if (!until.condition().getAsBoolean()) {
                    return false;
                }
                cursor++;
            }
        }
        return true;
    }

    /** Human-readable position, used in hang messages. */
    String pendingDescription() {
        if (cursor >= items.size()) {
            return "complete";
        }
        Item item = items.get(cursor);
        if (item instanceof Until until) {
            return "waiting until: " + until.description();
        }
        if (item instanceof Wait wait) {
            return "waiting " + wait.remaining + " more ticks";
        }
        return "step " + (cursor + 1) + " of " + items.size();
    }
}
