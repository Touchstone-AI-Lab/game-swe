# Review revision — 2026-09-21

This revision changes verifier semantics. Historical control, differential,
predicate and contract-hash tables describe the preceding revision and are
retained unchanged; they do not certify this revision.

Build fresh maintenance-only candidates outside the repository:

```sh
python validation/build-review-controls.py nop /absolute/new/nop
python validation/build-review-controls.py gold /absolute/new/gold
python validation/build-review-controls.py four-second-replacement /absolute/new/four-second-replacement
```

Use the regular managed full evaluator on each candidate. Record source hashes,
runtime identity and complete real-engine outcomes in new revision evidence.
Do not overwrite prior experiment results. Candidate generation itself is not
engine validation, and this generator never invokes the scorer.

Version 1.1.0; still 18 cases. The initial-delay check observes player_spawn and
every game frame, retaining the first living replacement timestamp even if it
later dies. The public round_start timestamp is a conservative lower bound for
the initial-wave scheduling request. First replacement must not precede it plus
eight seconds (two engine ticks of tolerance). The safe-zone startup poll can
arm the wave approximately one second later; this does not prove the exact
private timer deadline. It does reject both the original normal-delay regression
and a competing four-second death timer that the old 2.2/9.2-second samples missed.

A pending initial wave is reused without restarting its countdown at death.
The first prototype incorrectly measured from death and rejected unchanged gold
at approximately six seconds: the initial wave was queued earlier. A subsequent
public queue-message/allow-toggle fixture also failed setup and was abandoned;
the original proven public round setup is retained, without a new debug-command
contract. These failures remain evidence, not gold bugs or passing controls.

The earlier negative that only assigned SpawnTime = 4.0 had no effect because
the initial branch reuses its existing wave. The corrected
`four-second-replacement` explicitly adds a competing four-second death timer
and must fail `initial_timer_not_overwritten_by_normal_delay`. Gold must pass all
cases and NOP must retain intended regression failures. Historical tables do
not certify this revised suite; retain all failed fixture evidence.
