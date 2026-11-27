package com.example.coinledger;

import java.math.BigDecimal;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Whole-cent money helpers: command amounts, display and numeric settings. */
final class Money {

    private static final Pattern AMOUNT = Pattern.compile("([0-9]{1,9})(?:\\.([0-9]{1,2}))?");

    private Money() {
    }

    /**
     * Parses a command amount such as {@code 12}, {@code 12.5} or {@code 12.50} into cents.
     *
     * @return the amount in cents, or {@code -1} when the text is malformed or not positive
     */
    static long parseAmount(String text) {
        Matcher matcher = AMOUNT.matcher(text);
        if (!matcher.matches()) {
            return -1;
        }
        long cents = Long.parseLong(matcher.group(1)) * 100;
        String fraction = matcher.group(2);
        if (fraction != null) {
            cents += Long.parseLong(fraction) * (fraction.length() == 1 ? 10 : 1);
        }
        return cents > 0 ? cents : -1;
    }

    /** Formats cents as {@code <units>.<cc> <currency>}, e.g. {@code 1250.00 coins}. */
    static String format(long cents, String currency) {
        String sign = cents < 0 ? "-" : "";
        long abs = Math.abs(cents);
        long fraction = abs % 100;
        return sign + (abs / 100) + "." + (fraction < 10 ? "0" : "") + fraction + " " + currency;
    }

    /**
     * Converts a configured money value (a YAML number or numeric string with at most two
     * decimals, not negative) into cents.
     *
     * @return the cents, or {@code null} when the value is not a valid money setting
     */
    static Long settingCents(Object value) {
        BigDecimal decimal = decimal(value);
        if (decimal == null || decimal.signum() < 0 || decimal.stripTrailingZeros().scale() > 2) {
            return null;
        }
        try {
            return decimal.movePointRight(2).setScale(0).longValueExact();
        } catch (ArithmeticException tooLarge) {
            return null;
        }
    }

    /**
     * Converts a YAML number or numeric string holding a whole number into a {@code long}.
     *
     * @return the number, or {@code null} when the value is not a whole number
     */
    static Long wholeNumber(Object value) {
        BigDecimal decimal = decimal(value);
        if (decimal == null || decimal.stripTrailingZeros().scale() > 0) {
            return null;
        }
        try {
            return decimal.setScale(0).longValueExact();
        } catch (ArithmeticException tooLarge) {
            return null;
        }
    }

    private static BigDecimal decimal(Object value) {
        try {
            if (value instanceof Number number) {
                return new BigDecimal(number.toString());
            }
            if (value instanceof String text) {
                return new BigDecimal(text.trim());
            }
        } catch (NumberFormatException notNumeric) {
            return null;
        }
        return null;
    }
}
