package com.example.coinledger;

/** A rejected ledger operation; the message is the reply sent to the command sender. */
public final class LedgerException extends Exception {

    public LedgerException(String message) {
        super(message);
    }
}
