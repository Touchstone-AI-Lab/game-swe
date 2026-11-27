package io.gamecodebench.harness;

/** Outcome of one case as written to the result envelope. */
record CaseResult(String name, boolean passed, String message, int ticks) {

    static CaseResult pass(String name, int ticks) {
        return new CaseResult(name, true, "ok", ticks);
    }

    static CaseResult fail(String name, String message, int ticks) {
        return new CaseResult(name, false, message, ticks);
    }

    /** Assertion messages are reported verbatim; any other throwable as {@code Type: message}. */
    static String describe(Throwable thrown) {
        if (thrown instanceof GcbAssertionError) {
            return thrown.getMessage();
        }
        String type = thrown.getClass().getSimpleName();
        return thrown.getMessage() == null ? type : type + ": " + thrown.getMessage();
    }
}
