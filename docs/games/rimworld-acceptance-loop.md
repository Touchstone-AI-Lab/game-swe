# RimWorld compile and game-acceptance loop

This is repository maintenance and benchmark-authoring validation, not an exam
attempt. The original Adaptive Storage compatibility repair and the unregistered
ResearchOrganized reserve remain separate deliverables. Conversation and progress
updates may be Chinese; the authored exam remains English.

## State and evidence

Use `codex/rimworld-compat-reserve` in its attached delivery worktree. Preserve the
original dirty `feat/rimworld` checkout. Read root and nested agent rules before
editing; inspect status and the actual diff before every commit.

Keep generated state under `.rhenium/authoring/rimworld-ci-loop/`, never in a pack.
The local `state.json` records the source commit, current run/attempt/job IDs,
phase, failures, retry counts, and paths to sanitized evidence. Use a fresh output
directory for a new compilation or materialization. Do not store account sessions,
credentials, licensed files, runtime images or model trajectories in this ledger.
A result applies only to its recorded source, adapter, toolchain and artifact.

The phases are `inspect`, `repair`, `local_verify`, `linux_verify`,
`awaiting_game_environment`, `game_verify`, and `accepted`. Only measured evidence
advances a gate; a queued job, missing report, skipped required assertion or an
unprepared runtime cannot count as success.

## Each iteration

1. Resolve the branch head and inspect its latest compile-gate result. Do not reuse
   a green result for an older head as the current verdict. Read the compiler
   reports and failed-check logs before choosing a change.
2. Classify the failure. For archive/network infrastructure failures, retry only the
   affected check, at most twice per check and source commit. Preserve other
   running work. Park and request maintainer intervention after that limit.
3. For code or fixture defects, reproduce the contract failure, make the smallest
   justified fix, and retain before/after evidence. Never change prompts, assertions,
   reference behavior, expected values, scoring, checksums or frozen assets merely
   to make a check pass. A benchmark-semantic change needs its own authoring review
   and complete two-way revalidation.
4. Run affected regressions and repository-required applicable checks. Use the
   existing `check` entry point and authoring compile tools. Disclose failed,
   skipped and unavailable checks. Reuse unchanged build evidence only when its
   complete input identity matches; do not rerun unrelated successful checks
   without a new change, failure or unresolved concern.
5. Review and commit coherent changes with Conventional Commits, then push normally
   to the delivery branch. Do not force-push, merge, publish or modify unrelated
   user work. Return to `linux_verify` for the new head.
6. Record the evidence and next action. Report meaningful changes, new failures,
   gate completion or necessary human input. An unchanged queue or unchanged
   external prerequisite needs no repeated progress message.

A scheduled follow-up in the same chat can run this iteration while a check is pending.
It must use the exact attached worktree and ledger, not the original checkout.
Read existing state first and avoid concurrent mutation. The machine and desktop
app must remain available for local scheduled work. Scheduling does not itself
prove a test or acceptance gate passed.

## Compile gate

Require the repository checks (`devenv shell -- check`) and the applicable
core-only, packaging, shell/PowerShell and plugin checks to pass on the current head.
Retain any platform/engine skips from the unit suites explicitly. The fixed-SDK
compile commands must compile Adaptive Storage base/reference/NOP (six assemblies)
and all eight reserve controls (sixteen assemblies) with SDK 8.0.422 and locked
restore. Verify both reports, their per-control hashes, and all compiler logs.
These are compilation and infrastructure results; `engineValidated` stays false.

On 2026-10-28, commit `c40c44a2` passed the former CI RimWorld job and retained
both reports plus forty-seven logs.

macOS unit tests and reference compilation do not validate Ubuntu package setup,
Linux runtime images, Windows-only behavior or the real game. Existing local LFS,
case-insensitive filesystem and absent-Docker failures must remain visible rather
than being skipped or patched away for this RimWorld change.

## Game gate

After the compile gate passes, use a controlled Linux x86_64 Docker host with a legitimate
RimWorld entitlement. Authentication and licensed runtime preparation remain
explicit operator actions through the Steam provider and `rhenium runtime prepare`.
Do not rent a host, install host software, log in, acquire a game, use another
account's session, or substitute manual game files as an implicit loop action.

If the environment is unavailable, enter `awaiting_game_environment`, retain
`engineValidated=false`, and report the missing prerequisite once. Do not rerun
the compile gate or fabricate runtime evidence while waiting. Continue when the operator
provides an authorized host and preparation context; this state is not acceptance.

Use the commands and control definitions in
[Adaptive Storage revision 5](rimworld-authoring-revision-5.md) and the research-tab task's
[authoring notes](../../benchmarks/rimworld-core/private/harbor/research-organized-tab-state/validation/authoring.md).
Run controls through the normal Hub's `full` evaluator against matching immutable
prepared role images. Record source/adapter/rubric/assembly hashes, runtime and
image identities, anonymous run IDs, complete/passed/score and case outcomes.
Keep licensed content, caches and auth state on the controlled host.

Acceptance requires all of the following for each deliverable:

- Three fresh reference runs complete and pass every required assertion with
  score 100 and identical case outcomes; native setup and restoration gates pass.
- Base and independently materialized NOP complete and fail for the intended
  target defect, rather than a compile, setup, runtime or incomplete-run error.
- Every declared behavioral negative detects its intended defect. Fixture-fault
  controls remain incomplete failures, never passes. Use the original mutation
  plan and the reserve's five negative-control definitions without weakening them.
- No required game assertion is skipped: fifteen for Adaptive Storage, twenty-two
  for the reserve. A reduced profile cannot substitute for this evidence.

Only then record `accepted` and stop the loop. Formal admission, replacement and
registration remain a separate maintainer review decision. Until then the reserve
stays unregistered and neither repaired input set has a new full benchmark pass.

Status on 2026-10-29: the reserve passed this game gate after two verifier-side
fixture repairs and, at the maintainer's request, was registered in catalog 0.4.0
as `research-organized-tab-state`. Its evidence is in
[RimWorld support](rimworld.md#research-tab-task-catalog-040). Adaptive Storage's
game gate has not run, so that deliverable is still open.
