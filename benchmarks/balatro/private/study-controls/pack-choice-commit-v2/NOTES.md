# E0 notes: balatro/core/pack-choice-commit-v2

Private maintenance material. Never copy into an attempt or a model workspace.

Anchor numbering: a paragraph number counts body paragraphs of the public file in order, skipping headings, list items and table rows; bullets count list items in order, and table rows count body rows below the header.

## Baseline

From the validation matrix's recorded engine results: the starter fails 4 of 68 cases (all `target`), the
reference and gold-journal fail none. All 14 core cases pass on the starter, so the requested change
is measured by four native `.close` cases only. The starter's defects are all in the adapter: a
shifted-index payout, a refund on close after one choice, and across-pack paid-index flags.

## Manifest controls

Controls differ from the reference by one defect.

| control | kind | change | outcome |
| --- | --- | --- | --- |
| M01-preview-reward | compat-negative | Pays the reward when a preview is created. | Fails 6 `.open` cases; every target case passes. |
| M02-shifted-index | target-negative | Pays by shifted preview index. | Fails `full_full.p1.close`, `partial_full.p2.close` only. |
| M03-close-revocation | target-negative | Refunds a lone settled reward on close. | Fails `partial_full.p1.close` only. |
| M04-global-flags | target-negative | Paid-index flags persist across packs. | Fails `full_full.p2.close` only. |
| M05-repeat-settle | compat-negative | A settled ticket pays again. | Fails `core.close_pending`; every target case passes. |
| M06-view-alias | compat-negative | `view` returns a cached shared table. | Fails `core.view_alias`; every target case passes. |
| M07-repeat-commit | compat-negative | Replayed commit resets the ticket and reports it new. | Fails `core.commit_replay`, `core.receipt_alias`; every target case passes. |
| gold-journal | alternative | Replay-derived operation journal in `lib/ledger.lua`, against the reference's direct state. | Fails no case. |

The compatibility negatives are valid because the starter keeps each behavior: no preview payment,
at-most-once settlement, a detached view and idempotent commit replay all hold before the repair.

## Preserved contracts

The whole protocol in API.md (bullets 1 to 6), preview purity and the first ordinary selection
(CONTRACT.md paragraph 3), and native sale, purchase and later play (paragraph 4).

## Frozen controls left out of the manifest

None. Every frozen control other than base and gold is listed.

## Role and overlap changes

- `skip_full.p1.first` changed from `preserved` to `runtime-sentinel`. That pack makes no choice, so the
  record compares two empty lists (scenario.py:47-54) and cannot fail. No control fails it.
- `skip_full.p2.close` set to `overlap: true`. It stays `preserved` because it passes on the starter, but
  it grades `two-choice-sum`, the clause behind the target `.close` cases, and passes only because the
  skipped first pack sets no paid-index flag and that order of choices leaves the shifted-index defect
  nothing to shift.

## Coverage limits

- Unasserted: `no-manual-or-overwrite`, `api-no-game-globals`, `api-register-session-missing`.
- Weak: `native-cost-resale`, `deferred-payout`, `status-pure-detached`, `no-display-ledger`,
  `api-identifier-domain`, `api-commit-guards`, `api-preserve-lifecycle`.

CONTRACT.md paragraph 1 and the scope sentence of paragraph 6 identify the task and its limits; they are
not mapped as obligations.

## Not determined

Whether the hard-coded identity strings reject a valid adapter is reasoned from the scenario and API.md,
not shown by a run: no control uses other identifiers.
