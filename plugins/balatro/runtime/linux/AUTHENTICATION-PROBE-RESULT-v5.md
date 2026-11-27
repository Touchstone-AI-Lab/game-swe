# Namespace experiment v5 — login UI still incomplete

Status: **user-namespace preflight passed; sign-in UI repeatedly closed;
authentication and Linux game validation incomplete**. Earlier v3/v4 results
and their fingerprints are unchanged.

## Approved execution

The operator approved one 900-second client startup/login experiment with
`seccomp=unconfined` in this independent container only. UID/GID 1000,
cap-drop ALL, no-new-privileges, 3 GiB memory, 2 CPU, 512 PIDs and the isolated
mounts were retained. The image remained
`sha256:13dd77acbf5ea1fef11de17a313a5d1606bd9b9fa6e3e567c7a96da154188345`.
No host namespace setting, device access or privilege capability was added.

Container `ab910c09778137cb4274b9315458746345ee14b0ddb4d54f4a7e80c563ead227`
ran from **2026-10-30 17:21:14.658 UTC to 17:35:21.309 UTC**, 846.651 seconds.
The foreground controller remained active. The client performed another official
update in the same container; the updater reached 424,455 / 424,455 KB. This was
not a second manually launched client or a pinned client release.

## Findings and limits

- The authored entry's real `unshare --user --map-root-user true` passed.
  Valve's installed requirements checker also returned 0 during live observation.
  Bubblewrap and steamwebhelper processes subsequently ran. This resolves the
  earlier namespace prerequisite for this specific container policy; it does
  not prove successful authentication or sandboxed evaluation.
- The operator reported that “Sign in to Steam (Ubuntu)” repeatedly appeared
  and closed. No stable usable login or main interface was confirmed.
- At 17:32:03 UTC, `/dev/shm` was 60,452 / 65,536 KiB. Twelve bounded samples
  from 17:33:20 through 17:33:46 recorded 65,448 KiB used (88 KiB free) in
  eight samples. Shared-memory pressure is a concrete diagnostic lead, **not
  yet a confirmed cause** of the window failure.
- The cgroup recorded memory-limit hits (`memory.events max=1689`), but
  `oom=0`, `oom_kill=0`, and `pids.events max=0`. An earlier instantaneous
  1.25 GiB reading therefore did not exclude prior memory pressure.
- Bounded, pre-login CEF/webhelper log classification found no SIGBUS, explicit
  GPU exit, fatal error or allocation-failure match in the inspected tails.
  D-Bus connection messages were present. Generic occurrences of “crash” are
  not treated as crash counts. No crash dump or authentication file was read,
  and no raw client log or sign-in screenshot was exported.
- Current repository `providers/steam/src/rhenium_steam/official_client.py`
  uses `--shm-size=1g`; this probe inherited Docker's 64 MiB default. The
  provider also has different CPU/memory and graphics flags. Those differences
  are not silently applied or treated as proof of the cause.

The existing process was stopped after sufficient evidence. Official shutdown
IPC returned 0, but the container did not exit within the controller's wait.
Docker stop was required and the final exit was **137, OOMKilled=false**.
This is forced cleanup of an incomplete startup, not a normal successful
authenticated shutdown. No client remains running; the 900-second deadline was
not exceeded. Old containers, launch markers, private state and evidence remain.

## Validation and next boundary

The independently recorded state database still has zero Steam provider
sessions. No account marker was found; marker absence is supporting metadata,
not the authentication criterion. Game acquisition, `runtime prepare`, Balatro
startup and gold/base engine controls remain **unexecuted**.

The proposed next comparison changes only `/dev/shm` capacity to 1 GiB while
retaining the current 3 GiB total memory, 2 CPU and permission policy. It has a
separate approval gate and exclusive attempt record. It also checks the sampled
client file hashes before launch. Steam can still self-update afterward; any
such change must be recorded as a potential comparison confounder.
See [the concrete proposal](SHARED-MEMORY-CHANGE-REQUEST-v1.md).

Validation results and final authored-source fingerprints are recorded in
ignored `.test-state/linux-runtime-v1/PROGRESS-v5.json`. The new comparison
itself has **not run**. Twenty-one offline probe tests, targeted Ruff/Mypy
(six Python files), syntax checks for all five probe shell scripts and
`git diff --check` passed. ShellCheck is unavailable and was not installed.
Full repository checks and real-game regressions were not run in this revision.
Protection was rechecked: 16 frozen controller files, 350 private assets, all
six dependency groups and protected directories remain unchanged.

Evidence under `.test-state/linux-runtime-v1/official-client-v1-20261031/`:

- `namespace-v4-approval.json`, `namespace-v4-observations.jsonl`,
  `namespace-v4-updater-observations.jsonl`;
- `namespace-v4-ui-diagnosis-v5.json`, `namespace-v4-ui-resources-v6.json`;
- `linux-namespace-request.json`, `linux-namespace-supervision-result.json`,
  `linux-namespace-shutdown-result.json`, `final-metadata-v5.json`;
- `tests-shm-proposal-v1.json` (initial line-length lint failure),
  `tests-shm-proposal-v2.json` (final checks) and their text outputs.

All 38 prior authored-source files were byte-verified against unchanged
PROGRESS-v4 hashes and preserved before these follow-up edits. No game,
dependency binary, save or account state is in that source archive. No
production provider/core/evaluator change, commit, push or PR occurred here.
