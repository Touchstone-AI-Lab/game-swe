package io.gamecodebench.harness;

import java.util.Objects;

/** Minimal assertion helpers; every failure throws {@link GcbAssertionError}. */
public final class GcbAssert {

    private GcbAssert() {
    }

    public static void isTrue(boolean condition, String message) {
        if (!condition) {
            fail(message);
        }
    }

    public static void isFalse(boolean condition, String message) {
        if (condition) {
            fail(message);
        }
    }

    public static void equals(Object expected, Object actual, String message) {
        if (!valuesEqual(expected, actual)) {
            fail(message + " (expected <" + expected + "> but was <" + actual + ">)");
        }
    }

    public static void notNull(Object value, String message) {
        if (value == null) {
            fail(message);
        }
    }

    public static void isNull(Object value, String message) {
        if (value != null) {
            fail(message + " (was <" + value + ">)");
        }
    }

    public static <T extends Throwable> T throwsType(Class<T> type, GcbRunnable body, String message) {
        Objects.requireNonNull(type, "type");
        Objects.requireNonNull(body, "body");
        try {
            body.run();
        } catch (Throwable thrown) {
            if (type.isInstance(thrown)) {
                return type.cast(thrown);
            }
            throw new GcbAssertionError(message + " (expected " + type.getSimpleName()
                + " but got " + thrown.getClass().getSimpleName() + ": " + thrown.getMessage() + ")");
        }
        throw new GcbAssertionError(message + " (expected " + type.getSimpleName() + " but nothing was thrown)");
    }

    public static void fail(String message) {
        throw new GcbAssertionError(message);
    }

    // Numbers of different boxed types (e.g. Integer vs Long) compare by value.
    private static boolean valuesEqual(Object expected, Object actual) {
        if (expected instanceof Number left && actual instanceof Number right) {
            return Double.compare(left.doubleValue(), right.doubleValue()) == 0;
        }
        return Objects.equals(expected, actual);
    }
}
