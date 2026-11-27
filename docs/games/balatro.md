# Balatro support and validation

| Surface | Current status |
| --- | --- |
| Plugin / catalog | Independent `rhenium-balatro-plugin` 0.3.0; ten frozen catalog 0.2.0 tasks |
| Difficulty | Authored 3 Easy / 4 Medium / 3 Hard; uncalibrated |
| Linux runtime | Explicit Steam acquisition and preparation on the controlled native Linux x86_64 Docker host |
| Full task controls | All ten gold/base pairs complete through the core CLI; 20 controls, 56 real game processes, 912 required outcomes |
| Extended original controls | All 48 additional controls completed as intended; full original matrix: 68 controls, 197 real game processes, 3461 required outcomes |
| Anonymous attempts | Public starter materialization and sealed, source-reviewed honest scoring |
| New executable submissions | Actual source review and an explicit matching seal required before game execution; for E1 studies the static policy of `rhenium-study e1 review-balatro` may record the seal of a submission in which it finds nothing ([study README](../../tools/study/README.md)) |
| Untrusted / disposable evaluation host | Not implemented |
| Windows / WSL | Historical 0.2.2 evidence only; new default container bindings are native Linux only |
| macOS / other hosts | Not validated for container-v1 |
| Study admission | All ten tasks admitted on 62 real-engine E0 controls; four also qualify for the joint compatibility analysis |
| Model calibration | Not performed; a study attempt is not a calibration |

Use the [Linux container guide](balatro-container-v1.md) for preparation, exact-byte
review, migration and maintenance replay. The [plugin guide](../../plugins/balatro/README.md)
links the separately preserved Windows and WSL results. Historical evidence is not
relabeled as a container-v1 result.

The runtime uses the pinned licensed Steam build 17459173 with native Linux LÖVE,
Lovely and Steamodded. Evaluation uses the exact prepared dependency image ID and
read-only licensed source, with an owned X display, a normal 800×600 rendered
window, gamespeed=1, FAST=0, HEADLESS=0 and null audio. It performs no authentication,
source acquisition, dependency installation, update or image build. Runtime
preparation remains an explicit operator action.

This is controlled, source-reviewed **honest** execution. Container restrictions
do not establish the provider-neutral untrusted/disposable-host contract. A new
submission is not executable merely because an anonymous attempt can be prepared.
Missing engine evidence, an incomplete assertion set, runtime drift or a missing
review seal cannot pass; a reduced `core` result cannot pass either.

The [candidate README](../../benchmarks/balatro/README.md) and
[historical imported control record](../../benchmarks/balatro/validation/poc-v02-controls.md)
retain their original provenance. Authored prompts, starters, assertions, reference
solutions, scoring and task numbering are unchanged. Licensed game files, raw
logs, saves, provider state and review records remain private operator state.
The saved-run boundary remains seeded initialization followed by one load;
blank-MENU direct loading was not repaired by this runtime work.
