# Minecraft task authoring requirements

This document is the quality gate for Minecraft (Paper plugin) benchmark tasks.
It applies before a task is added to `benchmarks/minecraft-core/catalog.json`,
calibrated, or submitted in a pull request.

The central rule: design, verify and accept one independently authored task
before starting the next one. Renamed or mechanically cloned tasks do not count
as multiple tasks.

## Non-negotiable requirements

### Source every task from a real, permissively licensed repository

- The starter is the upstream plugin tree at the parent commit of a merged
  bug-fix pull request or commit (`upstream.base_commit`); the reference fix is
  the upstream change (`upstream.fix_commit`), trimmed to the changed files
  under `solution/after/`.
- A task may cover related defects that the same repository fixed together or
  in adjacent commits. The starter is then the parent of the earliest fix, the
  reference is the combined change up to the last fix (`upstream.fix_commit`),
  trimmed to the changed files, and the task's `NOTES.md` lists every merged
  commit. Every merged defect must meet the requirements below on its own.
- Only MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause and ISC repositories are
  admissible. Confirm the licence through the GitHub licence API **and** the
  `LICENSE` file at the base commit, and keep that file in the starter.
- Exclude repositories that depend on NMS/`paperweight-userdev`, that are mostly
  Kotlin, or whose defect needs a real connected player to reproduce.
- Retain only the source and metadata needed to understand and evaluate the
  repair. Do not commit `.git`, build output, package caches or binaries.

### Keep the build and the upstream tests frozen

- The verifier restores every path in `build.frozen_paths` (build scripts,
  wrapper, `gradle.properties`, `pom.xml`, `.mvn`, `src/test`) from
  `tests/starter` before building. A task must be solvable without touching them.
- The repository must build offline after one warm-up (`./gradlew --offline` or
  `mvn -o`); prove it in Docker with `eclipse-temurin:21-jdk` before vendoring.
- When the repository has JUnit tests, every test that passes at the base commit
  is a frozen `unit_cases` entry and an existing-contract candidate; a repair
  that breaks one fails the task.

### Author every task independently

- Each task needs its own defect analysis (`NOTES.md`), prompt, starter,
  reference fix, grader suite and case-contract mapping.
- Identical `solution/after` or `tests/suite` digests across tasks are a
  blocking audit finding.
- Case counts follow from the behaviour, not from a target number.

### Make the difficulty genuine and fair

- The symptom must be reproducible on a headless dedicated server without a
  player: commands from a recording console sender, configuration, scheduler
  behaviour, world/entity/block/inventory events, persistence, timing.
- Every scored behaviour must be derivable from the English exam, the visible
  repository and the documented Paper API. Hidden suites must not invent
  public API, signatures or boundary behaviour.
- The starter must fail exactly the mapped target cases; the reference must
  pass every case; an independently written alternative fix must also pass.
- Difficulty comes from repository reasoning (multiple interacting files,
  lifecycle, event ordering, persistence), not from hidden traps.

### Acceptance gates (all on the real Paper 1.21.11 build 132 server)

| Gate | Requirement |
| --- | --- |
| starter | complete, not passed, only mapped target cases fail |
| reference | complete, passed, 100, three consecutive runs |
| alternative | an independent fix scores 100 |
| target-negative | a plausible wrong fix fails only its mapped target case(s) |
| compat-negative | a fix that breaks a preserved behaviour fails exactly that contract case |
| tamper | editing a frozen build file or upstream test does not change the verdict |

Record the gates in `validation/controls.md` and the case → clause mapping in
`validation/case-contracts.tsv` (`case`, `layer` unit|server, `role`
target|preserved|sentinel, `public_report`).

### Follow benchmark format

- Task ids are `<repo-slug>-<short-symptom>`; all text is English.
- `exams/<id>.md` equals the Harbor `instruction.md` body; run
  `private/harbor/scripts/materialize.py` after every catalog edit and commit a
  zero-diff regeneration.
- The exam states the observable symptom and the expected behaviour; it does
  not name the fixing commit, the upstream issue number or the patch shape.
- Suites use only the GcbHarness API (`@GcbCase`, `GcbAssert`, `GcbSenders`,
  `GcbCommands`, `GcbEvents`, `GcbWorlds`, `GcbEntities`, `GcbInventories`).
  `GcbProxies.player` is a best-effort event-construction aid, never a real
  player; target cases must not depend on it.
