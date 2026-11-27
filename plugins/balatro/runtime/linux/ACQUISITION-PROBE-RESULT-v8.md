# Fixed-depot capability result, revision 8

On 2026-10-31 (Asia/Shanghai), the operator-approved container-local CEF probe
verified an actual loopback-only listener and the installed console/User APIs.
The source-confirmed login callback reported state 5 and result 1. The installed
UI's completion branch and enum were checked; no account/password/token fields
were exported. The independent sign-in was reused without a new login flow.

The first read-only help observer captured the echoed query, not its help. A
separate preserved revision excluded that echo and confirmed the client's real
`download_depot <appid> <depotid> [manifestid]` syntax.

Exactly one request was issued for app 2379780, depot 2379781, manifest
3512319404653808464 (build 17459173). Its completion event reported that exact
manifest once and no failure event. The initial controller nevertheless failed
its assumed path check. This original result remains **incomplete**.

Read-only reconciliation located the unique expected game file under
`.steam/debian-installation/ubuntu12_32/steamapps/content/app_2379780/depot_2379781`
inside the existing private home. It is 56,381,239 bytes and has the fixed SHA-256
`0d75fe164accf3312734d4b37ac98788dd15f0b8e4f9bb8b7f90c4e59de93f47`.
A second diagnostic incorrectly inferred the depot root from the Steam process
working directory and failed; that source is preserved too. Revision 3 verifies
the discovered confined file against the original request, exact completion
manifest and checksum. The original completion path string was not retained,
so its literal spelling cannot be reconstructed from that observer.

No acquisition command was resent. The separately versioned reconciliation
confirms the acquired fixed source; it does not rewrite the first probe as a
pass. The actual root layout is now handled by the managed provider's returned-
path validation rather than an assumed installation-directory suffix.

The client ran from 02:24:11 to 02:44:38, exited 0 after official shutdown IPC 0,
and needed no forced stop. Sampled client code stayed unchanged. All earlier
probe evidence and 47 v7 authored source files were preserved. The new protocol
and original probes passed 50 targeted Python tests and separate JS observer
unit checks. Those are not real-game tests.

Evidence: local `.test-state/linux-runtime-v1/acquisition-v8/` plus the sanitized
CEF/API/help/path receipts. The original private game and account state were not
exported. **Managed prepare and real Balatro engine validation are still separate,
unfinished stages at this revision.** No task score, Linux integration completion,
commit, push or PR is claimed here.
