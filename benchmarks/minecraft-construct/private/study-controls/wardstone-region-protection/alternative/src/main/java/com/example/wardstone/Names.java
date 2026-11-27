package com.example.wardstone;

import java.util.Locale;
import java.util.regex.Pattern;

/** Validation and normalisation of region and player names. */
final class Names {
    private static final Pattern REGION_NAME = Pattern.compile("[a-z0-9_-]{2,24}");
    private static final Pattern PLAYER_NAME = Pattern.compile("[A-Za-z0-9_]{3,16}");

    private Names() {
    }

    /** The lower-cased region name, or {@code null} when it is not a valid name. */
    static String region(String raw) {
        String lower = raw.toLowerCase(Locale.ROOT);
        return REGION_NAME.matcher(lower).matches() ? lower : null;
    }

    /** The lower-cased player name, or {@code null} when it is not a valid name. */
    static String player(String raw) {
        return PLAYER_NAME.matcher(raw).matches() ? raw.toLowerCase(Locale.ROOT) : null;
    }
}
