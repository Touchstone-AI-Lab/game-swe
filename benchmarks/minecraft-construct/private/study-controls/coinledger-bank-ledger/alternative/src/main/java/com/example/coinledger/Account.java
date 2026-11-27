package com.example.coinledger;

import java.util.Locale;
import java.util.regex.Pattern;

/** One bank account. Names are always stored in lower case; balances are whole cents. */
final class Account {

    private static final Pattern NAME = Pattern.compile("[A-Za-z0-9_]{3,16}");

    private final String name;
    private long balance;
    private boolean frozen;

    Account(String name, long balance, boolean frozen) {
        this.name = name;
        this.balance = balance;
        this.frozen = frozen;
    }

    /** Whether {@code text} is a syntactically valid account name (any case). */
    static boolean isValidName(String text) {
        return NAME.matcher(text).matches();
    }

    /** The canonical (lower-case) form of an account name. */
    static String normalize(String text) {
        return text.toLowerCase(Locale.ROOT);
    }

    String name() {
        return name;
    }

    long balance() {
        return balance;
    }

    boolean frozen() {
        return frozen;
    }

    void adjust(long deltaCents) {
        balance += deltaCents;
    }

    void setFrozen(boolean frozen) {
        this.frozen = frozen;
    }
}
