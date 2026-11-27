package com.example.blocktrail;

/** A rejected command; the message is the reply. */
public final class TrailException extends Exception {

    public TrailException(String message) {
        super(message);
    }
}
