package com.example.blocktrail;

import java.util.Locale;

/** What happened to a block. */
public enum Action {
    BREAK("broke"),
    PLACE("placed"),
    EXPLODE("exploded");

    private final String verb;

    Action(String verb) {
        this.verb = verb;
    }

    public String verb() {
        return verb;
    }

    public String key() {
        return name().toLowerCase(Locale.ROOT);
    }

    public static Action fromKey(String key) {
        for (Action action : values()) {
            if (action.key().equals(key)) {
                return action;
            }
        }
        return null;
    }
}
