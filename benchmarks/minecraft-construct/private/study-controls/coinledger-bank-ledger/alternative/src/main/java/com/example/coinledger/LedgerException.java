package com.example.coinledger;

/** A rejected command; the message is the exact reply line for the sender. */
final class LedgerException extends Exception {

    private static final long serialVersionUID = 1L;

    LedgerException(String reply) {
        super(reply, null, false, false);
    }
}
