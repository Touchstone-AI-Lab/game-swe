# Addon repair pack validation

All runs below went through `rhenium run garrys-mod/addon-repairs/<task> <tree> --profile full`,
the real Hub evaluator path, on a shared Linux x86_64 host with Docker, against the
prepared runtime `garrys-mod/gmod-gluatest-addons` (digest-pinned GLuaTest image,
Garry's Mod patch 2026.04.29). Dates are UTC. Trees are built from the pack itself:
starter = `environment/<addon>`, reference = starter + `solution/after/`, controls =
the manifest's base + its patch from `private/study-controls/<task>/`.

Scores: a complete run that fails any case scores 10 (the static preflight); a pass
scores 100. A starter must be complete and fail only target cases; a reference must
score 100 on three runs with identical case outcomes.

## advdupe2-paste-regressions

| Tree | Run ID | Date | Score | Complete | Cases passed | Failed cases |
| --- | --- | --- | ---: | --- | --- | --- |
| starter | `run-51d95c2b0e0b48aa` | 2026-09-23 | 10 | True | 5 of 11 | every target case (6) |
| reference #1 | `run-a18eb581de0547a1` | 2026-09-23 | 100 | True | 11 of 11 | none |
| reference #2 | `run-8b5eccb52d89469e` | 2026-09-23 | 100 | True | 11 of 11 | none |
| reference #3 | `run-374b45594a7a4a98` | 2026-09-23 | 100 | True | 11 of 11 | none |

Reference repeats: 3 runs, identical case outcomes: True.

E0 controls:

| control | kind | base | change | run | observed | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `target-negative-rope-limit` | target-negative | reference | Reference with the rope-limit check dropped: pasted ropes are counted as ropes but sbox_maxropeconstraints is never enforced (half of report D). | `run-fc9f6b72dcfb4e8e` (2026-09-23) | complete; fails exactly `D: the rope limit is enforced when pasting` | admissible |
| `compat-negative-all-ropes` | compat-negative | reference | Reference that counts every pasted constraint as a rope: every target passes, but a pasted weld no longer counts against the constraint allowance. | `run-d1dde9503c9742f2` (2026-09-23) | complete; fails exactly `preserved: a pasted weld still counts as a constraint` | admissible |
| `alternative-independent-fix` | alternative | starter | Starter plus an independent fix for all five reports: re-activate scaled props in the paste loop, remove the entity where DoGeneric fails, a numeric bone loop from 0, a per-type rope limit, and one-sided separator trimming. | `run-07062039d1d74081` (2026-09-23) | 100, every case passes | admissible |

## cfw-contraption-regressions

| Tree | Run ID | Date | Score | Complete | Cases passed | Failed cases |
| --- | --- | --- | ---: | --- | --- | --- |
| starter | `run-12bdf0e258994a31` | 2026-09-23 | 10 | True | 4 of 10 | every target case (6) |
| reference #1 | `run-2f8bee57ea32419a` | 2026-09-23 | 100 | True | 10 of 10 | none |
| reference #2 | `run-2a8e5ae106474189` | 2026-09-23 | 100 | True | 10 of 10 | none |
| reference #3 | `run-6720c1c0c0684325` | 2026-09-23 | 100 | True | 10 of 10 | none |

Reference repeats: 3 runs, identical case outcomes: True.

E0 controls:

| control | kind | base | change | run | observed | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `target-negative-players-only` | target-negative | reference | Reference with only the player exclusion kept: NPCs and nextbots are still pulled into contraptions (a partial repair of report C). | `run-b8b7032a0e0f4c75` (2026-09-23) | complete; fails exactly `C: something parented to an NPC stays out of contraptions`, `C: something parented to a nextbot stays out of contraptions` | admissible |
| `compat-negative-family-only` | compat-negative | reference | Reference that moves the mass update to the family instead of adding it: every target passes, but a contraption's total no longer follows a member's new mass. | `run-e15cba9bde5841b2` (2026-09-23) | complete; fails exactly `preserved: a welded contraption's total mass follows a member's new mass` | admissible |
| `alternative-independent-fix` | alternative | starter | Starter plus an independent fix for all four reports: recompute the family total from its members, ask any parent that defines the veto hook, one character check before linking, and ignore self-constraints where constraints are tracked. | `run-ad61457d90b2404b` (2026-09-23) | 100, every case passes | admissible |

## starfallex-library-regressions

| Tree | Run ID | Date | Score | Complete | Cases passed | Failed cases |
| --- | --- | --- | ---: | --- | --- | --- |
| starter | `run-554f1402f72440e2` | 2026-09-23 | 10 | True | 7 of 13 | every target case (6) |
| reference #1 | `run-f387869239854711` | 2026-09-23 | 100 | True | 13 of 13 | none |
| reference #2 | `run-ec473bea95d14bec` | 2026-09-23 | 100 | True | 13 of 13 | none |
| reference #3 | `run-dfbd45215ffb40d0` | 2026-09-23 | 100 | True | 13 of 13 | none |

Reference repeats: 3 runs, identical case outcomes: True.

E0 controls:

| control | kind | base | change | run | observed | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `target-negative-tell-guard` | target-negative | reference | Reference with the skip() clamp reverted and tell() made tolerant of the gap instead: the position query stops erroring, but a later write still leaves a hole (report D). | `run-80ceb6cd4d4c4f25` (2026-09-23) | complete; fails exactly `D: skipping past the end of a string stream leaves it usable` | admissible |
| `compat-negative-no-permission` | compat-negative | reference | Reference whose giveWeapon also drops its permission check: every target passes, but owners without the privilege can hand out weapons. | `run-d9b0d065f4c04ad3` (2026-09-23) | complete; fails exactly `preserved: an unpermitted chip still cannot hand out weapons` | admissible |
| `alternative-independent-fix` | alternative | starter | Starter plus an independent fix for all six reports: an env local in loadstring, pcall-guarded __tostring, PLY_META.Give at the call site, a post-skip clamp, a textbook sin-weighted slerp, and includedata registering the include directly. | `run-4c05680959bc44c4` (2026-09-23) | 100, every case passes | admissible |

## wiremod-e2-library-regressions

| Tree | Run ID | Date | Score | Complete | Cases passed | Failed cases |
| --- | --- | --- | ---: | --- | --- | --- |
| starter | `run-0289c8f21dbc45b5` | 2026-09-23 | 10 | True | 5 of 11 | every target case (6) |
| reference #1 | `run-599181ac610749c3` | 2026-09-23 | 100 | True | 11 of 11 | none |
| reference #2 | `run-802eea80a3c74ba7` | 2026-09-23 | 100 | True | 11 of 11 | none |
| reference #3 | `run-630e1c2488c84c18` | 2026-09-23 | 100 | True | 11 of 11 | none |

Reference repeats: 3 runs, identical case outcomes: True.

E0 controls:

| control | kind | base | change | run | observed | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `target-negative-complex-text` | target-negative | reference | Reference with the zero-part comparisons fixed but a real-only complex number still returned as a number rather than text (half of report C). | `run-3d145d114599487b` (2026-09-23) | complete; fails exactly `C: complex numbers with a zero part print cleanly` | admissible |
| `compat-negative-tochar-clamp` | compat-negative | reference | Reference whose toChar clamps a bad code instead of rejecting it: NaN still yields an empty string, but an out-of-range code now yields a character. | `run-65037d99e3e74ebb` (2026-09-23) | complete; fails exactly `preserved: character codes in and out of range behave as before` | admissible |
| `alternative-independent-fix` | alternative | starter | Starter plus an independent fix for all six reports: a clamp helper, truncation in the toString(n, base) wrapper, a rewritten complex formatter, NaN-proof range checks, a per-evaluation copy of the table element types, and element-wise comparison in indexOf. | `run-ee4688452f3940bf` (2026-09-23) | 100, every case passes | admissible |

## wiremod-gates-chips-regressions

| Tree | Run ID | Date | Score | Complete | Cases passed | Failed cases |
| --- | --- | --- | ---: | --- | --- | --- |
| starter | `run-0deee9dac0014432` | 2026-09-23 | 10 | True | 7 of 14 | every target case (7) |
| reference #1 | `run-bf66d7b72a204b34` | 2026-09-23 | 100 | True | 14 of 14 | none |
| reference #2 | `run-fa50e74433d14a28` | 2026-09-23 | 100 | True | 14 of 14 | none |
| reference #3 | `run-88aa9acb43b14a79` | 2026-09-23 | 100 | True | 14 of 14 | none |

Reference repeats: 3 runs, identical case outcomes: True.

E0 controls:

| control | kind | base | change | run | observed | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `target-negative-derive-untimed` | target-negative | reference | Reference with the vector/angle Delta gates fixed but the number Derivative gate left untimed (half of report A). | `run-6ad7e478313c4ebf` (2026-09-23) | complete; fails exactly `A: a derivative gate drops back to zero once its input settles` | admissible |
| `compat-negative-timers-kept` | compat-negative | reference | Reference that never forgets a lambda timer after its last run: every target passes, but a finished timer still reports that it exists. | `run-e9617eb4bc3f4576` (2026-09-23) | complete; fails exactly `preserved: a finished timer is gone afterwards` | admissible |
| `alternative-independent-fix` | alternative | starter | Starter plus an independent fix for all six reports: timed derivative and dT > 0 guards, a renumbering pass over declared outputs, a cached quota that also follows the unlimited switch, deferred timer removal keyed to its callback, early exits of typed hologram functions return the neutral value of the type declared in each e2function signature, and a statement-only return-type check. | `run-9b76625d8ba643e1` (2026-09-23) | 100, every case passes | admissible |

## Runtime identity

`rhenium runtime prepare garrys-mod/gmod-gluatest-addons` (2026-09-23) recorded artifact
identity `sha256:3c027567f449a13d70db5121ae264054b64a76af3d535bb4d11755124a2d3a5d`
over the five per-task evaluator images, built from
`ghcr.io/cfc-servers/gluatest/x86-64@sha256:23cd97d4fa9cf44fc16cabed6b973e117581769725b5735c533d10da7fe0b1fb`.

## Runs that are not part of the record

The host was shared and heavily loaded. The following executions never produced an
engine verdict for the task and were repeated; none of them was a model or task
failure:

- `run-ecb21d248622414f` (wiremod-e2 starter): the evaluator's Docker daemon probe timed
  out, so the result was `unavailable` / incomplete before the server started.
- `run-6238a214810d4c5e` (cfw starter): the dedicated server stalled in Steam client
  initialisation ("CSteamEngine::BMainLoop appears to have stalled > 15 seconds") and
  the two-minute engine timeout ended it; the collector correctly reported the run as
  incomplete.
- Several `rhenium run` invocations failed before evaluation or while recording the
  result because another Hub process held the shared state database ("database is
  locked"), was re-materialising the pack's starter workspaces at the same moment (the
  task key was briefly missing), or the development shell failed to start. These have
  no run record, or a run row without a verdict, and were retried.

One control was revised after its first execution: the first
`alternative-independent-fix` for `wiremod-gates-chips-regressions` wrapped every typed
hologram function at `postinit` and failed report [E]'s case (`run-6beb9aada4694445`,
complete, 13/14). It was replaced by the version in `private/study-controls/`, which
passed (`run-9b76625d8ba643e1`). See that task's `NOTES.md`.
