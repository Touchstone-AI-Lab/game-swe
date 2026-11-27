# Foreground client result v4 — namespace permission blocker

Status: **client update completed; login not reached; Linux runtime incomplete**.
This supplements the preserved v3 result and its two earlier failed starts.

## Authorized execution and observations

The operator approved one additional foreground-supervised start, initially
bounded to 15 minutes. After observed transfer speed showed that was insufficient,
the operator approved 45 minutes total for the same container. A controller
handoff retained that container and its download. Only the old `docker wait`
observer was terminated; its exit 143 was an intentional control transition,
not a Steam failure or another startup.

The container was `e82d52f2ec44b6c0331d25ad5fa2eedc521e4de03544bbb694594dc8028954b5`.
It ran from 2026-10-30 16:36:11.391 UTC to 17:11:07.415 UTC, about 34m56s, using
the same image and default container permissions as the earlier experiment.
The updater reached 487,789 / 487,789 KB. The operator confirmed a visible update
window, and the installed requirements checker subsequently ran. There was no
container restart and the 45-minute deadline was not exceeded.

Foreground supervision resolved the observed premature WSL lifetime problem
for this run. Completion of the update exposed a **separate** startup constraint:
the official client displayed “Steam now requires user namespaces to be enabled.”
The operator supplied that error screenshot; no authentication screen was captured.

## Permission diagnosis

| Bounded check | Exit | Observation |
| --- | --- | --- |
| WSL user-namespace creation | 0 | Supported by the host |
| Same WSL check with no-new-privileges | 0 | That flag alone does not cause this denial |
| Same check in the existing client container | 1 | Operation not permitted |
| Installed Valve requirements checker in the container | 71 | Bubblewrap could not create a namespace |

The container had no effective capabilities, no-new-privileges=1 and seccomp
mode 2. This identifies the current container policy as the blocking scope.
The exact sufficiency of a seccomp change has not yet been tested. No host
sysctl, WSL configuration, system package or permission was changed.

The installed `steam.sh` invokes `steam-runtime-check-requirements` and exits 71
after showing its error dialog. We closed only the single owned pre-login
`zenity` dialog; the container then exited 71 without forced termination. This
is orderly cleanup of a failed startup, not successful authenticated shutdown.

## Result boundaries

- WSL foreground lifetime: demonstrated through the complete client update.
- Visible independent official updater: confirmed by the operator.
- Login UI / usable authentication: not reached, not validated.
- Rhenium Steam provider session: none established.
- Fixed game depot acquisition / managed prepare / real Balatro controls: not run.
- Seccomp relaxation: proposed only, not executed.
- Original protection audit: passed again; 16 frozen controller and 350 private
  asset hashes match, as do every fixed dependency group and protected directory.

Fifteen offline probe tests, targeted Ruff/Mypy (five Python files), and shell
syntax checks passed for the prepared controls and permission gate. No production
core/Steam provider/evaluator was changed by these probe additions. Full repository
checks and real game regressions were not run in this revision.

Ignored evidence lives under `.test-state/linux-runtime-v1/`, including:

- `official-client-v1-20261031/foreground-v3-approval.json`
- `official-client-v1-20261031/foreground-v3-extension-approval.json`
- `official-client-v1-20261031/foreground-v3-observations.jsonl`
- `official-client-v1-20261031/foreground-result-v4.json`
- `official-client-v1-20261031/tests-namespace-proposal-v1.txt`
- `baseline-audit-post-auth-v4.json` and `PROGRESS-v4.json`

The earlier 31 authored-source files were preserved in a separate archive,
byte-verified against the unchanged PROGRESS-v3 hashes. Its receipt explicitly
records post-hoc preservation. No game, account state or dependency binary is in
that archive. Updated official-client state remains private in WSL; the client
self-update is not described as a pinned release.

Next proposed action is the explicitly gated, single-container
[permission experiment](CONTAINER-PERMISSION-REQUEST-v1.md). No further start
is authorized by this result. No commit, push, PR, model experiment or original
game/save modification occurred.
