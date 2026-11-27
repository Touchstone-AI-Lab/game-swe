package com.example.blocktrail;

import java.util.Locale;

/** The kind of block change, with its log key and the verb used in replies. */
enum ChangeAction {
    BREAK("break", "broke"),
    PLACE("place", "placed"),
    EXPLODE("explode", "exploded");

    private final String key;
    private final String verb;

    ChangeAction(String key, String verb) {
        this.key = key;
        this.verb = verb;
    }

    String key() {
        return key;
    }

    String verb() {
        return verb;
    }

    /** Returns the action whose log key is {@code key}, or {@code null}. */
    static ChangeAction fromKey(String key) {
        String normalized = key.toLowerCase(Locale.ROOT);
        for (ChangeAction action : values()) {
            if (action.key.equals(normalized)) {
                return action;
            }
        }
        return null;
    }
}
