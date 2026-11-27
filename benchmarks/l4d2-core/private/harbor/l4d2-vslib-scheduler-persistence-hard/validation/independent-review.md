# Independent maintenance review

Verdict: **PASS** for the authored task and its final deterministic controls.

Reviewed on 2026-09-19 by a fresh reviewer assigned only this task. This was
repository maintenance, not an exam attempt. The reviewer read root AGENTS.md,
the complete public instruction, relevant frozen VSLib sources and LinGe
overrides, all four reference replacement files, the engine suite and verifier,
candidate generation, case mapping, NOTES, and final control evidence. No
implementation, assertion, or model experiment was changed or run by this
reviewer. This file is the reviewer's only task modification.

## Scope and difficulty

The eight reports describe distinguishable release contracts: scheduler mutation,
identity retirement, options ownership, clock transitions, string/key encoding,
recursive value persistence, legacy compatibility, and nonexecuting parsing.
Shared modules do not collapse these into one defect. The starter visibly
contains the relevant faults, and the effective Base.nut serialization override
creates a legitimate cross-file integration requirement. Expectations such as
atomic invalid replacement, shared callback parameter identity, legacy key
recognition, and zero-fire short durations are stated publicly rather than
introduced only by hidden tests.

Compared with the accepted LinGe hard-v3 and Mutant Tanks hard instructions,
this task has less engine-entity breadth but substantial scheduler reentrancy,
ownership, temporal accounting, and recursive codec design. Author-assessed hard
is reasonable. It is not an empirically calibrated model difficulty claim; NOTES
correctly states that no solver experiment was run.

## Solvability and reference

The reference implements snapshot eligibility with live identity checks, retires
names through the common removal path, clones timer-owned options, settles clocks
before transitions and reads, and handles duration counts before callback entry.
The persistence path serializes fully before writing, tracks ancestor containers
without rejecting repeated siblings, preserves key types, and parses data without
compilestring. Legacy recursive conversion is separated from modern saves. The
late LinGe overload is repaired consistently with the FileIO implementation.
No blocking contradiction between the public contracts and the reference was
found. Public APIs and MIT attribution remain present.

## Test fairness and limitations

The 47 cases observe public callback effects, exported TimersID, public clock
reads, actual scriptdata round trips, wrapper APIs, and ConfigManager integration.
There is no patch comparison, private helper requirement, codec byte-format
oracle, or imposed ordering between independent due timers. The mutual-removal
case permits either peer to run first. The independent SourceMod pulse prevents
a broken candidate scheduler from stopping the observation driver.

Calling the existing VSLib_RemoveDeadTimers cleanup function is a legitimate
operation-level test. It does not establish map-transition behavior, and NOTES
explicitly avoids that claim. The real engine still supplies VM behavior, time,
scheduled callbacks, and file I/O.

The alternative control is a reference-derived ordering/encoding variant, not an
independently designed solution; its documentation accurately limits the claim.
Nonblocking opportunities for broader future coverage include a direct
DURATION_VARIANT preservation case, nonnumeric duration rejection, ordinary
unbounded repeat, explicit self-removal, and a deliberately late scheduler update.
The current partial controls are representative sensitivity checks, not exhaustive
proofs for every sentence of the contract.

## Evidence verification

Final contract:
`646df4c073315181134d58382df6f90e29a2fc6b70b5fc696d9cde2ba587347a`.

Runtime image:
`sha256:3604481021c1b605741e994fb623834fb0725b2309e53b7ed9a4c86fe3fb65cd`.

The reviewer independently recomputed all six component hashes, staged source
and tests hashes, verifier-log SHA-256, and server-log SHA-256 for all eleven
final runs under `.rhenium/authoring/vslib-controls`. Every value matched its raw
receipt and the published control-receipts.json. The earlier final gold receipt
under `.rhenium/authoring/vslib-runs` was also checked, but historical debugging
failures were not treated as final evidence.

| Candidate | Passed | Required cases | Exit |
| --- | ---: | ---: | ---: |
| gold | 47 | 47 | 0 |
| alternative | 47 | 47 | 0 |
| nop | 12 | 47 | 1 |
| minus-report-1 | 46 | 47 | 1 |
| minus-report-2 | 41 | 47 | 1 |
| minus-report-3 | 45 | 47 | 1 |
| minus-report-4 | 44 | 47 | 1 |
| minus-report-5 | 43 | 47 | 1 |
| minus-report-6 | 46 | 47 | 1 |
| minus-report-7 | 46 | 47 | 1 |
| minus-report-8 | 43 | 47 | 1 |

All final runs completed every required case. Each report-specific mutation fails
an assertion mapped to its intended contract; some naturally fail related
integration assertions too. These are real-engine authoring controls, inspected
independently rather than rerun by the reviewer. Catalogue integration and
repository-wide release checks are outside this task-local review verdict.
