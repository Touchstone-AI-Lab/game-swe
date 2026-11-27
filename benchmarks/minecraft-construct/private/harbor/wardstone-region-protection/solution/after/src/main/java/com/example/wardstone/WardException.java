package com.example.wardstone;

/** A rejected command; the message is the reply. */
public final class WardException extends Exception {

    public WardException(String message) {
        super(message);
    }
}
