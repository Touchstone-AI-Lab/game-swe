package io.gamecodebench.harness;

/** Assertion failure raised by {@link GcbAssert}; its message is reported verbatim. */
public final class GcbAssertionError extends AssertionError {

    private static final long serialVersionUID = 1L;

    public GcbAssertionError(String message) {
        super(message == null ? "assertion failed" : message);
    }
}
