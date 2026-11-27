package com.example.coinledger;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

/** accounts.yml and audit.log: the ledger's persistent state. */
public final class LedgerStore {

    private final File accountsFile;
    private final File auditFile;
    private final Map<String, Account> accounts = new TreeMap<>();
    private final List<AuditEntry> entries = new ArrayList<>();
    private long nextEntry = 1;

    public LedgerStore(File dataFolder) {
        this.accountsFile = new File(dataFolder, "accounts.yml");
        this.auditFile = new File(dataFolder, "audit.log");
    }

    /** Replaces the in-memory state with the files on disk. */
    public void load() throws IOException {
        accounts.clear();
        entries.clear();
        nextEntry = 1;
        if (accountsFile.isFile()) {
            YamlConfiguration yaml = YamlConfiguration.loadConfiguration(accountsFile);
            nextEntry = Math.max(1, yaml.getLong("next-entry", 1));
            ConfigurationSection section = yaml.getConfigurationSection("accounts");
            if (section != null) {
                for (String key : section.getKeys(false)) {
                    String name = key.toLowerCase(java.util.Locale.ROOT);
                    accounts.put(name, new Account(name, section.getLong(key + ".balance", 0),
                        section.getBoolean(key + ".frozen", false)));
                }
            }
        }
        if (auditFile.isFile()) {
            for (String line : Files.readAllLines(auditFile.toPath(), StandardCharsets.UTF_8)) {
                if (line.isBlank()) {
                    continue;
                }
                AuditEntry entry = AuditEntry.parse(line);
                if (entry != null) {
                    entries.add(entry);
                }
            }
        }
    }

    public Account account(String name) {
        return accounts.get(name);
    }

    public Collection<Account> accounts() {
        return Collections.unmodifiableCollection(accounts.values());
    }

    public void add(Account account) {
        accounts.put(account.name(), account);
    }

    public List<AuditEntry> entries() {
        return Collections.unmodifiableList(entries);
    }

    /** Records one change: appends it to audit.log and rewrites accounts.yml. */
    public AuditEntry record(String type, String account, String counterparty, long amount, long fee,
                             String feeAccount) throws IOException {
        AuditEntry entry = new AuditEntry(nextEntry++, type, account, counterparty, amount, fee, feeAccount);
        entries.add(entry);
        auditFile.getParentFile().mkdirs();
        Files.writeString(auditFile.toPath(), entry.toLine() + "\n", StandardCharsets.UTF_8,
            StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        save();
        return entry;
    }

    public void save() throws IOException {
        YamlConfiguration yaml = new YamlConfiguration();
        yaml.set("next-entry", nextEntry);
        yaml.createSection("accounts");
        for (Account account : accounts.values()) {
            yaml.set("accounts." + account.name() + ".balance", account.balance());
            yaml.set("accounts." + account.name() + ".frozen", account.frozen());
        }
        accountsFile.getParentFile().mkdirs();
        yaml.save(accountsFile);
    }
}
