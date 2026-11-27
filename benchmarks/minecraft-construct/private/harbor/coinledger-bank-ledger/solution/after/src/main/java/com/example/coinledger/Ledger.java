package com.example.coinledger;

import java.io.IOException;
import java.util.logging.Level;
import java.util.logging.Logger;

/** The ledger operations. Every method either applies and records a change or throws. */
public final class Ledger {

    private final LedgerStore store;
    private final Logger logger;
    private LedgerSettings settings;

    public Ledger(LedgerStore store, LedgerSettings settings, Logger logger) {
        this.store = store;
        this.settings = settings;
        this.logger = logger;
    }

    public LedgerSettings settings() {
        return settings;
    }

    public LedgerStore store() {
        return store;
    }

    /** Re-reads the files with new settings and makes sure the fee account exists. */
    public void reload(LedgerSettings newSettings) throws IOException {
        this.settings = newSettings;
        store.load();
        ensureFeeAccount();
    }

    public void ensureFeeAccount() throws IOException {
        if (settings.hasFeeAccount() && store.account(settings.feeAccount()) == null) {
            store.add(new Account(settings.feeAccount(), 0, false));
            record("OPEN", settings.feeAccount(), AuditEntry.NONE, 0, 0, AuditEntry.NONE);
        }
    }

    /** The existing account with this (already validated) lower-case name. */
    public Account require(String name) throws LedgerException {
        Account account = store.account(name);
        if (account == null) {
            throw new LedgerException("Unknown account: " + name);
        }
        return account;
    }

    public Account open(String name) throws LedgerException {
        if (store.account(name) != null) {
            throw new LedgerException("Account " + name + " already exists.");
        }
        Account account = new Account(name, settings.startingBalance(), false);
        store.add(account);
        record("OPEN", name, AuditEntry.NONE, account.balance(), 0, AuditEntry.NONE);
        return account;
    }

    public void deposit(Account account, long amount) throws LedgerException {
        checkNotFrozen(account);
        checkMaximum(account, amount);
        account.balance(account.balance() + amount);
        record("DEPOSIT", account.name(), AuditEntry.NONE, amount, 0, AuditEntry.NONE);
    }

    public void withdraw(Account account, long amount) throws LedgerException {
        checkNotFrozen(account);
        checkFunds(account, amount);
        account.balance(account.balance() - amount);
        record("WITHDRAW", account.name(), AuditEntry.NONE, amount, 0, AuditEntry.NONE);
    }

    /** Moves {@code amount} and charges the fee; returns the fee in cents. */
    public long transfer(Account from, Account to, long amount) throws LedgerException {
        if (from.name().equals(to.name())) {
            throw new LedgerException("Cannot transfer to the same account.");
        }
        checkNotFrozen(from);
        checkNotFrozen(to);
        long fee = settings.feeFor(amount);
        long debit;
        try {
            debit = Math.addExact(amount, fee);
        } catch (ArithmeticException overflow) {
            throw new LedgerException("Invalid amount.");
        }
        checkFunds(from, debit);
        Account feeAccount = null;
        if (fee > 0) {
            feeAccount = store.account(settings.feeAccount());
            if (feeAccount == null) {
                feeAccount = new Account(settings.feeAccount(), 0, false);
            }
        }
        long recipientCredit = amount;
        if (feeAccount == to) {
            try {
                recipientCredit = Math.addExact(amount, fee);
            } catch (ArithmeticException overflow) {
                throw new LedgerException("Rejected: " + to.name() + " would exceed the maximum balance of "
                    + settings.format(settings.maxBalance()) + ".");
            }
        }
        checkMaximum(to, recipientCredit);
        if (feeAccount != null && feeAccount != to && feeAccount != from) {
            checkMaximum(feeAccount, fee);
        }
        from.balance(from.balance() - amount - fee);
        to.balance(to.balance() + amount);
        String feeAccountName = AuditEntry.NONE;
        if (fee > 0) {
            if (store.account(settings.feeAccount()) == null) {
                store.add(feeAccount);
            }
            feeAccount.balance(feeAccount.balance() + fee);
            feeAccountName = feeAccount.name();
        }
        record("TRANSFER", from.name(), to.name(), amount, fee, feeAccountName);
        return fee;
    }

    public void freeze(Account account) throws LedgerException {
        if (account.frozen()) {
            throw new LedgerException("Account " + account.name() + " is already frozen.");
        }
        account.frozen(true);
        record("FREEZE", account.name(), AuditEntry.NONE, 0, 0, AuditEntry.NONE);
    }

    public void unfreeze(Account account) throws LedgerException {
        if (!account.frozen()) {
            throw new LedgerException("Account " + account.name() + " is not frozen.");
        }
        account.frozen(false);
        record("UNFREEZE", account.name(), AuditEntry.NONE, 0, 0, AuditEntry.NONE);
    }

    private void checkNotFrozen(Account account) throws LedgerException {
        if (account.frozen()) {
            throw new LedgerException("Account " + account.name() + " is frozen.");
        }
    }

    private void checkFunds(Account account, long needed) throws LedgerException {
        if (account.balance() < needed) {
            throw new LedgerException("Insufficient funds: " + account.name() + " has "
                + settings.format(account.balance()) + ".");
        }
    }

    private void checkMaximum(Account account, long credit) throws LedgerException {
        if (account.balance() + credit > settings.maxBalance()) {
            throw new LedgerException("Rejected: " + account.name() + " would exceed the maximum balance of "
                + settings.format(settings.maxBalance()) + ".");
        }
    }

    private void record(String type, String account, String counterparty, long amount, long fee, String feeAccount) {
        try {
            store.record(type, account, counterparty, amount, fee, feeAccount);
        } catch (IOException failure) {
            logger.log(Level.SEVERE, "Could not write the ledger files", failure);
        }
    }
}
