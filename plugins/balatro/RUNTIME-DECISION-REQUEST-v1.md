# Decision requested: licensed Windows maintenance validation

Status: **pending**, no native platform run authorized or performed by this adapter.
Maintainer: Sangyu Pan. This document changes no project rule or frozen task.

## Why a specific decision is needed

Root `AGENTS.md`, section 3, says:

> A plugin-owned native Windows runner is permitted for a separately prepared,
> non-licensed server when evaluation performs no login, acquisition, install,
> update, or build.

Balatro is a licensed desktop game. It is outside that documented server allowance.
The earlier asset-stage `docs/games/balatro.md` explicitly requires resolution of
this boundary. The request to implement a plugin authorizes source work, but does
not expressly resolve this different runtime category. The existing PoC smoke
approval applies to the PoC recovery batch, not a general platform policy change.

## Proposed bounded decision

Authorize this Balatro integration work to implement and validate a **trusted,
honest-mode maintenance adapter** against the already licensed, operator-prepared
Windows installation and fixed PoC dependencies. This is a local maintenance
exception for this task, not an edit to AGENTS.md or a platform-wide support claim.

The candidate set is limited to the self-authored, source-reviewed, hash-sealed
v0.2 gold/base controls and named targeted mutations. No arbitrary new submission,
model experiment, external mod, login, download, acquisition, installation, update,
repinning, VM, permission expansion or system-setting change is included.

The plugin/core remains Python 3.12. The existing fixed Python 3.13 controller is
invoked as a separately bound tool. It reuses the original Session, RPC, game
start/close lifecycle and fixed dependency/protected-directory checks. No game
component or frozen PoC file is rewritten. The existing protected baseline remains
mandatory. Real native execution stays serial, visible, gamespeed=1, FAST=0,
HEADLESS=0; existing-game process protection remains enabled.

## Reviewable implementation boundary

- `catalog.py` and `plugin.py` read exact frozen public assets via `pack_root`.
  Anonymous presentation replaces only the local identity token. No rules change.
- `submission.py` seals allowlisted starter files under platform state; the seal
  is not authorization to run unreviewed Lua.
- `protocol.py` defines a size-bounded response with protocol version, request ID,
  nonce and submission hash. Missing checks, changed fingerprints, duplicate cases,
  incomplete execution or failed cleanup cannot become a passing result.
- `evaluator.py` currently seals a valid submission and returns
  `runtime_action_required`. It has no launch path or environment-variable bypass.
- Proposed next implementation: pack-local byte-identical private authored task
  assets, a fixed-tool sidecar binding and a minimal Runtime initializer adapter
  to place generated directories under platform state. Reuse the original
  Runtime.start/close and Session behavior; do not duplicate a game runner.
- Before any game launch, validate private source/required-case closure, tool and
  dependency bytes, environment/harness/task/candidate identities and a fresh
  matching smoke. Cancellation/timeout cleanup requires owned-process evidence;
  unresolved cleanup halts subsequent runs and remains incomplete.

## Proposed real validation after the decision

1. Freeze the completed adapter and run tests, packaging checks and read-only
   protection/dependency preflight.
2. Run one bounded serial platform smoke/control pilot. Retain any failure;
   distinguish protocol/environment/behavior and stop on protected-data drift.
3. Through actual `prepare-attempt` and `run-attempt --profile full`, run ten
   gold/base pairs three times each, interleaved: 60 clean task workflows. Expected
   native-process count is derived from the frozen task scenarios (currently 168
   for this matrix), never counted as 60 identical single-process runs.
4. Run the declared targeted mutations and necessary common-adapter regressions.
   Do not relabel the old 108 PoC flows / 309 native processes as new evidence.
5. Publish only sanitized summaries, hashes and reproducible operator commands.
   Keep all licensed content, private assertions, raw logs and saves private.

This authorizes neither `untrusted` evaluation nor formal disposable-host support.
Those require a separate credential-free, networkless, disposable evaluation-host
implementation and independent evidence of destruction under the existing
contract. This adapter does not provide those guarantees.

If this scoped maintenance exception is not desired, the plugin must remain at
anonymous preparation/sealing plus an incomplete runtime result until an approved
licensed runtime route is supplied. No alternative host is installed implicitly.
