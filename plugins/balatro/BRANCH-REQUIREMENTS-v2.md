# Branch implementation requirements and references

This is repository maintenance, not an exam attempt. References are the actual
local `origin/feat/palworld` revision `9f7edfc` and current main `a518348`, not an
assumption about a remote branch's present state. Palworld's branch is already an
ancestor of main; no merge, rebase, checkout or remote mutation was needed.

| Requirement | Reference | Balatro implementation / evidence |
| --- | --- | --- |
| Independent distribution and entry point | Palworld `plugin.py`, `pyproject.toml`; plugin contract | `plugins/balatro`, one entry point, Python 3.12, no game import or default in core |
| Game/pack/task ownership and identity | Adding-a-game sections 1–4; GMod plugin | Maintainer Sangyu Pan, `balatro/core/<task>`; two-plugin same-local-ID isolation tests |
| Anonymous public repair starter | GMod materialization; core attempt contract | Frozen starter bytes, API/EXAM identity-only rendering, immutable-file checks; no private tests, gold or prior results in attempts |
| Usable submission evaluator | Palworld evaluator and native runtime config | Full semantic suite; task and submitted-byte fingerprints; explicit operator trust records for previously unlisted code; no role-based pass decision |
| Real scoring entry | Palworld Windows Hub controls | V2 invokes the unmodified `score-exam.ps1` on new strict anonymous attempts, once each |
| Read-only readiness and no implicit preparation | Managed runtime rules, existing native plugin pattern | Fixed external controller; explicit prepare/smoke; bounded read-only doctor; byte drift, missing smoke and halt state refuse readiness |
| Generated state stays outside pack | Plugin contract | All run/review/seal/cache data below state; explicit rejection of state inside pack |
| Full versus reduced results | Plugin contract; API profile tests | Missing engine/cases/cleanup stays incomplete; no core-profile pass; API rejects unknown profiles |
| Untrusted policy stays in core/provider | Disposable evaluation-host contract | No local fallback; no VM/container security claim; real Balatro API integration test proves missing provider never calls the local evaluator |
| Failure/secret isolation | Plugin contract; two-plugin tests | Allowlisted result projection; private protocol/log data not forwarded; minimal constructed game/helper environment |
| Controlled native implementation proof | Root AGENTS section 9 | Fresh installed-wheel smoke and wrapper gold/base/targeted/admission matrices required; v1 evidence is preserved, not re-labelled |
| Complete engine failure reporting | Root AGENTS; Palworld support record | Business rejection separated from incomplete environment/protocol/cleanup results; failed developer pilot retained |
| Repository checks and packaging | CONTRIBUTING and root AGENTS | Plugin tests/Ruff/Mypy, wheel contents, Web checks, Bash syntax, final diff checks; full-repo Windows failures and absent ShellCheck must be reported explicitly |

The plugin does not need to implement a hypervisor or a new provider to contribute
its local evaluator. It also must not claim formal untrusted support merely because
the native tests pass. The licensed desktop execution permission is the already
approved scoped controlled-host exception, not a rewritten global project rule.

The external Python 3.13 controller and licensed installation remain prerequisites,
not bundled runtime artifacts. Arbitrary-host setup, managed acquisition, Harbor
export, model calibration and Stable promotion are outside the implemented scope.
An implementation ready for branch review is not an assertion that every global
release gate or maintainer merge decision has passed. Final statuses must be read
from the new branch validation and report, not from this requirements mapping.
