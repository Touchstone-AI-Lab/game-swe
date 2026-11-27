package com.example.wardstone;

import java.util.Locale;

/**
 * The protection flags a region can set. The constants are declared in the
 * alphabetical order of their ids, so enum order is also display order.
 */
enum Flag {
    BLOCK_BREAK("block-break"),
    BLOCK_PLACE("block-place"),
    EXPLOSION("explosion"),
    FIRE("fire");

    private final String id;

    Flag(String id) {
        this.id = id;
    }

    String id() {
        return id;
    }

    /** Looks a flag up by id, ignoring case; returns {@code null} for an unknown id. */
    static Flag fromId(String text) {
        String wanted = text.toLowerCase(Locale.ROOT);
        for (Flag flag : values()) {
            if (flag.id.equals(wanted)) {
                return flag;
            }
        }
        return null;
    }
}
