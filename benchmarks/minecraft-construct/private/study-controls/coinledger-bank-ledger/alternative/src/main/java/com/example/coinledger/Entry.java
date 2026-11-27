package com.example.coinledger;

import java.util.Locale;

/**
 * One audit-log entry.
 *
 * @param number       the entry number (1, 2, 3, ...)
 * @param type         what happened
 * @param account      the account the entry is about (the sender of a transfer)
 * @param counterparty the recipient of a transfer, otherwise {@code null}
 * @param amount       the amount in cents ({@code 0} for freeze and unfreeze)
 * @param fee          the transfer fee in cents ({@code 0} for everything else)
 * @param feeAccount   the account that received the fee when the fee is positive, otherwise
 *                     {@code null}
 */
record Entry(long number, Type type, String account, String counterparty, long amount, long fee,
             String feeAccount) {

    enum Type {
        OPEN, DEPOSIT, WITHDRAW, TRANSFER, FREEZE, UNFREEZE
    }

    private static final String NONE = "-";
    private static final char SEPARATOR = '|';

    /** Whether the entry involves {@code name} as account, counterparty or fee account. */
    boolean involves(String name) {
        return name.equals(account) || name.equals(counterparty) || name.equals(feeAccount);
    }

    /** The audit-log line, without the line end. */
    String toLogLine() {
        return String.valueOf(number) + SEPARATOR + type.name() + SEPARATOR + account + SEPARATOR
                + orNone(counterparty) + SEPARATOR + amount + SEPARATOR + fee + SEPARATOR
                + orNone(feeAccount);
    }

    /**
     * Parses one audit-log line.
     *
     * @return the entry, or {@code null} when the line is not a well-formed entry
     */
    static Entry parse(String line) {
        String[] fields = line.split("\\|", -1);
        if (fields.length != 7) {
            return null;
        }
        try {
            long number = Long.parseLong(fields[0].trim());
            Type type = Type.valueOf(fields[1].trim().toUpperCase(Locale.ROOT));
            String account = Account.normalize(fields[2].trim());
            long amount = Long.parseLong(fields[4].trim());
            long fee = Long.parseLong(fields[5].trim());
            return new Entry(number, type, account, noneToNull(fields[3]), amount, fee,
                    noneToNull(fields[6]));
        } catch (IllegalArgumentException malformed) {
            return null;
        }
    }

    private static String orNone(String value) {
        return value == null ? NONE : value;
    }

    private static String noneToNull(String field) {
        String value = field.trim();
        return value.isEmpty() || value.equals(NONE) ? null : Account.normalize(value);
    }
}
