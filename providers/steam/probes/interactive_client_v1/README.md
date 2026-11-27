# Official client interactive capability probe v1

This is an approved, bounded local experiment, not a registered provider backend.
It is not a replacement for `rhenium runtime prepare` or managed validation.

The operator enters their credentials only into the visible Valve client. The
controller has no password input API and does not capture or inspect the sign-in
screen. The existing QR/screenshot bootstrap script is not used. Client stdout
and stderr go to `/dev/null`; Valve's own state stays in the private mounted home.
Do not read or publish client credential files or raw authentication logs.

Use the task-owned home under `/home/psy/balatro-linux-v1/state`, uid/gid 1000,
the WSLg X11 socket, Docker's default seccomp policy, `--cap-drop ALL` and
`--security-opt no-new-privileges`. Do not mount the Docker socket, devices,
daily Steam directories or Windows user data. No host package installation.
The base and bootstrap archive reuse the reviewed provider recipe's hashes.
Container packages and Steam's subsequent self-update are not pinned releases.
The client has not yet demonstrated that it works with this security policy.

The launch marker intentionally prevents an accidental second login attempt in
the same home. No retries or acquired-game fallback are automatic. Record each
attempt's image identity, recipe hashes, permissions and outcome privately.

Stop if startup requires extra permissions. At most two acquisition/diagnostic
attempts are approved, the second only after new evidence and confirmation that
it is safe. A usable authenticated client, automatic exact-depot acquisition,
manifest/file verification and normal shutdown all remain to be demonstrated.

The two approved attempts on 2026-10-31 stopped during client updates. The
controller originally returned after detached launch; read-only host observation
showed Ubuntu stopping after its foreground caller returned. `control.py start`
now keeps a bounded foreground `docker wait`. The original attempt marker and
receipts still prevent reusing the initial launch. The separate
`resume_foreground_v3.py` / `resume-launch-v3.sh` pair was prepared for a separate
replay, which was subsequently approved, executed and extended to 45 minutes total
with the operator's explicit approval. It completed the update in the same
container and then encountered the official user-namespace requirements error.
The old observer's termination during deadline handoff was not a client restart.
No login occurred; the error flow exited 71 without forced container termination.

`namespace_probe_v4.py` / `namespace-launch-v4.sh` subsequently ran once with
explicit permission for 900 seconds and container-local `seccomp=unconfined`.
The namespace preflight passed and webhelper started, but the sign-in window
repeatedly closed. Bounded metadata showed nearly full 64 MiB `/dev/shm`.
Shutdown IPC did not finish cleanup; Docker stop produced exit 137 without
an OOM kill. No usable login or provider session was established.

`shm_probe_v5.py` / `shm-launch-v5.sh` subsequently ran once with separate
approval: 1 GiB `/dev/shm` with the same other limits and permissions. The
operator confirmed successful sign-in; official shutdown completed with exit 0
and no forced stop. Shared-memory use reached about 248 MiB. That single-attempt
approval is now consumed, and its marker must not be removed for another run.

The general observer does not validate authentication; operator confirmation
is recorded separately. There is still no registered provider session or
automatic fixed-depot acquisition result. No host namespace setting changed.
Historical default launch permissions and wait durations remain unchanged.
These probes are not an untrusted-code sandbox or a completed managed
authentication backend. See the Balatro Linux authentication result v6 for the
actual policy, evidence and remaining boundaries.

`console_probe_v7.py` / `console-launch-v7.sh` are prepared but unexecuted.
They require separate approval for the authenticated client's CEF control
endpoint. The first probe validates the actual loopback listener before reading
bounded metadata; it exports no raw titles, URLs, page content or credentials.
It does not yet issue console commands or prove authentication/acquisition.
The tested resource/security policy and existing client state are reused.
