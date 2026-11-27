# Balatro plugin branch readiness v2

Scope: the user's 2026-09-21 request to complete the plugin implementation using
other game branches as references. No commit, push, PR, rule edits, host changes,
dependency upgrades, model trials or frozen task changes are included.

Reference revisions: local `origin/feat/palworld` at `9f7edfc` (already included
in main `a518348`), its plugin/runtime/evaluator and `docs/games/palworld.md`;
Garry's Mod's plugin hooks; `docs/adding-a-game.md`, `docs/plugin-contract.md`,
`docs/disposable-evaluation-hosts.md`, and `CONTRIBUTING.md` at `a518348`.

The target is an Experimental local honest plugin with an explicit reviewed
runtime and source-reviewed submissions. Formal untrusted hosts are core/provider
responsibility; no VM or false sandbox claim is necessary to contribute a plugin.
The licensed desktop exception remains limited to the operator-prepared controlled
host. No new arbitrary code is executed merely because a submission is well formed.

| Gap in native v1 | Implementation and acceptance |
| --- | --- |
| Only packaged control hashes accepted | Add explicit operator source-review records bound to task, candidate, adapter, environment and assets. Candidate fingerprints are computed from submitted bytes; grading remains semantic. Unreviewed submissions stay incomplete. |
| Runtime health always reports unavailable | Add a bounded, read-only probe checking fixed controller/dependency bytes, protected baseline, matching smoke and halt state; no game launch or state writes. |
| Native validation used CLI directly | Exercise the actual existing PowerShell scoring wrapper on fresh anonymous strict attempts; never alter the shared wrapper or repeat an attempt. |
| Incomplete plugin/support documentation | Document installation, preparation, review, probe, scoring, state layout, failure categories and actual platform limits; add ownership/status navigation using the same structure as other games. |
| Missing branch-level integration evidence | Test CLI/API profiles, redaction and untrusted no-fallback behavior, package contents and core/plugin boundaries; rerun all ten gold/base controls on the final adapter and targeted review-path controls. |

Native-v1 source and reports were preserved before changes as 471 authored files
in `.test-state/branch-ready-v2/native-v1-authored-baseline.zip`, SHA-256
`289925bdbe9ffc6b246cd491441fa0977eb5ec705a2dd9ccaf98a546dcadb7ad`.
This contains no game, fixed dependencies, save data or runtime state. Original
v1 evidence and its fingerprints remain unchanged. V2 gets fresh binding, smoke,
source freeze and result paths. All 501 original PoC sources and the 76 prior
staged assets remain unchanged; support documentation uses the integration
supplement rather than rewriting the historical asset-import record.

Validation scope: targeted development tests, installed wheel checks, read-only
probe before/after smoke and drift tests, ten gold/base pairs three times through
the actual scoring wrapper, plus the existing ten targeted full mutations and
four alternatives through explicit review records. Existing reviewed controls
may use the original reviewed allowlist; review-path controls must be authorized
independently and graded without candidate role lookup. Final counts are generated
from actual records, not this plan. Report existing Windows full-repository test
failures and unavailable tools separately; do not weaken or silently skip them.

Admission-specific supplement, declared before final validation: two extra growth
copies (gold/base) receive a comment-only byte change so their seals are not in the
old control set. They require explicit source review and one strict wrapper score
each. This is not new task coverage, a new correct implementation or an added
mutation. It tests the new operator-review route without altering frozen candidates.

Development finding: the first wrapper pilot failed before any native operation
because the constructed scorer environment omitted PATHEXT. A bounded read-only
PowerShell lookup failed without PATHEXT and resolved the installed rhenium.exe
with explicitly constructed `.EXE`. Only the operator wrapper environment changed;
the shared wrapper, game environment and runtime/RPC were left unchanged. The
failed pilot is preserved and a new anonymous pilot uses a new evidence directory.
