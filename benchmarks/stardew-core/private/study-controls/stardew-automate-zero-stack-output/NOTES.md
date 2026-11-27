# E0 notes: stardew-valley/core/stardew-automate-zero-stack-output

Private study material. It names the defect and the reference; never copy it into an attempt workspace.

## Sets

- Target (2 cases): `a zero-size output is discarded and the machine empties`,
  `the machine resumes processing input after the discard`. The second uses the first one's fixture.
- Preserved (1 case): `sentinel: a normal furnace cycle lands its bar in the chest`. It passes in the unchanged starter.
  Publicly stated in the exam (Task: "Machines with normal output must keep behaving exactly as before") and
  discoverable in the supplied source (`Automate/docs/README.md:34`, `Framework/MachineGroup.cs:154-218`).
- Static: `check:submission-shape`.

## Controls (all patches apply with `patch -p1` in `/app/StardewMods`)

| control | kind | base | change | expected | observed |
| --- | --- | --- | --- | --- | --- |
| `target-negative-warns-without-discard` | target-negative | reference | Partial revert: `TryPushOutput` still detects the zero-size stack, logs the warning and returns true, but the `output.Take(1)` that fires the machine's on-empty reset is removed. The machine stays ready forever (now with a warning every cycle). | both target F, sentinel P | static P, sentinel P, target F F. Admissible. |
| `compat-negative-discards-single-item-output` | compat-negative | reference | The broken-stack branch is moved ahead of the push and widened to `stackSize <= 1`. Zero-size output is still discarded and the machine resumes; every normal single-item output (one copper bar) is discarded instead of stored. | sentinel F, both target P | static P, sentinel F, target P P. Admissible. |
| `alternative-machine-layer-discard` | alternative | starter | `MachineGroup` is untouched. `BaseMachine.GetTracked` (used by the object machines' `GetOutput`) treats a held item with `Stack < 1` as broken: it invokes the machine's own on-empty callback (the same reset the reference reaches through `Take(1)`) and reports no output, after which the existing `output is null` branch of `MachineGroup.Automate` re-queues the now-empty machine for input. Different layer and strategy; no warning is logged, which the exam marks as optional ("a warning log is fine"). | all P | all P. Admissible. |

The unchanged starter is the first target-negative (both target F, sentinel P).

## Assertion-strength findings

- The three enumerated outcomes (discarded, leaves ready state, continues) are asserted on live game state.
- `Task-like-manual` (equivalence with manual emptying: stats, experience, OutputCollected rules) is unasserted; the
  enumerated items carry the obligation. Recommend excluding it.
- Scope: only a furnace (`DataBasedObjectMachine`) is exercised. The alternative covers machines that go through
  `BaseMachine.GetTracked` (object machines, where broken `Data/Machines` rules apply) and not the terrain-feature and
  tile machines that construct `TrackedItem` directly; the reference covers all. The exam's report is about "content
  mods with broken machine rules", which is the object-machine path, so the alternative is valid under the public text,
  and the suite cannot tell the two scopes apart.
- No over-constraining assertion found.

## Fixture race (read from code, not observed)

`SuiteZeroStackOutput.cs:71-73` zeroes the stack one tick after the clock advance. If Automate's 60-tick automation
pass lands in that one-tick window, the good bar is collected first and the deadline-less wait at line 72 hangs to
the 2400-tick timeout on a correct tree. Expected about 1 boot in 60. An isolated `hung` on the first target case
should be rerun before it is counted.

## Harness note

`SuiteZeroStackOutput.cs:92-93` can throw only when the previous case failed before placing its furnace; the verdict is
F under both runners. The prepared evaluator image still contains the pre-fix runner (see `known_issues`).

## Not run

Each control was run once; no repeat runs to measure the race above.

Starter, reference and the three declared controls were executed with the full profile in the real game container
(records under `e0/records/stardew-valley/core/stardew-automate-zero-stack-output/`); `rhenium-study e0 run` reported an empty `problems` list for all five.
