package com.example.towncrier;

/** A rejected command; the message is the reply. */
public final class CrierException extends Exception {

    public CrierException(String message) {
        super(message);
    }
}
