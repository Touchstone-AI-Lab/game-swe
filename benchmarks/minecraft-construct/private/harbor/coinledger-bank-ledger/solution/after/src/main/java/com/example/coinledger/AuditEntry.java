package com.example.coinledger;

/**
 * One line of audit.log: {@code number|type|account|counterparty|amount|fee|feeAccount}.
 * Missing counterparty and fee account are written as {@code -}.
 */
public record AuditEntry(
    long number, String type, String account, String counterparty, long amount, long fee, String feeAccount) {

    public static final String NONE = "-";

    public String toLine() {
        return number + "|" + type + "|" + account + "|" + counterparty + "|" + amount + "|" + fee + "|" + feeAccount;
    }

    /** Parses a line, or returns null when it is not a well-formed entry. */
    public static AuditEntry parse(String line) {
        String[] fields = line.split("\\|", -1);
        if (fields.length != 7) {
            return null;
        }
        try {
            return new AuditEntry(Long.parseLong(fields[0].trim()), fields[1].trim(), fields[2].trim(),
                fields[3].trim(), Long.parseLong(fields[4].trim()), Long.parseLong(fields[5].trim()), fields[6].trim());
        } catch (NumberFormatException invalid) {
            return null;
        }
    }

    public boolean involves(String name) {
        return account.equals(name) || counterparty.equals(name) || (fee > 0 && feeAccount.equals(name));
    }

    /** The history line of this entry as seen by {@code viewer}. */
    public String describe(String viewer, LedgerSettings settings) {
        String prefix = "#" + number + " ";
        return switch (type) {
            case "OPEN" -> prefix + "OPEN +" + settings.format(amount);
            case "DEPOSIT" -> prefix + "DEPOSIT +" + settings.format(amount);
            case "WITHDRAW" -> prefix + "WITHDRAW -" + settings.format(amount);
            case "TRANSFER" -> {
                if (account.equals(viewer)) {
                    yield prefix + "TRANSFER -" + settings.format(amount) + " to " + counterparty
                        + " (fee " + settings.format(fee) + ")";
                }
                if (counterparty.equals(viewer)) {
                    yield prefix + "TRANSFER +" + settings.format(amount) + " from " + account;
                }
                yield prefix + "FEE +" + settings.format(fee) + " from " + account;
            }
            default -> prefix + type;
        };
    }
}
