package com.example.coinledger;

import java.io.IOException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * The bank ledger: accounts, the audit trail and the state rules of every operation.
 *
 * <p>Operations check their state rules in the order same account, frozen sender, frozen
 * recipient, funds, maximum balance, and throw {@link LedgerException} before changing
 * anything. A successful operation records exactly one entry and writes {@code audit.log} and
 * {@code accounts.yml} before returning.
 */
final class Ledger {

    private final Path configFile;
    private final LedgerStorage storage;
    private final Logger logger;

    private Settings settings = Settings.DEFAULTS;
    private final Map<String, Account> accounts = new LinkedHashMap<>();
    private final List<Entry> entries = new ArrayList<>();
    private long nextEntry = 1;

    Ledger(Path dataFolder, Logger logger) {
        this.configFile = dataFolder.resolve("config.yml");
        this.storage = new LedgerStorage(dataFolder, logger);
        this.logger = logger;
    }

    /**
     * Re-reads {@code config.yml}, {@code accounts.yml} and {@code audit.log}, then creates the
     * configured fee account when it is missing.
     */
    void reload() {
        settings = Settings.load(configFile, logger);
        LedgerStorage.Snapshot snapshot = storage.loadAccounts();
        List<Entry> history = storage.loadAudit();

        accounts.clear();
        accounts.putAll(snapshot.accounts());
        entries.clear();
        entries.addAll(history);
        nextEntry = snapshot.nextEntry() != null
                ? snapshot.nextEntry()
                : 1 + history.stream().mapToLong(Entry::number).max().orElse(0);

        if (settings.hasFeeAccount() && !accounts.containsKey(settings.feeAccount())) {
            Account feeAccount = new Account(settings.feeAccount(), 0, false);
            accounts.put(feeAccount.name(), feeAccount);
            record(Entry.Type.OPEN, feeAccount.name(), null, 0, 0, null);
        }
    }

    Settings settings() {
        return settings;
    }

    /** The account with this lower-case name, or {@code null}. */
    Account find(String name) {
        return accounts.get(name);
    }

    int accountCount() {
        return accounts.size();
    }

    /** Opens a new account (the caller has checked that it does not exist). */
    Account open(String name) {
        Account account = new Account(name, settings.startingBalance(), false);
        accounts.put(name, account);
        record(Entry.Type.OPEN, name, null, account.balance(), 0, null);
        return account;
    }

    void deposit(Account account, long amount) throws LedgerException {
        requireNotFrozen(account);
        requireRoom(account, amount);
        account.adjust(amount);
        record(Entry.Type.DEPOSIT, account.name(), null, amount, 0, null);
    }

    void withdraw(Account account, long amount) throws LedgerException {
        requireNotFrozen(account);
        requireFunds(account, amount);
        account.adjust(-amount);
        record(Entry.Type.WITHDRAW, account.name(), null, amount, 0, null);
    }

    /**
     * Moves {@code amount} from {@code from} to {@code to}; the sender also pays the fee, which
     * goes to the fee account.
     *
     * @return the fee in cents
     */
    long transfer(Account from, Account to, long amount) throws LedgerException {
        if (from.name().equals(to.name())) {
            throw new LedgerException("Cannot transfer to the same account.");
        }
        requireNotFrozen(from);
        requireNotFrozen(to);
        Account feeAccount = settings.hasFeeAccount() ? accounts.get(settings.feeAccount()) : null;
        long fee = feeAccount == null ? 0 : amount * settings.transferFeePercent() / 100;
        requireFunds(from, amount + fee);
        requireRoom(to, amount + (feeAccount == to ? fee : 0));
        if (fee > 0 && feeAccount != to && feeAccount != from) {
            requireRoom(feeAccount, fee);
        }

        from.adjust(-(amount + fee));
        to.adjust(amount);
        if (fee > 0) {
            feeAccount.adjust(fee);
        }
        record(Entry.Type.TRANSFER, from.name(), to.name(), amount, fee,
                fee > 0 ? feeAccount.name() : null);
        return fee;
    }

    /** Freezes an account (the caller has checked that it is not frozen). */
    void freeze(Account account) {
        account.setFrozen(true);
        record(Entry.Type.FREEZE, account.name(), null, 0, 0, null);
    }

    /** Unfreezes an account (the caller has checked that it is frozen). */
    void unfreeze(Account account) {
        account.setFrozen(false);
        record(Entry.Type.UNFREEZE, account.name(), null, 0, 0, null);
    }

    /** Every entry involving the account, newest first. */
    List<Entry> history(String name) {
        return entries.stream()
                .filter(entry -> entry.involves(name))
                .sorted(Comparator.comparingLong(Entry::number).reversed())
                .toList();
    }

    /** Every account, highest balance first and by name for equal balances. */
    List<Account> ranking() {
        return accounts.values().stream()
                .sorted(Comparator.comparingLong(Account::balance).reversed()
                        .thenComparing(Account::name))
                .toList();
    }

    private void requireNotFrozen(Account account) throws LedgerException {
        if (account.frozen()) {
            throw new LedgerException("Account " + account.name() + " is frozen.");
        }
    }

    private void requireFunds(Account account, long needed) throws LedgerException {
        if (needed > account.balance()) {
            throw new LedgerException("Insufficient funds: " + account.name() + " has "
                    + settings.format(account.balance()) + ".");
        }
    }

    private void requireRoom(Account account, long incoming) throws LedgerException {
        if (account.balance() + incoming > settings.maxBalance()) {
            throw new LedgerException("Rejected: " + account.name()
                    + " would exceed the maximum balance of "
                    + settings.format(settings.maxBalance()) + ".");
        }
    }

    private void record(Entry.Type type, String account, String counterparty, long amount,
                        long fee, String feeAccount) {
        Entry entry = new Entry(nextEntry++, type, account, counterparty, amount, fee, feeAccount);
        entries.add(entry);
        try {
            storage.appendAudit(entry);
        } catch (IOException e) {
            logger.log(Level.SEVERE, "Cannot append entry " + entry.number() + " to audit.log", e);
        }
        try {
            storage.saveAccounts(nextEntry, accounts.values());
        } catch (IOException e) {
            logger.log(Level.SEVERE, "Cannot write accounts.yml", e);
        }
    }
}
