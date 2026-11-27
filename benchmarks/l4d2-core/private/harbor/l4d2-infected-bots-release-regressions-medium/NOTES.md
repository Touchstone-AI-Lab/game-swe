# Maintainer notes

## Scope and provenance

This task contains a source-only snapshot of L4D Infected Bots and its required
public-source dependency from `fbef0102/L4D1_2-Plugins` commit
`b570e9efd9534ea8822f6fc7909704b4ee8fcdf2`. It seeds four independently
repairable release regressions in the target plugin: runtime slot accounting,
current-map configuration selection, initial-round replacement timing, and
finale cleanup. The reference behavior is based on the upstream revisions listed
in `task.toml`; no private helper name or reference diff is scored.

The public artifact contains the target and dependency SourcePawn sources,
public includes, required gamedata/data/translation files, exact upstream license
texts, and provenance hashes. The Left4DHooks bundle is present only as public
compile-time source/include material. No compiled `.smx`, Valve game file,
credential, maintainer test, or reference solution is included in the agent
artifact.

## Agent and verifier boundary

The agent receives the broken `l4d1_2_plugins` artifact and `instruction.md`.
Private tests, this file, validation tables, and `solution/` are outside the
submitted artifact. The public `tools/smoke.py` performs an answer-free license
and SourcePawn compilation check; it does not expose the four target values or
emulate dedicated-server behavior.

The separate verifier compiles the submitted target, the submitted public spawn
dependency, and a verifier-owned external consumer of all three target config
natives with SourceMod 1.12.0.7246. Runtime suites compile only against
verifier-owned headers, then boot the pinned Left 4 Dead 2 dedicated server and
observe the submitted plugins through public commands, public cvars/natives,
events, and live entities. Candidate-controlled gamedata/data/translation copies
are allowlisted; verifier-owned Left4DHooks runtime data is installed last.

Package validation requires every one of the frozen snapshot's 63 public-source
files and checks canonical UTF-8 CRLF-to-LF hashes for both license texts and
provenance. The accepted file-suffix set is closed, with only the three exact
license paths allowed without suffixes. All files must be regular, strict UTF-8
text without NUL bytes; compiled binaries, archives, common Valve assets, Python
bytecode, WebAssembly, and SMX content disguised by name are rejected through
suffix and file-magic checks. Added source files remain possible within the
documented package limits, but a solver cannot shrink the snapshot by deleting an
unexercised profile or replace its legal/provenance record.

No Valve files are stored in this repository. The shared verifier image supplies
anonymous dedicated-server app `222860`, fixed game build `23990100`, and pinned
MetaMod/SourceMod. Verification runs with network disabled. SourceMod exceptions,
unbound natives, plugin-load failures, crashes, missing/duplicate case markers,
duplicate/missing FINAL markers, or an incomplete exact case set fail closed.

## Case design

Eighteen private cases comprise two package/compile checks and sixteen managed
SourceMod cases across four independent server boots. Capacity and configuration
run in coop; the initial-window suite explicitly runs versus and guards
`L4D_HasPlayerControlledZombies()`. The configuration fixtures exercise the
upstream two-stage contract: Settings default/count when no map profile exists,
then Maps default/count when the current-map profile exists, with omitted count
keys inheriting the stage default. Both `sm_zlimit` and `sm_timer` overrides are
observed before reload and must be replaced by the reloaded profile.

Initial and finale fixtures create live clients and entities after round setup.
They observe real delayed replacement behavior rather than call private timer or
cleanup helpers. The initial suite checks both preservation of the initial delay
and restoration of the normal delay after the window. The finale suite drives the
public allow-cvar disable/re-enable lifecycle before firing `finale_win` and
checking that the pending replacement stays cancelled.

## Validation status

The EOL-de-fingerprinted post-audit frozen-v8 verifier image is
`sha256:ea1e646a7c9ec513ccd8a795f2c87165fd0256da39ef88971a83b1c85d571a1e`.
An extraction audit found the image's 36 files under `/tests` byte-identical to
the current test build context (excluding only the Dockerfile, which is not an
image payload).
The frozen evaluation-contract SHA-256 is
`7b626134a23e25f245dbb6f579aa09372d2d5227a71727bed58cdc16e647e92a`.
Final direct offline controls produced:

- broken base and independent byte-identical no-op: exact 14/18, with one target
  failure in each defect group and all fourteen guard cases passing;
- oracle: three fresh full runs at exact 18/18, with identical verifier-log
  hashes and no fatal or incomplete suite;
- four single-group predicates: exact 15/18 each, unlocking only the mapped target
  case with zero guard regression;
- two structurally different complete alternatives: exact 18/18 each.

Every one of these eleven fresh controls emitted the exact eighteen-case set and
four server `FINAL` markers, with zero fatal-runtime matches, duplicate cases, or
unexecuted cases. The verifier image and all candidates were run with network
disabled. Final Harbor nop/oracle trials were then run against this exact v8
contract; no v7 Harbor result is represented as current evidence.

The public release's twelve `.sp`/`.inc` files, the oracle, and all six rebuilt
candidate trees use one LF convention and exactly one final LF. This removes a
mixed-EOL minority-line fingerprint found by the fresh audit: the former seven
rare bare-LF lines in the otherwise-CRLF target intersected all four seeded
regions. The v8 broken target's raw SHA-256 now equals its canonical content hash,
and `validation/eol-audit.tsv` records zero CR bytes and zero mixed-EOL files.
This is a release-artifact hygiene invariant only; neither public smoke nor the
private package gate rejects a solver's reasonable LF/CRLF edits.

The package matrix contains fifteen public/private probes: the positive original,
the earlier seven binary/text/node mutations, credential material, an extra
Python helper, direct network code, a `#tryinclude` plus macro-alias network
variant, inert comment/string tokens, a padded minimal shim, and a reasonable
SourcePawn helper. All prohibited variants fail closed. The inert and reasonable
source additions remain accepted and preserve the base 14/18 shape. The minimal
shim passes source shape and compilation but scores only 7/18 with reward zero,
demonstrating that padding cannot bypass the real-server contract or crash the
grading framework. Public/private log hashes and exact mutation-tree hashes are
recorded in `validation/package-probes.tsv`.

Exact verifier-log and candidate hashes are recorded in `validation/`. Final
Harbor 0.20.0 nop/oracle trials on v8 reproduce 14/18 and 18/18 with rewards 0
and 1, no exception, the exact case set, and four server `FINAL` markers.
The six tested candidate sources are reproducible from the broken tree using the
unified patches and `validation/candidates/rebuild.py`. Patch application is
defined after UTF-8 CRLF-to-LF normalization, with Git autocrlf explicitly
disabled for cross-platform deterministic output. The checked-in manifest distinguishes
the full environment tree (including the Dockerfile) from the exact artifact tree
mounted at `/app/l4d1_2_plugins`; both hashes match fresh independent rebuilds and
the sources used for the recorded runs.

## Version 1.1 timing review

Initial-wave delay is measured from the wave scheduling request, not each later
death. The suite retains its existing public round setup and latches first living
replacement with player_spawn plus every-frame observation. The public round_start
time is a conservative scheduling lower bound; the safe-zone poll may arm the
actual initial wave approximately one second later. The check therefore does not
certify the private deadline exactly, but rejects a competing four-second death
timer that previously escaped both sparse samples. No private helper or added
public diagnostic interface is required. See validation/REVIEW-REVISION.md for
failed fixture prototypes; no gold source was changed to accommodate them.
