# Terraria task authoring requirements

This document is the quality gate for Terraria and tModLoader benchmark tasks.
It applies before a task is added to the benchmark, calibrated, or submitted in
a pull request.

The central rule is simple: design and finish one independently authored task
before starting the next one. A batch of renamed or mechanically cloned tasks
does not count as multiple tasks.

## Non-negotiable requirements

### Exercise real repository code

- The repair must change existing upstream mod source files that participate in
  the mod's normal build or runtime behavior.
- The evaluator must exercise that behavior through the real code path, or
  through a faithful abstraction that already exists in the upstream project.
- Do not add a standalone substitute implementation, synthetic contract, or
  verifier-only seam that allows a solver to ignore the upstream source tree.
- Retain only the source and metadata needed to understand and evaluate the
  repair. Do not commit Git metadata, build output, package caches, binaries, or
  unrelated assets.

### Author every task independently

- Each task needs its own defect analysis, prompt, broken snapshot, oracle
  patch, and tests.
- Shared harness infrastructure is acceptable; shared task semantics with only
  names, labels, or repositories changed are not.
- Identical starter, oracle, or test hashes across supposedly different tasks
  are a blocking audit finding unless the identical file is documented shared
  infrastructure outside the task payload.
- A fixed case count repeated across tasks is a warning that must be explained,
  not a target. The number of checks follows from the behavior being tested.

### Make the difficulty genuine

- Prefer coherent defects that require understanding multiple interacting
  files, state transitions, save/load behavior, client/server authority,
  networking, content registration, hooks, or the tModLoader lifecycle.
- Difficulty should come from repository reasoning and a realistic repair, not
  from placing many unrelated algorithms in one file.
- Do not make a task hard through undocumented requirements, arbitrary hidden
  edge cases, misleading wording, excessive mechanical work, or all-or-nothing
  scoring alone.
- A small cluster of related defects is preferable to a long checklist of
  unrelated faults.
- The target is comparable to or harder than accepted hard tasks, while still
  resembling a change a maintainer could reasonably review.

### Keep the task fair and solvable

- Every scored behavior must be derivable from the English prompt, the visible
  repository, and documented platform semantics.
- Public APIs, signatures, ownership rules, and boundary behavior needed for
  the solution must not be invented only inside hidden tests.
- The broken snapshot must fail because of the described defects. The oracle
  must repair those defects with a minimal, maintainable change that preserves
  upstream style and compatibility.
- Rejection cases and edge conditions must reflect real C#, .NET, Terraria, or
  tModLoader behavior rather than traps created only for the benchmark.
- A capable solver must have a plausible path from repository inspection to the
  intended fix without access to the oracle or private assertions.

### Preserve repository authenticity

- Prefer a mature, well-known, actively used mod when its code offers a suitable
  repair. Popularity is useful context, but it is not a substitute for a sound
  task design.
- Pin the upstream repository, commit, license, Terraria version, tModLoader
  version, and relevant toolchain versions.
- Record why the selected code path is representative and list the source files
  a maintainer should inspect.
- Verify that the affected files are included in the real project/build path.
- The prompt should require meaningful inspection of the existing repository;
  the surrounding snapshot must not be decorative.

### Follow benchmark format

- Prompts, task instructions, and maintainer-facing task documentation must be
  in English.
- Match the structure, schema, packaging rules, and metadata conventions of
  already accepted tasks.
- Keep task metadata accurate; do not claim runtime or server coverage that the
  evaluator does not provide.
- Generate validation receipts and content hashes only after the task design is
  final. A hash proves which bytes were validated; it does not prove that the
  task is good, unique, fair, or difficult.

### Use layered engine evidence honestly

- The exhaustive source projection remains the deterministic contract layer.
  A `full` task must also compile submitted production files into a real `.tmod`
  and run task-specific assertions in the pinned tModLoader runtime whenever
  the behavior can be exercised reliably by a dedicated server.
- Engine assertions must touch the production files under repair and meaningful
  Terraria/tModLoader state; a boot-only sentinel or a verifier-only duplicate
  implementation is insufficient.
- Record a broken/oracle control for every engine assertion on the exact pinned
  runtime. The broken snapshot must fail for the intended defect, and the oracle
  must pass.
- Full evaluation must fail closed on a missing, partial, malformed,
  wrong-version, wrong-mode, or inconsistent engine report. Core diagnostics
  may omit the engine layer but are never complete benchmark results.
- Client-only drawing, input, map, or IL behavior should use a real client/Xvfb
  path only when it is deterministic and maintainable. Otherwise keep the
  behavior in the source projection, list it explicitly in `engine-rubric.json`,
  and do not claim that the dedicated server covered it.

## One-task workflow

Complete this entire sequence for one task before authoring another:

1. **Select a candidate.** Identify a real code path and a coherent repair
   opportunity in a pinned, license-compatible upstream snapshot.
2. **Write a design brief.** Name the affected files, current behavior, desired
   behavior, expected patch shape, why repository exploration is required, why
   the task is hard, and why it is fair.
3. **Review the design first.** Audit the proposed task against accepted hard
   tasks, including accepted L4D2 hard tasks. Do not spend a model run or heavy
   test cycle on a design that has not passed this review.
4. **Map the contract.** For every defect, map the upstream files to an explicit
   prompt clause, evaluator checks, and the oracle change.
5. **Implement the task.** Prepare the broken snapshot, oracle, evaluator, and
   metadata without starting a second task.
6. **Audit structure.** Check packaging, English text, source provenance,
   licenses, ignored artifacts, and consistency with accepted tasks.
7. **Audit reasonableness.** Review every assertion against the prompt and
   visible code. Remove tests that depend on hidden or artificial assumptions.
8. **Run controls.** Confirm the oracle passes, the broken snapshot fails for
   the intended reasons, and unrelated or empty submissions cannot pass.
9. **Check uniqueness.** Compare prompts, starter patches, oracle patches, and
   tests with existing tasks. Explain any legitimate shared infrastructure.
10. **Calibrate once.** Run one strict, one-shot high-reasoning model attempt
   for this unique task and retain its result as that task's evidence.
11. **Review the outcome.** The desired aggregate full-pass rate is below 50%,
    but difficulty must never be increased with hidden or unreasonable
    requirements merely to force a failure. If a passing task needs to become
    harder, add only coherent behavior grounded in the real repository and
    repeat the full design audit before a new strict calibration.

## Required review evidence

Each task must carry or link to enough maintainer evidence to answer these
questions:

| Evidence | Required answer |
| --- | --- |
| Upstream provenance | Which repository, commit, license, and platform versions are frozen? |
| Real execution path | How do the affected upstream files participate in the build/runtime and evaluator? |
| Defect map | Which prompt clause and evaluator checks correspond to each intended repair? |
| Expected repair | What files and interactions should a correct patch need to understand? |
| Fairness | Why can the required behavior be inferred without private-test knowledge? |
| Difficulty | Which real cross-file or lifecycle interactions make a one-shot solution challenging? |
| Controls | Do the oracle, broken snapshot, empty submission, and unrelated-change controls behave correctly? |
| Uniqueness | How does this task differ substantively from every existing task? |
| Calibration | What happened in the single strict calibration attempt for this exact task revision? |

## Blocking rejection conditions

Do not submit a task when any of these conditions is true:

- its starter, oracle, and tests are copies of another task with renamed nouns;
- its prompt differs from another prompt mainly by repository or feature names;
- the evaluator can pass while the solver ignores the retained upstream source;
- it was batch-generated without an individual design and assertion audit;
- most of its difficulty comes from the number of unrelated requirements;
- a calibration result from another task or another revision is reused;
- scored behavior depends on requirements unavailable in the prompt or visible
  repository; or
- build output, package caches, binaries, or unrelated bulk are committed.

## Recorded rejected approach

In September 2026, a proposed ten-task Terraria batch was reverted. All ten
entries reused the same synthetic `ReleaseContract` starter, oracle, and test
suite, while the retained mod repositories were not part of the evaluated
implementation. The repeated 138 cases were 23 common groups with six variants
each; they were not evidence of ten independently designed tasks, and a shared
contract cannot establish per-task difficulty.

That approach violates the real-code, independent-authoring, fairness, and
calibration requirements above and must not be repeated.
