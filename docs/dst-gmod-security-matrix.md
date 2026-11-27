# DST and Garry's Mod security boundary

This matrix records the current evaluator controls. It distinguishes repeatability and
process containment from the disposable host boundary required for formal untrusted scoring.

| Surface | DST | Garry's Mod (DarkRP and addon-repair packs) | Common formal requirement |
| --- | --- | --- | --- |
| Submission input | Temporary copied mod under the located `mods` directory | Submitted gamemode or addon tree mounted read-only, copied into the per-run container and staged into the server's `gamemodes/` or `addons/` directory | Stage only the submission into a clean guest and mount it read-only |
| Public/private assets | Public exam is separated; the hidden server suite (plus, for `dst/construct`, the plain-Lua suite) and the reference stay in the pack | Public exam is separated; the per-task GLuaTest suite, collector and reference stay in the pack and are mounted read-only at run time | Private assets are preinstalled in the immutable guest image and never exported |
| Engine installation | Hub: managed container with Dedicated Server build `24700372`; direct native use: operator-provided server without a build check | Hub: per-task evaluator images built from the digest-pinned public GLuaTest image by `rhenium runtime prepare`; evaluation performs no download, update or build | Runtime is prepared before imaging; evaluation performs no login/download/update/build |
| Game network setting | Offline/LAN cluster configuration | Container `--network=none` | Hypervisor/provider must enforce network `none` |
| Environment | Inherits the evaluator process environment | Container environment only; no host environment is passed | Disposable guest inherits no host environment or user profile |
| Filesystem | Temporary storage and mod copy; game install remains host-visible | Read-only submission and test mounts; only the run's log directory is writable | Runtime, benchmark and submission read-only; only declared run paths writable |
| Process control | POSIX session/process group with TERM/KILL timeout cleanup | Container CPU, memory and process-count limits, all capabilities dropped except six file/identity capabilities the entrypoint needs, and a two-minute engine timeout inside an outer evaluator timeout | Provider additionally proves no residual guest process/resource and destroys the guest |
| Plain-Lua limits | `dst/core`: none, mod code runs only inside the dedicated server. `dst/construct`: the plain-Lua runner removes dangerous globals and applies CPU, memory, file-size and wall-clock limits where supported | None beyond the engine; a static preflight rejects harness tokens, native modules and, for addons, `lua/gluatest/` and `lua/tests/` | Useful defense in depth, not a hostile-code boundary |
| Result integrity | Nonce-bound result marker and the exact frozen server case set (and, for `dst/construct`, the exact plain-Lua case set) | Patched GLuaTest runner: nonce-bound per-case audit, exact case set, harness hash, clean-exit, crash and terminal-verdict checks | Guest emits a bounded sanitized run-ID/nonce-bound envelope |
| Private-suite secrecy | Submission and injected assertions execute in the game runtime | Submission and private suite execute in the same GMod Lua state | Not guaranteed; disposable host limits host compromise, not same-process inspection |
| Current formal provider | None | None | Untrusted mode fails closed until an approved provider and immutable image exist |

The DST column describes the native runner. Hub `full` evaluations of `dst/core` and
`dst/construct` run that same runner inside the managed `dst/dst-dedicated-24700372` and
`dst/dst-dedicated-24700372-construct` containers, which add `--network=none`,
dropped capabilities, resource limits and a read-only submission mount. The private suite and the
submission still share one Lua state there, and a container is not a disposable host.

The Garry's Mod column applies to both GLuaTest packs; they share one evaluator and one
collector and differ only in the staged tree and their separately prepared runtime keys.
The two plugins share the same `DisposableEvaluationHost` policy path at the Hub
boundary. Neither container is described or renamed as a VM sandbox.

## Garry's Mod Addons pack (native App 4020 runner)

The `garrys-mod/addons` construct pack does not use the GLuaTest container. Its
plugin-owned native runner has these controls:

| Surface | Garry's Mod Addons | Common formal requirement |
| --- | --- | --- |
| Submission input | Validated Addon copied into a task-scoped hard-linked server view | Stage only the submission into a clean guest and mount it read-only |
| Public/private assets | Public exam is separated; per-task hidden, integration and server suites stay private | Private assets are preinstalled in the immutable guest image and never exported |
| Engine installation | Operator-provided Windows or Linux App 4020 with separate catalog pins, currently build `23150012` | Runtime is prepared before imaging; evaluation performs no login/download/update/build |
| Game network setting | Native server command and isolated run directories; no OS network block | Hypervisor/provider must enforce network `none` |
| Environment | Server environment uses an explicit allowlist | Disposable guest inherits no host environment or user profile |
| Filesystem | Per-phase server views, isolated data/temp/log/result directories | Runtime, benchmark and submission read-only; only declared run paths writable |
| Process control | Windows Job Object or Linux POSIX process group with bounded output, timeout cleanup and residue checks | Provider additionally proves no residual guest process/resource and destroys the guest |
| Plain-Lua limits | Shared Lua 5.1 runner removes dangerous globals and applies CPU, address-space, file and descriptor limits where supported | Useful defense in depth, not a hostile-code boundary |
| Result integrity | Nonce, framed marker, exact cases, evidence hash, phase identity and cleanup checks | Guest emits a bounded sanitized run-ID/nonce-bound envelope |
| Private-suite secrecy | Submission and private suite execute in the same GMod Lua state | Not guaranteed; disposable host limits host compromise, not same-process inspection |
| Current formal provider | None | Untrusted mode fails closed until an approved provider and immutable image exist |

The Garry's Mod Addons Harbor verifier image runs the unchanged native Linux runner in
a networkless container around an operator-retained pinned installation. It is a Harbor
asset only; the Hub path for that pack is still the native runner in this table, and it
shares the same `DisposableEvaluationHost` policy path at the Hub boundary.
