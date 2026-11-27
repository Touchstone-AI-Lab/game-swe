package com.example.coinledger;

import java.math.BigDecimal;
import java.util.regex.Pattern;

/** Money is kept in whole cents; this class parses command input and formats amounts. */
public final class Money {

    private static final Pattern AMOUNT = Pattern.compile("^[0-9]{1,9}(\\.[0-9]{1,2})?$");

    private Money() {
    }

    /** Parses a command amount into cents, or returns -1 when it is not a valid positive amount. */
    public static long parse(String text) {
        if (text == null || !AMOUNT.matcher(text).matches()) {
            return -1;
        }
        int dot = text.indexOf('.');
        long units = Long.parseLong(dot < 0 ? text : text.substring(0, dot));
        long cents = 0;
        if (dot >= 0) {
            String fraction = text.substring(dot + 1);
            cents = Long.parseLong(fraction.length() == 1 ? fraction + "0" : fraction);
        }
        long total = units * 100 + cents;
        return total > 0 ? total : -1;
    }

    /** Converts a configuration value (a number or a string with up to two decimals) to cents. */
    public static long fromConfig(Object value, long fallback) {
        if (value == null) {
            return fallback;
        }
        try {
            BigDecimal decimal = new BigDecimal(value.toString().trim());
            return decimal.movePointRight(2).setScale(0, java.math.RoundingMode.DOWN).longValueExact();
        } catch (NumberFormatException | ArithmeticException invalid) {
            return fallback;
        }
    }

    /** Formats cents as {@code 12.50} without currency. */
    public static String plain(long cents) {
        String sign = cents < 0 ? "-" : "";
        long absolute = Math.abs(cents);
        return sign + (absolute / 100) + "." + String.format("%02d", absolute % 100);
    }

    /** Formats cents with the currency, e.g. {@code 12.50 coins}. */
    public static String format(long cents, String currency) {
        return plain(cents) + " " + currency;
    }
}
