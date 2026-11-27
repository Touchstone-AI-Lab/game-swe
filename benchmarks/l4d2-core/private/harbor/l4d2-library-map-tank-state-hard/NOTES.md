# Authoring evidence

Version 1.1.0 clarifies malformed/truncated imports and isolates the missing-file
fixture with a fresh valid baseline, adding one setup assertion (44 cases total).
New engine validation is recorded separately in `validation/revision-controls.json`
and [`../../../review-revisions.md`](../../../review-revisions.md). The 12 controls and 43/43
reference/alternative passes below are historical version 1.0.0 evidence.

This author-assessed **hard** task retains the complete Competitive Rework source
snapshot, with the accepted release and score lifecycle repairs incorporated.
The new eight-report surface is L4D2Lib: atomic map imports, shared KeyValues
cursor ownership, native output bounds, geometry, and a connection-aware Tank
state machine with delayed death and reentrant observers. The interacting state
contracts put it in the hard range, though below the breadth of Mutant Tanks.

The private suite compiles and loads the complete submitted L4D2Lib in two fresh
pinned dedicated-server boots: 23 map/native cases and 21 Tank lifecycle cases.
Assertions observe public natives/forwards, real KeyValues files, engine events,
real fake-client entities, connection serials, and SourceMod timers. No private
function bridge or source-text predicate supplies a behavioral verdict.

A trusted Confogl provider supplies local mapinfo paths. The suite replays the
public `OnLibraryAdded` forward; this covers its callback contract, not an entire
provider unload/reload operation. It directly tests failed and missing-file
reloads after a successful import. Initial import failure, explicit negative
radii, observer-triggered round reset, and a full map transition are supported by
the reference but are not separately exercised. Round-start cancellation and
worldspawn rejection are tested; non-networked/free-entity categories are not individually instantiated.
The geometry contract preserves the existing networked m_vecOrigin input domain.
These are stated coverage limits, not claims of exhaustive testing.

Valve's KeyValues importer can accept a truncated file. The reference validates
syntax before swapping the imported image. The public contract now explicitly
requires rejecting malformed/truncated documents even when the engine importer
returns success. The missing-file scenario first reimports a valid fixture so a
malformed-file failure cannot cascade into it. A `minus-syntax-validation`
control omits only the syntax failure gate; it should fail the malformed case
while preserving the independent missing-file case. Tests require transactional behavior,
not a particular parser implementation. Present subsection copies follow real
`KvCopySubkeys` replacement semantics. Missing copies leave the destination
unchanged. Slash-separated nested paths are explicit in the public specification.

Fake clients are created after map initialization so SourceMod receives actual
disconnect callbacks. Before the slot-reuse fixture disconnects its dying owner,
it sets that entity dead to prevent the engine from creating an unrelated Tank
replacement. The fixture checks actual index reuse; new ownership is then tested
through `tank_spawn`. Duplicate death events are separated by 0.30 seconds and
checked 0.65 seconds after the original event, detecting timer postponement.
After handoff cancellation, a further transfer checks owner and pass-count
continuity, catching a stale timer that silently clears the new owner.

Historical `validation/control-receipts.json` and `control-matrix.tsv` retain version 1.0.0 component,
source, test, verifier-log, and engine-log hashes. Raw local evidence is under
`.rhenium/authoring/library-accepted-controls/`; earlier `library-runs/` records are
superseded authoring diagnostics, as are `library-final-controls/` and
`library-reviewed-controls/` records. The immutable local runtime is used offline;
no Valve files or generated binaries enter the task. Tree hashes sort relative
POSIX paths lexically and delimit names and exact content with NUL bytes.

The alternative is reference-derived: it uses squared-distance geometry with
explicit negative-radius guards and a separate committed pass-count increment.
It is not a wholly independent implementation. Eight report mutations check
representative omissions; an additional mutation deliberately restarts a pending
death timer. Runtime exceptions fail the complete verifier closed, so a zero
scored result may coexist with passing raw engine markers.

Reproduce with `python -B validation/run-control.py gold --output-root
/absolute/path/outside/task`. Generated source copies, logs and caches belong
outside the benchmark task. The public smoke command compiles L4D2Lib; it does
not expose private behavioral assertions.

## Hub full-profile validation and harness revision (2026-09-24)

The receipts above were direct maintainer runs. This task was then run through the
Hub full profile (`rhenium run`) on a Linux x86_64 Docker host, where `tests/verify.py`
needed these plumbing corrections; the suites, case names, pass criteria and source
checks are unchanged:

- the message after a fail-closed `FAIL <case>:` now names the SourceMod exception or a missing FINAL marker instead of the last engine line containing `error` (such as "Invalid counterterrorist spawnpoint"); the text never changes a verdict.
- a server that has been sent SIGKILL is now waited for up to 120 seconds instead of five (a still-unreaped server is `INVALID_ENVIRONMENT`), because a loaded host took 8 to 15 seconds to reap the multithreaded srcds and the verifier crashed with a traceback.
- each boot now has 240 seconds instead of 55 to reach its FINAL marker. A healthy boot needs 5 to 15 seconds; on this host one L4D2Lib reference boot stalled during plugin loading for over 55 seconds, and the old budget turned that into a complete failing verdict for every case of the boot.

The historical receipts in `validation/` still carry the previous tests hash and stay
historical evidence. Current starter, reference (three runs) and control results are in
[`../../../validation/hub-full-profile-hard-tasks.md`](../../../validation/hub-full-profile-hard-tasks.md).
