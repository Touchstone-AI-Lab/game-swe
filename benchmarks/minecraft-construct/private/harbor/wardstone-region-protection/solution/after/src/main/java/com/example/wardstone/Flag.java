package com.example.wardstone;

import java.util.Locale;

/** The protection flags a region can set. */
public enum Flag {
    BLOCK_BREAK("block-break"),
    BLOCK_PLACE("block-place"),
    EXPLOSION("explosion"),
    FIRE("fire");

    private final String key;

    Flag(String key) {
        this.key = key;
    }

    public String key() {
        return key;
    }

    public static Flag fromKey(String key) {
        String wanted = key.toLowerCase(Locale.ROOT);
        for (Flag flag : values()) {
            if (flag.key.equals(wanted)) {
                return flag;
            }
        }
        return null;
    }
}
