# Proposed non-QR acquisition capability probe — approval required

This is a concrete proposal, not implemented support. It requests a bounded
provider capability experiment, not permission to change AGENTS.md or receive a
Steam password. No password-based helper protocol is proposed.

## Proposed operator flow

1. Prepare one independent official Steam client in a task-owned Linux container
   and a new provider-owned home under the existing dedicated WSL state root.
   Do not mount daily Steam directories, Windows user data or existing saves.
2. Present the official client through the existing visible WSLg display. The
   operator enters credentials directly into Valve's client and confirms on the
   phone. The agent and Rhenium do not enter, capture, inspect, relay or log the
   password or authenticator code. Do not use the current screenshot/QR loop.
3. Test whether an authenticated official-client mechanism can automatically
   obtain **app 2379780, depot 2379781, manifest 3512319404653808464, build
   17459173** into the dedicated source cache. The acquisition interface and its
   reliable completion signal still require verification; do not assume client
   sign-in supplies the existing helper's refresh token or guarantees an old
   manifest remains accessible.
4. Require exact downloaded game hash
   `0d75fe164accf3312734d4b37ac98788dd15f0b8e4f9bb8b7f90c4e59de93f47`, complete
   manifest/file verification and bounded normal process shutdown. Authentication
   or partial-download success alone is insufficient.
5. Only if these capabilities are demonstrated, propose the minimal provider
   implementation that makes the flow an explicit `rhenium runtime prepare`
   operation. Preserve the generic core and existing QR backend. Do not begin
   benchmark controls using an out-of-band acquired tree and call them managed
   runtime validation.

## Expected implementation boundary

- Work belongs in the Steam provider, adjacent to `provider.py`,
  `official_client.py`, its assets and provider tests. Use an explicitly versioned
  official-client session type; do not invent a fake helper refresh token.
- Keep client credentials entirely provider-owned. Public status contains only
  backend, account alias, operation stage, completion and failure category.
- The current official-client screenshot script must not run in this mode.
  Tests must prove no password input API, screen capture or secret-bearing
  logging path is enabled during authentication.
- Login validation must prove an authenticated usable client, not just the
  presence of `loginusers.vdf`. Acquisition must enforce the exact source and
  check completion/contents; evaluation must never acquire or update anything.
- No provider source, helper manifest, dependency pin, game component or project
  rule has been modified for this proposal.

## Limits of requested approval

Permit one isolated client preparation and one operator login attempt. Run at
most two bounded acquisition/diagnostic attempts, and permit the second only if
the first provides a concrete new diagnosis and the action is confirmed safe to
repeat. Preserve each failure. No unconfirmed non-idempotent action is resent.

Use the current WSL and Docker installation. Do not install host packages or
change host settings. The existing bootstrap uses `seccomp=unconfined`; that
permission is **not** implicitly included here. If the new visible client needs
additional container/host permissions, stop and report the exact requirement.
Steam's official client may self-update; its version is not a fixed game/runtime
pin and must be recorded truthfully. No game, loader or frozen dependency upgrade
is authorized.

Stop if the client cannot start within existing permissions, a reliable automatic
fixed-depot interface cannot be established, the manifest is unavailable, or
progress would require handing a password to Rhenium. Keep the Linux task blocked
and request a specific decision rather than substituting manually copied files.

## Decision requested

Approve this bounded official-client/provider capability experiment, or retain
the acquisition blocker. Approval for a successful experiment would still not
mean the full Linux runtime or ten real-engine controls have passed.
