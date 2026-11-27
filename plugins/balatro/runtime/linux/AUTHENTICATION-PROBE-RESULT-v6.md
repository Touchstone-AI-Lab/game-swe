# Shared-memory comparison v6 — interactive login and normal exit

Status: **operator-confirmed sign-in succeeded; normal shutdown confirmed**.
This is a local official-client capability result, not a registered Rhenium
Steam session, automatic acquisition result or completed Linux game runtime.
All earlier results and the original approval proposals are preserved.

## Exact comparison and outcome

The operator separately approved one run of at most 900 seconds. The launch
configuration changed only `/dev/shm` capacity, from Docker's 64 MiB default to
1 GiB. The image, private client home, UID/GID 1000, cap-drop ALL,
no-new-privileges, container-local seccomp=unconfined, 3 GiB memory, 2 CPU,
512 PIDs and original mount boundaries were retained. The new script/attempt
markers identify this authorized comparison and prevent automatic reuse.

The controller verified all 42 reviewed authored-source hashes and prior
evidence before launch. It also verified the sampled client files against
the previous run before starting; those same hashes still matched afterward.
This is a sampled comparison, not a claim that the self-updating Steam client,
all its caches or remote web content are a fully pinned distribution.

| Observation | Result |
| --- | --- |
| Container | `1ccc1f621ac791c9d364cebe2f1429006e7c894068f236e4b063cf41b10d197a` |
| Image | `sha256:13dd77acbf5ea1fef11de17a313a5d1606bd9b9fa6e3e567c7a96da154188345` |
| Started, Asia/Shanghai | 2026-10-31 01:43:59.124 |
| Finished, Asia/Shanghai | 2026-10-31 01:48:45.673 |
| Duration | 286.549 seconds; deadline not exceeded |
| Namespace preflight | Passed |
| Interactive authentication | Operator reported successful sign-in and main interface |
| Shutdown | Official shutdown IPC 0; container exit 0; no forced stop |
| Process cleanup | This container and all four previous probe containers stopped |
| Credentials / sign-in screen | Not received, captured, inspected or exported by the controller |
| Game acquisition / game controls | Not executed |

Before operator confirmation, bounded samples recorded 83,276 and 79,260 KiB
shared-memory use. After confirmation the last live sample recorded
254,056 KiB (about 248 MiB), with 794,520 KiB free. All three live samples
reported zero cgroup memory-limit hits, OOM kills and PID-limit hits.
The last sample had 380 PIDs and 3,012,296,704 bytes of cgroup memory use,
still below the retained 512 PID / 3 GiB caps.

The previous 64 MiB run repeatedly approached capacity and the operator saw
the sign-in window close repeatedly. The new window allowed sign-in and
used more than that former capacity. This supports insufficient shared memory
as a practical startup constraint in this environment. No exact prior crash
signal was established, and this is one successful comparison, not a repeated
reliability study or proof that every previous symptom had the same cause.

## Authentication boundary and remaining work

The operator's explicit confirmation is the evidence for interactive sign-in.
An account marker exists, but its contents were not read and its presence is
not the success criterion. The general status observer intentionally continues
to report `authenticated: not_validated`: it has no authentication validator.
The result records human confirmation separately from **programmatic
authentication validation, which remains unimplemented/unverified**.

The independent official client retained its own private state in the existing
task-owned WSL home. The Rhenium state database still has **zero** Steam provider
sessions. No refresh token was extracted, fabricated or imported. An ordinary
official-client login is not a session accepted by the current helper backend.

Next technical work is a separately reviewed automatic acquisition interface
for the exact pinned depot/manifest, with an authenticated-client check and
reliable completion/file verification. The current approval excluded game
acquisition and additional starts, so neither ran. No manual game copy is used
to substitute for `rhenium runtime prepare`. Balatro startup, RPC and all real
gold/base controls remain unexecuted on Linux. No Linux, untrusted-execution,
managed-acquisition or release-readiness support claim follows from this probe.

## Evidence, checks and preservation

Ignored evidence under `.test-state/linux-runtime-v1/official-client-v1-20261031/`:

- `shm-v5-approval.json`, `shm-v5-observations.jsonl`;
- `operator-auth-confirmation-v6.json`;
- `linux-shm-request.json`, `linux-shm-supervision-result.json`,
  `linux-shm-shutdown-result.json`, `final-metadata-v6.json`.

`.test-state/linux-runtime-v1/PROGRESS-v6.json` binds this result to current
source, evidence and the actual authentication-container policy fingerprint.
This fingerprint is not a Balatro engine-runtime fingerprint.

No launch/control/test source changed after the 21 passing offline tests,
targeted Ruff/Mypy (six Python files) and five shell syntax checks recorded in
the preserved v5 evidence; their exact source hashes were rechecked. Those
tests were not rerun or relabeled as new runs. `git diff --check` and local
documentation links were checked again. ShellCheck remains unavailable; full
repository checks and real-game regressions were not run in this revision.

The post-run protection audit passed for 16 frozen controller files, 350 private
assets, all six dependency groups and protected directories. All 42 prior
authored-source files were preserved and byte-verified before documentation
updates. No credential, client cache, game, dependency binary or save entered
the source archive or Git. No original game/Mods, daily Steam, host settings,
project rules, frozen task semantics, core/provider production code or
evaluator changed. No commit, push or PR was performed.
