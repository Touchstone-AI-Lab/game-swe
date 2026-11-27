package com.example.coinledger;

import java.math.BigInteger;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Pattern;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

/**
 * The {@code /ledger} command.
 *
 * <p>Validation order: subcommand, argument count, permission, arguments from left to right
 * (account syntax then existence, amount syntax), then the ledger's state checks. The first
 * failure is the only reply.
 */
final class LedgerCommand implements CommandExecutor {

    static final String PERMISSION_ADMIN = "coinledger.admin";
    static final String PERMISSION_VIEW = "coinledger.view";
    static final String PERMISSION_PAY = "coinledger.pay";

    private static final String GENERAL_USAGE = "Usage: /ledger "
            + "<open|balance|deposit|withdraw|transfer|pay|freeze|unfreeze|history|top|reload>";
    private static final String NO_PERMISSION = "You do not have permission to do that.";
    private static final String NO_OWN_ACCOUNT = "You do not have an account.";
    private static final int TOP_SIZE = 5;
    private static final Pattern PAGE = Pattern.compile("[0-9]+");

    @FunctionalInterface
    private interface Handler {
        List<String> handle(CommandSender sender, String[] args) throws LedgerException;
    }

    private record Subcommand(String usage, int minArgs, int maxArgs, Handler handler) {
    }

    private final Ledger ledger;
    private final Map<String, Subcommand> subcommands = new HashMap<>();

    LedgerCommand(Ledger ledger) {
        this.ledger = ledger;
        register("open", "<account>", 1, 1, this::open);
        register("balance", "[account]", 0, 1, this::balance);
        register("deposit", "<account> <amount>", 2, 2, this::deposit);
        register("withdraw", "<account> <amount>", 2, 2, this::withdraw);
        register("transfer", "<from> <to> <amount>", 3, 3, this::transfer);
        register("pay", "<account> <amount>", 2, 2, this::pay);
        register("freeze", "<account>", 1, 1, this::freeze);
        register("unfreeze", "<account>", 1, 1, this::unfreeze);
        register("history", "<account> [page]", 1, 2, this::history);
        register("top", "", 0, 0, this::top);
        register("reload", "", 0, 0, this::reload);
    }

    private void register(String name, String parameters, int minArgs, int maxArgs,
                          Handler handler) {
        String usage = "Usage: /ledger " + name + (parameters.isEmpty() ? "" : " " + parameters);
        subcommands.put(name, new Subcommand(usage, minArgs, maxArgs, handler));
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label,
                             String[] args) {
        for (String line : dispatch(sender, args)) {
            sender.sendMessage(line);
        }
        return true;
    }

    private List<String> dispatch(CommandSender sender, String[] args) {
        Subcommand subcommand = args.length == 0
                ? null : subcommands.get(args[0].toLowerCase(Locale.ROOT));
        if (subcommand == null) {
            return List.of(GENERAL_USAGE);
        }
        String[] parameters = Arrays.copyOfRange(args, 1, args.length);
        if (parameters.length < subcommand.minArgs() || parameters.length > subcommand.maxArgs()) {
            return List.of(subcommand.usage());
        }
        try {
            return subcommand.handler().handle(sender, parameters);
        } catch (LedgerException rejected) {
            return List.of(rejected.getMessage());
        }
    }

    // --- subcommands -------------------------------------------------------------------------

    private List<String> open(CommandSender sender, String[] args) throws LedgerException {
        requirePermission(sender, PERMISSION_ADMIN);
        String name = accountName(args[0]);
        if (ledger.find(name) != null) {
            throw new LedgerException("Account " + name + " already exists.");
        }
        Account account = ledger.open(name);
        return List.of("Opened account " + name + " with " + money(account.balance()) + ".");
    }

    private List<String> balance(CommandSender sender, String[] args) throws LedgerException {
        Account account;
        if (args.length == 0) {
            account = ownAccount(
                    requirePlayer(sender, "Only players can use /ledger balance without an account."));
        } else {
            account = existingAccount(args[0]);
            if (!ownsAccount(sender, account) && !sender.hasPermission(PERMISSION_VIEW)
                    && !sender.hasPermission(PERMISSION_ADMIN)) {
                throw new LedgerException(NO_PERMISSION);
            }
        }
        return List.of("Balance of " + account.name() + ": " + money(account.balance()) + ".");
    }

    private List<String> deposit(CommandSender sender, String[] args) throws LedgerException {
        requirePermission(sender, PERMISSION_ADMIN);
        Account account = existingAccount(args[0]);
        long amount = amount(args[1]);
        ledger.deposit(account, amount);
        return List.of("Deposited " + money(amount) + " to " + account.name() + ". Balance: "
                + money(account.balance()) + ".");
    }

    private List<String> withdraw(CommandSender sender, String[] args) throws LedgerException {
        requirePermission(sender, PERMISSION_ADMIN);
        Account account = existingAccount(args[0]);
        long amount = amount(args[1]);
        ledger.withdraw(account, amount);
        return List.of("Withdrew " + money(amount) + " from " + account.name() + ". Balance: "
                + money(account.balance()) + ".");
    }

    private List<String> transfer(CommandSender sender, String[] args) throws LedgerException {
        requirePermission(sender, PERMISSION_ADMIN);
        Account from = existingAccount(args[0]);
        Account to = existingAccount(args[1]);
        long amount = amount(args[2]);
        long fee = ledger.transfer(from, to, amount);
        return List.of("Transferred " + money(amount) + " from " + from.name() + " to "
                + to.name() + " (fee " + money(fee) + ").");
    }

    private List<String> pay(CommandSender sender, String[] args) throws LedgerException {
        requirePermission(sender, PERMISSION_PAY);
        Account from = ownAccount(requirePlayer(sender, "Only players can use /ledger pay."));
        Account to = existingAccount(args[0]);
        long amount = amount(args[1]);
        long fee = ledger.transfer(from, to, amount);
        return List.of("Paid " + money(amount) + " to " + to.name() + " (fee " + money(fee)
                + "). Balance: " + money(from.balance()) + ".");
    }

    private List<String> freeze(CommandSender sender, String[] args) throws LedgerException {
        requirePermission(sender, PERMISSION_ADMIN);
        Account account = existingAccount(args[0]);
        if (account.frozen()) {
            throw new LedgerException("Account " + account.name() + " is already frozen.");
        }
        ledger.freeze(account);
        return List.of("Account " + account.name() + " is now frozen.");
    }

    private List<String> unfreeze(CommandSender sender, String[] args) throws LedgerException {
        requirePermission(sender, PERMISSION_ADMIN);
        Account account = existingAccount(args[0]);
        if (!account.frozen()) {
            throw new LedgerException("Account " + account.name() + " is not frozen.");
        }
        ledger.unfreeze(account);
        return List.of("Account " + account.name() + " is no longer frozen.");
    }

    private List<String> history(CommandSender sender, String[] args) throws LedgerException {
        Account account = existingAccount(args[0]);
        if (!ownsAccount(sender, account)) {
            requirePermission(sender, PERMISSION_ADMIN);
        }
        BigInteger page = args.length > 1 ? page(args[1]) : BigInteger.ONE;

        List<Entry> entries = ledger.history(account.name());
        long pageSize = ledger.settings().historyPageSize();
        long lastPage = Math.max(1, (entries.size() + pageSize - 1) / pageSize);
        if (page.compareTo(BigInteger.valueOf(lastPage)) > 0) {
            throw new LedgerException("Page " + page + " does not exist; last page is "
                    + lastPage + ".");
        }
        int from = (int) Math.min(entries.size(), (page.longValue() - 1) * pageSize);
        int to = (int) Math.min(entries.size(), from + pageSize);

        List<String> lines = new ArrayList<>();
        lines.add("History of " + account.name() + " (page " + page + "/" + lastPage + "):");
        for (Entry entry : entries.subList(from, to)) {
            lines.add(describe(entry, account.name()));
        }
        return lines;
    }

    private List<String> top(CommandSender sender, String[] args) {
        List<Account> ranking = ledger.ranking();
        if (ranking.isEmpty()) {
            return List.of("No accounts.");
        }
        List<String> lines = new ArrayList<>();
        lines.add("Top accounts:");
        for (int i = 0; i < Math.min(TOP_SIZE, ranking.size()); i++) {
            Account account = ranking.get(i);
            lines.add((i + 1) + ". " + account.name() + ": " + money(account.balance()));
        }
        return lines;
    }

    private List<String> reload(CommandSender sender, String[] args) throws LedgerException {
        requirePermission(sender, PERMISSION_ADMIN);
        ledger.reload();
        return List.of("CoinLedger reloaded: " + ledger.accountCount() + " accounts.");
    }

    // --- helpers -----------------------------------------------------------------------------

    /** One history line for {@code entry} as seen by the account {@code viewer}. */
    private String describe(Entry entry, String viewer) {
        String prefix = "#" + entry.number() + " ";
        return switch (entry.type()) {
            case OPEN -> prefix + "OPEN +" + money(entry.amount());
            case DEPOSIT -> prefix + "DEPOSIT +" + money(entry.amount());
            case WITHDRAW -> prefix + "WITHDRAW -" + money(entry.amount());
            case FREEZE -> prefix + "FREEZE";
            case UNFREEZE -> prefix + "UNFREEZE";
            case TRANSFER -> {
                if (viewer.equals(entry.account())) {
                    yield prefix + "TRANSFER -" + money(entry.amount()) + " to "
                            + entry.counterparty() + " (fee " + money(entry.fee()) + ")";
                }
                if (viewer.equals(entry.counterparty())) {
                    yield prefix + "TRANSFER +" + money(entry.amount()) + " from "
                            + entry.account();
                }
                yield prefix + "FEE +" + money(entry.fee()) + " from " + entry.account();
            }
        };
    }

    private String money(long cents) {
        return ledger.settings().format(cents);
    }

    private static void requirePermission(CommandSender sender, String permission)
            throws LedgerException {
        if (!sender.hasPermission(permission)) {
            throw new LedgerException(NO_PERMISSION);
        }
    }

    private static Player requirePlayer(CommandSender sender, String reply)
            throws LedgerException {
        if (sender instanceof Player player) {
            return player;
        }
        throw new LedgerException(reply);
    }

    private Account ownAccount(Player player) throws LedgerException {
        Account account = ledger.find(Account.normalize(player.getName()));
        if (account == null) {
            throw new LedgerException(NO_OWN_ACCOUNT);
        }
        return account;
    }

    private static boolean ownsAccount(CommandSender sender, Account account) {
        return sender instanceof Player player
                && Account.normalize(player.getName()).equals(account.name());
    }

    private static String accountName(String argument) throws LedgerException {
        if (!Account.isValidName(argument)) {
            throw new LedgerException("Invalid account name: " + argument);
        }
        return Account.normalize(argument);
    }

    private Account existingAccount(String argument) throws LedgerException {
        String name = accountName(argument);
        Account account = ledger.find(name);
        if (account == null) {
            throw new LedgerException("Unknown account: " + name);
        }
        return account;
    }

    private static long amount(String argument) throws LedgerException {
        long cents = Money.parseAmount(argument);
        if (cents <= 0) {
            throw new LedgerException("Invalid amount: " + argument);
        }
        return cents;
    }

    private static BigInteger page(String argument) throws LedgerException {
        if (PAGE.matcher(argument).matches()) {
            BigInteger page = new BigInteger(argument);
            if (page.signum() > 0) {
                return page;
            }
        }
        throw new LedgerException("Invalid page: " + argument);
    }
}
