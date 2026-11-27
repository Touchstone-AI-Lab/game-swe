# Official-client probe result v3 — 2026-10-31

Status: **incomplete; authentication and acquisition not validated**.
The operator approved `AUTHENTICATION-CHANGE-REQUEST-v1.md`. This report records
execution of that approval; it does not rewrite the earlier blocker or receipts.

## Executed scope

One container-only client preparation used the existing provider recipe's
Ubuntu base digest and Steam bootstrap 1.0.0.79 archive/hash. The new image is
`sha256:13dd77acbf5ea1fef11de17a313a5d1606bd9b9fa6e3e567c7a96da154188345`.
Build duration was 242.549 seconds. It contains OS libraries, not account state
or game files. Container packages and subsequent official client updates are not
claimed as pinned releases. Missing Docker buildx caused the existing CLI to use
its legacy builder; no host package was installed.

Both client containers used uid/gid 1000, default seccomp, dropped capabilities,
no-new-privileges, a private home and a read-only WSLg X11 socket. The second also
mounted one authored diagnostic script read-only. No device, Docker socket,
daily Steam directory or Windows personal directory was mounted.

| Attempt | UTC timestamps | Observation | Outcome |
| --- | --- | --- | --- |
| Initial startup | 2026-10-30 16:12:48.448 to 16:13:44.553 | Updater log reached 63,916 / 504,927 KB; sign-in webhelper not installed | Docker reported exit 255; OOM=false |
| Final approved diagnostic | 16:21:19.807 to 16:21:38.320 | Updater log reached 4,522 / 487,789 KB in this invocation; fixed stderr classifications emitted no error class | Docker reported exit 255; OOM=false |

These are client-update counters, not game acquisition progress. The operator
reported not closing the first window. There was no credential submission by
the controller, no screenshot/QR loop and no authentication validation. Client
stdout was discarded; the diagnostic emitted only fixed deduplicated error
classes, never raw stderr. Only the pre-login updater log was examined, with
sign-in-component/account-marker guards; no authentication log was read/exported.

Docker's exit 255 is not established as Steam's own error or a permission denial.
Neither process exit constitutes normal successful client shutdown.

## Confirmed control lifecycle defect and remaining uncertainty

Read-only host observation found no running Ubuntu distro before inspection.
An explicit foreground WSL process kept Ubuntu running for 25 seconds. Eighteen
seconds after that process returned, `wsl --list --running` again returned no
distros. The kernel boot ID was unchanged in this short experiment: the evidence
establishes distro shutdown, not a full VM reboot on every invocation.

The original launcher returned immediately after `docker run --detach`. It
therefore did not preserve a foreground WSL lifetime for the Docker service and
client. This is a confirmed controller deficiency and a supported explanation
for the interrupted updates. It has **not yet been proved to be the only cause**
by a corrected real-client run. Absence of a matched stderr class does not rule
out another client/display/network/sandbox problem.

Microsoft documents that systemd services do not keep a WSL instance alive:
[Systemd support in WSL](https://devblogs.microsoft.com/commandline/systemd-support-is-now-available-in-wsl/).
No WSL setting, service, VM timeout or security policy was changed.

The probe controller now retains a foreground, bounded `docker wait` after
launch. A 900-second deadline requests shutdown of the owned client and records
failure if cleanup needs container termination. Startup cannot be resent after
an ambiguous result. A new versioned resume script has been prepared, but **has
not been executed**: the approved two-attempt budget is exhausted.

An unrelated observation bug was fixed: Docker `top` requires a PID column;
the controller now requests `pid,comm` and publishes only process basenames.
Earlier failed observations and source hashes remain historical evidence.

## Validation and evidence

- Ten local probe boundary tests cover mount/privilege limits, non-resend,
  ownership, failed-exit classification, bounded foreground lifetime, deadline
  cleanup and fixed-class diagnostic output. No account/network is used.
- Targeted Ruff, Mypy and shell syntax checks accompany the final source receipt.
- Post-attempt audit passed: protected directories and fixed dependency bytes
  unchanged; all 16 frozen controller files and 350 private assets matched.
- No production Steam provider/core/evaluator code changed in this step. Old
  Balatro tests and game results were not relabeled as new regression results.
  No real game, depot acquisition, model experiment, commit or push was performed.

Ignored evidence: `.test-state/linux-runtime-v1/official-client-v1-20261031/`,
`baseline-audit-post-auth-v3.json` and `PROGRESS-v3.json` in its parent directory.
Private client state remains in the dedicated WSL state root; it must not be
published. The two exited containers and private state have not been deleted.

The original managed-runtime gate remains: a usable provider-owned session,
automatic exact-depot acquisition through `rhenium runtime prepare`, immutable
runtime identity and real engine controls must all pass before Linux support can
be claimed. No password/helper-token conversion or manual game copy is proposed.

See [the bounded foreground follow-up request](WSL-FOREGROUND-CHANGE-REQUEST-v1.md).
