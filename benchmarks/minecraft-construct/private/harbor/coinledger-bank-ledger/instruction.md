# Harbor workspace

Write this plugin in `/app/plugin`; the skeleton's `pom.xml` and anything under `src/test` are frozen and restored by the verifier.

# Write a plugin: CoinLedger, a bank ledger for the server

You are writing a **new** Paper plugin. The skeleton at `/app/plugin` holds:

- `pom.xml`: the frozen Maven build. It compiles `src/main/java` with Java 21 against the
  Paper API 1.21.11 (the exact API of the server that grades you) and packages
  `src/main/resources` into `target/CoinLedger.jar`. No other library is available.
- `src/main/resources/plugin.yml`: plugin name `CoinLedger`, the main class and
  `api-version: '1.21'`. Add the command and the permissions described below.
- `src/main/java/com/example/coinledger/CoinLedgerPlugin.java`: an empty main class.

Keep the plugin name and the main class `com.example.coinledger.CoinLedgerPlugin`. Everything
else is yours to write: add classes under `src/main/java` and resources under
`src/main/resources`.

## How the plugin is built and graded

- The verifier restores `pom.xml` (and removes anything under `src/test`), then builds offline
  with `mvn -o -DskipTests package`. You can run the same build yourself where Maven and its
  cache are available.
- The jar is loaded into a real Paper 1.21.11 dedicated server with no players and no network,
  and with an empty data folder `plugins/CoinLedger/`. Private cases then run one after another
  in that single server session. If the plugin fails to enable, no case can be graded.
- The grader runs commands on the main server thread by looking the command up in the server's
  command map and calling `Command#execute`, with its own senders:
  - a console-like sender that has every permission;
  - senders that hold only the permissions a case grants them (they are not players);
  - player stand-ins that implement `Player` but support only `getName`, `getUniqueId`,
    `hasPermission`, `isOp` (always false), `sendMessage`, `sendPlainMessage`,
    `sendRichMessage` and `getServer`. Any other `Player` method throws.

  Declare the command in `plugin.yml` and handle it with a Bukkit `CommandExecutor` (not the
  Brigadier lifecycle API). Do not give the command a `permission:` key: the plugin checks
  permissions itself and answers with the message below.
- Replies are compared line by line. The grader records every message the sender receives,
  turns it into plain text (colour and formatting are dropped; a message with line breaks
  counts as several lines), trims each line and compares the sequence exactly with the lines
  this document specifies. Send nothing else to the sender. Colours are fine if they are real
  formatting, not literal `&` codes.
- Every file change is written to disk before the command that caused it returns.

## Money and names

1. **Amounts.** A command amount must match `^[0-9]{1,9}(\.[0-9]{1,2})?$` and be greater than
   zero; otherwise the reply is `Invalid amount: <argument>` (the argument as typed). Keep money
   as whole cents, never as floating point. An amount is displayed as the whole units, a dot,
   exactly two digits of cents, a space and the configured currency, with no thousands
   separator: `0.50 coins`, `1250.00 coins`. In the messages below, `<amount>`, `<fee>` and
   `<balance>` are displayed this way.
2. **Account names** match `^[A-Za-z0-9_]{3,16}$`. They are case-insensitive: they are stored,
   displayed and written to files in lower case. A name that does not match is answered with
   `Invalid account name: <argument>` (as typed); a valid name with no account is answered
   with `Unknown account: <name>` (lower case). A player's own account is the account named
   after the player's name in lower case.

## Configuration

3. **`config.yml`.** When `plugins/CoinLedger/config.yml` does not exist at enable, write it
   with exactly these values (comments and key order are free):

   ```yaml
   currency: coins
   starting-balance: 100.00
   max-balance: 1000000.00
   transfer-fee-percent: 2
   fee-account: treasury
   history-page-size: 5
   ```

   Money settings are numbers with at most two decimals, `transfer-fee-percent` is a whole
   number from 0 to 100, `history-page-size` a whole number of at least 1, and `fee-account`
   an account name or the empty string (no fee account).
4. **The fee account.** On enable and on every reload, when `fee-account` is not empty and no
   such account exists, create it with a balance of 0.00. Its creation is an `OPEN` entry of
   0.00 like any other (see requirement 11) and sends no message.

## Ledger operations

5. **Open.** A new account starts with `starting-balance` and is not frozen.
6. **Deposit and withdraw** add to or take from one account. A withdrawal larger than the
   balance is rejected with `Insufficient funds: <name> has <balance>.`
7. **Transfer.** Moving `<amount>` from one account to another charges a fee of
   `amount × transfer-fee-percent / 100`, rounded **down** to the whole cent. The sender pays
   amount plus fee, the recipient receives the amount, and the fee account receives the fee.
   When `fee-account` is empty the fee is always 0.00. A transfer the sender cannot cover
   (amount plus fee above its balance) is rejected with `Insufficient funds: <name> has
   <balance>.` A transfer to the same account is rejected with
   `Cannot transfer to the same account.` Compare the lower-case account names: for example,
   `transfer Alice ALICE 1.00` is a same-account transfer. This check runs before frozen-account
   checks, and rejection must leave the balances, `accounts.yml`, `audit.log` and next entry number
   unchanged.
8. **Maximum balance.** A deposit or transfer credit that would leave any receiving account above
   `max-balance` is rejected with
   `Rejected: <name> would exceed the maximum balance of <max-balance>.` (the maximum displayed
   as an amount). Fee credits are subject to the same limit. If the recipient is also the
   configured fee account, validate the combined principal and fee against its final balance;
   mutate the aliased account only after every destination passes validation.
9. **Frozen accounts** can neither send nor receive: a deposit, withdrawal, transfer or payment
   involving a frozen account (as sender or as recipient) is rejected with
   `Account <name> is frozen.` (the sender is checked first). The fee account receiving a fee
   is not checked.
10. **Validation order.** For every subcommand: an unknown subcommand, or no subcommand at all,
    gets the general usage line; a wrong number of arguments gets the subcommand's usage line;
    then permissions are checked; then the arguments are validated from left to right (for
    each account argument, first its syntax, then its existence; for an amount, its syntax);
    then the state checks run in this order: same account, frozen sender, frozen recipient,
    funds, maximum balance. The first failure is the only reply. A rejected command changes
    nothing: no balance, no file and no entry number.

## Audit log and history

11. **Entries.** Every successful change is recorded as exactly one entry with the next entry
    number (1, 2, 3, …, never reused). Types: `OPEN`, `DEPOSIT`, `WITHDRAW`, `TRANSFER` (also
    for payments), `FREEZE`, `UNFREEZE`. A transfer is one entry, whatever the fee.
12. **`audit.log`.** Each entry is appended to `plugins/CoinLedger/audit.log` as one line
    (UTF-8, `\n` line ends) of seven fields separated by `|`:

    ```text
    <number>|<type>|<account>|<counterparty>|<amount-cents>|<fee-cents>|<fee-account>
    ```

    `<account>` is the account the entry is about (the sender for a transfer), `<counterparty>`
    is the recipient of a transfer and `-` otherwise; amounts are whole cents; the fee is `0`
    for everything but a transfer; `<fee-account>` is the fee account name when the fee is
    greater than zero and `-` otherwise. `FREEZE` and `UNFREEZE` have amount `0`. Examples:

    ```text
    1|OPEN|treasury|-|0|0|-
    2|OPEN|alice|-|10000|0|-
    3|DEPOSIT|alice|-|1000|0|-
    4|TRANSFER|alice|bob|5000|100|treasury
    5|FREEZE|alice|-|0|0|-
    ```

13. **History.** `/ledger history <account> [page]` lists the entries that involve the account
    (as account, counterparty or fee account), newest first, `history-page-size` per page. The
    page defaults to 1 and must be a whole number of at least 1, otherwise
    `Invalid page: <argument>`. When the page is past the last page:
    `Page <page> does not exist; last page is <last>.` Otherwise the reply is the header
    `History of <name> (page <page>/<last>):` followed by one line per entry:

    | Entry | Line |
    | --- | --- |
    | `OPEN` | `#<n> OPEN +<amount>` |
    | `DEPOSIT` | `#<n> DEPOSIT +<amount>` |
    | `WITHDRAW` | `#<n> WITHDRAW -<amount>` |
    | `TRANSFER`, seen by the sender | `#<n> TRANSFER -<amount> to <recipient> (fee <fee>)` |
    | `TRANSFER`, seen by the recipient | `#<n> TRANSFER +<amount> from <sender>` |
    | `TRANSFER`, seen by the fee account | `#<n> FEE +<fee> from <sender>` |
    | `FREEZE` / `UNFREEZE` | `#<n> FREEZE` / `#<n> UNFREEZE` |

## Persistence

14. **`accounts.yml`.** After every change, `plugins/CoinLedger/accounts.yml` holds the next
    entry number and every account, balances in whole cents:

    ```yaml
    next-entry: 6
    accounts:
      alice:
        balance: 4900
        frozen: true
    ```

15. **Reload.** `/ledger reload` re-reads `config.yml`, `accounts.yml` (missing file: no
    accounts, next entry 1) and `audit.log` (missing file: no history) from disk, applies
    requirement 4, and replies `CoinLedger reloaded: <n> accounts.` counting every account after
    the reload. Balances come from `accounts.yml`; history comes from `audit.log`.

## Commands and permissions

16. One command, `/ledger`, with these subcommands (case-insensitive subcommand names):

    | Subcommand | Permission | Success reply |
    | --- | --- | --- |
    | `open <account>` | `coinledger.admin` | `Opened account <name> with <balance>.` |
    | `balance [account]` | see requirement 18 | `Balance of <name>: <balance>.` |
    | `deposit <account> <amount>` | `coinledger.admin` | `Deposited <amount> to <name>. Balance: <balance>.` |
    | `withdraw <account> <amount>` | `coinledger.admin` | `Withdrew <amount> from <name>. Balance: <balance>.` |
    | `transfer <from> <to> <amount>` | `coinledger.admin` | `Transferred <amount> from <from> to <to> (fee <fee>).` |
    | `pay <account> <amount>` | `coinledger.pay` | `Paid <amount> to <name> (fee <fee>). Balance: <balance>.` |
    | `freeze <account>` | `coinledger.admin` | `Account <name> is now frozen.` |
    | `unfreeze <account>` | `coinledger.admin` | `Account <name> is no longer frozen.` |
    | `history <account> [page]` | see requirement 18 | requirement 13 |
    | `top` | none | requirement 17 |
    | `reload` | `coinledger.admin` | requirement 15 |

    Other replies: `Account <name> already exists.` (open), `Account <name> is already frozen.`,
    `Account <name> is not frozen.` A sender without the permission gets
    `You do not have permission to do that.` The usage lines are:

    ```text
    Usage: /ledger <open|balance|deposit|withdraw|transfer|pay|freeze|unfreeze|history|top|reload>
    Usage: /ledger open <account>
    Usage: /ledger balance [account]
    Usage: /ledger deposit <account> <amount>
    Usage: /ledger withdraw <account> <amount>
    Usage: /ledger transfer <from> <to> <amount>
    Usage: /ledger pay <account> <amount>
    Usage: /ledger freeze <account>
    Usage: /ledger unfreeze <account>
    Usage: /ledger history <account> [page]
    Usage: /ledger top
    Usage: /ledger reload
    ```

    Register the permissions `coinledger.admin` and `coinledger.view` with default `op`, and
    `coinledger.pay` with default `true`, in `plugin.yml`.
17. **Top.** `/ledger top` replies `Top accounts:` followed by up to five lines
    `<rank>. <name>: <balance>`, ranked 1 to 5 by balance (highest first) and, for equal
    balances, by name in alphabetical order. With no account at all it replies `No accounts.`
18. **Players.** `pay` is a transfer from the paying player's own account to `<account>`, so
    requirements 7 to 10 apply to it. Right after its permission check, a sender that is not a
    `Player` gets `Only players can use /ledger pay.` and a player without an own account gets
    `You do not have an account.`; the arguments are validated after that.
    `balance` with no argument shows the sender's own account and needs no permission; a
    sender that is not a player gets `Only players can use /ledger balance without an account.`
    and a player without an account gets `You do not have an account.`
    `balance <account>` needs `coinledger.view` or `coinledger.admin`, and
    `history <account> [page]` needs `coinledger.admin`, unless the account is the sender's own
    player account. For these two subcommands the account argument (syntax, then existence) is
    validated before the permission check, and the page after it.

The hidden cases run against the real server and cover the default files, every reply above,
fee rounding, the validation order, frozen accounts and the maximum balance, the exact content
of `accounts.yml` and `audit.log`, history paging, the ranking, reload from files the grader
writes itself, payments by player stand-ins, case-normalized self-transfer ordering, a fee account
that is also the recipient at its balance limit, and permission checks with limited senders.
