# Maintenance notes: coinledger-bank-ledger

## Task

Construct task: the model writes the whole CoinLedger plugin (a bank ledger with named
accounts, rounded-down transfer fees, frozen accounts, an append-only audit log, paged history,
a ranking, reload from disk and player payments) into a frozen Maven skeleton. The exam fixes
every reply line, both file formats and the validation order, so the hidden cases assert only
what the exam states.

## Skeleton

`environment/plugin/` holds the frozen `pom.xml` (Maven 3.9.11, Java 21, `paper-api`
`1.21.11-R0.1-20260511.115010-91`, byte-identical to the API jar bundled with Paper 1.21.11
build 132, plugin versions pinned), a `plugin.yml` with name, version, main class and
`api-version` only, and an empty `CoinLedgerPlugin`. The empty skeleton builds and enables, so
the `nop` control is complete and fails every case but the sentinel.

## Reference

`solution/after/` is the complete reference plugin (about 740 lines of Java): `Money` (cents
parsing and formatting), `LedgerSettings`, `Account`, `AuditEntry` (log line and history line),
`LedgerStore` (accounts.yml and audit.log), `Ledger` (operations and state checks),
`LedgerCommand` (argument order, permissions, replies) and `CoinLedgerPlugin`.
`solution/solve.sh` copies it over the skeleton.

## Live-server design

- 29 cases in `tests/suite/CoinLedgerSuite.java`, sentinel first, all synchronous. The added
  case combines case-insensitive account lookup, same-account transfer rejection, frozen-state
  validation order and rejection atomicity.
- Commands run through the command map with grader-owned senders (`tests/suite/Actor.java`):
  a console-like sender, permission-limited senders and `Player` stand-ins. Replies are
  compared as trimmed plain-text lines (`Kit.lines`).
- The first four cases check the state left by the first enable (default `config.yml`, the
  `plugin.yml` declarations, the fee account and `audit.log` line 1) and must run first.
- Every other case uses fresh account names, reads entry numbers from `accounts.yml` before
  acting, and asserts `accounts.yml` and `audit.log` directly. The ranking and reload cases write
  both files themselves and reload; the reload cases restore the default `config.yml` in
  `finally`.

## Fairness review

- Everything asserted is stated in the exam: amount syntax, display format, name rules, fee
  rounding, check order, file formats, history lines, ranking order, reply texts, usage lines,
  permission registration and defaults.
- The `Player` stand-in supports the methods the exam lists; the reference uses only
  `getName`, `hasPermission` and `sendMessage`.
- Timing does not matter: every case is synchronous and every file write happens before the
  command returns.
