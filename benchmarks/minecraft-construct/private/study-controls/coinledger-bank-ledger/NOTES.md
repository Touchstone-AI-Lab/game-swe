> E0 controls for pack version 1.0.0 (2026-09-24).

> Historical evidence below. Current pack 1.3.0 validation is recorded separately.

# E0 notes: minecraft/construct/coinledger-bank-ledger

Private maintenance material. Never copy into an attempt or a model workspace.

Layout: construct task. The workspace holds `plugin/` (the frozen `pom.xml`, a minimal `plugin.yml` and an empty main class). Controls use `root` = `plugin`: patches apply with `patch -p1` from `/app/plugin`, the `alternative` tree is copied over `/app/plugin`. Reference = skeleton + `solution/after/` (`solution/solve.sh`).

## Case roles

30 cases: 2 `static` (`check:submission-shape`, `check:offline-build`), 1 `runtime-sentinel` (`server:CoinLedger is enabled`), 27 `target`, 0 `preserved`. A construct task has no preserved contract: the skeleton does nothing, and every target case fails on it.

## Controls

| control | kind | what it is | observed | admissible |
| --- | --- | --- | --- | --- |
| `starter` | starter | the unchanged skeleton | complete, fails every target case, passes the sentinel and both static checks (10/100) | yes |
| `reference` | reference | skeleton + `solution/after` | 28/28, 100 | yes |
| `target-negative-fee-rounded-to-nearest` | target-negative | reference with `Math.round(amount * percent / 100.0)` as the fee | fails exactly `fees are rounded down to the cent` (`transfer hank_10 ivy_10 12.34` replied fee 0.25 coins, expected 0.24) | yes |
| `alternative` | alternative | independent plugin written from the exam alone | 28/28, 100 | yes |

## The alternative

Written by an isolated agent that read only the public exam and the skeleton (no suite, reference or other task), compiled against the pinned API and never run on a server before the control run: nine classes: a table of subcommands (usage, argument counts, handler), `Entry`/`LedgerStorage` split, an atomic `accounts.yml` rewrite, fee-account creation shared by enable and reload. It scored 100 on its first run. The agent listed the points it found underspecified: the pay reply balance (the payer's), the fee account as a transfer party, an empty history page, a missing `next-entry`; none of them is asserted by a case.

## Runs

Engine: real Paper 1.21.11 build 132 in the prepared verifier image, `--network=none`, through `rhenium run minecraft/construct/coinledger-bank-ledger` (runtime `paper-1.21.11-132-construct`).

| control | run | score | complete | failed cases |
| --- | --- | --- | --- | --- |
| reference-1 | `run-603fdc49edbc446a` | 100.0 | True | none |
| reference-2 | `run-dc9244c5107c4082` | 100.0 | True | none |
| reference-3 | `run-5032a29d06674b18` | 100.0 | True | none |
| starter | `run-f4acc4ca786247df` | 10.0 | True | all but the sentinel |
| target-negative | `run-fda967d14b2546b6` | 10.0 | True | `fees are rounded down to the cent` |
| alternative | `run-98e915c73a624770` | 100.0 | True | none |

Authoring runs before the Hub runs (same server image and suite, the trusted javac build instead of Maven) gave the same outcomes for the reference, the target-negative and the alternative.

## Pack 1.3.0 alternative maintenance, 2026-11-04

The original independent alternative predates the public combined-credit requirement.
Its current-version run `run-01dda71eb8b0489b` completed but failed the case where
the recipient aliases the configured fee account. That record is retained.

Maintenance now validates principal plus fee together for an aliased recipient and
validates any separate fee destination before mutating balances. A sender receiving
its own fee has a net debit and needs no extra credit capacity. This extends the
original alternative to the current public exam; it is no longer claimed as an
untouched independent first-attempt implementation. Assertions, reference, skeleton
and scoring are unchanged. Fresh full real-server run `run-e37cebfd3baf456a` completed at 100/100 with every current case passing.
