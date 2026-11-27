# Review revision — 2026-09-21

This revision changes verifier semantics. Historical control, differential,
predicate and contract-hash tables describe the preceding revision and are
retained unchanged; they do not certify this revision.

Build fresh maintenance-only candidates outside the repository:

```sh
python validation/build-review-controls.py nop /absolute/new/nop
python validation/build-review-controls.py gold /absolute/new/gold
python validation/build-review-controls.py empty-timestamp-rewrite /absolute/new/empty-timestamp-rewrite
```

Use the regular managed full evaluator on each candidate. Record source hashes,
runtime identity and complete real-engine outcomes in new revision evidence.
Do not overwrite prior experiment results. Candidate generation itself is not
engine validation, and this generator never invokes the scorer.

Version 1.1.0; still 20 cases. The empty-clip check now compares against the
seeded timestamp, rather than merely accepting a value in the past. The
`empty-timestamp-rewrite` negative differs from gold only by rewriting this value
to five seconds in the past; it must fail
`incap_empty_clip_leaves_reload_unblocked`. Gold must pass all cases; NOP must
retain intended regression failures. Real player commands remain the entry point.
