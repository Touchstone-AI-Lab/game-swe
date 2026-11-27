# Native Linux startup diagnosis, revision 1

This is maintenance evidence on the controlled WSL2/WSLg host. It is not yet a
complete Linux benchmark integration. No task score or save/load result has been
claimed from these probes.

## Acquisition boundary

The operator-approved container-loopback CEF path reused the independent official
Steam login. Packaged provider authentication, `rhenium runtime prepare` and
read-only `runtime verify` completed. The fixed source is app 2379780, build
17459173, depot 2379781, manifest **3512319404653808464** (kept as a decimal string).
The 56,381,239-byte `Balatro.exe` matches SHA-256
`0d75fe164accf3312734d4b37ac98788dd15f0b8e4f9bb8b7f90c4e59de93f47`.

The first managed preparation received the complete event and exited normally,
but the authored path parser rejected the client's mixed `/` and `\` separators.
Preparation v3 normalized those separators and reconciled the original request,
completion, normal-exit receipt and file hash. It did **not** resend the command.
The earlier capability-path assumption and first managed-authentication failure
remain recorded; the latter's precise Docker-exec cause is unknown.

Prepared artifact identity:
`sha256:8a201bc4a3696d829c2f8cf5c3b4ba81503c5c8327b18b6a3099bef2e780e9c0`.
It remains the unbound `balatro-linux-17459173-probe-v1` artifact, whose builder
deliberately reports `engineValidated: false`.

## Real-engine timeline

The following IDs identify exclusive local process directories under the Linux
operator state's `engine-v1/`. Each result includes its actual source hashes.

| Run ID | Controlled difference | Observed result |
|---|---|---|
| 20261031-033813-4076288d | Original guard, native LÖVE `--fused` | Physical save/mod/appdata isolation passed; exit 0 before game initialization |
| 20261031-033858-627bdd8d | Original game, SMODS, Bot and control | Visible MENU and owned loopback RPC passed; one `start` timed out after 25 seconds |
| 20261031-034550-2ee21ee8 | Read-only event observer v1 | One completion event registered; callbacks returned false; no completion response sent |
| 20261031-035454-9a261771 | Ordinary private-profile window change to 1280×720; observer v2 | Still about 5 FPS; update work dominated, not drawing/presentation; incomplete |
| 20261031-035932-85ec82c7 | Original fullscreen profile; timing observer v3 | Focus present; RPC, controller, event manager and mouse work small; no clipboard reads; incomplete |
| 20261031-040349-e43d68c6 | Timing observer v4 | 147 frames: sound modulation 26.801 s, total Game.update 27.376 s; incomplete |
| 20261031-040913-d0a63f71 | Process-local OpenAL null output; observer v4 | Full original start response, select and real play passed; 727 frames, sound modulation 0.242 s, about 60 FPS |
| 20261031-041332-420cefff | Same null output, **no diagnostic/window mods** | All five real smoke checks passed, including actual hand-counter advancement |

Every listed process exited normally with code 0 and verified unchanged managed
artifact/staged input bytes. The five start timeouts remain incomplete. Their
read-only reconciliation reaching BLIND_SELECT was never counted as success.
No uncertain start was resent within a process.

## Confirmed cause and narrow control change

The event manager was progressing too slowly in wall time because the original
sound-update path dominated each frame. The fixed Bot supplies 1/60 second per
visible update; at about 5 real FPS the ordinary startup events could not satisfy
the original completion predicate within the unchanged timeout. The predicate
requires the blind-on-deck value and the small-blind tag UI object; neither was
written or fabricated by the diagnostic.

The new process environment can select `ALSOFT_DRIVERS=null`. OpenAL's own log
confirmed library **1.23.1-d3875f3**, backend **null**, device **No Output**.
The real audio API and all original game updates still execute. This is not a
replacement `modulate_sound`, skipped event queue, lock clear, speed change,
shader disable, headless mode, or timeout increase. The frozen Bot already mutes
game audio in this profile. No host audio setting or component byte changed.
The exact internal reason for the default audio route's latency was not traced;
the controlled comparison establishes the working process profile, not a claim
that a particular host driver has an upstream defect.

The controls are documented by [OpenAL's environment-variable documentation](https://github.com/kcat/openal-soft/blob/master/docs/env-vars.txt).
The packaged binary was also checked for the corresponding supported options.
LÖVE's [fixed 11.5 argument implementation](https://github.com/love2d/love/blob/11.5/src/modules/love/arg.lua)
and the prepared AppRun supplied the native launch semantics. An earlier authored
inspection mistakenly tried unsupported `--help`; its bounded 10-second timeout
is retained as an inspection failure, not game evidence. No process remained.

## Diagnostic integrity and remaining work

Observers v1–v4 retain original call counts, arguments, all return values and
exceptions. They only wrap callbacks subsequently invoked by the engine. Counts,
state changes and timing metadata are bounded to 512 rows / 192 KiB. They never
record clipboard contents, full game source or saves. Four LuaJIT unit cases
verified forwarding, nil-containing multiple returns, exception identity and no
unscheduled callbacks; these fake-object unit tests are **not engine evidence**.

Still required: the frozen save/new-process/initialized-load capability probe,
Linux Session/evaluator artifact boundary, current-code smoke and gold/base task
controls, relevant final tests, final protection audit and replay documentation.
Task bindings are empty. No untrusted-execution, cross-host, model-calibration or
release claim is made. No commit, push or PR was performed.
