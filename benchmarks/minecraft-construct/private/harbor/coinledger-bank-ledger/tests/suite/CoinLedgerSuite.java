package gcbtest.coinledger;

import io.gamecodebench.harness.GcbAssert;
import io.gamecodebench.harness.GcbCase;
import io.gamecodebench.harness.GcbSuite;
import java.math.BigDecimal;
import java.util.Arrays;
import java.util.List;
import org.bukkit.Bukkit;
import org.bukkit.command.PluginCommand;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.permissions.Permission;
import org.bukkit.permissions.PermissionDefault;
import org.bukkit.plugin.java.JavaPlugin;

/** Hidden live-server cases for the CoinLedger construct task. */
public final class CoinLedgerSuite implements GcbSuite {

    private static final String DENIED = "You do not have permission to do that.";
    private static final String USAGE =
        "Usage: /ledger <open|balance|deposit|withdraw|transfer|pay|freeze|unfreeze|history|top|reload>";
    private static final String DEFAULT_CONFIG = """
        currency: coins
        starting-balance: 100.00
        max-balance: 1000000.00
        transfer-fee-percent: 2
        fee-account: treasury
        history-page-size: 5
        """;

    @Override
    public void onEnable(JavaPlugin grader) {
    }

    // --- helpers -------------------------------------------------------------------------

    private static List<String> ledger(String arguments) {
        return Actor.console().run("ledger " + arguments);
    }

    private static void expect(String arguments, String... expected) {
        Kit.lines(ledger(arguments), "/ledger " + arguments, expected);
    }

    private static void open(String... names) {
        for (String name : names) {
            expect("open " + name, "Opened account " + name + " with 100.00 coins.");
        }
    }

    private static long balance(String account) {
        YamlConfiguration yaml = Kit.yaml("accounts.yml");
        GcbAssert.isTrue(yaml.contains("accounts." + account + ".balance"),
            "accounts.yml has accounts." + account + ".balance");
        return yaml.getLong("accounts." + account + ".balance");
    }

    private static long nextEntry() {
        return Kit.yaml("accounts.yml").getLong("next-entry");
    }

    private static List<String> auditTail(int count) {
        List<String> lines = Kit.lines("audit.log");
        GcbAssert.isTrue(lines.size() >= count, "audit.log has at least " + count + " lines: " + lines);
        return lines.subList(lines.size() - count, lines.size());
    }

    private static void assertDecimal(YamlConfiguration yaml, String key, String expected) {
        Object value = yaml.get(key);
        GcbAssert.notNull(value, "config.yml sets " + key);
        BigDecimal actual;
        try {
            actual = new BigDecimal(value.toString().trim());
        } catch (NumberFormatException invalid) {
            throw new io.gamecodebench.harness.GcbAssertionError(key + " is not a number: " + value);
        }
        GcbAssert.isTrue(actual.compareTo(new BigDecimal(expected)) == 0,
            "config.yml " + key + " is " + expected + " (was " + value + ")");
    }

    private static void restoreDefaultConfig() {
        Kit.write("config.yml", DEFAULT_CONFIG);
        List<String> reply = ledger("reload");
        GcbAssert.isTrue(reply.size() == 1 && reply.get(0).startsWith("CoinLedger reloaded: "),
            "reload after restoring config.yml: " + reply);
    }

    // --- cases ---------------------------------------------------------------------------

    @GcbCase(value = "CoinLedger is enabled", order = 0)
    public void sentinel() {
        GcbAssert.isTrue(Kit.plugin().isEnabled(), "CoinLedger is enabled");
        GcbAssert.equals("CoinLedger", Kit.plugin().getName(), "plugin name");
    }

    @GcbCase(value = "default config.yml is written on first enable", order = 1)
    public void defaultConfig() {
        YamlConfiguration yaml = Kit.yaml("config.yml");
        GcbAssert.equals("coins", yaml.getString("currency"), "currency");
        assertDecimal(yaml, "starting-balance", "100.00");
        assertDecimal(yaml, "max-balance", "1000000.00");
        assertDecimal(yaml, "transfer-fee-percent", "2");
        GcbAssert.equals("treasury", yaml.getString("fee-account"), "fee-account");
        assertDecimal(yaml, "history-page-size", "5");
    }

    @GcbCase(value = "plugin.yml declares the ledger command and permissions", order = 2)
    public void declarations() {
        PluginCommand command = Bukkit.getPluginCommand("ledger");
        GcbAssert.notNull(command, "/ledger is a plugin command");
        GcbAssert.equals("CoinLedger", command.getPlugin().getName(), "/ledger belongs to CoinLedger");
        GcbAssert.isNull(command.getPermission(), "/ledger has no permission key");
        String[][] expected = {
            {"coinledger.admin", "OP"}, {"coinledger.view", "OP"}, {"coinledger.pay", "TRUE"},
        };
        for (String[] pair : expected) {
            Permission permission = Bukkit.getPluginManager().getPermission(pair[0]);
            GcbAssert.notNull(permission, pair[0] + " is registered");
            GcbAssert.equals(PermissionDefault.valueOf(pair[1]), permission.getDefault(), pair[0] + " default");
        }
    }

    @GcbCase(value = "the fee account is created on enable", order = 3)
    public void feeAccountOnEnable() {
        YamlConfiguration yaml = Kit.yaml("accounts.yml");
        GcbAssert.equals(0L, yaml.getLong("accounts.treasury.balance", -1), "treasury balance in cents");
        GcbAssert.isFalse(yaml.getBoolean("accounts.treasury.frozen", true), "treasury is not frozen");
        GcbAssert.equals(2L, yaml.getLong("next-entry"), "next-entry after the first OPEN");
        GcbAssert.equals(List.of("1|OPEN|treasury|-|0|0|-"), Kit.lines("audit.log"), "audit.log");
        expect("balance treasury", "Balance of treasury: 0.00 coins.");
    }

    @GcbCase(value = "open creates an account with the starting balance", order = 4)
    public void openAccount() {
        long number = nextEntry();
        expect("open Alice_04", "Opened account alice_04 with 100.00 coins.");
        expect("balance ALICE_04", "Balance of alice_04: 100.00 coins.");
        GcbAssert.equals(10000L, balance("alice_04"), "alice_04 balance in cents");
        GcbAssert.isFalse(Kit.yaml("accounts.yml").getBoolean("accounts.alice_04.frozen", true),
            "a new account is not frozen");
        GcbAssert.equals(List.of(number + "|OPEN|alice_04|-|10000|0|-"), auditTail(1), "OPEN entry");
    }

    @GcbCase(value = "account names are case-insensitive and validated", order = 5)
    public void accountNames() {
        open("bob_05");
        expect("open BOB_05", "Account bob_05 already exists.");
        expect("open ab", "Invalid account name: ab");
        expect("open bad-name", "Invalid account name: bad-name");
        expect("open abcdefghijklmnopq", "Invalid account name: abcdefghijklmnopq");
        expect("balance nobody_05", "Unknown account: nobody_05");
        expect("balance NoBody_05", "Unknown account: nobody_05");
        expect("deposit Bob_05 1", "Deposited 1.00 coins to bob_05. Balance: 101.00 coins.");
    }

    @GcbCase(value = "deposit and withdraw report the new balance", order = 6)
    public void depositWithdraw() {
        open("carl_06");
        expect("deposit carl_06 25.5", "Deposited 25.50 coins to carl_06. Balance: 125.50 coins.");
        expect("withdraw CARL_06 0.75", "Withdrew 0.75 coins from carl_06. Balance: 124.75 coins.");
        expect("deposit carl_06 7", "Deposited 7.00 coins to carl_06. Balance: 131.75 coins.");
        GcbAssert.equals(13175L, balance("carl_06"), "carl_06 balance in cents");
    }

    @GcbCase(value = "invalid amounts are rejected", order = 7)
    public void invalidAmounts() {
        open("dana_07");
        for (String raw : List.of("0", "0.00", "-5", "1.234", "abc", "1e3", "12.", ".5", "1234567890")) {
            expect("deposit dana_07 " + raw, "Invalid amount: " + raw);
        }
        GcbAssert.equals(10000L, balance("dana_07"), "dana_07 balance is unchanged");
    }

    @GcbCase(value = "withdrawals cannot overdraw an account", order = 8)
    public void overdraw() {
        open("erin_08");
        expect("withdraw erin_08 100.01", "Insufficient funds: erin_08 has 100.00 coins.");
        expect("withdraw erin_08 100", "Withdrew 100.00 coins from erin_08. Balance: 0.00 coins.");
        expect("withdraw erin_08 0.01", "Insufficient funds: erin_08 has 0.00 coins.");
    }

    @GcbCase(value = "transfers move money and pay the fee", order = 9)
    public void transfer() {
        open("fred_09", "gina_09");
        long treasury = balance("treasury");
        expect("transfer fred_09 gina_09 50", "Transferred 50.00 coins from fred_09 to gina_09 (fee 1.00 coins).");
        expect("balance fred_09", "Balance of fred_09: 49.00 coins.");
        expect("balance gina_09", "Balance of gina_09: 150.00 coins.");
        GcbAssert.equals(4900L, balance("fred_09"), "fred_09 in cents");
        GcbAssert.equals(15000L, balance("gina_09"), "gina_09 in cents");
        GcbAssert.equals(treasury + 100, balance("treasury"), "treasury received the fee");
    }

    @GcbCase(value = "fees are rounded down to the cent", order = 10)
    public void feeRounding() {
        open("hank_10", "ivy_10");
        expect("deposit hank_10 900", "Deposited 900.00 coins to hank_10. Balance: 1000.00 coins.");
        long treasury = balance("treasury");
        expect("transfer hank_10 ivy_10 12.34", "Transferred 12.34 coins from hank_10 to ivy_10 (fee 0.24 coins).");
        expect("transfer hank_10 ivy_10 0.49", "Transferred 0.49 coins from hank_10 to ivy_10 (fee 0.00 coins).");
        expect("transfer hank_10 ivy_10 0.5", "Transferred 0.50 coins from hank_10 to ivy_10 (fee 0.01 coins).");
        expect("transfer hank_10 ivy_10 99.99", "Transferred 99.99 coins from hank_10 to ivy_10 (fee 1.99 coins).");
        long paid = (1234 + 24) + (49) + (50 + 1) + (9999 + 199);
        GcbAssert.equals(100000L - paid, balance("hank_10"), "hank_10 paid amounts plus rounded-down fees");
        GcbAssert.equals(10000L + 1234 + 49 + 50 + 9999, balance("ivy_10"), "ivy_10 received the amounts");
        GcbAssert.equals(treasury + 24 + 1 + 199, balance("treasury"), "treasury received the fees");
    }

    @GcbCase(value = "transfers need funds for the amount plus the fee", order = 11)
    public void feeFunds() {
        open("jack_11", "kim_11");
        expect("transfer jack_11 kim_11 100", "Insufficient funds: jack_11 has 100.00 coins.");
        expect("transfer jack_11 kim_11 98.04", "Transferred 98.04 coins from jack_11 to kim_11 (fee 1.96 coins).");
        expect("balance jack_11", "Balance of jack_11: 0.00 coins.");
    }

    @GcbCase(value = "transfers are validated from left to right", order = 12)
    public void validationOrder() {
        expect("transfer x ghost_12 5", "Invalid account name: x");
        expect("transfer ghost_12 x abc", "Unknown account: ghost_12");
        open("lara_12");
        expect("transfer lara_12 x abc", "Invalid account name: x");
        expect("transfer lara_12 ghost_12 abc", "Unknown account: ghost_12");
        expect("transfer lara_12 LARA_12 abc", "Invalid amount: abc");
        expect("transfer lara_12 LARA_12 5", "Cannot transfer to the same account.");
        expect("transfer lara_12 lara_12 500", "Cannot transfer to the same account.");
    }

    @GcbCase(value = "frozen accounts can neither send nor receive", order = 13)
    public void frozenAccounts() {
        open("nick_13", "olga_13");
        expect("freeze nick_13", "Account nick_13 is now frozen.");
        expect("deposit nick_13 5", "Account nick_13 is frozen.");
        expect("withdraw nick_13 5", "Account nick_13 is frozen.");
        expect("transfer nick_13 olga_13 5", "Account nick_13 is frozen.");
        expect("transfer olga_13 nick_13 5", "Account nick_13 is frozen.");
        expect("freeze olga_13", "Account olga_13 is now frozen.");
        expect("transfer nick_13 olga_13 500", "Account nick_13 is frozen.");
        expect("unfreeze nick_13", "Account nick_13 is no longer frozen.");
        expect("transfer nick_13 olga_13 500", "Account olga_13 is frozen.");
        GcbAssert.equals(10000L, balance("nick_13"), "nick_13 is unchanged");
        GcbAssert.equals(10000L, balance("olga_13"), "olga_13 is unchanged");
    }

    @GcbCase(value = "freeze and unfreeze report the state change", order = 14)
    public void freezeState() {
        open("pam_14");
        long number = nextEntry();
        expect("freeze pam_14", "Account pam_14 is now frozen.");
        GcbAssert.isTrue(Kit.yaml("accounts.yml").getBoolean("accounts.pam_14.frozen"), "accounts.yml frozen: true");
        expect("freeze PAM_14", "Account pam_14 is already frozen.");
        expect("unfreeze pam_14", "Account pam_14 is no longer frozen.");
        expect("unfreeze pam_14", "Account pam_14 is not frozen.");
        GcbAssert.isFalse(Kit.yaml("accounts.yml").getBoolean("accounts.pam_14.frozen", true), "frozen: false");
        GcbAssert.equals(List.of(number + "|FREEZE|pam_14|-|0|0|-", (number + 1) + "|UNFREEZE|pam_14|-|0|0|-"),
            auditTail(2), "FREEZE and UNFREEZE entries");
    }

    @GcbCase(value = "the maximum balance caps deposits and transfers", order = 15)
    public void maximumBalance() {
        open("quin_15", "rita_15");
        expect("deposit quin_15 999900", "Deposited 999900.00 coins to quin_15. Balance: 1000000.00 coins.");
        expect("deposit quin_15 0.01", "Rejected: quin_15 would exceed the maximum balance of 1000000.00 coins.");
        expect("transfer rita_15 quin_15 1", "Rejected: quin_15 would exceed the maximum balance of 1000000.00 coins.");
        GcbAssert.equals(10000L, balance("rita_15"), "rita_15 is unchanged");
        expect("withdraw quin_15 0.01", "Withdrew 0.01 coins from quin_15. Balance: 999999.99 coins.");
        expect("transfer rita_15 quin_15 0.01", "Transferred 0.01 coins from rita_15 to quin_15 (fee 0.00 coins).");
    }

    @GcbCase(value = "accounts.yml holds balances in cents", order = 16)
    public void accountsFile() {
        open("sam_16");
        expect("deposit sam_16 0.05", "Deposited 0.05 coins to sam_16. Balance: 100.05 coins.");
        expect("freeze sam_16", "Account sam_16 is now frozen.");
        YamlConfiguration yaml = Kit.yaml("accounts.yml");
        Object raw = yaml.get("accounts.sam_16.balance");
        GcbAssert.isTrue(raw instanceof Integer || raw instanceof Long, "balance is a whole number: " + raw);
        GcbAssert.equals(10005L, yaml.getLong("accounts.sam_16.balance"), "balance in cents");
        GcbAssert.isTrue(yaml.getBoolean("accounts.sam_16.frozen"), "frozen: true");
        List<String> audit = Kit.lines("audit.log");
        String last = audit.get(audit.size() - 1);
        long lastNumber = Long.parseLong(last.substring(0, last.indexOf('|')));
        GcbAssert.equals(lastNumber + 1, yaml.getLong("next-entry"), "next-entry follows the last entry");
    }

    @GcbCase(value = "audit.log records each change as one line", order = 17)
    public void auditLog() {
        long n = nextEntry();
        open("tina_17", "uma_17");
        expect("deposit tina_17 10", "Deposited 10.00 coins to tina_17. Balance: 110.00 coins.");
        expect("withdraw tina_17 2.5", "Withdrew 2.50 coins from tina_17. Balance: 107.50 coins.");
        expect("transfer tina_17 uma_17 50", "Transferred 50.00 coins from tina_17 to uma_17 (fee 1.00 coins).");
        expect("freeze uma_17", "Account uma_17 is now frozen.");
        expect("unfreeze uma_17", "Account uma_17 is no longer frozen.");
        GcbAssert.equals(List.of(
            n + "|OPEN|tina_17|-|10000|0|-",
            (n + 1) + "|OPEN|uma_17|-|10000|0|-",
            (n + 2) + "|DEPOSIT|tina_17|-|1000|0|-",
            (n + 3) + "|WITHDRAW|tina_17|-|250|0|-",
            (n + 4) + "|TRANSFER|tina_17|uma_17|5000|100|treasury",
            (n + 5) + "|FREEZE|uma_17|-|0|0|-",
            (n + 6) + "|UNFREEZE|uma_17|-|0|0|-"), auditTail(7), "audit.log lines");
        GcbAssert.equals(n + 7, nextEntry(), "next-entry");
    }

    @GcbCase(value = "rejected commands change nothing", order = 18)
    public void rejectedCommands() {
        open("vic_18");
        byte[] accounts = Kit.bytes("accounts.yml");
        byte[] audit = Kit.bytes("audit.log");
        long n = nextEntry();
        expect("deposit vic_18 abc", "Invalid amount: abc");
        expect("withdraw vic_18 500", "Insufficient funds: vic_18 has 100.00 coins.");
        expect("transfer vic_18 vic_18 1", "Cannot transfer to the same account.");
        expect("open VIC_18", "Account vic_18 already exists.");
        expect("freeze nobody_18", "Unknown account: nobody_18");
        expect("unfreeze vic_18", "Account vic_18 is not frozen.");
        expect("deposit vic_18 999999", "Rejected: vic_18 would exceed the maximum balance of 1000000.00 coins.");
        expect("history vic_18 9", "Page 9 does not exist; last page is 1.");
        GcbAssert.isTrue(Arrays.equals(accounts, Kit.bytes("accounts.yml")), "accounts.yml is unchanged");
        GcbAssert.isTrue(Arrays.equals(audit, Kit.bytes("audit.log")), "audit.log is unchanged");
        expect("deposit vic_18 1", "Deposited 1.00 coins to vic_18. Balance: 101.00 coins.");
        GcbAssert.equals(List.of(n + "|DEPOSIT|vic_18|-|100|0|-"), auditTail(1), "no entry number was used up");
    }

    @GcbCase(value = "history pages entries newest first", order = 19)
    public void historyPaging() {
        long n = nextEntry();
        open("walt_19", "xena_19");
        expect("deposit walt_19 1", "Deposited 1.00 coins to walt_19. Balance: 101.00 coins.");
        expect("withdraw walt_19 1", "Withdrew 1.00 coins from walt_19. Balance: 100.00 coins.");
        expect("transfer walt_19 xena_19 10", "Transferred 10.00 coins from walt_19 to xena_19 (fee 0.20 coins).");
        expect("transfer xena_19 walt_19 5", "Transferred 5.00 coins from xena_19 to walt_19 (fee 0.10 coins).");
        expect("freeze walt_19", "Account walt_19 is now frozen.");
        expect("unfreeze walt_19", "Account walt_19 is no longer frozen.");
        expect("history walt_19",
            "History of walt_19 (page 1/2):",
            "#" + (n + 7) + " UNFREEZE",
            "#" + (n + 6) + " FREEZE",
            "#" + (n + 5) + " TRANSFER +5.00 coins from xena_19",
            "#" + (n + 4) + " TRANSFER -10.00 coins to xena_19 (fee 0.20 coins)",
            "#" + (n + 3) + " WITHDRAW -1.00 coins");
        expect("history WALT_19 2",
            "History of walt_19 (page 2/2):",
            "#" + (n + 2) + " DEPOSIT +1.00 coins",
            "#" + n + " OPEN +100.00 coins");
        expect("history xena_19",
            "History of xena_19 (page 1/1):",
            "#" + (n + 5) + " TRANSFER -5.00 coins to walt_19 (fee 0.10 coins)",
            "#" + (n + 4) + " TRANSFER +10.00 coins from walt_19",
            "#" + (n + 1) + " OPEN +100.00 coins");
        List<String> treasury = ledger("history treasury");
        GcbAssert.isTrue(treasury.size() >= 3, "treasury history: " + treasury);
        GcbAssert.equals(List.of("#" + (n + 5) + " FEE +0.10 coins from xena_19", "#" + (n + 4) + " FEE +0.20 coins from walt_19"),
            treasury.subList(1, 3), "the fee account sees FEE lines");
    }

    @GcbCase(value = "history rejects pages that do not exist", order = 20)
    public void historyPages() {
        long n = nextEntry();
        open("yuri_20");
        expect("history yuri_20 2", "Page 2 does not exist; last page is 1.");
        expect("history yuri_20 0", "Invalid page: 0");
        expect("history yuri_20 x", "Invalid page: x");
        expect("history yuri_20 -1", "Invalid page: -1");
        expect("history ghost_20", "Unknown account: ghost_20");
        expect("history yuri_20 1", "History of yuri_20 (page 1/1):", "#" + n + " OPEN +100.00 coins");
    }

    @GcbCase(value = "top ranks accounts by balance then name", order = 21)
    public void top() {
        Kit.write("accounts.yml", """
            next-entry: 50
            accounts:
              amy:
                balance: 5000
                frozen: false
              ben:
                balance: 90000
                frozen: false
              cal:
                balance: 5000
                frozen: false
              dan:
                balance: 120000
                frozen: true
              eve:
                balance: 5000
                frozen: false
              fay:
                balance: 70000
                frozen: false
              gus:
                balance: 100
                frozen: false
              treasury:
                balance: 0
                frozen: false
            """);
        Kit.write("audit.log", "");
        expect("reload", "CoinLedger reloaded: 8 accounts.");
        expect("top",
            "Top accounts:",
            "1. dan: 1200.00 coins",
            "2. ben: 900.00 coins",
            "3. fay: 700.00 coins",
            "4. amy: 50.00 coins",
            "5. cal: 50.00 coins");
    }

    @GcbCase(value = "reload re-reads accounts, history and configuration", order = 22)
    public void reloadFromDisk() {
        try {
            Kit.write("accounts.yml", """
                next-entry: 42
                accounts:
                  hal_22:
                    balance: 123456
                    frozen: true
                  treasury:
                    balance: 0
                    frozen: false
                """);
            Kit.write("audit.log", "40|OPEN|hal_22|-|10000|0|-\n41|DEPOSIT|hal_22|-|113456|0|-\n");
            Kit.write("config.yml", """
                currency: gems
                starting-balance: 5.5
                max-balance: 2000
                transfer-fee-percent: 10
                fee-account: treasury
                history-page-size: 1
                """);
            expect("reload", "CoinLedger reloaded: 2 accounts.");
            expect("balance hal_22", "Balance of hal_22: 1234.56 gems.");
            expect("history hal_22", "History of hal_22 (page 1/2):", "#41 DEPOSIT +1134.56 gems");
            expect("history hal_22 2", "History of hal_22 (page 2/2):", "#40 OPEN +100.00 gems");
            expect("deposit hal_22 1", "Account hal_22 is frozen.");
            expect("unfreeze hal_22", "Account hal_22 is no longer frozen.");
            GcbAssert.equals(List.of("40|OPEN|hal_22|-|10000|0|-", "41|DEPOSIT|hal_22|-|113456|0|-",
                "42|UNFREEZE|hal_22|-|0|0|-"), Kit.lines("audit.log"), "numbering continues at next-entry");
            expect("open ivan_22", "Opened account ivan_22 with 5.50 gems.");
            expect("deposit ivan_22 2000", "Rejected: ivan_22 would exceed the maximum balance of 2000.00 gems.");
            expect("transfer hal_22 ivan_22 10", "Transferred 10.00 gems from hal_22 to ivan_22 (fee 1.00 gems).");
            expect("balance hal_22", "Balance of hal_22: 1223.56 gems.");
        } finally {
            restoreDefaultConfig();
        }
    }

    @GcbCase(value = "reload applies a new fee account", order = 23)
    public void reloadFeeAccount() {
        try {
            open("jill_23", "kurt_23");
            Kit.write("config.yml", DEFAULT_CONFIG.replace("fee-account: treasury", "fee-account: vault_23")
                .replace("transfer-fee-percent: 2", "transfer-fee-percent: 5"));
            long n = nextEntry();
            List<String> reply = ledger("reload");
            GcbAssert.isTrue(reply.size() == 1 && reply.get(0).matches("CoinLedger reloaded: \\d+ accounts\\."),
                "reload reply: " + reply);
            GcbAssert.equals(List.of(n + "|OPEN|vault_23|-|0|0|-"), auditTail(1), "the new fee account is opened");
            expect("balance vault_23", "Balance of vault_23: 0.00 coins.");
            expect("transfer jill_23 kurt_23 20", "Transferred 20.00 coins from jill_23 to kurt_23 (fee 1.00 coins).");
            GcbAssert.equals(List.of((n + 1) + "|TRANSFER|jill_23|kurt_23|2000|100|vault_23"), auditTail(1),
                "the fee goes to vault_23");
            expect("balance vault_23", "Balance of vault_23: 1.00 coins.");
            Kit.write("config.yml", DEFAULT_CONFIG.replace("fee-account: treasury", "fee-account: ''"));
            ledger("reload");
            expect("transfer jill_23 kurt_23 20", "Transferred 20.00 coins from jill_23 to kurt_23 (fee 0.00 coins).");
            GcbAssert.equals(List.of((n + 2) + "|TRANSFER|jill_23|kurt_23|2000|0|-"), auditTail(1),
                "no fee without a fee account");
        } finally {
            restoreDefaultConfig();
        }
    }

    @GcbCase(value = "players pay from their own account", order = 24)
    public void playersPay() {
        open("zed_24", "abe_24");
        Actor zed = Actor.player("Zed_24", "coinledger.pay");
        long n = nextEntry();
        Kit.lines(zed.run("ledger pay ABE_24 10"), "pay by Zed_24", "Paid 10.00 coins to abe_24 (fee 0.20 coins). Balance: 89.80 coins.");
        GcbAssert.equals(List.of(n + "|TRANSFER|zed_24|abe_24|1000|20|treasury"), auditTail(1), "payment entry");
        Kit.lines(zed.run("ledger pay zed_24 1"), "paying yourself", "Cannot transfer to the same account.");
        Kit.lines(zed.run("ledger pay abe_24 1000"), "paying too much", "Insufficient funds: zed_24 has 89.80 coins.");
        Kit.lines(zed.run("ledger pay ghost_24 1"), "paying nobody", "Unknown account: ghost_24");
        Kit.lines(Actor.player("Nobody_24", "coinledger.pay").run("ledger pay abe_24 1"), "player without account",
            "You do not have an account.");
        Kit.lines(Actor.player("Zed_24").run("ledger pay abe_24 1"), "player without coinledger.pay", DENIED);
        expect("pay abe_24 1", "Only players can use /ledger pay.");
        GcbAssert.equals(8980L, balance("zed_24"), "zed_24 in cents");
        GcbAssert.equals(11000L, balance("abe_24"), "abe_24 in cents");
    }

    @GcbCase(value = "players see their own balance and history", order = 25)
    public void ownAccount() {
        long n = nextEntry();
        open("bea_25");
        Actor bea = Actor.player("Bea_25");
        Kit.lines(bea.run("ledger balance"), "own balance", "Balance of bea_25: 100.00 coins.");
        Kit.lines(bea.run("ledger balance BEA_25"), "own balance by name", "Balance of bea_25: 100.00 coins.");
        Kit.lines(bea.run("ledger balance treasury"), "another balance", DENIED);
        Kit.lines(bea.run("ledger balance ghost_25"), "unknown account before permission", "Unknown account: ghost_25");
        Kit.lines(bea.run("ledger history bea_25"), "own history", "History of bea_25 (page 1/1):", "#" + n + " OPEN +100.00 coins");
        Kit.lines(bea.run("ledger history treasury"), "another history", DENIED);
        Kit.lines(Actor.player("Cody_25").run("ledger balance"), "player without account", "You do not have an account.");
        expect("balance", "Only players can use /ledger balance without an account.");
        Actor viewer = Actor.limited("viewer_25", "coinledger.view");
        Kit.lines(viewer.run("ledger balance bea_25"), "coinledger.view reads balances", "Balance of bea_25: 100.00 coins.");
        Kit.lines(viewer.run("ledger history bea_25"), "coinledger.view cannot read history", DENIED);
    }

    @GcbCase(value = "permissions are enforced", order = 26)
    public void permissions() {
        open("dora_26", "emil_26");
        byte[] accounts = Kit.bytes("accounts.yml");
        Actor clerk = Actor.limited("clerk_26");
        for (String line : List.of("open fern_26", "deposit dora_26 5", "withdraw dora_26 5",
                "transfer dora_26 emil_26 5", "freeze dora_26", "unfreeze dora_26", "reload",
                "balance dora_26", "history dora_26", "pay emil_26 5")) {
            Kit.lines(clerk.run("ledger " + line), "/ledger " + line + " without permission", DENIED);
        }
        GcbAssert.isTrue(Arrays.equals(accounts, Kit.bytes("accounts.yml")), "denied commands change nothing");
        List<String> top = clerk.run("ledger top");
        GcbAssert.isTrue(!top.isEmpty() && top.get(0).equals("Top accounts:"), "top needs no permission: " + top);
        Actor admin = Actor.limited("admin_26", "coinledger.admin");
        Kit.lines(admin.run("ledger open fern_26"), "coinledger.admin opens accounts", "Opened account fern_26 with 100.00 coins.");
        Kit.lines(admin.run("ledger history fern_26"), "coinledger.admin reads history",
            "History of fern_26 (page 1/1):", "#" + (nextEntry() - 1) + " OPEN +100.00 coins");
        Kit.lines(admin.run("ledger balance fern_26"), "coinledger.admin reads balances", "Balance of fern_26: 100.00 coins.");
    }

    @GcbCase(value = "case-variant self-transfer is rejected before frozen checks", order = 27)
    public void caseVariantSelfTransfer() {
        open("nora_27");
        expect("freeze nora_27", "Account nora_27 is now frozen.");
        long balanceBefore = balance("nora_27");
        long nextBefore = nextEntry();
        List<String> auditBefore = Kit.lines("audit.log");

        expect("transfer Nora_27 NORA_27 1.00", "Cannot transfer to the same account.");

        GcbAssert.equals(balanceBefore, balance("nora_27"), "self-transfer leaves the balance unchanged");
        GcbAssert.equals(nextBefore, nextEntry(), "self-transfer does not consume an entry number");
        GcbAssert.equals(auditBefore, Kit.lines("audit.log"), "self-transfer does not append an audit entry");
    }

    @GcbCase(value = "fee account as recipient checks the combined credit before mutation", order = 28)
    public void feeAccountRecipientLimit() {
        Kit.write("config.yml", """
            currency: coins
            starting-balance: 100.00
            max-balance: 100.00
            transfer-fee-percent: 2
            fee-account: vaultcase
            history-page-size: 5
            """);
        List<String> reload = ledger("reload");
        GcbAssert.isTrue(reload.size() == 1 && reload.get(0).startsWith("CoinLedger reloaded: "),
            "the fee-account test configuration reloads: " + reload);
        open("rhea_28");
        expect("deposit vaultcase 10.00", "Deposited 10.00 coins to vaultcase. Balance: 10.00 coins.");

        byte[] accounts = Kit.bytes("accounts.yml");
        List<String> audit = Kit.lines("audit.log");
        expect("transfer rhea_28 vaultcase 89.00",
            "Rejected: vaultcase would exceed the maximum balance of 100.00 coins.");
        GcbAssert.isTrue(Arrays.equals(accounts, Kit.bytes("accounts.yml")),
            "a principal-plus-fee overflow leaves every account unchanged");
        GcbAssert.equals(audit, Kit.lines("audit.log"), "a rejected aliased credit consumes no audit entry");
        GcbAssert.equals(10000L, balance("rhea_28"), "the sender keeps the full balance");
        GcbAssert.equals(1000L, balance("vaultcase"), "the fee account keeps its prior balance");
    }

    @GcbCase(value = "malformed commands show usage", order = 29)
    public void usage() {
        expect("", USAGE);
        expect("bogus", USAGE);
        expect("open", "Usage: /ledger open <account>");
        expect("open a b", "Usage: /ledger open <account>");
        expect("balance a b", "Usage: /ledger balance [account]");
        expect("deposit a", "Usage: /ledger deposit <account> <amount>");
        expect("withdraw a b c", "Usage: /ledger withdraw <account> <amount>");
        expect("transfer a b", "Usage: /ledger transfer <from> <to> <amount>");
        expect("pay a", "Usage: /ledger pay <account> <amount>");
        expect("freeze", "Usage: /ledger freeze <account>");
        expect("unfreeze a b", "Usage: /ledger unfreeze <account>");
        expect("history", "Usage: /ledger history <account> [page]");
        expect("history a 1 2", "Usage: /ledger history <account> [page]");
        expect("top x", "Usage: /ledger top");
        expect("reload x", "Usage: /ledger reload");
        Kit.lines(Actor.limited("nobody_27").run("ledger deposit a"), "usage comes before the permission check",
            "Usage: /ledger deposit <account> <amount>");
        List<String> top = ledger("TOP");
        GcbAssert.isTrue(!top.isEmpty() && top.get(0).equals("Top accounts:"), "subcommands are case-insensitive: " + top);
    }
}
