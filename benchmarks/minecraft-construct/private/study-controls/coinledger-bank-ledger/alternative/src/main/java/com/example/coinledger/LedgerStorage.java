package com.example.coinledger;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.SeekableByteChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.logging.Logger;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.InvalidConfigurationException;
import org.bukkit.configuration.file.YamlConfiguration;

/** Reads and writes {@code accounts.yml} and {@code audit.log} in the plugin data folder. */
final class LedgerStorage {

    /** The contents of {@code accounts.yml}; {@code nextEntry} is {@code null} when absent. */
    record Snapshot(LinkedHashMap<String, Account> accounts, Long nextEntry) {
    }

    private static final String NEXT_ENTRY = "next-entry";
    private static final String ACCOUNTS = "accounts";
    private static final String BALANCE = "balance";
    private static final String FROZEN = "frozen";

    private final Path accountsFile;
    private final Path auditFile;
    private final Logger logger;

    LedgerStorage(Path dataFolder, Logger logger) {
        this.accountsFile = dataFolder.resolve("accounts.yml");
        this.auditFile = dataFolder.resolve("audit.log");
        this.logger = logger;
    }

    /** Reads {@code accounts.yml}; a missing file means no accounts and next entry 1. */
    Snapshot loadAccounts() {
        LinkedHashMap<String, Account> accounts = new LinkedHashMap<>();
        if (!Files.isRegularFile(accountsFile)) {
            return new Snapshot(accounts, 1L);
        }
        YamlConfiguration yaml = new YamlConfiguration();
        try {
            yaml.load(accountsFile.toFile());
        } catch (IOException | InvalidConfigurationException e) {
            logger.severe("Cannot read accounts.yml: " + e.getMessage());
            return new Snapshot(accounts, null);
        }
        Long next = Money.wholeNumber(yaml.get(NEXT_ENTRY));
        if (next != null && next < 1) {
            logger.warning("Ignoring invalid next-entry " + next + " in accounts.yml.");
            next = null;
        }
        ConfigurationSection section = yaml.getConfigurationSection(ACCOUNTS);
        if (section != null) {
            for (String key : section.getKeys(false)) {
                ConfigurationSection data = section.getConfigurationSection(key);
                if (!Account.isValidName(key) || data == null) {
                    logger.warning("Skipping invalid account '" + key + "' in accounts.yml.");
                    continue;
                }
                Long balance = Money.wholeNumber(data.get(BALANCE));
                if (balance == null) {
                    logger.warning("Account '" + key + "' has no valid balance; using 0.");
                    balance = 0L;
                }
                Object frozen = data.get(FROZEN);
                boolean isFrozen = frozen instanceof Boolean flag
                        ? flag : frozen != null && Boolean.parseBoolean(frozen.toString().trim());
                String name = Account.normalize(key);
                accounts.put(name, new Account(name, balance, isFrozen));
            }
        }
        return new Snapshot(accounts, next);
    }

    /** Rewrites {@code accounts.yml} with the next entry number and every account. */
    void saveAccounts(long nextEntry, Collection<Account> accounts) throws IOException {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set(NEXT_ENTRY, nextEntry);
        ConfigurationSection section = yaml.createSection(ACCOUNTS);
        for (Account account : accounts) {
            ConfigurationSection data = section.createSection(account.name());
            data.set(BALANCE, account.balance());
            data.set(FROZEN, account.frozen());
        }
        writeAtomically(accountsFile, yaml.saveToString());
    }

    /** Reads every well-formed entry of {@code audit.log}; a missing file means no history. */
    List<Entry> loadAudit() {
        List<Entry> entries = new ArrayList<>();
        if (!Files.isRegularFile(auditFile)) {
            return entries;
        }
        List<String> lines;
        try {
            lines = Files.readAllLines(auditFile, StandardCharsets.UTF_8);
        } catch (IOException e) {
            logger.severe("Cannot read audit.log: " + e.getMessage());
            return entries;
        }
        for (String line : lines) {
            if (line.isBlank()) {
                continue;
            }
            Entry entry = Entry.parse(line.strip());
            if (entry == null) {
                logger.warning("Skipping malformed audit.log line: " + line);
            } else {
                entries.add(entry);
            }
        }
        return entries;
    }

    /** Appends one entry to {@code audit.log} as a single {@code \n}-terminated line. */
    void appendAudit(Entry entry) throws IOException {
        Files.createDirectories(auditFile.getParent());
        String line = entry.toLogLine() + "\n";
        if (lacksFinalNewline(auditFile)) {
            line = "\n" + line;
        }
        Files.writeString(auditFile, line, StandardCharsets.UTF_8,
                StandardOpenOption.CREATE, StandardOpenOption.WRITE, StandardOpenOption.APPEND);
    }

    private static boolean lacksFinalNewline(Path file) throws IOException {
        if (!Files.isRegularFile(file)) {
            return false;
        }
        try (SeekableByteChannel channel = Files.newByteChannel(file, StandardOpenOption.READ)) {
            long size = channel.size();
            if (size == 0) {
                return false;
            }
            ByteBuffer last = ByteBuffer.allocate(1);
            channel.position(size - 1);
            channel.read(last);
            return last.get(0) != '\n';
        }
    }

    private static void writeAtomically(Path target, String content) throws IOException {
        Files.createDirectories(target.getParent());
        Path temp = target.resolveSibling(target.getFileName() + ".tmp");
        Files.writeString(temp, content, StandardCharsets.UTF_8);
        try {
            Files.move(temp, target, StandardCopyOption.REPLACE_EXISTING,
                    StandardCopyOption.ATOMIC_MOVE);
        } catch (AtomicMoveNotSupportedException unsupported) {
            Files.move(temp, target, StandardCopyOption.REPLACE_EXISTING);
        }
    }
}
