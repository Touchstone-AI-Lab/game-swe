package com.example.coinledger;

/** One bank account; balances are whole cents. */
public final class Account {

    private final String name;
    private long balance;
    private boolean frozen;

    public Account(String name, long balance, boolean frozen) {
        this.name = name;
        this.balance = balance;
        this.frozen = frozen;
    }

    public String name() {
        return name;
    }

    public long balance() {
        return balance;
    }

    public void balance(long balance) {
        this.balance = balance;
    }

    public boolean frozen() {
        return frozen;
    }

    public void frozen(boolean frozen) {
        this.frozen = frozen;
    }
}
