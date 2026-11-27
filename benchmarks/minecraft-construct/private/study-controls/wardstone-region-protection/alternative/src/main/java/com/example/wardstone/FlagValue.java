package com.example.wardstone;

import java.util.Locale;

/** The value a region sets a flag to. An unset flag has no value at all. */
enum FlagValue {
    ALLOW("allow"),
    DENY("deny");

    private final String id;

    FlagValue(String id) {
        this.id = id;
    }

    String id() {
        return id;
    }

    /** Looks a value up by id, ignoring case; returns {@code null} for anything else. */
    static FlagValue fromId(String text) {
        String wanted = text.toLowerCase(Locale.ROOT);
        for (FlagValue value : values()) {
            if (value.id.equals(wanted)) {
                return value;
            }
        }
        return null;
    }
}
