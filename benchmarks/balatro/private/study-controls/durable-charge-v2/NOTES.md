# E0 notes: balatro/core/durable-charge-v2

Private maintenance material. Never copy into an attempt or a model workspace.

Anchor numbering: a paragraph number counts body paragraphs of the public file in order, skipping headings, list items and table rows; bullets count list items in order, and table rows count body rows below the header.

## Baseline

From the validation matrix's recorded engine results: the starter fails 11 of 76 cases (all
`target`), the reference and gold-journal fail none. The starter has three defects: `snapshot`
returns its history by reference, `restore` turns a consumed zero into 2, and restored balances are
read by row position.

## Manifest controls

| control | kind | change | outcome |
| --- | --- | --- | --- |
| M01-duplicate | compat-negative | All three defects fixed; a replayed discard adds charge again. | Fails `core.duplicate`, `core.receipt_alias`; every target case passes. |
| M02-snapshot-alias | target-negative | Zero and row defects fixed; snapshot alias kept. | Fails `core.snapshot_alias` only. |
| M03-zero-restore | target-negative | Alias and row defects fixed; zero resurrection kept. | Fails 7 target cases only. |
| M04-restore-pollution | compat-negative | All three defects fixed; `restore` clears state before validating. | Fails `core.restore_atomic`, `core.snapshot_validation`; every target case passes. |
| M05-row-restore | target-negative | Alias and zero defects fixed; row-based balance kept. | Fails 4 target cases only. |
| gold-journal | alternative | Append-only event journal with state derived by replay, against the reference's mutable maps. | Fails no case. |

M01 and M04 are valid compatibility negatives because the starter already passes those cases: replay
without re-application and atomic restore failure both hold before the repair.

## Preserved contracts

The ledger semantics in API.md paragraphs 2 to 8 other than the snapshot alias and zero restore, and
ordinary play without a restart (CONTRACT.md paragraphs 2 to 4, measured by the `local.*` cases).
Native membership across a load (CONTRACT.md paragraph 5) also already holds.

## Frozen controls left out of the manifest

- M06-display-only: restored scoring ignores the displayed balance; fails 2 target cases
  (`restored.postload.score`, `trajectory.equivalent`) and 2 preserved cases (`restored.pair.consume`,
  `restored.cap.score`), so it fits neither negative kind. Those two preserved cases are the generated
  `overlap` cases.

## Role and overlap changes

Nine cases changed from `preserved` to `runtime-sentinel`. None is failed by a compat-negative control.

- `restored.unequal1.load`, `restored.unequal2.load`, `restored.zero.load`: the record compares two
  literals (scenario.py:79); a bad load raises ProtocolError on the line before, so the case cannot fail.
- `restored.unequal1.save`, `restored.unequal2.save`, `restored.zero.save`: a bad response raises first
  (scenario.py:62), leaving only a non-empty file check (scenario.py:63). That proves the save step ran.
- `restored.unequal1.hash`, `restored.unequal2.hash`, `restored.zero.hash`: compare the save file hash
  later in the run (scenario.py:107). This protects the evidence file and matches no public obligation.

`restored.unequal1.charge` set to `overlap: true`. It stays `preserved` because it passes on the starter,
but it grades the same restored-balance clauses as the target `.charge` cases and passes only because
rows and sorted IDs still agree at that checkpoint.

## Coverage limits

- Unasserted: `recruit-capacity`, `preserve-callbacks`, `no-manual-callbacks`, `api-no-game-globals`,
  `api-identifier-domain`, `api-membership-before-limit`.
- Weak: `same-ledger`, `unrelated-state`, `api-restore-shape`.

CONTRACT.md paragraph 7's scope list and "same submission bytes" sentence describe the environment and
are not mapped as obligations.

## Not determined

Nothing open for the roles or clause statuses.
