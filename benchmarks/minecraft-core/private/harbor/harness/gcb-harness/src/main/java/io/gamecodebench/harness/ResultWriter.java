package io.gamecodebench.harness;

import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

/** Emits the {@code MINECRAFT_RESULT} envelope exactly once with a hand-rolled JSON encoder. */
final class ResultWriter {

    static final String HARNESS = "gcb-harness";
    static final String VERSION = "0.1.0";
    static final String PREFIX = "MINECRAFT_RESULT ";

    private final AtomicBoolean emitted = new AtomicBoolean();

    boolean emitted() {
        return emitted.get();
    }

    /** Prints the envelope; returns false (printing nothing) if one was already emitted. */
    boolean emit(String nonce, String candidate, String fatal, List<CaseResult> cases) {
        if (!emitted.compareAndSet(false, true)) {
            return false;
        }
        System.out.println(PREFIX + envelope(nonce, candidate, fatal, cases));
        System.out.flush();
        return true;
    }

    static String envelope(String nonce, String candidate, String fatal, List<CaseResult> cases) {
        int passed = 0;
        for (CaseResult result : cases) {
            if (result.passed()) {
                passed++;
            }
        }
        StringBuilder json = new StringBuilder(256);
        json.append('{');
        field(json, "harness", HARNESS).append(',');
        field(json, "version", VERSION).append(',');
        field(json, "nonce", nonce).append(',');
        field(json, "candidate", candidate).append(',');
        json.append("\"passed\":").append(passed).append(',');
        json.append("\"failed\":").append(cases.size() - passed).append(',');
        field(json, "fatal", fatal).append(',');
        json.append("\"cases\":[");
        for (int i = 0; i < cases.size(); i++) {
            CaseResult result = cases.get(i);
            if (i > 0) {
                json.append(',');
            }
            json.append('{');
            field(json, "name", result.name()).append(',');
            json.append("\"passed\":").append(result.passed()).append(',');
            field(json, "message", result.message()).append(',');
            json.append("\"ticks\":").append(result.ticks());
            json.append('}');
        }
        json.append("]}");
        return json.toString();
    }

    private static StringBuilder field(StringBuilder json, String key, String value) {
        quote(json, key).append(':');
        return value == null ? json.append("null") : quote(json, value);
    }

    static StringBuilder quote(StringBuilder json, String value) {
        json.append('"');
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            switch (c) {
                case '"' -> json.append("\\\"");
                case '\\' -> json.append("\\\\");
                case '\n' -> json.append("\\n");
                case '\r' -> json.append("\\r");
                case '\t' -> json.append("\\t");
                case '\b' -> json.append("\\b");
                case '\f' -> json.append("\\f");
                default -> {
                    if (c < 0x20 || c == 0x7f) {
                        json.append(String.format("\\u%04x", (int) c));
                    } else {
                        json.append(c);
                    }
                }
            }
        }
        return json.append('"');
    }
}
