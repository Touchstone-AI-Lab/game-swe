# Socket verifier r3 authoring review

The maintainer explicitly authorized revising the socket verifier and updating
its benchmark baseline on 2026-10-27. Catalog 1.4.0 retires r2 (SG-138) and admits
r3 (SG-159). This is a new baseline, not a checksum update that accepts an
unexplained failure. The r2 source, gold repair, manifest and all historical
control records are preserved unchanged.

## Scope and provenance

The public exam, starter tree, solution, build template, scorer and twelve
scenes are byte-identical to r2. The original Downfall MIT provenance and
licenses accompany the copied tree. Exactly three task files change:

- `tests/Probe.java`: fixture setup, slow-frame handling and bounded phase timing;
- `tests/expectations.json`: require the intended action phase as well as every
  existing native behavioral expectation;
- `tests/test.sh`: document the EXIT trap's indirect function invocation for
  ShellCheck; executable shell behavior is unchanged.

A regression test compares every new task file against the frozen r2 manifest
and permits only these three reviewed differences. The r3 manifest binds the
new bytes separately; r2 results are not inherited or relabeled.
The runtime version/fingerprint also changes to require explicit preparation of
the new task set through the pinned Steam provider.

## Real-game fixture correction

On Lab, r2's unchanged gold repeatedly completed only 3/13 assertions. The game
was running, but scenes remained before the gem grid or the native Smith grid
could receive their selection. Read-only diagnostics found the game's original
render method drops the entire update and render when raw frame time exceeds
100 ms. Software GL under the frozen two-CPU quota repeatedly exceeded that
limit. This discarded input and let wall-clock scene deadlines expire while
native effects and screens barely advanced.

The r3 ModTheSpire probe instruments only that guard's raw-time measurement,
bounding it below 100 ms. It leaves the graphics clock, game update/render,
mod code, screen logic, native timers and physical OS input in place. It does
not replace an engine type, project source behavior or synthesize a result.
The probe logs the number of slow frames to private runtime diagnostics.

Fixture construction now clears the starting-deck animation queued during
Guardian/Exordium construction, after installing the explicit four-card deck,
and uses native fast mode and an immediate initial fade. These operations are
setup only. No selected-card collection, candidate selection flag, expected
upgrade, gem insertion or cancellation outcome is injected. Actual play still
uses the game's campfire option, grid, confirm button and Java Robot input;
follow-up Smith actions still use the real public SmithOption.

Each action phase has a 15-second stall deadline and each scene has a
45-second ceiling, inside the unchanged 450-second game-process timeout. A
single first-scene load delay no longer consumes every later action's budget.
A missed click can no longer pass the cancellation controls merely because the
deck stayed unchanged: the expected action phase must also have been reached.
Every original visible outcome and the intended seven NOP failures remain
required. Nonce, unique-case, process-exit and complete-observation checks are
unchanged.

## Validation policy

Require a complete real-game NOP result with exactly the original seven failed
case IDs, a 13/13 gold result, the independent alternative and the two isolated
repairs' original failure sets. Also replay the six admitted tasks through the
Hub against the automatically prepared final runtime. Retain failed authoring
runs and raw logs privately; commit only compact receipts and hashes, never
licensed images, trajectories or model submissions.

Authoring retained the first r3 draft's 12/13 gold result (the first scene
expired) and the revised 13/13 result separately. Later changes to the shell
trap annotation and provenance flags do not change executable behavior. The
inherited pre-repair-freeze flag is explicitly false for this new authoring
process; no r2 freeze is claimed for r3.

## Final Lab real-game controls

The automatically Steam-prepared catalog 1.4.0 runtime completed all twelve Hub
NOP/gold executions: 199/199 gold assertions passed and every NOP failure set
matched its intended baseline. Socket r3 produced base 6/13, gold 13/13,
alternative 13/13, back-only 10/13 and retirement-only 9/13, with complete
observations in every run. The three independently replayed repair variants
preserve all six positive controls. See `author-controls.json` and
`../lab-steam-runtime-controls-r3.json` for compact receipts and source identities.

The preparation list contains exactly the six admitted real-game tasks. It
excludes the unavailable enum JVM diagnostic; that task's frozen source and old
records remain intact and its public full result stays incomplete. Earlier
network failures and the rejected enum image build remain in private diagnostics.
The final run used checksum-verified public Maven/Git caches from earlier
automatic preparation; game acquisition still used the pinned Steam provider.
