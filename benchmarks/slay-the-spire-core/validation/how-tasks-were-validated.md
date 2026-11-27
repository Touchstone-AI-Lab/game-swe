# How each task in this pack was validated

Every task in this pack went through the same four gates. Three of the six tasks built for
this pack were changed or thrown away because a gate caught something; the notes below
record what each gate is for and what it actually caught, because the failures are more
instructive than the passes.

## Gate 1 — the per-defect matrix

Build one tree per defect group, each carrying exactly that group and nothing else. Every
single-defect tree must fail exactly its own group's assertions and pass everything else,
including all positive controls.

This is the gate that catches masking, and it earns its keep. Two examples from this pack:

- A defect that widened a bounds check in `ParamInfo` was meant to reject the last
  argument of the *patched* routine. The same class also describes the parameters of the
  *patch* method, so it rejected the last parameter of every patch — breaking the entire
  prefix mechanism, hiding four other defect groups and turning all five positive controls
  red. Replaced with a defect that leaves prefixes on static methods working, which is
  what the controls then test.
- In the enum-injection task, an early version of the removal defect truncated the array
  to the wrong length. Combined with the restore defect the two errors cancelled, and the
  restore group's symptom disappeared. Choosing a renumbering-loop variant instead leaves
  every group observable in every combination.

A masking defect shows up as *the controls going red on the all-defects tree*, not as a
missing flip. That is the signature to look for.

## Gate 2 — positive controls that hold on both trees

Every test class carries at least one assertion that passes on the broken tree as well as
the reference. Without them a submission that deletes the offending check, or rewrites the
subsystem into something that merely satisfies the reports, scores full marks.

## Gate 3 — `nop` scores 0 and `oracle` scores 1

Run the task through Harbor with the empty agent and with the reference patch. Read
`entrypoint_exit` **before** `reward`: `passed=0 failed=0` means the harness died and the
run must be discarded rather than counted as a failure.

## Gate 4 — independently satisfiable

Write a second fix, deliberately in a different style from the reference, and confirm the
suite still passes. This is the only gate that distinguishes "the assertions test
behaviour" from "the assertions test the reference implementation" — and it is the gate
that decides whether a model's correct-but-different fix scores 0 unfairly.

All four tasks in this pack pass it. The alternative fixes derive the same behaviour by
different routes: an ordinal taken from where the entry actually landed rather than from
an array length; a stored version read by trying the strict parser first and falling back
to the lenient one; a mod list whose selection is reset only when the deleted list was the
selected one.

## Two things that are not gates, but cost a round each

**Reachability.** A defect must sit on the code path the *test* executes, not merely on a
path a production caller executes. Defects planted in `ParamInfo2` were dead code for a
patch object a test constructs directly, because `isSpirePatch2()` returns false when no
annotation is attached and the legacy `ParamInfo` path runs instead. Base and reference
produced byte-identical results. The cheapest proof is to break the function outright and
watch your own test fail.

**Concurrent gate jobs need per-task job names.** A gate script naming its Harbor job
`qc_${action}_$(date +%s)` collides when two gates start in the same second on different
tasks, and the second reads the first one's `reward.txt`.

## The image is pinned by digest, and the pin was re-gated rather than assumed

Every task's `environment/Dockerfile` pins the base image by digest:

```
FROM maven:3.9-eclipse-temurin-8@sha256:d8b1b22e93012cd0257d37b3fd6d7bec3d0f7ae611730fc3ba0657b9ebe4e7ca
```

This started as a documentation defect worth recording: the comment above that line
already claimed the image was pinned by digest while the `FROM` used a mutable tag, so the
file asserted something that was not true of itself. Tags move; a pack whose results
cannot be reproduced next month is not a benchmark.

After pinning, every task was put through `nop`/`oracle` again on the pinned image rather
than assumed equivalent. All pass: `nop` scores 0 and `oracle` scores 1, with the same
assertion counts as before (9, 7, 16 and 6 respectively).

## Per-defect matrices were run for the earliest tasks too

The two earliest tasks had only been validated in both directions (broken tree fails,
reference passes). That is weaker than what the rest of the pack claims, so the matrices
were built and run afterwards rather than left implicit.

Decomposing a shipped task back into single-defect trees needs its own check, because a
mis-decomposition would produce a matrix that describes a task nobody ships. The
generator's all-defects output was therefore diffed byte-for-byte against the tree that
actually ships, for every file, before any matrix was believed.

That decomposition also settled what one of the tasks really contains: six edits, of which
five are graded. The sixth — a narrowed type check in the accessor generator — has neither
an assertion nor a report. It is a distractor, which is where a distractor belongs: in the
code and out of the prompt.

## Stray build output, and why "it happens to be safe" is not safe

Two of the shipped task trees carried a leftover `target/` directory — 337 files of Maven
build output, including `target/test-classes/gcb/LoadOrderTest.class` and
`target/surefire-reports/gcb.LoadOrderTest.txt`. The surefire report lists the private
suite's method names and its assertion messages verbatim, down to
`the dependency must load first, got [dependent, base]`. Shipped into the agent's tree,
that turns a symptom-only task into a specification.

It never reached an agent. Every task's Dockerfile ends its warm-up with
`rm -rf src/test/java/warm target`, so the directory is deleted while the image is built.
The compiled main classes were also from a *base*-tree build, not the reference — the
surefire report shows `Tests run: 8, Failures: 3` — so they were the defective code, not
the answer.

But that safety was incidental. The `rm -rf target` exists to clean up after the
dependency warm-up, not to protect the suite; anyone tidying that line would have silently
started shipping the private tests into the image, and nothing would have failed to warn
them. The directories are now removed from the trees themselves, and every affected task
was re-gated afterwards rather than assumed unaffected.

Worth stating plainly: earlier runs of those two tasks used trees that still contained this
directory. Since the image build deleted it, the agent saw the same tree either way.
