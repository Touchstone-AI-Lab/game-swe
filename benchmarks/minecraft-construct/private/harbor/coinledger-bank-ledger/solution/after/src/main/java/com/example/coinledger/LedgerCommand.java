package com.example.coinledger;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.logging.Level;
import java.util.regex.Pattern;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

/** The /ledger command. */
public final class LedgerCommand implements CommandExecutor {

    static final String USAGE =
        "Usage: /ledger <open|balance|deposit|withdraw|transfer|pay|freeze|unfreeze|history|top|reload>";
    private static final String NO_PERMISSION = "You do not have permission to do that.";
    private static final Pattern NAME = Pattern.compile("^[A-Za-z0-9_]{3,16}$");
    private static final Pattern PAGE = Pattern.compile("^[0-9]{1,9}$");
    private static final String ADMIN = "coinledger.admin";
    private static final String VIEW = "coinledger.view";
    private static final String PAY = "coinledger.pay";

    private final CoinLedgerPlugin plugin;

    public LedgerCommand(CoinLedgerPlugin plugin) {
        this.plugin = plugin;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (args.length == 0) {
            sender.sendMessage(USAGE);
            return true;
        }
        String[] rest = Arrays.copyOfRange(args, 1, args.length);
        try {
            switch (args[0].toLowerCase(Locale.ROOT)) {
                case "open" -> open(sender, rest);
                case "balance" -> balance(sender, rest);
                case "deposit" -> deposit(sender, rest);
                case "withdraw" -> withdraw(sender, rest);
                case "transfer" -> transfer(sender, rest);
                case "pay" -> pay(sender, rest);
                case "freeze" -> freeze(sender, rest, true);
                case "unfreeze" -> freeze(sender, rest, false);
                case "history" -> history(sender, rest);
                case "top" -> top(sender, rest);
                case "reload" -> reload(sender, rest);
                default -> sender.sendMessage(USAGE);
            }
        } catch (LedgerException rejected) {
            sender.sendMessage(rejected.getMessage());
        }
        return true;
    }

    private Ledger ledger() {
        return plugin.ledger();
    }

    private String format(long cents) {
        return ledger().settings().format(cents);
    }

    private static void arity(String[] args, int min, int max, String usage) throws LedgerException {
        if (args.length < min || args.length > max) {
            throw new LedgerException(usage);
        }
    }

    private static void permission(CommandSender sender, String... permissions) throws LedgerException {
        for (String permission : permissions) {
            if (sender.hasPermission(permission)) {
                return;
            }
        }
        throw new LedgerException(NO_PERMISSION);
    }

    private static String name(String raw) throws LedgerException {
        if (!NAME.matcher(raw).matches()) {
            throw new LedgerException("Invalid account name: " + raw);
        }
        return raw.toLowerCase(Locale.ROOT);
    }

    private Account account(String raw) throws LedgerException {
        return ledger().require(name(raw));
    }

    private static long amount(String raw) throws LedgerException {
        long cents = Money.parse(raw);
        if (cents <= 0) {
            throw new LedgerException("Invalid amount: " + raw);
        }
        return cents;
    }

    private static String ownName(CommandSender sender) {
        return sender instanceof Player player ? player.getName().toLowerCase(Locale.ROOT) : null;
    }

    private void open(CommandSender sender, String[] args) throws LedgerException {
        arity(args, 1, 1, "Usage: /ledger open <account>");
        permission(sender, ADMIN);
        Account account = ledger().open(name(args[0]));
        sender.sendMessage("Opened account " + account.name() + " with " + format(account.balance()) + ".");
    }

    private void balance(CommandSender sender, String[] args) throws LedgerException {
        arity(args, 0, 1, "Usage: /ledger balance [account]");
        Account account;
        if (args.length == 0) {
            String own = ownName(sender);
            if (own == null) {
                throw new LedgerException("Only players can use /ledger balance without an account.");
            }
            account = ledger().store().account(own);
            if (account == null) {
                throw new LedgerException("You do not have an account.");
            }
        } else {
            account = account(args[0]);
            if (!account.name().equals(ownName(sender))) {
                permission(sender, VIEW, ADMIN);
            }
        }
        sender.sendMessage("Balance of " + account.name() + ": " + format(account.balance()) + ".");
    }

    private void deposit(CommandSender sender, String[] args) throws LedgerException {
        arity(args, 2, 2, "Usage: /ledger deposit <account> <amount>");
        permission(sender, ADMIN);
        Account account = account(args[0]);
        long amount = amount(args[1]);
        ledger().deposit(account, amount);
        sender.sendMessage("Deposited " + format(amount) + " to " + account.name() + ". Balance: "
            + format(account.balance()) + ".");
    }

    private void withdraw(CommandSender sender, String[] args) throws LedgerException {
        arity(args, 2, 2, "Usage: /ledger withdraw <account> <amount>");
        permission(sender, ADMIN);
        Account account = account(args[0]);
        long amount = amount(args[1]);
        ledger().withdraw(account, amount);
        sender.sendMessage("Withdrew " + format(amount) + " from " + account.name() + ". Balance: "
            + format(account.balance()) + ".");
    }

    private void transfer(CommandSender sender, String[] args) throws LedgerException {
        arity(args, 3, 3, "Usage: /ledger transfer <from> <to> <amount>");
        permission(sender, ADMIN);
        Account from = account(args[0]);
        Account to = account(args[1]);
        long amount = amount(args[2]);
        long fee = ledger().transfer(from, to, amount);
        sender.sendMessage("Transferred " + format(amount) + " from " + from.name() + " to " + to.name()
            + " (fee " + format(fee) + ").");
    }

    private void pay(CommandSender sender, String[] args) throws LedgerException {
        arity(args, 2, 2, "Usage: /ledger pay <account> <amount>");
        permission(sender, PAY);
        String own = ownName(sender);
        if (own == null) {
            throw new LedgerException("Only players can use /ledger pay.");
        }
        Account from = ledger().store().account(own);
        if (from == null) {
            throw new LedgerException("You do not have an account.");
        }
        Account to = account(args[0]);
        long amount = amount(args[1]);
        long fee = ledger().transfer(from, to, amount);
        sender.sendMessage("Paid " + format(amount) + " to " + to.name() + " (fee " + format(fee) + "). Balance: "
            + format(from.balance()) + ".");
    }

    private void freeze(CommandSender sender, String[] args, boolean freeze) throws LedgerException {
        arity(args, 1, 1, freeze ? "Usage: /ledger freeze <account>" : "Usage: /ledger unfreeze <account>");
        permission(sender, ADMIN);
        Account account = account(args[0]);
        if (freeze) {
            ledger().freeze(account);
            sender.sendMessage("Account " + account.name() + " is now frozen.");
        } else {
            ledger().unfreeze(account);
            sender.sendMessage("Account " + account.name() + " is no longer frozen.");
        }
    }

    private void history(CommandSender sender, String[] args) throws LedgerException {
        arity(args, 1, 2, "Usage: /ledger history <account> [page]");
        Account account = account(args[0]);
        if (!account.name().equals(ownName(sender))) {
            permission(sender, ADMIN);
        }
        int page = 1;
        if (args.length == 2) {
            if (!PAGE.matcher(args[1]).matches() || Integer.parseInt(args[1]) < 1) {
                throw new LedgerException("Invalid page: " + args[1]);
            }
            page = Integer.parseInt(args[1]);
        }
        List<AuditEntry> entries = new ArrayList<>();
        for (AuditEntry entry : ledger().store().entries()) {
            if (entry.involves(account.name())) {
                entries.add(entry);
            }
        }
        entries.sort(Comparator.comparingLong(AuditEntry::number).reversed());
        int size = ledger().settings().pageSize();
        int last = Math.max(1, (entries.size() + size - 1) / size);
        if (page > last) {
            throw new LedgerException("Page " + page + " does not exist; last page is " + last + ".");
        }
        sender.sendMessage("History of " + account.name() + " (page " + page + "/" + last + "):");
        int from = (page - 1) * size;
        for (AuditEntry entry : entries.subList(from, Math.min(entries.size(), from + size))) {
            sender.sendMessage(entry.describe(account.name(), ledger().settings()));
        }
    }

    private void top(CommandSender sender, String[] args) throws LedgerException {
        arity(args, 0, 0, "Usage: /ledger top");
        List<Account> accounts = new ArrayList<>(ledger().store().accounts());
        if (accounts.isEmpty()) {
            sender.sendMessage("No accounts.");
            return;
        }
        accounts.sort(Comparator.comparingLong((Account account) -> account.balance()).reversed()
            .thenComparing(Account::name));
        sender.sendMessage("Top accounts:");
        for (int rank = 1; rank <= Math.min(5, accounts.size()); rank++) {
            Account account = accounts.get(rank - 1);
            sender.sendMessage(rank + ". " + account.name() + ": " + format(account.balance()));
        }
    }

    private void reload(CommandSender sender, String[] args) throws LedgerException {
        arity(args, 0, 0, "Usage: /ledger reload");
        permission(sender, ADMIN);
        try {
            plugin.reloadLedger();
        } catch (IOException failure) {
            plugin.getLogger().log(Level.SEVERE, "Could not reload the ledger", failure);
        }
        sender.sendMessage("CoinLedger reloaded: " + ledger().store().accounts().size() + " accounts.");
    }
}
