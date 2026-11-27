# Review revision — 2026-09-21

This revision changes verifier semantics. Historical control, differential,
predicate and contract-hash tables describe the preceding revision and are
retained unchanged; they do not certify this revision.

Build fresh maintenance-only candidates outside the repository:

```sh
python validation/build-review-controls.py nop /absolute/new/nop
python validation/build-review-controls.py gold /absolute/new/gold
python validation/build-review-controls.py equivalent-long-docs /absolute/new/equivalent-long-docs
```

Use the regular managed full evaluator on each candidate. Record source hashes,
runtime identity and complete real-engine outcomes in new revision evidence.
Do not overwrite prior experiment results. Candidate generation itself is not
engine validation, and this generator never invokes the scorer.

Version 1.10.0; 71 automatically scored cases (one public float ABI check and
70 real-server cases). The old documentation keyword case is removed rather than
replaced by another prose heuristic. Correctness of documentation is explicitly a
manual review requirement, outside the automatic score. Absolute engine time and
invalid-index behavior remain tested on the engine. `equivalent-long-docs` uses
accurate wording without “absolute” and places it outside the old 900-character
window; it must pass exactly like gold. NOP must still fail behavioral/ABI cases.

`build-review-controls.py` reproduces all of `solution/solve.sh`, including the
three ordered patches in addition to the `after` overlay. GNU patch is required.
`python validation/check-include-fairness.py` checks five host-side verifier
policy cases, with compilation explicitly mocked: accurate long alternative
prose and ABI-only text are accepted; an integer signature, a comment-only
signature and compiler failure are rejected. This is not compile/engine evidence.
