# Per-defect matrices

For each task: what the reference tree scores, what the broken tree scores, and — where
the defect groups were built as separate trees — which assertions each individual group
flips. Every number below came from a real headless Maven run, not from reading the code.

The rule these tables exist to enforce: **a single-defect tree must fail exactly its own
group's assertions and pass everything else, including every positive control.** A defect
that fails somebody else's assertions is masking, and masking makes a task both unfair and
unmeasurable.

## mts-load-order-regressions

Six edits, of which **five are graded and four are independent enough to name**. The
matrix was run after the fact, on six trees, and it is reported here as measured rather
than as intended — the defects in this task interact, and saying otherwise would be a
claim the run does not support.

| tree | failures | which |
|---|---|---|
| reference | 0/9 | — |
| all six edits | 4 | chain, dependency-before-dependent, edge-into-newest, by-reference |
| flipped circular test only | 2 | dependency-before-dependent, edge-into-newest |
| transposed relation index only | 5 | the four ordering ones **plus** a 5s timeout on the circular case and the asymmetry case |
| removed cycle guard only | **0** | nothing — unobservable on its own |
| wrong node looked up only | 3 | chain, dependency-before-dependent, edge-into-newest |
| narrowed accessor type check only | **0** | nothing — a distractor, confirmed inert |
| by-reference boxing only | 1 | by-reference |

Three things this run establishes that the earlier base/reference check could not:

1. **The defects are not independent.** The transposed-index edit alone fails five
   assertions; all six edits together fail only four. Removing the cycle guard, which does
   nothing by itself, *suppresses* the runaway recursion that the transposed index causes.
   That is masking, in the shipped task.
2. **Two of the six edits are distractors.** The removed cycle guard and the narrowed
   accessor type check are both invisible to the suite. Distractors are legitimate and
   both are correctly absent from the prompt, but only four graded symptoms remain.
3. **One report is not enforced.** The report describing two mods that name each other and
   freeze the loading screen has no failing assertion on the shipped base — both circular
   cases pass there. A submission can ignore that report and still score 1.

Point 3 is a real defect in the task and the top follow-up: it needs an assertion that
reproduces the freeze on the shipped base, after which the task must be **revalidated**,
because that changes the graded suite. It is recorded rather than quietly patched for
exactly that reason.

None of this invalidates the task as an evaluation artifact — the base fails and the
reference passes. It does mean this task's matrix should be read as overlap, not as the
clean one-group-per-tree separation the newer tasks show.

## mts-mod-identity-regressions

Four defect groups across two files — what identifies a mod, what makes two records the
same mod, how a stored version is read back, and which mod a requirement resolves to. The
matrix is the clean case: each single-defect tree fails exactly one assertion and nothing
else, and the three controls hold everywhere.

| tree | failures | which assertion |
|---|---|---|
| reference | 0/7 | — |
| all four defects | 4 | one per group |
| blank identifier only | 1 | a blank identifier falls back to the name |
| equality test only | 1 | an identified mod is not the same as an unidentified one |
| version parser only | 1 | an ordinary two-part version is accepted |
| requirement lookup only | 1 | a requirement resolves to the first match |

This is what the other matrices are compared against. Note the contrast with the
load-order task above, whose defects interact: same codebase, same author, same intent —
independence is a property you measure, not one you design in.

## mts-loader-internals-regressions

7 defect groups across 4 files and 3 subsystems — mod-descriptor persistence and identity,
early-return semantics, postfix result forwarding, by-reference parameter marshalling.

| tree | result |
|---|---|
| reference | `Tests run: 16, Failures: 0, Errors: 0` — BUILD SUCCESS |
| all defects | `Tests run: 16, Failures: 4, Errors: 1` — BUILD FAILURE |
| independent fix (different style from the reference) | 16/16 — BUILD SUCCESS |

## mts-patch-placement-regressions

6 defect groups across 5 files and 4 subsystems.

| tree | result |
|---|---|
| reference | `Tests run: 14, Failures: 0, Errors: 0` — BUILD SUCCESS |
| all defects | `Tests run: 14, Failures: 5, Errors: 3` — BUILD FAILURE |
| independent fix | 14/14 — BUILD SUCCESS |

## mts-attachment-and-binding-regressions

5 defect groups across 5 files and 4 subsystems.

| tree | result |
|---|---|
| reference | `Tests run: 11, Failures: 0, Errors: 0` — BUILD SUCCESS |
| all defects | `Tests run: 11, Failures: 3, Errors: 3` — BUILD FAILURE |
| independent fix | 11/11 — BUILD SUCCESS |

A sixth group was built and removed. Widening `ParamInfo`'s position bound from `>` to
`>=` was meant to reject the last argument of the patched routine; because the same class
also describes the parameters of the patch method, it rejected the last parameter of every
patch, broke the whole prefix mechanism, hid the other four groups and turned all five
positive controls red.

## mts-enum-injection-regressions

4 defect groups in one file — the reflection machinery behind `@SpireEnum`.

| tree | result | which assertions |
|---|---|---|
| reference | 9/9 pass | — |
| all four defects | 4 failures | one per group; all five controls still pass |
| d1 only | 1 failure | the added-entry group only |
| d2 only | 1 failure | the substitute group only |
| d3 only | 1 failure | the removal group only |
| d4 only | 1 failure | the restore group only |
| independent fix | 9/9 pass | — |

The matrix shaped this task's defect set. An earlier version of the removal defect
truncated the array to the wrong length instead of misnumbering it; combined with the
restore defect the two errors cancelled and the restore group's symptom disappeared.
Choosing the renumbering-loop variant instead leaves every group observable in every
combination.

## mts-mod-discovery-regressions

Two defect groups in the routine that reconciles a hand-installed copy of a mod with a
subscribed one. Clean separation.

| tree | failures | which |
|---|---|---|
| reference | 0/6 | — |
| both defects | 2 | the same-release case and the no-release-stated case |
| widened precedence test only | 1 | the same-release case |
| unversioned handling only | 1 | the no-release-stated case |
| independent fix | 0/6 | — |

Four of the six assertions are positive controls that hold on both trees: a strictly newer
subscribed copy does take over, a strictly older one does not, a mod present only one way
is used and marked accordingly, and an empty setup yields nothing.

This task was built to apply what the earlier discarded candidates taught. It is not in
the pack. It is recorded here because the reason is instructive.

The premise was sound — nothing in the loader, in the descriptor class, or in any comment
states which copy is supposed to win, so reaching the right lines should have left the
reader still having to decide what correct means. Then the reports gave it away:

> *"The launcher used to leave the copy in their folder alone and run that one; since this
> build it runs the subscribed one instead."*

That sentence is the policy. The whole point was that correctness could not be derived from
the code, and it was then supplied in the one document the model is guaranteed to read. The
second report repeated the mistake — *"putting a release number in the descriptor makes it
behave"* names the exact branch.

Two rules came out of it, both now in the task-authoring notes:

- **Never write "it used to …", "it should …", or "X makes it work again".** Each hands
  over the specification. Describe the damage the user suffered, not the behaviour that was
  lost and not the workaround that restores it. Self-check: delete every clause describing
  correct behaviour; if nothing is left, the defect was never suitable.
- **There is a size floor.** Even with faultless prose, this fix was two lines inside a
  thirty-line method that a single grep reaches. Once the model is looking at the method, a
  two-line policy choice is small enough to brute-force. That is a property of the fix, not
  of the report.

## A task that was built and thrown away

A fifth candidate planted three defects in the bytecode transformer that rewrites
`INVOKESPECIAL` into `INVOKEVIRTUAL`. The matrix rejected it outright:

- two of the three were **unobservable**. The subtype test they targeted is unreachable
  for a `super.x()` call, because the constant-pool entry already names the declaring
  class and an earlier equality check returns first. The cached-index one has no effect
  when a single class is converted.
- the third — a one-byte offset in where the rewritten constant-pool reference is written —
  was **too destructive**: the class no longer loads at all, so three of the four
  assertions error, including two positive controls.

One usable defect, and a catastrophic one. Not a task. It cost a five-minute job to find
that out, which is the argument for running the matrix before writing any prose.
